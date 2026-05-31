"""Integration tests — comfy_agent_bridge node-pack route contracts (Tier-1).

These cross the real process seam mocked unit tests cannot see:
    agent (httpx) -> ComfyUI server -> comfy_agent_bridge routes -> back

They exist because gap #5 (get_execution_profile) once shipped "green" on
mocked unit tests while the node-pack route was actually 404-hollow — the route
did not exist server-side. A mock cannot catch that; only a live contract can.

No GPU, no model, no render required. All tests skip cleanly when ComfyUI is not
running (via the ``comfyui_available`` fixture). They additionally skip when the
comfy_agent_bridge node pack is not loaded, so a vanilla ComfyUI does not fail.

The key discriminator for the #5 regression: a *registered* bridge route returns
404 with a STRUCTURED JSON body ({"error": ..., "nodes": []}); a *missing* route
returns aiohttp's plain-text "404: Not Found". Asserting the structured body is
what proves the route is wired, not merely that "something returned 404".
"""

import json

import httpx
import pytest

pytestmark = pytest.mark.integration


def _bridge_loaded(base_url: str) -> bool:
    """True if the comfy_agent_bridge node pack is registered on this server.

    Uses /agent/canvas_state as the liveness probe: it is a GET route the pack
    registers unconditionally and that returns 200 even before any artist edit.
    """
    try:
        resp = httpx.get(f"{base_url}/agent/canvas_state", timeout=5.0)
    except Exception:
        return False
    return resp.status_code == 200


@pytest.fixture()
def bridge_available(comfyui_available: str) -> str:
    """Return the base URL only if the bridge node pack is loaded, else skip."""
    if not _bridge_loaded(comfyui_available):
        pytest.skip("comfy_agent_bridge node pack not loaded (restart ComfyUI to load it)")
    return comfyui_available


class TestBridgeRoutesRegistered:
    """The node-pack routes must exist and answer — the #5 404-hollow guard."""

    def test_canvas_state_route_is_registered(self, bridge_available: str):
        """GET /agent/canvas_state returns 200 with the buffered-graph contract."""
        resp = httpx.get(f"{bridge_available}/agent/canvas_state", timeout=5.0)
        assert resp.status_code == 200
        data = resp.json()
        # Contract: a 'workflow' key always present (None until an artist edit).
        assert "workflow" in data

    def test_exec_profile_route_is_registered_not_hollow(self, bridge_available: str):
        """GET /agent/exec_profile/<unknown> → 404 with a STRUCTURED body.

        This is the regression killer. A registered route returns our JSON
        ({"error": ..., "nodes": []}); a missing route returns aiohttp's
        plain-text '404: Not Found'. We assert the structured body to prove the
        route is actually wired, distinguishing "route works, no such prompt"
        from "#5 shipped hollow".
        """
        resp = httpx.get(
            f"{bridge_available}/agent/exec_profile/__no_such_prompt_id__",
            timeout=5.0,
        )
        assert resp.status_code == 404
        # Must be JSON (a missing route yields text/plain "404: Not Found").
        try:
            data = resp.json()
        except json.JSONDecodeError:
            pytest.fail(
                "exec_profile route is 404-HOLLOW: returned non-JSON, meaning the "
                "route is not registered (the #5 regression). Restart ComfyUI with "
                "the comfy_agent_bridge node pack."
            )
        assert "nodes" in data, f"profile 404 body missing 'nodes' contract: {data}"
        assert data["nodes"] == []

    def test_push_workflow_route_rejects_bad_payload_not_404(self, bridge_available: str):
        """POST /agent/push_workflow with junk → 400 (route exists), never 404.

        A 404 here would mean the push route is missing. A 400 proves the route
        is registered and validating its payload.
        """
        resp = httpx.post(
            f"{bridge_available}/agent/push_workflow",
            json={"not_a_workflow": True},
            timeout=5.0,
        )
        assert resp.status_code == 400, (
            f"expected 400 (route present, bad payload), got {resp.status_code}"
        )
        data = resp.json()
        assert data.get("ok") is False


class TestBridgeToolsCrossSeam:
    """The agent-side tools must round-trip through the live routes."""

    def test_get_execution_profile_tool_handles_unknown_cleanly(self, bridge_available: str):
        """get_execution_profile on an unknown id → structured error, no traceback.

        Proves the tool's httpx call reaches the route and the 404 path is mapped
        to a human-readable error rather than an exception.
        """
        from agent.tools.exec_profile import handle as profile_handle

        result = json.loads(
            profile_handle("get_execution_profile", {"prompt_id": "__no_such_prompt_id__"})
        )
        assert "error" in result
        # The tool's 404 branch names the node pack — proves it took that path.
        assert "comfy_agent_bridge" in result["error"] or "never ran" in result["error"]

    def test_get_canvas_state_tool_round_trips(self, bridge_available: str):
        """get_canvas_state tool returns the buffered-graph contract, no error."""
        from agent.tools.canvas_bridge import handle as canvas_handle

        result = json.loads(canvas_handle("get_canvas_state", {}))
        assert "error" not in result
        # Either a captured workflow or the 'no edit yet' note — both have 'workflow'.
        assert "workflow" in result

    def test_parse_ui_workflow_matches_live_object_info(self, bridge_available: str):
        """parse_ui_workflow maps a minimal UI graph against the REAL /object_info.

        Uses KSampler (a guaranteed-present core node) so the test asserts the
        widget→input mapping works against the live schema order, not a fixture.
        """
        from agent.tools.ui_api_parser import handle as parse_handle

        # Minimal UI-format node: KSampler with widgets in schema order.
        ui_workflow = {
            "nodes": [
                {
                    "id": 1,
                    "type": "KSampler",
                    "widgets_values": [156680208700286, "randomize", 20, 8.0,
                                       "euler", "normal", 1.0],
                    "inputs": [],
                }
            ],
            "links": [],
        }
        result = json.loads(parse_handle("parse_ui_workflow", {"workflow": ui_workflow}))
        assert "error" not in result, result
        api = result["api_workflow"]
        assert "1" in api
        assert api["1"]["class_type"] == "KSampler"
        inputs = api["1"]["inputs"]
        # Schema-order mapping must land the named inputs (not positional guesses).
        assert inputs.get("steps") == 20
        assert inputs.get("cfg") == 8.0
        assert inputs.get("sampler_name") == "euler"
        # KSampler is a core node — it must NOT be reported unmappable.
        assert result["unmapped"] == []
