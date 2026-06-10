"""C-P0-3 crucible — gate completeness + fail-closed hardening.

Covers the four verified gate defects:
  (1) a broken agent.gate import previously FAILED OPEN ("degrade silently"),
      dispatching even DESTRUCTIVE tools ungated — now every tool is DENIED
      while the gate cannot import,
  (2) breaker_state was never wired into pre_dispatch_check (the system-health
      check always saw the "closed" default) — now the real COMFYUI_BREAKER
      singleton state is passed,
  (3) agent/gate/checks.py imported agent.stage.constitution at module level,
      so a stage breakage killed the whole gate (which then failed open via
      (1)) — the import is now lazy inside check_constitution and fails
      closed for mutation-class tools while READ_ONLY tools keep flowing,
  (4) several registered tools had no explicit TOOL_RISK_LEVELS entry and
      fell to the implicit REVERSIBLE default — the drift-stopper test pins
      the registry so new tools cannot ship unclassified.
"""

import copy
import sys
from collections import deque
from unittest.mock import patch

import pytest

from agent.tools import handle, workflow_patch


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    """Force the pre-dispatch gate ON so the real gate path is tested deterministically."""
    monkeypatch.setattr("agent.config.GATE_ENABLED", True, raising=False)


def _seed_loaded_unmutated(workflow: dict) -> None:
    """Loaded-but-unmutated registry session (pattern from test_write_gate_failopen)."""
    st = workflow_patch._get_state()
    st["base_workflow"] = copy.deepcopy(workflow)
    st["current_workflow"] = copy.deepcopy(workflow)
    st["history"] = deque(maxlen=workflow_patch._MAX_HISTORY)
    st["_engine"] = None


class TestRiskRegistryComplete:
    """Drift-stopper (defect 4): every dispatched tool must carry an EXPLICIT
    TOOL_RISK_LEVELS entry — the implicit REVERSIBLE default is a
    misclassification trap (a destructive tool silently landing on REVERSIBLE
    would skip LOCKED). Extra forward entries in the map are fine (subset
    check, not equality): nim_* classify tools registered by the open NIM
    lifecycle PR."""

    def test_every_registered_tool_has_explicit_entry(self):
        import agent.tools as T
        from agent.gate.risk_levels import TOOL_RISK_LEVELS

        try:
            T._ensure_brain()
            known = set(T._HANDLERS) | set(T._BRAIN_TOOL_NAMES)
        except Exception:
            # Brain import failed — assert over the intelligence/stage layers
            # alone (brain tools are re-checked once the brain imports again).
            known = set(T._HANDLERS)
        missing = sorted(known - set(TOOL_RISK_LEVELS))
        assert missing == [], (
            f"Tools with NO explicit risk entry (falling to the REVERSIBLE "
            f"default): {missing}. Classify them in agent/gate/risk_levels.py."
        )


class TestGateFailsClosed:
    """Defect 1: a gate import failure must DENY dispatch (C-P0-3).

    Tradeoff (deliberate): while agent.gate cannot import there is no way to
    classify a tool's risk, so even READ_ONLY tools are denied — closed means
    closed. The denial message points at the gate package so the outage is
    loud, not silent.
    """

    def test_broken_gate_denies_write_and_does_not_mutate(self, sample_workflow, monkeypatch):
        _seed_loaded_unmutated(sample_workflow)
        before = copy.deepcopy(workflow_patch._get_state()["current_workflow"])
        monkeypatch.setitem(sys.modules, "agent.gate", None)
        result = handle("set_input", {"node_id": "3", "input_name": "text", "value": "X"})
        assert "Gate unavailable" in result and "denied for safety" in result, result
        assert workflow_patch._get_state()["current_workflow"] == before, (
            "workflow mutated despite gate-unavailable denial — fail-open regression"
        )

    def test_broken_gate_denies_read_only_too(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "agent.gate", None)
        result = handle("get_system_stats", {})
        assert "Gate unavailable" in result and "denied for safety" in result, result


class TestBreakerWiring:
    """Defect 2: the gate now reads the REAL COMFYUI_BREAKER state instead of
    the hardcoded "closed" default."""

    def test_open_breaker_denies_mutation(self, sample_workflow):
        from agent.circuit_breaker import COMFYUI_BREAKER

        _seed_loaded_unmutated(sample_workflow)
        breaker = COMFYUI_BREAKER()
        breaker._state = "open"  # force OPEN; conftest autouse fixture also resets
        try:
            result = handle("set_input", {"node_id": "3", "input_name": "text", "value": "X"})
            assert "Gate denied" in result, result
            assert "circuit breaker" in result.lower(), result
        finally:
            breaker.reset()


class TestConstitutionFailsClosed:
    """Defect 3: a stage breakage no longer kills the gate package — the lazy
    import inside check_constitution fails CLOSED (mutation-class tools are
    denied via the failed check) while READ_ONLY tools keep flowing through
    the fast-path."""

    def test_check_constitution_returns_unavailable(self, monkeypatch):
        from agent.gate.checks import check_constitution

        monkeypatch.setitem(sys.modules, "agent.stage.constitution", None)
        passed, reason = check_constitution([], "set_input")
        assert passed is False
        assert "Constitution check unavailable" in reason
        assert "failing closed" in reason

    def test_reversible_denied_while_read_only_flows(self, sample_workflow, monkeypatch):
        _seed_loaded_unmutated(sample_workflow)
        monkeypatch.setitem(sys.modules, "agent.stage.constitution", None)

        denied = handle("set_input", {"node_id": "3", "input_name": "text", "value": "X"})
        assert "Gate denied" in denied, denied
        assert "Constitution check unavailable" in denied, denied

        # READ_ONLY fast-path bypasses all five checks — still flows.
        # HTTP is mocked so the test stays offline (suite convention).
        with patch(
            "agent.tools.comfy_api._get", return_value={"system": {"os": "test"}}
        ):
            result = handle("get_system_stats", {})
        assert "Gate denied" not in result, result
        assert "Gate unavailable" not in result, result
        assert '"system"' in result, result
