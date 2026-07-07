"""Tests for the capability-aware selector + tool-calling gate (swap.py).

capabilities() reports {tool_calling, vision, tier} per provider (with an
optional alias tier override); swap(require_tools=True) refuses a swap to a
non-tool-capable provider WITHOUT half-mutating config. The gate is a no-op
for every existing (tool-capable) alias. Fully mocked.

Mirrors test_model_swap.py's config snapshot/restore + SDK-patch style.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent import config
from agent.llm import _provider_cache
from agent.llm.swap import (
    MODEL_ALIASES,
    capabilities,
    list_capabilities,
    swap,
)


@pytest.fixture(autouse=True)
def _restore_config_and_cache():
    """swap() mutates global config — snapshot and restore around every test."""
    snap = (config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL)
    _provider_cache.clear()
    yield
    config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL = snap
    _provider_cache.clear()


# ---------------------------------------------------------------------------
# capabilities() — per-provider table + alias override
# ---------------------------------------------------------------------------


class TestCapabilities:
    def test_anthropic_is_tool_and_vision_capable(self):
        caps = capabilities("anthropic")
        assert caps["tool_calling"] is True
        assert caps["vision"] is True

    def test_nvidia_tool_capable_text_only(self):
        caps = capabilities("nvidia")
        assert caps["tool_calling"] is True
        assert caps["vision"] is False

    def test_unknown_provider_defaults_permissive(self):
        # An unknown provider defaults to tool_calling True so we never wedge a
        # legit endpoint the table simply hasn't heard of.
        assert capabilities("bogus")["tool_calling"] is True

    def test_alias_overrides_tier(self):
        assert capabilities("anthropic", "", alias="claude-fast")["tier"] == "fast"


class TestListCapabilities:
    def test_includes_claude_custom_and_every_alias(self):
        caps = list_capabilities()
        assert "claude" in caps
        assert "custom" in caps
        for alias in MODEL_ALIASES:
            assert alias in caps

    def test_every_row_has_the_three_keys(self):
        for row in list_capabilities().values():
            assert {"tool_calling", "vision", "tier"} <= set(row.keys())


# ---------------------------------------------------------------------------
# the tool-calling gate — bites only when require_tools AND not tool_calling
# ---------------------------------------------------------------------------


class TestToolGate:
    @patch("agent.llm._anthropic.anthropic")
    def test_tool_capable_provider_passes(self, mock_sdk):
        mock_sdk.Anthropic.return_value = MagicMock()
        result = swap(provider="anthropic", model="x", require_tools=True)
        assert result == {"provider": "anthropic", "model": "x"}
        assert config.LLM_PROVIDER == "anthropic"
        assert config.AGENT_MODEL == "x"

    @patch("agent.llm._anthropic.anthropic")
    def test_gate_refuses_non_tool_provider_without_half_swap(self, mock_sdk, monkeypatch):
        mock_sdk.Anthropic.return_value = MagicMock()
        from agent.llm import swap as swap_mod

        before = (config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL)
        monkeypatch.setattr(
            swap_mod,
            "capabilities",
            lambda *a, **k: {"tool_calling": False, "vision": False, "tier": "standard"},
        )
        with pytest.raises(ValueError, match="tool-calling"):
            swap_mod.swap(provider="anthropic", model="x", require_tools=True)
        # refusal is atomic — config is exactly as it was.
        assert (config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL) == before

    @patch("agent.llm._anthropic.anthropic")
    def test_require_tools_false_bypasses_gate(self, mock_sdk, monkeypatch):
        mock_sdk.Anthropic.return_value = MagicMock()
        from agent.llm import swap as swap_mod

        monkeypatch.setattr(
            swap_mod,
            "capabilities",
            lambda *a, **k: {"tool_calling": False, "vision": False, "tier": "standard"},
        )
        # Same non-tool provider, but the caller opted out of the gate.
        result = swap_mod.swap(provider="anthropic", model="x", require_tools=False)
        assert result == {"provider": "anthropic", "model": "x"}


# ---------------------------------------------------------------------------
# list_models_available tool — aliases unchanged, capabilities added alongside
# ---------------------------------------------------------------------------


class TestListModelsAvailableTool:
    def test_aliases_unchanged_and_capabilities_present(self):
        from agent.tools import model_swap

        out = json.loads(model_swap.handle("list_models_available", {}))
        # INV: existing alias row is byte-for-byte unchanged.
        assert out["aliases"]["claude"] == {
            "provider": "anthropic",
            "model": "claude-opus-4-7",
        }
        # …and capabilities ride alongside.
        assert out["capabilities"]["claude"]["tool_calling"] is True
