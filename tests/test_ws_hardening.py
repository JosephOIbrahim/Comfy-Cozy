"""C-R6 WebSocket hardening tests.

Covers: (a) connect kwargs (max_size / ping settings — the named coverage
gap), (b)/(c) mid-stream transport loss translated to EngineConnectionError,
(d)/(e) the nim_run polling fallback, (f) the __timeout__ sentinel contract.

All mocked — no ComfyUI server. Engine mocking mirrors
tests/manual/test_nim_lifecycle_unit.py (patch agent.engine.get_engine).
"""
import pytest

pytest.importorskip("websockets")
pytest.importorskip("agent.tools.nim_lifecycle")

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import websockets.exceptions
from websockets.frames import Close

import agent.tools.nim_lifecycle as nl
from agent.engine import EngineConnectionError, EngineEvent
from agent.engine.comfyui_adapter import ComfyUIAdapter

_CONNECT = "agent.engine.comfyui_adapter.websockets.sync.client.connect"


def _ev(t, **data):
    return EngineEvent(type=t, data=data, raw={})


_GEN_ID = "7"  # NIMFLUXNode id, matches tests/manual/test_nim_lifecycle_unit.py
WF = {_GEN_ID: {"class_type": "NIMFLUXNode", "inputs": {}}}


# --- adapter-side helpers ----------------------------------------------------

def _ws_cm_with_recv(side_effect):
    """A fake connect() return whose ws.recv() runs through side_effect."""
    mock_ws = MagicMock()
    mock_ws.recv.side_effect = side_effect
    cm = MagicMock()
    cm.__enter__.return_value = mock_ws
    cm.__exit__.return_value = False
    return cm


# --- (a) connect kwargs: max_size + ping settings ----------------------------

def test_connect_called_with_max_size_and_ping_settings():
    adapter = ComfyUIAdapter()
    with patch(_CONNECT) as conn:
        with adapter.subscribe_ws(client_id="t-kwargs"):
            pass
    kwargs = conn.call_args.kwargs
    assert kwargs["max_size"] == 16 * 1024 * 1024
    assert kwargs["ping_interval"] == 20
    assert kwargs["ping_timeout"] == 60
    assert kwargs["close_timeout"] == 5
    assert kwargs["open_timeout"] == 10


# --- (b) mid-stream ConnectionClosed -> EngineConnectionError ----------------

def test_midstream_connection_closed_raises_engine_connection_error():
    closed = websockets.exceptions.ConnectionClosedError(
        Close(1009, "message too big"), None
    )
    adapter = ComfyUIAdapter()
    with patch(_CONNECT, return_value=_ws_cm_with_recv([closed])):
        with adapter.subscribe_ws(client_id="t-closed") as events:
            with pytest.raises(EngineConnectionError) as exc_info:
                next(events)
    assert "mid-stream" in str(exc_info.value)
    assert exc_info.value.__cause__ is closed


# --- (c) mid-stream OSError -> EngineConnectionError -------------------------

def test_midstream_oserror_raises_engine_connection_error():
    err = OSError("connection reset by peer")
    adapter = ComfyUIAdapter()
    with patch(_CONNECT, return_value=_ws_cm_with_recv([err])):
        with adapter.subscribe_ws(client_id="t-oserr") as events:
            with pytest.raises(EngineConnectionError) as exc_info:
                next(events)
    assert "mid-stream" in str(exc_info.value)
    assert exc_info.value.__cause__ is err


# --- (f) sentinel contract: __timeout__ still flows every <=2 s --------------

def test_timeout_sentinel_still_flows():
    adapter = ComfyUIAdapter()
    side_effect = [
        TimeoutError(),
        json.dumps({"type": "progress", "data": {"value": 1}}),
    ]
    with patch(_CONNECT, return_value=_ws_cm_with_recv(side_effect)):
        with adapter.subscribe_ws(client_id="t-sentinel") as events:
            first = next(events)
            second = next(events)
    assert first.type == "__timeout__"
    assert first.data == {}
    assert second.type == "progress"
    assert second.data == {"value": 1}


# --- nim_run-side helpers (mirrors tests/manual/test_nim_lifecycle_unit.py) --

