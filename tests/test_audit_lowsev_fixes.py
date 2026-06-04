"""Route-auth audit low-severity fixes: 3.4 (load_session reclassify) + 3.2/2.3
(unauthenticated-bind startup advisory)."""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import patch


# --- 3.4: load_session is REVERSIBLE, but a fresh load still passes the gate ---


def test_load_session_is_reversible():
    from agent.gate.risk_levels import get_risk_level, RiskLevel

    assert get_risk_level("load_session") == RiskLevel.REVERSIBLE


def test_load_session_passes_gate_on_fresh_load(monkeypatch):
    """REVERSIBLE + self-baselining: loading a session with nothing loaded must NOT be
    gate-denied (check_reversibility would otherwise reject 'REVERSIBLE with no undo')."""
    from agent.tools import handle

    monkeypatch.setattr("agent.config.GATE_ENABLED", True, raising=False)
    result = json.loads(handle("load_session", {"name": "definitely-not-a-real-session-xyz"}))
    err = (result.get("error") or "").lower()
    # The gate let it through to the handler (which reports the session missing) --
    # it was NOT blocked by the gate's reversibility/consent checks.
    assert "gate denied" not in err
    assert "reversible but no undo" not in err
    assert "requires" not in err or "session" in err


# --- 3.2 / 2.3: unauthenticated-bind startup advisory ---


def test_unauth_bind_warns_on_non_loopback(monkeypatch):
    from ui.server import routes as uiroutes

    fake_cli = types.ModuleType("comfy.cli_args")
    fake_cli.args = types.SimpleNamespace(listen="0.0.0.0")
    monkeypatch.setitem(sys.modules, "comfy", types.ModuleType("comfy"))
    monkeypatch.setitem(sys.modules, "comfy.cli_args", fake_cli)
    monkeypatch.setattr("agent.config.MCP_AUTH_TOKEN", "", raising=False)

    with patch.object(uiroutes.log, "warning") as warn, patch.object(uiroutes.log, "info"):
        uiroutes._warn_on_unauthenticated_bind()

    assert warn.called, "non-loopback + no token must warn loudly"
    assert "non-loopback" in warn.call_args.args[0].lower()


def test_unauth_bind_silent_when_token_set(monkeypatch):
    from ui.server import routes as uiroutes

    monkeypatch.setattr("agent.config.MCP_AUTH_TOKEN", "a-token", raising=False)
    with patch.object(uiroutes.log, "warning") as warn, patch.object(uiroutes.log, "info") as info:
        uiroutes._warn_on_unauthenticated_bind()

    assert not warn.called and not info.called
