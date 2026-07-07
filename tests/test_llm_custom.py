"""Tests for the bring-your-own custom HTTP engine (agent/llm/_custom.py).

CustomProvider is an OpenAI-compatible provider pointed at an arbitrary
base_url (a self-hosted vLLM / TGI / LM Studio endpoint), so a local box
isn't mislabeled "nvidia". Fully mocked — no real openai SDK calls.

Mirrors test_model_swap.py's config snapshot/restore + SDK-patch style.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent import config
from agent.llm import _provider_cache


@pytest.fixture(autouse=True)
def _restore_config_and_cache():
    """CustomProvider construction + swap mutate global config/cache."""
    snap = (config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL)
    _provider_cache.clear()
    yield
    config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL = snap
    _provider_cache.clear()


def _fake_completion(model: str = "custom-model"):
    """A minimally-shaped ChatCompletion so _to_response() doesn't blow up."""
    message = SimpleNamespace(content="hi", tool_calls=None)
    choice = SimpleNamespace(message=message, finish_reason="stop")
    return SimpleNamespace(choices=[choice], model=model, usage=None)


# ---------------------------------------------------------------------------
# Construction — base_url + key fallback
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_uses_base_url_and_key_fallback(self, monkeypatch):
        monkeypatch.setattr(config, "CUSTOM_BASE_URL", "http://box:9000/v1")
        monkeypatch.setattr(config, "CUSTOM_API_KEY", None)
        with patch("agent.llm._custom.openai") as mock_openai:
            from agent.llm._custom import CustomProvider

            CustomProvider()
        mock_openai.OpenAI.assert_called_once_with(
            base_url="http://box:9000/v1", api_key="not-needed"
        )

    def test_uses_provided_key_when_set(self, monkeypatch):
        monkeypatch.setattr(config, "CUSTOM_BASE_URL", "http://box:9000/v1")
        monkeypatch.setattr(config, "CUSTOM_API_KEY", "sk-local-abc")
        with patch("agent.llm._custom.openai") as mock_openai:
            from agent.llm._custom import CustomProvider

            CustomProvider()
        mock_openai.OpenAI.assert_called_once_with(
            base_url="http://box:9000/v1", api_key="sk-local-abc"
        )

    def test_metric_name_is_custom(self):
        with patch("agent.llm._custom.openai"):
            from agent.llm._custom import CustomProvider

            assert CustomProvider()._metric_name == "custom"


# ---------------------------------------------------------------------------
# Factory + resolve registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_get_provider_returns_custom(self):
        from agent.llm import get_provider

        with patch("agent.llm._custom.openai"):
            from agent.llm._custom import CustomProvider

            prov = get_provider("custom")
        assert isinstance(prov, CustomProvider)

    def test_resolve_custom_uses_config_model(self, monkeypatch):
        from agent.llm.swap import resolve

        monkeypatch.setattr(config, "CUSTOM_MODEL", "backend-model-x")
        assert resolve("custom") == ("custom", "backend-model-x")


# ---------------------------------------------------------------------------
# create(timeout=...) — preserves base_url via with_options, no fresh client
# ---------------------------------------------------------------------------


class TestCreateTimeout:
    def test_timeout_uses_with_options_not_fresh_client(self):
        with patch("agent.llm._custom.openai") as mock_openai:
            from agent.llm._custom import CustomProvider

            provider = CustomProvider()
            client = mock_openai.OpenAI.return_value
            scoped = client.with_options.return_value
            scoped.chat.completions.create.return_value = _fake_completion()

            provider.create(
                model="m",
                max_tokens=4,
                system="",
                messages=[{"role": "user", "content": "hi"}],
                timeout=12.0,
            )

        # timeout is applied by re-scoping the existing (base_url-bound) client,
        # NOT by constructing a fresh default openai.OpenAI(timeout=...).
        client.with_options.assert_called_once_with(timeout=12.0)
        assert mock_openai.OpenAI.call_count == 1  # only __init__ built a client
        scoped.chat.completions.create.assert_called_once()
