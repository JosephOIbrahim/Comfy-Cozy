"""Tests for the preflight health surface (agent/llm/_health.py + the
list_models_available 'status' sibling).

provider_configured() is a FREE, network-free config read; probe_provider()
does ONE bounded live call and NEVER raises; model_status() rolls them into a
per-alias table WITHOUT ever mutating the active selection. The five safety
invariants under test:
  1. NO STATE MUTATION — a health check never touches LLM_PROVIDER/AGENT_MODEL/
     VISION_MODEL, never swaps.
  2. NEVER HANGS — every probe passes a bounded timeout.
  3. NEVER RAISES — a probe failure yields reachable=False, not an exception.
  4. ADDITIVE — list_models_available keeps 'aliases'/'capabilities' byte-for-
     byte; 'status' is a NEW sibling.
  5. COST-HONEST — the default (probe=False) makes NO network call; probing is
     opt-in and only touches CONFIGURED providers.

Fully mocked — no real network. Mirrors test_model_capabilities.py's config
snapshot/restore + provider-cache reset style.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agent import config
from agent.llm import _provider_cache
from agent.llm._health import model_status, probe_provider, provider_configured


@pytest.fixture(autouse=True)
def _restore_config_and_cache():
    """A health check must NEVER mutate the active selection (INV-1). Snapshot
    the swap triple and the name-keyed provider cache; restore around each test
    so a leak would surface as a cross-test failure, not silent drift."""
    snap = (config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL)
    _provider_cache.clear()
    yield
    config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL = snap
    _provider_cache.clear()


def _configure_only_anthropic(monkeypatch) -> None:
    """Leave anthropic the only KEY-configured provider (ollama is keyless and
    stays always-configured; that is fine — the negative assertions target
    openai/nvidia/gemini/custom, which this pins to unconfigured)."""
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setattr(config, "OPENAI_API_KEY", None)
    monkeypatch.setattr(config, "GEMINI_API_KEY", None)
    monkeypatch.setattr(config, "NVIDIA_API_KEY", None)
    monkeypatch.setattr(config, "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    monkeypatch.setattr(config, "CUSTOM_MODEL", "")


# ---------------------------------------------------------------------------
# provider_configured — free, static config read (no network)
# ---------------------------------------------------------------------------


class TestProviderConfigured:
    def test_anthropic_configured_when_key_set(self, monkeypatch):
        monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-test")
        assert provider_configured("anthropic")["configured"] is True

    def test_anthropic_unconfigured_gives_a_reason(self, monkeypatch):
        monkeypatch.setattr(config, "ANTHROPIC_API_KEY", None)
        row = provider_configured("anthropic")
        assert row["configured"] is False
        assert row["reason"]  # non-empty, human-readable explanation

    def test_nvidia_configured_with_key(self, monkeypatch):
        monkeypatch.setattr(config, "NVIDIA_API_KEY", "nvapi-test")
        monkeypatch.setattr(config, "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        assert provider_configured("nvidia")["configured"] is True

    def test_nvidia_configured_keyless_when_self_hosted(self, monkeypatch):
        # A self-hosted vLLM/NIM endpoint needs no key — a local base_url alone
        # configures nvidia.
        monkeypatch.setattr(config, "NVIDIA_API_KEY", None)
        monkeypatch.setattr(config, "NVIDIA_BASE_URL", "http://localhost:8000/v1")
        assert provider_configured("nvidia")["configured"] is True

    def test_custom_configured_iff_model_set(self, monkeypatch):
        monkeypatch.setattr(config, "CUSTOM_MODEL", "my-local-model")
        assert provider_configured("custom")["configured"] is True
        monkeypatch.setattr(config, "CUSTOM_MODEL", "")
        assert provider_configured("custom")["configured"] is False

    def test_ollama_always_configured(self):
        assert provider_configured("ollama")["configured"] is True

    def test_unknown_provider_not_configured(self):
        assert provider_configured("bogus")["configured"] is False


# ---------------------------------------------------------------------------
# probe_provider — one bounded live call; caught, never raised
# ---------------------------------------------------------------------------


class TestProbeProvider:
    def test_success_is_reachable_and_probe_is_bounded(self):
        prov = MagicMock()
        prov.create.return_value = MagicMock()  # LLMResponse-ish
        with patch("agent.llm._health.get_provider", return_value=prov):
            row = probe_provider("anthropic", "claude-opus-4-7")
        assert row["reachable"] is True
        assert isinstance(row["latency_ms"], int)
        assert row["latency_ms"] >= 0
        assert row["detail"] == ""
        # INV-2/INV-5: the probe is CHEAP (<=4 tokens) and BOUNDED (a timeout).
        prov.create.assert_called_once()
        kwargs = prov.create.call_args.kwargs
        assert kwargs["max_tokens"] <= 4
        assert "timeout" in kwargs
        assert kwargs["timeout"] and kwargs["timeout"] > 0

    def test_failure_is_caught_not_raised(self):
        # INV-3: a bad key / unreachable endpoint yields reachable=False, not an
        # exception.
        prov = MagicMock()
        prov.create.side_effect = RuntimeError("boom")
        with patch("agent.llm._health.get_provider", return_value=prov):
            row = probe_provider("anthropic", "claude-opus-4-7")  # must not raise
        assert row["reachable"] is False
        assert row["latency_ms"] is None
        assert "boom" in row["detail"]

    def test_nonpositive_timeout_is_clamped_not_unbounded(self):
        # INV-2: a 0/None timeout must NOT reach create() as a falsy value — every
        # provider treats that as "no timeout" (unbounded -> potential hang). It is
        # clamped to a positive default so the probe stays bounded.
        prov = MagicMock()
        prov.create.return_value = MagicMock()
        with patch("agent.llm._health.get_provider", return_value=prov):
            probe_provider("anthropic", "claude-opus-4-7", timeout=0)
        assert prov.create.call_args.kwargs["timeout"] > 0


# ---------------------------------------------------------------------------
# model_status — per-alias table; opt-in probe; no mutation, no raise
# ---------------------------------------------------------------------------


class TestModelStatus:
    def test_probe_false_is_free_and_covers_every_alias(self):
        # INV-5: the default is network-free — a probe must never fire.
        with patch("agent.llm._health.get_provider") as gp:
            out = model_status(probe=False)
        gp.assert_not_called()
        # keyed by every alias, including the dynamic 'custom' row
        assert "claude" in out
        assert "custom" in out
        for row in out.values():
            assert {"provider", "model", "configured", "reason"} <= set(row.keys())

    def test_probe_true_never_mutates_active_selection(self, monkeypatch):
        # INV-1 — the load-bearing one: probing must not swap or touch config.*.
        _configure_only_anthropic(monkeypatch)
        before = (config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL)
        prov = MagicMock()
        prov.create.return_value = MagicMock()
        with patch("agent.llm._health.get_provider", return_value=prov):
            model_status(probe=True)
        after = (config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL)
        assert after == before

    def test_probe_true_marks_configured_reachable_and_skips_unconfigured(self, monkeypatch):
        _configure_only_anthropic(monkeypatch)
        prov = MagicMock()
        prov.create.return_value = MagicMock()  # fast success for every probe
        with patch("agent.llm._health.get_provider", return_value=prov):
            out = model_status(probe=True)
        # anthropic-backed aliases were probed and came back reachable
        assert out["claude"]["reachable"] is True
        assert out["claude-fast"]["reachable"] is True
        # INV-5: an unconfigured alias is skipped — configured False, never probed
        assert out["gpt-4o"]["configured"] is False
        assert out["gpt-4o"].get("reachable") is not True

    def test_probe_true_never_raises_when_one_probe_errors(self, monkeypatch):
        # INV-3: one bad probe cannot bring the whole table down.
        _configure_only_anthropic(monkeypatch)

        def _create(model=None, **kwargs):
            if model == "claude-haiku-4-5-20251001":  # the claude-fast target
                raise RuntimeError("boom")
            return MagicMock()

        prov = MagicMock()
        prov.create.side_effect = _create
        with patch("agent.llm._health.get_provider", return_value=prov):
            out = model_status(probe=True)  # must not raise
        assert out["claude"]["reachable"] is True
        assert out["claude-fast"]["reachable"] is False


# ---------------------------------------------------------------------------
# tool surface — list_models_available gains an additive 'status' sibling
# ---------------------------------------------------------------------------


class TestListModelsAvailableStatus:
    def test_status_sibling_is_additive_and_leaves_the_rest_intact(self):
        from agent.tools import model_swap

        out = json.loads(model_swap.handle("list_models_available", {}))
        # NEW sibling key, always present, boolean 'configured'
        assert "configured" in out["status"]["claude"]
        assert isinstance(out["status"]["claude"]["configured"], bool)
        # INV-4: aliases + capabilities are byte-for-byte unchanged.
        assert out["aliases"]["claude"] == {
            "provider": "anthropic",
            "model": "claude-opus-4-7",
        }
        assert out["capabilities"]["claude"]["tool_calling"] is True

    def test_probe_flag_adds_reachable_to_configured_rows(self, monkeypatch):
        from agent.tools import model_swap

        monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-test")
        prov = MagicMock()
        prov.create.return_value = MagicMock()
        with patch("agent.llm._health.get_provider", return_value=prov):
            out = json.loads(model_swap.handle("list_models_available", {"probe": True}))
        # a configured row now carries a live reachability verdict
        assert "reachable" in out["status"]["claude"]
