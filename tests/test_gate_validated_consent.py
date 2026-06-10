"""H1.4 crucible — validate->execute consent enforced at the pre-dispatch gate.

Director ratification 2026-06-09, ledger H1.4: check_consent's docstring said
"Level 2 requires prior validation" but the code never enforced it — the
caller never wired the flag, and a fix-forward removed the dead check.
Re-imposed: the session's validated_since_mutation flag — set by
validate_before_execute (SESSION validations only; a "path" validation says
nothing about the session workflow), cleared whenever a mutation-class
(REVERSIBLE) tool dispatches — is wired into pre_dispatch_check(validated=...),
and check_consent DENIES execute_workflow / execute_with_progress on the
session workflow until the flag is True. An explicit "path" input is exempt
(it executes an external file, not the session workflow).

All tests run through the REAL central dispatcher (agent.tools.handle) with
the real gate forced ON (seeding + monkeypatch patterns mirror
test_write_gate_failopen.py). HTTP is mocked at the edges only: the
/object_info GET inside validate_before_execute, and the queue POST seam
(comfy_execute._queue_prompt) as a spy that must NEVER fire when denied.
"""

import copy
import json
from collections import deque
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from agent.tools import comfy_execute, handle, workflow_patch


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    """Force the pre-dispatch gate ON so the real gate path is tested deterministically."""
    monkeypatch.setattr("agent.config.GATE_ENABLED", True, raising=False)


@pytest.fixture
def queue_spy(monkeypatch):
    """Spy on the queue POST seam — must NEVER fire on a denied call.

    The poll edge is stubbed so an ALLOWED execution returns immediately
    instead of polling /history.
    """
    spy = MagicMock(return_value=("test-prompt-id", None))
    monkeypatch.setattr(comfy_execute, "_queue_prompt", spy)
    monkeypatch.setattr(
        comfy_execute,
        "_poll_completion",
        lambda prompt_id, timeout, poll_interval=1.0, progress=None: {
            "status": "complete", "prompt_id": prompt_id, "outputs": [],
        },
    )
    return spy


def _seed_loaded(workflow: dict) -> None:
    """Loaded registry session with a CLEAN consent baseline (no validation yet)."""
    st = workflow_patch._get_state()
    st["base_workflow"] = copy.deepcopy(workflow)
    st["current_workflow"] = copy.deepcopy(workflow)
    st["history"] = deque(maxlen=workflow_patch._MAX_HISTORY)
    st["_engine"] = None  # direct-write fallback; the GATE is under test
    st["action_history"] = []
    st["validated_since_mutation"] = False


def _flag() -> bool:
    return workflow_patch._get_state().get("validated_since_mutation", False)


def _object_info_for(workflow: dict, *, drop: str | None = None) -> dict:
    """object_info covering every class_type in the workflow (optionally minus one)."""
    return {
        node["class_type"]: {"input": {"required": {}}}
        for node in workflow.values()
        if node["class_type"] != drop
    }


@contextmanager
def _object_info_mocked(object_info: dict):
    """Mock the /object_info GET edge inside validate_before_execute."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = object_info
    mock_resp.raise_for_status = MagicMock()
    with patch("httpx.Client") as mock_client:
        mock_client.return_value.__enter__ = MagicMock(return_value=mock_client.return_value)
        mock_client.return_value.__exit__ = MagicMock(return_value=False)
        mock_client.return_value.get.return_value = mock_resp
        yield


class TestValidatedConsent:
    def test_mutation_then_execute_denied(self, sample_workflow, queue_spy):
        """(a) mutate -> execute with NO validation: DENIED with the
        validate-first reason; the queue spy never fires; flag stays False."""
        _seed_loaded(sample_workflow)
        r = handle("set_input", {"node_id": "3", "input_name": "text", "value": "mutated"})
        assert "Gate denied" not in r, r

        result = handle("execute_workflow", {})
        assert "Gate denied" in result, result
        assert "validate_before_execute" in result, result
        queue_spy.assert_not_called()
        assert _flag() is False

    def test_validate_arms_then_execute_dispatches(self, sample_workflow, queue_spy):
        """(b) a PASSING session validation arms the flag; execute dispatches
        (queue spy fires exactly once)."""
        _seed_loaded(sample_workflow)
        r = handle("set_input", {"node_id": "3", "input_name": "text", "value": "mutated"})
        assert "Gate denied" not in r, r

        with _object_info_mocked(_object_info_for(sample_workflow)):
            verdict = json.loads(handle("validate_before_execute", {}))
        assert verdict.get("valid") is True, verdict
        assert _flag() is True

        result = handle("execute_workflow", {})
        assert "Gate denied" not in result, result
        queue_spy.assert_called_once()
        assert json.loads(result)["status"] == "complete"

    def test_mutation_invalidates_prior_validation(self, sample_workflow, queue_spy):
        """(c) validate -> mutate -> execute: the mutation cleared the flag,
        so execution is DENIED again."""
        _seed_loaded(sample_workflow)
        with _object_info_mocked(_object_info_for(sample_workflow)):
            verdict = json.loads(handle("validate_before_execute", {}))
        assert verdict.get("valid") is True, verdict
        assert _flag() is True

        r = handle("set_input", {"node_id": "3", "input_name": "text", "value": "post-validate"})
        assert "Gate denied" not in r, r
        assert _flag() is False, "REVERSIBLE dispatch must clear the validation flag"

        result = handle("execute_workflow", {})
        assert "Gate denied" in result, result
        queue_spy.assert_not_called()

    def test_failed_validation_does_not_arm(self, sample_workflow, queue_spy):
        """(d) a FAILING session validation (one node class missing from
        object_info) must NOT arm the flag — execute stays DENIED."""
        _seed_loaded(sample_workflow)
        with _object_info_mocked(_object_info_for(sample_workflow, drop="KSampler")):
            verdict = json.loads(handle("validate_before_execute", {}))
        assert verdict.get("valid") is False, verdict
        assert _flag() is False

        result = handle("execute_workflow", {})
        assert "Gate denied" in result, result
        queue_spy.assert_not_called()

    def test_path_override_exempt(self, sample_workflow, sample_workflow_file, queue_spy):
        """(e) an explicit "path" input executes an EXTERNAL file — consent
        passes with the flag False and dispatch reaches the handler."""
        _seed_loaded(sample_workflow)
        assert _flag() is False

        result = handle("execute_workflow", {"path": str(sample_workflow_file)})
        assert "Gate denied" not in result, result
        queue_spy.assert_called_once()
        assert json.loads(result)["status"] == "complete"

    def test_path_validation_does_not_set_flag(self, sample_workflow, sample_workflow_file):
        """(f) validating a "path" workflow says nothing about the session
        workflow — the session flag must stay False even on a valid verdict."""
        _seed_loaded(sample_workflow)
        assert _flag() is False

        with _object_info_mocked(_object_info_for(sample_workflow)):
            verdict = json.loads(
                handle("validate_before_execute", {"path": str(sample_workflow_file)})
            )
        assert verdict.get("valid") is True, verdict
        assert _flag() is False, "path validation must not arm the session flag"
