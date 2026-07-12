"""D3 fail-soft tests — the diagnostician never kills the patient (DIAG.C1).

A raising trigger callback, a raising emission path, and a broken subscriber
install must all be swallowed; and the execution result must be BYTE-IDENTICAL
whether the diagnosis seam is healthy or broken (the acceptance-gate
condition). All HTTP and WebSocket traffic is mocked — no ComfyUI server, no
API key.
"""

import json
from unittest.mock import MagicMock, patch

import agent.diagnosis.diagnosis as diag
from agent.tools import comfy_execute
from cognitive.transport import triggers as T
from cognitive.transport.events import EventType, ExecutionEvent

WS_PROMPT_ID = "ws-diag-1"


def _synthetic_complete_event() -> ExecutionEvent:
    return ExecutionEvent(event_type=EventType.EXECUTION_COMPLETE, prompt_id=WS_PROMPT_ID)


class TestCallbackFailSoft:
    def test_raising_callback_never_propagates(self):
        """Registry dispatch swallows a raising callback and still counts the fire."""
        T.clear()
        try:
            T.on_execution_complete(lambda e: 1 / 0)
            fired = T.dispatch(_synthetic_complete_event())  # must not raise
            assert fired >= 1
        finally:
            T.clear()


class TestEmissionFailSoft:
    def test_on_event_swallows_diagnose_error(self):
        """_on_event suppresses any exception from the emission path (DIAG.C1)."""
        with patch.object(diag, "_diagnose_event", side_effect=RuntimeError("boom")):
            assert diag._on_event(_synthetic_complete_event()) is None


# ---------------------------------------------------------------------------
# Byte-identical execution result — the acceptance-gate condition
# ---------------------------------------------------------------------------

_WORKFLOW = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd15.safetensors"}},
    "2": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "seed": 42, "steps": 5}},
}


def _ws_mock() -> MagicMock:
    """Fake WebSocket yielding a start -> node 1 -> node 2 -> complete sequence."""
    messages = [
        json.dumps({"type": "execution_start", "data": {"prompt_id": WS_PROMPT_ID}}),
        json.dumps({"type": "executing", "data": {"node": "1", "prompt_id": WS_PROMPT_ID}}),
        json.dumps({"type": "executing", "data": {"node": "2", "prompt_id": WS_PROMPT_ID}}),
        json.dumps({"type": "executing", "data": {"node": None, "prompt_id": WS_PROMPT_ID}}),
    ]
    it = iter(messages)
    ws = MagicMock()
    ws.recv.side_effect = lambda *a, **k: next(it)
    ws.__enter__ = MagicMock(return_value=ws)
    ws.__exit__ = MagicMock(return_value=False)
    return ws


def _history_payload() -> dict:
    return {
        WS_PROMPT_ID: {
            "prompt": [0, WS_PROMPT_ID, _WORKFLOW],
            "status": {"status_str": "success", "completed": True},
            "outputs": {"2": {"images": [{"filename": "out_00001.png", "subfolder": ""}]}},
        },
    }


def _fake_httpx_get(url, *args, **kwargs):
    """Route the diagnosis path's httpx.get calls: history, system_stats, bridge."""
    resp = MagicMock()
    if "/system_stats" in url:
        resp.status_code = 200
        resp.json.return_value = {
            "system": {
                "os": "posix",
                "python_version": "3.12.10",
                "pytorch_version": "2.7.1+cu128",
                "comfyui_version": "0.3.44",
            },
        }
    elif "/history/" in url:
        resp.status_code = 200
        resp.json.return_value = _history_payload()
    else:  # bridge exec_profile absent -> stages [] (DIAG.C6)
        resp.status_code = 404
        resp.json.return_value = {}
    return resp


def _run_execution(workflow_path: str, break_diagnosis: bool) -> str:
    """Run execute_with_progress fully mocked, diagnosis seam healthy or broken.

    The ONLY difference between the two variants is what the trigger registry
    holds: the real diagnosis subscriber, or a callback that raises. Constant
    time.monotonic makes every timing field in the result deterministic so the
    strings can be compared byte-for-byte.
    """
    from agent.engine import _reset_cache_for_tests

    _reset_cache_for_tests()  # fresh engine so this run's mocked client is used
    T.clear()
    if break_diagnosis:

        def _boom(event):
            raise RuntimeError("diagnosis subscriber broken")

        T.on_execution_complete(_boom)
        T.on_execution_error(_boom)
    else:
        T.on_execution_complete(diag._on_event)
        T.on_execution_error(diag._on_event)

    queue_resp = MagicMock()
    queue_resp.json.return_value = {"prompt_id": WS_PROMPT_ID}
    queue_resp.raise_for_status = MagicMock()
    history_resp = MagicMock()
    history_resp.json.return_value = _history_payload()
    history_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = queue_resp
    mock_client.get.return_value = history_resp

    with patch.object(comfy_execute, "_HAS_WS", True), \
         patch("agent.tools.comfy_execute.httpx.Client", return_value=mock_client), \
         patch("agent.engine.comfyui_adapter.websockets.sync.client.connect",
               return_value=_ws_mock()), \
         patch("httpx.get", side_effect=_fake_httpx_get), \
         patch("time.monotonic", return_value=1000.0):
        return comfy_execute.handle(
            "execute_with_progress", {"path": str(workflow_path), "timeout": 30}
        )


class TestByteIdenticalResult:
    def test_result_identical_with_diagnosis_healthy_vs_broken(
        self, tmp_path, isolated_diagnosis_dir
    ):
        wf_path = tmp_path / "wf.json"
        wf_path.write_text(json.dumps(_WORKFLOW), encoding="utf-8")
        try:
            result_healthy = _run_execution(wf_path, break_diagnosis=False)
            emitted = sorted(isolated_diagnosis_dir.rglob("*.json"))
            assert len(emitted) == 1  # the healthy seam really ran and emitted a document

            result_broken = _run_execution(wf_path, break_diagnosis=True)
            assert sorted(isolated_diagnosis_dir.rglob("*.json")) == emitted  # broken: none

            assert isinstance(result_healthy, str)
            assert isinstance(result_broken, str)
            assert result_healthy == result_broken  # byte-identical execution artifact
            assert json.loads(result_healthy)["status"] == "complete"
        finally:
            T.clear()


class TestInstallSubscriber:
    def test_install_fail_soft_then_idempotent(self, monkeypatch):
        """Broken registry -> False without raising; healthy -> True, then short-circuit."""
        monkeypatch.setattr(diag, "_installed", False)
        with patch.object(T, "on_execution_complete", side_effect=RuntimeError("boom")):
            assert diag.install_subscriber() is False  # fail-soft, no raise
        assert diag._installed is False

        T.clear()  # deterministic registry before the real install
        assert diag.install_subscriber() is True
        assert diag._installed is True
        assert T._default_registry.count() == 2  # one complete + one error trigger

        assert diag.install_subscriber() is True  # second call short-circuits
        assert T._default_registry.count() == 2  # and registers nothing new
