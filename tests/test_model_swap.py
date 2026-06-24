"""Tests for the runtime model/provider swap (agent/llm/swap.py) and the
main.py wiring that makes a swap reach the live agent loop.

Fully mocked — no real provider SDK calls.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from agent import config
from agent.llm import _provider_cache
from agent.llm._types import LLMResponse, TextBlock
from agent.llm.swap import MODEL_ALIASES, list_aliases, resolve, swap


@pytest.fixture(autouse=True)
def _restore_config_and_cache():
    """Swap mutates global config — snapshot and restore around every test."""
    snap = (config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL)
    _provider_cache.clear()
    yield
    config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL = snap
    _provider_cache.clear()


@patch("agent.llm._anthropic.anthropic")
def _swap_anthropic(mock_sdk, **kwargs):
    """Helper: swap with the anthropic SDK mocked so construction is free."""
    mock_sdk.Anthropic.return_value = MagicMock()
    return swap(**kwargs)


# ---------------------------------------------------------------------------
# resolve / registry
# ---------------------------------------------------------------------------


class TestResolve:
    def test_alias(self):
        assert resolve("claude") == ("anthropic", "claude-opus-4-7")

    def test_provider_colon_model(self):
        assert resolve("nvidia:nvidia/some-nemotron") == ("nvidia", "nvidia/some-nemotron")

    def test_bare_id_keeps_current_provider(self):
        config.LLM_PROVIDER = "anthropic"
        assert resolve("claude-sonnet-4-6") == ("anthropic", "claude-sonnet-4-6")

    def test_unknown_prefix_is_not_provider_colon_model(self):
        # 'gpt-4o:foo' — 'gpt-4o' is not a known provider, so treated as bare id
        config.LLM_PROVIDER = "anthropic"
        assert resolve("gpt-4o:foo") == ("anthropic", "gpt-4o:foo")

    def test_list_aliases_shape(self):
        al = list_aliases()
        assert al["claude"] == {"provider": "anthropic", "model": "claude-opus-4-7"}
        # NVIDIA rows stay commented out until ratified
        assert "nemotron" not in MODEL_ALIASES


# ---------------------------------------------------------------------------
# swap — success, propagation, atomicity
# ---------------------------------------------------------------------------


class TestSwap:
    def test_swap_reassigns_config(self):
        config.LLM_PROVIDER = "openai"
        config.AGENT_MODEL = "gpt-4o"
        result = _swap_anthropic(alias="claude")
        assert result == {"provider": "anthropic", "model": "claude-opus-4-7"}
        assert config.LLM_PROVIDER == "anthropic"
        assert config.AGENT_MODEL == "claude-opus-4-7"

    def test_swap_clears_stale_cache(self):
        sentinel = MagicMock()
        _provider_cache["ollama"] = sentinel  # stale entry from before the swap
        _swap_anthropic(alias="claude")
        assert _provider_cache.get("ollama") is not sentinel  # cache was cleared

    def test_swap_resets_brain_config(self):
        with patch("agent.brain._sdk.reset_integrated_config") as reset:
            _swap_anthropic(alias="claude")
        reset.assert_called_once()

    def test_swap_does_not_move_vision_by_default(self):
        config.VISION_MODEL = "claude-opus-4-7"
        _swap_anthropic(provider="anthropic", model="some-text-model")
        assert config.VISION_MODEL == "claude-opus-4-7"  # vision untouched (INV-5)

    def test_swap_also_vision_opt_in(self):
        _swap_anthropic(provider="anthropic", model="m2", also_vision=True)
        assert config.VISION_MODEL == "m2"

    def test_swap_requires_a_model(self):
        with pytest.raises(ValueError, match="requires a model"):
            swap()

    def test_rollback_on_unknown_provider(self):
        config.LLM_PROVIDER = "anthropic"
        config.AGENT_MODEL = "claude-opus-4-7"
        config.VISION_MODEL = "claude-opus-4-7"
        # get_provider('bogus') raises ValueError during eager validation
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            swap(provider="bogus", model="whatever")
        # config fully restored — no half-swap
        assert config.LLM_PROVIDER == "anthropic"
        assert config.AGENT_MODEL == "claude-opus-4-7"
        assert config.VISION_MODEL == "claude-opus-4-7"


# ---------------------------------------------------------------------------
# main.py wiring — the swap must actually reach the live loop
# ---------------------------------------------------------------------------


class TestSwapReachesLoop:
    def test_run_agent_turn_reads_model_dynamically(self):
        """S-3: run_agent_turn streams config.AGENT_MODEL (not a stale import)."""
        from agent import main

        client = MagicMock()
        client.stream.return_value = LLMResponse(
            content=[TextBlock(text="ok")], stop_reason="end_turn"
        )
        with patch.object(config, "AGENT_MODEL", "swapped-model-xyz"):
            main.run_agent_turn(client, [{"role": "user", "content": "hi"}], "system")
        assert client.stream.call_args.kwargs["model"] == "swapped-model-xyz"

    def test_loop_reresolves_provider_each_turn(self):
        """S-4: run_interactive re-resolves the provider per turn via get_provider()."""
        from agent import main

        class _Handler:
            def __init__(self):
                self.n = 0

            def on_input(self):
                self.n += 1
                return "hi" if self.n == 1 else None  # one turn, then exit

            def on_stream_end(self):
                pass

            def on_text(self, _t):
                pass

        fresh_provider = MagicMock()
        with (
            patch("agent.main.get_provider", return_value=fresh_provider) as gp,
            patch("agent.main.run_agent_turn", return_value=([], True)) as rat,
            patch("agent.main.build_system_prompt_blocks", return_value="sys"),
        ):
            main.run_interactive(MagicMock(), handler=_Handler())

        assert gp.called  # provider re-resolved inside the loop
        # the re-resolved provider (not the passed-in one) drives the turn
        assert rat.call_args.args[0] is fresh_provider


# ---------------------------------------------------------------------------
# Tool surface — swap_model / list_models_available
# ---------------------------------------------------------------------------


class TestSwapModelTool:
    def test_list_models_available(self):
        from agent.tools import model_swap

        out = json.loads(model_swap.handle("list_models_available", {}))
        assert out["aliases"]["claude"] == {"provider": "anthropic", "model": "claude-opus-4-7"}

    @patch("agent.llm._anthropic.anthropic")
    def test_swap_model_cli_mode(self, mock_sdk):
        mock_sdk.Anthropic.return_value = MagicMock()
        from agent.tools import model_swap

        prev = os.environ.pop("COMFY_COZY_MCP", None)
        try:
            out = json.loads(model_swap.handle("swap_model", {"alias": "claude"}))
        finally:
            if prev is not None:
                os.environ["COMFY_COZY_MCP"] = prev
        assert out["swapped"] is True
        assert out["provider"] == "anthropic"

    @patch("agent.llm._anthropic.anthropic")
    def test_swap_model_mcp_mode_reports_host_unchanged(self, mock_sdk):
        mock_sdk.Anthropic.return_value = MagicMock()
        from agent.tools import model_swap

        with patch.dict(os.environ, {"COMFY_COZY_MCP": "1"}):
            out = json.loads(model_swap.handle("swap_model", {"alias": "claude"}))
        assert out["swapped"] is False
        assert "host" in out["note"].lower()

    def test_swap_model_error_is_human(self):
        from agent.tools import model_swap

        out = json.loads(model_swap.handle("swap_model", {"provider": "bogus", "model": "x"}))
        assert "error" in out

    def test_registered_in_dispatch(self):
        from agent.tools import _HANDLERS

        assert "swap_model" in _HANDLERS
        assert "list_models_available" in _HANDLERS
