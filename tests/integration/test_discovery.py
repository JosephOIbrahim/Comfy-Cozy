"""Integration tests — discovery and node inspection tool handlers.

All tests mock the actual HTTP calls to ComfyUI. They exercise the tool
handler dispatch logic (input validation, response shaping, error paths)
without requiring a live server.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


class TestDiscoverModels:
    """discover tool with model-oriented queries."""

    def test_discover_models(self, comfyui_available: str) -> None:
        """Discover with a common query returns model names.

        Patches the CURRENT unified search legs (the old _search_civitai /
        _search_local_models / _search_hf targets no longer exist — ledger
        L-STALE-DISCOVERY). The memo layer keys on fn.__name__, so the
        mocks carry explicit names.
        """
        civitai = MagicMock(return_value=(
            [{"name": "SDXL Base 1.0", "type": "checkpoint", "source": "civitai"}], None,
        ))
        civitai.__name__ = "_search_civitai_unified"
        hf = MagicMock(return_value=([], None))
        hf.__name__ = "_search_hf_unified"
        with patch("agent.tools.comfy_discover._search_civitai_unified", civitai), \
             patch("agent.tools.comfy_discover._search_hf_unified", hf):
            from agent.tools.comfy_discover import handle

            raw = handle("discover", {"query": "SDXL", "category": "models"})
            result = json.loads(raw)
            assert "error" not in result
            assert len(result.get("results", [])) >= 1


class TestDiscoverNodes:
    """discover tool with node-oriented queries."""

    def test_discover_nodes(self, comfyui_available: str) -> None:
        """Discover custom nodes returns structured response.

        Realigned to the current registry leg (_search_nodes_unified); the
        old _search_registry/_search_local_nodes targets no longer exist.
        """
        with patch(
            "agent.tools.comfy_discover._search_nodes_unified",
            return_value=[
                {
                    "name": "ComfyUI-Manager",
                    "type": "node_pack",
                    "description": "ComfyUI node manager",
                    "url": "https://github.com/example/ComfyUI-Manager",
                    "source": "registry",
                },
            ],
        ):
            from agent.tools.comfy_discover import handle

            raw = handle("discover", {"query": "manager", "category": "nodes"})
            result = json.loads(raw)
            assert "error" not in result
            assert len(result.get("results", [])) >= 1


class TestGetModelsSummary:
    """get_models_summary tool handler."""

    def test_get_models_summary(self, comfyui_available: str, tmp_path) -> None:
        """get_models_summary returns dict with model categories.

        Realigned: the tool lives in comfy_inspect (filesystem-backed) and
        is reached through the central dispatcher — the old version called
        comfy_api.handle ("Unknown tool") with a stale response-object mock.
        Hermetic: MODELS_DIR patched to a tmp layout, not the real disk.
        """
        (tmp_path / "checkpoints").mkdir()
        (tmp_path / "checkpoints" / "model_a.safetensors").write_bytes(b"x")
        with patch("agent.tools.comfy_inspect.MODELS_DIR", tmp_path):
            from agent.tools import handle

            raw = handle("get_models_summary", {})
        result = json.loads(raw)
        assert isinstance(result, dict)
        assert "error" not in result


class TestGetNodeInfo:
    """get_node_info tool handler."""

    def test_get_node_info_ksampler(self, comfyui_available: str) -> None:
        """get_node_info for KSampler returns inputs and outputs."""
        # _get returns PARSED JSON (post-H2 pooled client) — not a response
        # object; the old response-object mock made every lookup a MagicMock.
        object_info = {
            "KSampler": {
                "input": {
                    "required": {
                        "seed": ["INT", {"default": 0}],
                        "steps": ["INT", {"default": 20}],
                        "cfg": ["FLOAT", {"default": 8.0}],
                        "sampler_name": [["euler", "dpm_2"]],
                        "scheduler": [["normal", "karras"]],
                        "denoise": ["FLOAT", {"default": 1.0}],
                        "model": ["MODEL"],
                        "positive": ["CONDITIONING"],
                        "negative": ["CONDITIONING"],
                        "latent_image": ["LATENT"],
                    }
                },
                "output": ["LATENT"],
                "output_name": ["LATENT"],
                "name": "KSampler",
                "display_name": "KSampler",
                "category": "sampling",
            }
        }

        with patch("agent.tools.comfy_api._get", return_value=object_info):
            from agent.tools.comfy_api import handle as api_handle

            raw = api_handle("get_node_info", {"node_type": "KSampler"})
            result = json.loads(raw)
            assert "error" not in result
            # Should have input information
            node_data = result.get("KSampler", result)
            assert "input" in node_data or "inputs" in node_data or "required" in str(result)