@contextmanager
def _fake_ws(events_iter):
    yield events_iter


def _dying_stream(events, exc):
    def gen():
        yield from events
        raise exc
    return gen()


def _fake_engine(events_iter, *, prompt_id="pid-1", history=None):
    eng = MagicMock()
    eng.queue_prompt.return_value = prompt_id
    eng.subscribe_ws.side_effect = lambda *, client_id: _fake_ws(events_iter)
    eng.get_history.return_value = history if history is not None else {}
    return eng


def _stub_preflight(*, warm, comfy_alive=True, node_pack_present=True):
    return nl.PreflightResult(
        node_pack_present=node_pack_present,
        comfy_alive=comfy_alive,
        warm=warm,
    )


class _FakeClock:
    """monotonic()/sleep() pair so polling loops terminate deterministically."""

    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def sleep(self, seconds):
        self.t += seconds


_SUCCESS_HISTORY = {
    "pid-1": {
        "status": {"status_str": "success", "completed": True},
        "outputs": {"9": {"images": [{"filename": "nim_out.png"}]}},
    }
}


# --- (d) WS loss during WARMUP -> polling fallback -> COMPLETE ---------------

def test_nim_run_ws_loss_falls_back_to_polling_complete():
    stream = _dying_stream(
        [_ev("status", status={})],  # warmup activity, no COOKING flip
        EngineConnectionError("WebSocket connection lost mid-stream: 1009"),
    )
    eng = _fake_engine(stream, history=_SUCCESS_HISTORY)
    with patch("agent.engine.get_engine", return_value=eng), patch.object(
        nl, "nim_preflight", return_value=_stub_preflight(warm=False)
    ), patch.object(nl, "record_warm_state") as rec, patch.object(
        nl.time, "sleep", lambda s: None
    ):
        r = nl.nim_run(WF)
    assert r.ok is True
    assert r.phase is nl.Phase.DONE
    assert r.monitoring == "polling_fallback"
    assert "mid-stream" in r.ws_error
    assert "polling" in r.reason
    assert r.images == ["nim_out.png"]
    # WS died during WARMUP: warmup timing is unknowable -> no warm record.
    rec.assert_not_called()


# --- (d2) flip observed before WS loss -> warm record with real timing -------

def test_nim_run_fallback_records_warm_state_only_when_flip_observed():
    stream = _dying_stream(
        [_ev("progress", value=1, max=20, prompt_id="pid-1")],  # COOKING flip
        EngineConnectionError("socket gone"),
    )
    eng = _fake_engine(stream, history=_SUCCESS_HISTORY)
    with patch("agent.engine.get_engine", return_value=eng), patch.object(
        nl, "nim_preflight", return_value=_stub_preflight(warm=False)
    ), patch.object(nl, "record_warm_state") as rec, patch.object(
        nl.time, "sleep", lambda s: None
    ):
        r = nl.nim_run(WF)
    assert r.ok is True
    assert r.phase is nl.Phase.DONE
    assert r.monitoring == "polling_fallback"
    rec.assert_called_once()
    assert rec.call_args.kwargs["warmup_seconds"] is not None


# --- (e) WS loss, history never completes -> budget-exhausted timeout --------

def test_nim_run_fallback_budget_exhausted_times_out():
    stream = _dying_stream([], EngineConnectionError("socket gone"))
    eng = _fake_engine(stream, history={})  # history never knows the prompt
    clock = _FakeClock()
    with patch("agent.engine.get_engine", return_value=eng), patch.object(
        nl, "nim_preflight", return_value=_stub_preflight(warm=False)
    ), patch.object(nl, "record_warm_state") as rec, patch.object(
        nl.time, "monotonic", clock.monotonic
    ), patch.object(nl.time, "sleep", clock.sleep):
        r = nl.nim_run(WF, warmup_timeout=10.0)
    assert r.ok is False
    assert r.phase is nl.Phase.FAILED
    assert r.monitoring == "polling_fallback"
    assert "no events" in r.reason or "stalled" in r.reason
    assert eng.get_history.call_count >= 2
    rec.assert_not_called()
