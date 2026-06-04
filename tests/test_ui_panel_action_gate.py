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
