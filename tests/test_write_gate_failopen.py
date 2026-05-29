"""Crucible for the write-gate fail-open fix (write-gate deadlock).

Root cause (recon): the pre-dispatch gate's check_reversibility
(agent/gate/checks.py) DENIED every REVERSIBLE write when has_undo was False,
and has_undo (computed in agent/tools/__init__.py) (a) required a NON-EMPTY
history deque — which is empty right after a load — and (b) on the ctx path read
ONLY ctx.workflow, a WorkflowSession that DIVERGES from the registry session the
loaders (load_workflow_from_data / _load_workflow) actually write to. Result: a
loaded-but-unmutated session deadlocked, and the advised "Load or save first"
could not break it (load is READ_ONLY and seeds nothing; save is itself gated).

Fix (agent/tools/__init__.py): a LOADED workflow (current_workflow present in
EITHER store) is treated as having undo capability — it is reversible via
reset_workflow, which restores base_workflow. A genuinely unloaded session still
fails closed.
"""

import copy
from collections import deque

import pytest

from agent.tools import handle, workflow_patch


def _seed_loaded_unmutated(workflow: dict) -> None:
    """Put the REGISTRY session into the exact deadlock precondition:
    base_workflow + current_workflow present, history EMPTY, no mutation yet."""
    st = workflow_patch._get_state()
    st["base_workflow"] = copy.deepcopy(workflow)
    st["current_workflow"] = copy.deepcopy(workflow)
    st["history"] = deque(maxlen=workflow_patch._MAX_HISTORY)
    st["_engine"] = None  # exercise the direct-write fallback; the GATE is under test


def _seed_unloaded() -> None:
    st = workflow_patch._get_state()
    st["base_workflow"] = None
    st["current_workflow"] = None
    st["history"] = deque()
    st["_engine"] = None


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    """Force the pre-dispatch gate ON so the real gate path is tested deterministically."""
    monkeypatch.setattr("agent.config.GATE_ENABLED", True, raising=False)


class _DivergedCtx:
    """Stand-in for a SessionContext whose .workflow is a FRESH empty
    WorkflowSession (mirrors session_context.py:40-41) — i.e. diverged from the
    registry session the loaders write to. The gate only ever reads ctx.workflow,
    so this faithfully reproduces the divergence the gate sees."""

    def __init__(self):
        from agent.workflow_session import WorkflowSession
        self.workflow = WorkflowSession("diverged-ctx")


class TestWriteGateFailOpen:
    def test_loaded_unmutated_session_can_write(self, sample_workflow):
        """DEADLOCK GONE: a loaded-but-unmutated workflow (empty history) is no
        longer gate-denied for a REVERSIBLE write."""
        _seed_loaded_unmutated(sample_workflow)
        result = handle("set_input", {
            "node_id": "3", "input_name": "text", "value": "a serene mountain lake",
        })
        assert "Gate denied" not in result, result
        assert (
            workflow_patch._get_state()["current_workflow"]["3"]["inputs"]["text"]
            == "a serene mountain lake"
        )

    def test_unloaded_session_still_fails_closed(self):
        """SAFETY: a genuinely unloaded session (current_workflow None) is STILL
        denied — fail-open must not blanket-open."""
        _seed_unloaded()
        result = handle("set_input", {
            "node_id": "3", "input_name": "text", "value": "x",
        })
        assert "Gate denied" in result, result

    def test_safety_hinge_reset_restores_base_after_failopen_write(self, sample_workflow):
        """SAFETY HINGE: after a fail-open write, the reset MECHANISM restores
        base_workflow — proving 'loaded' is a legitimate reversibility baseline.
        If this fails, fail-open is UNSAFE and the fix must be reverted.

        Note: reset_workflow is gate-LOCKED as destructive (requires human
        confirmation — see test_reset_workflow_is_gate_locked), so we exercise the
        restore MECHANISM (_handle_reset) directly; the lock is the intended human
        escape hatch, not a defect."""
        import json
        _seed_loaded_unmutated(sample_workflow)
        base_before = copy.deepcopy(workflow_patch._get_state()["base_workflow"])

        write = handle("set_input", {
            "node_id": "3", "input_name": "text", "value": "MUTATED",
        })
        assert "Gate denied" not in write, write
        assert workflow_patch._get_state()["current_workflow"]["3"]["inputs"]["text"] == "MUTATED"
        # the fail-open write must NOT touch base_workflow, or reset cannot restore
        assert workflow_patch._get_state()["base_workflow"] == base_before, \
            "fail-open write mutated base_workflow — reversibility broken"

        reset = json.loads(workflow_patch._handle_reset())
        assert reset.get("reset") is True, reset
        cur = workflow_patch._get_state()["current_workflow"]
        assert cur == base_before, "reset did NOT restore base_workflow — fail-open is UNSAFE"
        assert cur["3"]["inputs"]["text"] == "a beautiful landscape"  # original value

    def test_reset_workflow_is_gate_locked(self, sample_workflow):
        """reset_workflow is intentionally LOCKED by the gate (DESTRUCTIVE — needs
        explicit human confirmation); it is the reversibility escape hatch, not an
        auto-executable tool. Documents why the safety-hinge test invokes the
        restore mechanism directly rather than through the gate."""
        _seed_loaded_unmutated(sample_workflow)
        result = handle("reset_workflow", {})
        assert ("destructive" in result.lower()) or ("confirm" in result.lower()), result

    def test_ctx_sidebar_path_resolves_has_undo(self, sample_workflow):
        """DEFECT (ii): SessionContext present (ctx.workflow EMPTY) but the
        REGISTRY session loaded (the sidebar/MCP store divergence). has_undo must
        now resolve True via the registry store, so the write is allowed."""
        ctx = _DivergedCtx()
        assert ctx.workflow.get("current_workflow") is None  # ctx store empty (diverged)
        _seed_loaded_unmutated(sample_workflow)  # registry store loaded
        result = handle("set_input", {
            "node_id": "3", "input_name": "text", "value": "via ctx path",
        }, ctx=ctx)
        assert "Gate denied" not in result, result
