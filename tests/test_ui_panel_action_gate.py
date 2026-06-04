"""Regression test for route-auth audit finding 5.1.

The ui sidebar's panel direct-action path (`_handle_panel_action`) must dispatch
PROVISION/code-executing actions through the gated `agent.tools.handle()` so the
pre-dispatch safety gate runs (ESCALATE-needs-confirm / LOCKED). Calling the
module handlers (`comfy_provision.handle` / `comfy_execute.handle`) directly
bypassed the gate entirely — that bypass must stay closed.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


class _FakeConv:
    def __init__(self) -> None:
        self.id = "test-conv"
        self.busy = False


async def _run_action(action: str, data: dict) -> _FakeWS:
    from ui.server import routes as uiroutes

    ws, conv = _FakeWS(), _FakeConv()
    loop = asyncio.get_running_loop()
    await uiroutes._handle_panel_action(ws, conv, loop, action, data)
    return ws


async def test_install_action_routes_through_gate_not_direct():
    """install_node_pack reaches agent.tools.handle() (gated), never the direct module handler."""
    with patch(
        "agent.tools.handle",
        return_value=json.dumps(
            {"error": "needs explicit confirmation", "hint": "re-call with confirm: true"}
        ),
    ) as gated, patch("agent.tools.comfy_provision.handle") as direct:
        ws = await _run_action(
            "install_node_pack", {"url": "https://example/x", "name": "x"}
        )

    # Routed through the central gated dispatcher...
    assert gated.called, "install action must dispatch via agent.tools.handle()"
    assert gated.call_args.args[0] == "install_node_pack"
    # ...and the direct module handler (the old bypass) is NOT invoked.
    direct.assert_not_called()
    # The gate's needs-confirmation surfaced to the user.
    assert "confirm" in json.dumps(ws.sent).lower()


async def test_install_action_forwards_confirm_token():
    """A confirmed panel click passes confirm=true into the gated call (ESCALATE-confirmed path)."""
    with patch(
        "agent.tools.handle", return_value=json.dumps({"installed": "x"})
    ) as gated, patch("agent.tools.comfy_provision.handle"):
        await _run_action(
            "install_node_pack",
            {"url": "https://example/x", "name": "x", "confirm": True},
        )

    assert gated.called
    assert gated.call_args.args[1].get("confirm") is True


async def test_repair_action_routes_through_gate_not_direct():
    """repair_workflow (a real _DIRECT_ACTIONS member) dispatches via the gated handler."""
    with patch(
        "agent.tools.handle", return_value=json.dumps({"status": "report"})
    ) as gated, patch("agent.tools.comfy_provision.handle") as direct:
        await _run_action("repair", {})

    assert gated.called
    assert gated.call_args.args[0] == "repair_workflow"
    direct.assert_not_called()


async def test_validate_action_now_reachable_and_gated():
    """Regression: 'validate' was unreachable ('validate_before_execute' was missing
    from _DIRECT_ACTIONS, so it was rejected as 'Unknown action'). It now maps and
    dispatches through the gated handler (READ_ONLY fast-path)."""
    with patch(
        "agent.tools.handle", return_value=json.dumps({"valid": True})
    ) as gated, patch("agent.tools.comfy_execute.handle") as direct:
        ws = await _run_action("validate", {})

    assert gated.called, "validate must now reach the dispatcher"
    assert gated.call_args.args[0] == "validate_before_execute"
    direct.assert_not_called()
    assert not any("unknown action" in str(m).lower() for m in ws.sent)


# --- fix #2: handle_chat / handle_status origin guard (audit 4.3 / 2.1) ---


class _FakeRequest:
    def __init__(self, headers=None, content_length=0, method="POST"):
        self.headers = headers or {}
        self.content_length = content_length
        self.method = method


async def test_handle_chat_rejects_cross_origin():
    """POST /superduper/chat must 403 a cross-origin caller before any agent work."""
    from ui.server import routes as uiroutes

    resp = await uiroutes.handle_chat(
        _FakeRequest(headers={"Origin": "http://evil.example"}, content_length=10)
    )
    assert resp.status == 403


async def test_handle_status_rejects_cross_origin():
    """GET /superduper/status must 403 a cross-origin caller (info-disclosure guard)."""
    from ui.server import routes as uiroutes

    resp = await uiroutes.handle_status(
        _FakeRequest(headers={"Origin": "http://evil.example"}, method="GET")
    )
    assert resp.status == 403


async def test_ws_handler_rejects_over_cap():
    """The ui WS handler 503s a new connection once the conversation table is full (DoS guard)."""
    from ui.server import routes as uiroutes
    from agent._session_helpers import allowed_origins

    saved = dict(uiroutes._conversations)
    try:
        uiroutes._conversations.clear()
        for i in range(uiroutes._MAX_WS_CONNECTIONS):
            uiroutes._conversations[f"c{i}"] = object()
        origin = next(iter(allowed_origins()))
        resp = await uiroutes.websocket_handler(
            _FakeRequest(headers={"Origin": origin}, method="GET")
        )
        assert resp.status == 503
    finally:
        uiroutes._conversations.clear()
        uiroutes._conversations.update(saved)
