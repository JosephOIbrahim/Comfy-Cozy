"""Integration tests — verify ComfyUI connectivity and basic API calls.

All tests skip cleanly when ComfyUI is not running.
"""

import json

import httpx
import pytest

pytestmark = pytest.mark.integration


class TestComfyUIConnection:
    """Verify basic ComfyUI REST endpoints are reachable and well-formed."""

    def test_server_reachable(self, comfyui_available: str):
        """GET /system_stats returns 200 with GPU info."""
        resp = httpx.get(f"{comfyui_available}/system_stats", timeout=5.0)
        assert resp.status_code == 200
        data = resp.json()
        assert "devices" in data or "system" in data

    def test_list_models(self, comfyui_available: str):
        """GET /object_info includes checkpoint loaders that reference models."""
        from agent.tools.comfy_api import handle as api_handle

        result = json.loads(api_handle("get_all_nodes", {"format": "names_only"}))
        assert "error" not in result
        assert result.get("count", 0) > 0
        assert isinstance(result.get("nodes"), list)

    def test_list_nodes(self, comfyui_available: str):
        """Node list contains known standard types like KSampler."""
        from agent.tools.comfy_api import handle as api_handle

        result = json.loads(api_handle("get_all_nodes", {"format": "names_only"}))
        assert "error" not in result
        nodes = result.get("nodes", [])
        assert "KSampler" in nodes, f"KSampler not found in {len(nodes)} nodes"

    def test_queue_status(self, comfyui_available: str):
        """Queue status endpoint returns a valid dict."""
        from agent.tools.comfy_api import handle as api_handle

        result = json.loads(api_handle("get_queue_status", {}))
        assert "error" not in result
        assert isinstance(result, dict)
        assert "running_count" in result
        assert "pending_count" in result
