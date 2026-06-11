"""Mocked unit tests for the nim_lifecycle two-deadline state machine (PRD §10, AC-5/8).

No GPU / no ComfyUI — feeds nim_run a synthetic EngineEvent stream. Lives under
tests/manual/ (forge zone) and is run explicitly by the crucible.
"""
import pytest

pytest.importorskip("agent.tools.nim_lifecycle")

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import agent.tools.nim_lifecycle as nl
from agent.engine import EngineEvent  # real dataclass, _types.py:21


def _ev(t, **data):
    return EngineEvent(type=t, data=data, raw={})


_GEN_ID = "7"  # NIMFLUXNode id from FLUX_Dev_NIM_Workflow.json (recon)
WF = {_GEN_ID: {"class_type": "NIMFLUXNode", "inputs": {}}}


@contextmanager
def _fake_ws(events):
    yield iter(events)


def _fake_engine(events, *, prompt_id="pid-1", history=None):
    eng = MagicMock()
    eng.queue_prompt.return_value = prompt_id
    eng.subscribe_ws.side_effect = lambda *, client_id: _fake_ws(events)
    eng.get_history.return_value = history or {prompt_id: {"outputs": {}}}
    return eng


def _stub_preflight(*, warm, comfy_alive=True, node_pack_present=True):
    return nl.PreflightResult(
        node_pack_present=node_pack_present,
        comfy_alive=comfy_alive,
        warm=warm,
    )


# --- (a) long WARMUP silence -> generate-progress -> DONE (AC-3) ------------
def test_warmup_silence_then_generate_then_done():
    events = (
        [_ev(nl.TIMEOUT_EVENT)] * 5
        + [_ev("executing", node=_GEN_ID, prompt_id="pid-1")]
        + [_ev("progress", value=10, max=20, prompt_id="pid-1")]
        + [_ev("executing", node=None, prompt_id="pid-1")]
    )
    eng = _fake_engine(events)
    with patch("agent.engine.get_engine", return_value=eng), patch.object(
        nl, "nim_preflight", return_value=_stub_preflight(warm=False)
    ):
        r = nl.nim_run(WF)
    assert r.ok is True
    assert r.phase is nl.Phase.DONE


# --- (b) silence past warmup_timeout, zero events -> hang-fail (AC-5) -------
def test_warmup_silence_past_deadline_hang_fail():
    events = [_ev(nl.TIMEOUT_EVENT)] * 1000  # never a real event
    eng = _fake_engine(events)
    # Step monotonic past the budget on the 2nd loop turn:
    #   submit-read, turn-1 (0.0), turn-2 (1e6 > budget).
    clock = [0.0, 0.0, 1e6, 1e6, 1e6]
    with patch("agent.engine.get_engine", return_value=eng), patch.object(
        nl, "nim_preflight", return_value=_stub_preflight(warm=False)
    ), patch.object(nl.time, "monotonic", side_effect=clock):
        r = nl.nim_run(WF, warmup_timeout=100.0)
    assert r.ok is False
    assert r.phase is nl.Phase.FAILED
    assert "no events" in r.reason or "stalled" in r.reason


# --- (c) execution_error -> FAILED with reason -----------------------------
def test_execution_error_fails_with_reason():
    events = [
        _ev(
            "execution_error",
            node_type="NIMFLUXNode",
            exception_message="CUDA OOM",
            node_id="7",
        )
    ]
    eng = _fake_engine(events)
    with patch("agent.engine.get_engine", return_value=eng), patch.object(
        nl, "nim_preflight", return_value=_stub_preflight(warm=False)
    ):
        r = nl.nim_run(WF)
    assert r.ok is False
    assert r.phase is nl.Phase.FAILED
    assert "CUDA OOM" in r.reason
    assert "NIMFLUXNode" in r.reason


# --- (d) warm record present -> 180s budget chosen (AC-4) ------------------
def test_warm_record_selects_warm_budget(monkeypatch):
    monkeypatch.setattr(nl, "WARMUP_TIMEOUT_WARM", 180.0)
    monkeypatch.setattr(nl, "WARMUP_TIMEOUT_COLD", 900.0)
    assert (
        nl._select_warmup_budget(
            nl.PreflightResult(node_pack_present=True, warm=True), None
        )
        == 180.0
    )
    assert (
        nl._select_warmup_budget(
            nl.PreflightResult(node_pack_present=True, warm=False), None
        )
        == 900.0
    )
    # Override always wins.
    assert (
        nl._select_warmup_budget(
            nl.PreflightResult(node_pack_present=True, warm=False), 42.0
        )
        == 42.0
    )
    # End-to-end: a warm preflight completes a fast stream.
    events = [_ev("executing", node=_GEN_ID, prompt_id="pid-1"), _ev(
        "executing", node=None, prompt_id="pid-1"
    )]
    eng = _fake_engine(events)
    with patch("agent.engine.get_engine", return_value=eng), patch.object(
        nl, "nim_preflight", return_value=_stub_preflight(warm=True)
    ):
        r = nl.nim_run(WF)
    assert r.ok is True


# --- (e) nim_preflight is read-only (AC-1 / INV-2) -------------------------
def test_preflight_is_read_only_even_when_unreachable():
    # H2: the node-kind check goes through comfy_api._get (per-class
    # /object_info GETs); the system_stats GET still uses nl's httpx.Client.
    # Both edges must fail for "unreachable".
    with patch.object(nl, "record_warm_state") as rec, patch.object(
        nl.os, "replace"
    ) as repl, patch.object(nl.httpx, "Client") as cli, patch(
        "agent.tools.comfy_api._get", side_effect=Exception("no server")
    ):
        cli.return_value.__enter__.return_value.get.side_effect = Exception(
            "no server"
        )
        result = nl.nim_preflight("flux-dev")
    rec.assert_not_called()
    repl.assert_not_called()
    assert result.node_pack_present is False
    assert result.note != ""
