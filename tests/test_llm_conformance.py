"""Cross-provider conformance tests for the LLM abstraction layer.

Uses @pytest.mark.parametrize to verify all 4 providers implement
the LLMProvider protocol correctly. All tests are mocked — no network.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent.llm._base import LLMProvider
from agent.llm._types import (
    TextBlock,
)


# ---------------------------------------------------------------------------
# Provider factories — each returns (provider_instance, cleanup_fn | None)
# ---------------------------------------------------------------------------


def _make_anthropic():
    """Build an AnthropicProvider with mocked SDK."""
    with patch("agent.llm._anthropic.anthropic") as mock_sdk:
        mock_sdk.Anthropic.return_value = MagicMock()
        from agent.llm._anthropic import AnthropicProvider

        return AnthropicProvider()


def _make_openai():
    """Build an OpenAIProvider with mocked SDK."""
    with patch("agent.llm._openai.openai") as mock_openai:
        mock_openai.OpenAI.return_value = MagicMock()
        mock_openai.__bool__ = lambda self: True
        from agent.llm._openai import OpenAIProvider

        return OpenAIProvider()


def _make_gemini():
    """Build a GeminiProvider with mocked SDK."""
    mock_genai = MagicMock()
    mock_errors = MagicMock()
    mock_types = MagicMock()

    # Part factories
    mock_types.Part.from_text = lambda text: SimpleNamespace(
        text=text, thought=False, function_call=None
    )
    mock_types.Part.from_function_call = lambda name, args: SimpleNamespace(
        text=None, thought=False, function_call=SimpleNamespace(name=name, args=args)
    )
    mock_types.Part.from_function_response = lambda name, response: SimpleNamespace(
        text=None, thought=False, function_call=None
    )
    mock_types.Part.from_bytes = lambda data, mime_type: SimpleNamespace(
        text=None, thought=False, function_call=None
    )

    with (
        patch("agent.llm._gemini.genai", mock_genai),
        patch("agent.llm._gemini.genai_errors", mock_errors),
        patch("agent.llm._gemini.genai_types", mock_types),
        patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}),
    ):
        from agent.llm._gemini import GeminiProvider

        provider = GeminiProvider()

    # Keep references alive
    import agent.llm._gemini as mod

    mod.genai = mock_genai
    mod.genai_errors = mock_errors
    mod.genai_types = mock_types
    return provider


def _make_ollama():
    """Build an OllamaProvider with mocked SDK."""
    with (
        patch("agent.llm._ollama.openai") as mock_openai,
        patch("agent.config.OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    ):
        mock_openai.OpenAI.return_value = MagicMock()
        from agent.llm._ollama import OllamaProvider

        return OllamaProvider()


PROVIDER_FACTORIES = {
    "anthropic": _make_anthropic,
    "openai": _make_openai,
    "gemini": _make_gemini,
    "ollama": _make_ollama,
}


@pytest.fixture(params=list(PROVIDER_FACTORIES.keys()))
def provider(request):
    """Parametrized fixture that yields each provider instance."""
    factory = PROVIDER_FACTORIES[request.param]
    return factory()


# ---------------------------------------------------------------------------
# Protocol Conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Verify all providers implement the LLMProvider interface."""

    def test_is_llm_provider(self, provider):
        """Each provider is a subclass of LLMProvider."""
        assert isinstance(provider, LLMProvider)

    def test_has_stream_method(self, provider):
        """Each provider has a stream() method."""
        assert callable(getattr(provider, "stream", None))

    def test_has_create_method(self, provider):
        """Each provider has a create() method."""
        assert callable(getattr(provider, "create", None))

    def test_has_convert_tools_method(self, provider):
        """Each provider has a convert_tools() method."""
        assert callable(getattr(provider, "convert_tools", None))

    def test_has_convert_messages_method(self, provider):
        """Each provider has a convert_messages() method."""
        assert callable(getattr(provider, "convert_messages", None))


# ---------------------------------------------------------------------------
# Tool Schema Round-Trip
# ---------------------------------------------------------------------------


class TestToolSchemaRoundTrip:
    """Verify tool schema conversion preserves required fields."""

    def test_tool_name_preserved(self, provider):
        """Tool name survives conversion."""
        tools = [
            {
                "name": "get_weather",
                "description": "Get weather for a city",
                "input_schema": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            }
        ]
        result = provider.convert_tools(tools)
        assert len(result) >= 1

        # Dig into the provider-specific format to find the name
        converted = result[0]
        # OpenAI/Ollama: {"type": "function", "function": {"name": ...}}
        # Gemini: genai_types.Tool(function_declarations=[...])
        # Anthropic: same dict with cache_control added
        if isinstance(converted, dict):
            if "function" in converted:
                assert converted["function"]["name"] == "get_weather"
            elif "name" in converted:
                assert converted["name"] == "get_weather"
            else:
                pytest.fail(f"Unexpected tool format: {converted}")
        else:
            # Gemini returns mock objects — check the FunctionDeclaration call
            pass  # Gemini tested separately in test_llm_gemini.py

    def test_empty_tools_returns_empty(self, provider):
        """Empty input produces empty (or falsy) output."""
        result = provider.convert_tools([])
        assert not result  # Empty list or falsy


# ---------------------------------------------------------------------------
# Message Conversion Preserves Text
# ---------------------------------------------------------------------------


class TestMessageConversion:
    """Verify text content survives message conversion."""

    def test_string_content_preserved(self, provider):
        """Simple string-content message is preserved through conversion."""
        msgs = [{"role": "user", "content": "Hello world"}]
        result = provider.convert_messages(msgs)
        assert len(result) >= 1

        # For all providers, the text "Hello world" should appear somewhere
        first = result[0]
        if isinstance(first.get("content"), str):
            assert first["content"] == "Hello world"
        elif isinstance(first.get("content"), list):
            # Anthropic keeps as-is
            assert first["content"] == "Hello world"
        elif "parts" in first:
            # Gemini wraps in parts
            assert any(getattr(p, "text", None) == "Hello world" for p in first["parts"])
        else:
            pytest.fail(f"Cannot find text in converted message: {first}")

    def test_role_preserved_or_mapped(self, provider):
        """User role is preserved (or mapped to equivalent)."""
        msgs = [{"role": "user", "content": "test"}]
        result = provider.convert_messages(msgs)
        role = result[0].get("role", "")
        assert role in ("user", "human")  # All providers use "user"

    def test_assistant_role_mapped(self, provider):
        """Assistant role is preserved or mapped to provider equivalent."""
        msgs = [{"role": "assistant", "content": "response"}]
        result = provider.convert_messages(msgs)
        role = result[0].get("role", "")
        # Gemini uses "model", everyone else uses "assistant"
        assert role in ("assistant", "model")


# ---------------------------------------------------------------------------
# TextBlock Conversion
# ---------------------------------------------------------------------------


class TestTextBlockConversion:
    """Verify TextBlock content blocks survive conversion."""

    def test_text_block_content_preserved(self, provider):
        """TextBlock text is accessible after conversion."""
        msgs = [{"role": "user", "content": [TextBlock(text="Hello from block")]}]
        result = provider.convert_messages(msgs)
        assert len(result) >= 1

        first = result[0]
        content = first.get("content") or first.get("parts")

        if isinstance(content, list):
            # Find the text
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item["text"])
                elif hasattr(item, "text") and item.text:
                    texts.append(item.text)
            assert "Hello from block" in texts
        elif isinstance(content, str):
            # Ollama joins text blocks into a string
            assert "Hello from block" in content
        else:
            pytest.fail(f"Unexpected content format: {content}")
