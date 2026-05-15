"""Tests for the thinking_budget parameter across all LLM providers.

Behavior under test (inside-out branch):
  - Anthropic threads thinking_budget into stream/create as
    `thinking={"type": "enabled", "budget_tokens": N}` when N > 0.
  - Anthropic's convert_messages replays signature-bearing ThinkingBlocks
    verbatim (so multi-turn extended-thinking + tool_use stays valid).
  - Signature-less ThinkingBlocks are silently dropped — a known-fragile
    path pinned here for visibility (Action 2 was deferred).
  - OpenAI / Gemini / Ollama accept thinking_budget without raising
    and do NOT forward it to their respective SDK calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent.llm import _provider_cache
from agent.llm._types import (
    LLMResponse,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
)


@pytest.fixture(autouse=True)
def _clear_provider_cache():
    _provider_cache.clear()
    yield
    _provider_cache.clear()


# ============================================================================
# Anthropic — thinking_budget wiring
# ============================================================================


def _make_anthropic(mock_sdk):
    mock_sdk.Anthropic.return_value = MagicMock()
    from agent.llm._anthropic import AnthropicProvider

    return AnthropicProvider()


def _wire_anthropic_stream(provider):
    """Wire provider._client.messages.stream to a minimal success response."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "ok"

    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)
    mock_stream.__iter__ = MagicMock(return_value=iter([]))

    mock_msg = MagicMock()
    mock_msg.content = [text_block]
    mock_msg.stop_reason = "end_turn"
    mock_msg.model = "claude-test"
    mock_msg.usage = MagicMock(input_tokens=1, output_tokens=1)
    mock_stream.get_final_message.return_value = mock_msg

    provider._client.messages.stream.return_value = mock_stream
    return mock_stream


def _wire_anthropic_create(provider):
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "ok"

    mock_msg = MagicMock()
    mock_msg.content = [text_block]
    mock_msg.stop_reason = "end_turn"
    mock_msg.model = "claude-test"
    mock_msg.usage = MagicMock(input_tokens=1, output_tokens=1)

    provider._client.messages.create.return_value = mock_msg


class TestAnthropicThinkingBudgetStream:
    def test_thinking_budget_zero_omits_thinking_kwarg(self):
        with patch("agent.llm._anthropic.anthropic") as mock_sdk:
            provider = _make_anthropic(mock_sdk)
            _wire_anthropic_stream(provider)
            provider.stream(
                model="claude-test",
                max_tokens=16384,
                system="sys",
                tools=[],
                messages=[{"role": "user", "content": "hi"}],
                # thinking_budget omitted — defaults to 0
            )
            kwargs = provider._client.messages.stream.call_args.kwargs
            assert "thinking" not in kwargs

    def test_thinking_budget_positive_adds_enabled_thinking_kwarg(self):
        with patch("agent.llm._anthropic.anthropic") as mock_sdk:
            provider = _make_anthropic(mock_sdk)
            _wire_anthropic_stream(provider)
            provider.stream(
                model="claude-test",
                max_tokens=16384,
                system="sys",
                tools=[],
                messages=[{"role": "user", "content": "hi"}],
                thinking_budget=4000,
            )
            kwargs = provider._client.messages.stream.call_args.kwargs
            assert kwargs["thinking"] == {
                "type": "enabled",
                "budget_tokens": 4000,
            }

    def test_thinking_budget_clamped_below_max_tokens_normal_range(self):
        """budget > max_tokens-1024 → clamped to (max_tokens-1024)."""
        with patch("agent.llm._anthropic.anthropic") as mock_sdk:
            provider = _make_anthropic(mock_sdk)
            _wire_anthropic_stream(provider)
            provider.stream(
                model="claude-test",
                max_tokens=16384,
                system="sys",
                tools=[],
                messages=[{"role": "user", "content": "hi"}],
                thinking_budget=20000,
            )
            kwargs = provider._client.messages.stream.call_args.kwargs
            # min(20000, max(16384-1024, 1024)) = min(20000, 15360) = 15360
            assert kwargs["thinking"]["budget_tokens"] == 15360

    def test_thinking_budget_raises_when_max_tokens_too_small(self):
        """When thinking is requested with max_tokens <= 1024, the call
        raises ValueError before reaching the SDK (review action C3,
        formerly deferred). Previously the clamp formula yielded
        budget_tokens == max_tokens and the Anthropic API would 400
        at request time."""
        with patch("agent.llm._anthropic.anthropic") as mock_sdk:
            provider = _make_anthropic(mock_sdk)
            _wire_anthropic_stream(provider)
            with pytest.raises(ValueError, match=r"max_tokens"):
                provider.stream(
                    model="claude-test",
                    max_tokens=1024,
                    system="sys",
                    tools=[],
                    messages=[{"role": "user", "content": "hi"}],
                    thinking_budget=4000,
                )
            # SDK must not have been called past the validation
            provider._client.messages.stream.assert_not_called()


class TestAnthropicThinkingBudgetCreate:
    def test_thinking_budget_zero_omits_thinking_kwarg(self):
        with patch("agent.llm._anthropic.anthropic") as mock_sdk:
            provider = _make_anthropic(mock_sdk)
            _wire_anthropic_create(provider)
            provider.create(
                model="claude-test",
                max_tokens=4096,
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
            )
            kwargs = provider._client.messages.create.call_args.kwargs
            assert "thinking" not in kwargs

    def test_thinking_budget_positive_adds_enabled_thinking_kwarg(self):
        with patch("agent.llm._anthropic.anthropic") as mock_sdk:
            provider = _make_anthropic(mock_sdk)
            _wire_anthropic_create(provider)
            provider.create(
                model="claude-test",
                max_tokens=4096,
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                thinking_budget=2000,
            )
            kwargs = provider._client.messages.create.call_args.kwargs
            assert kwargs["thinking"] == {
                "type": "enabled",
                "budget_tokens": 2000,
            }


# ============================================================================
# Anthropic — ThinkingBlock signature replay (convert_messages)
# ============================================================================


class TestAnthropicThinkingBlockReplay:
    """Multi-turn behavior: when extended thinking + tool_use is in history,
    the prior assistant turn's thinking block (with signature) must be
    replayed verbatim before the tool_use, or the API rejects the request.
    """

    def test_signature_bearing_thinking_block_replayed_with_signature(self):
        with patch("agent.llm._anthropic.anthropic") as mock_sdk:
            provider = _make_anthropic(mock_sdk)
            history = [
                {
                    "role": "assistant",
                    "content": [
                        ThinkingBlock(thinking="step 1", signature="sig-abc"),
                        ToolUseBlock(id="tu_1", name="x", input={}),
                    ],
                },
            ]
            converted = provider.convert_messages(history)
            assistant_content = converted[0]["content"]
            assert assistant_content[0] == {
                "type": "thinking",
                "thinking": "step 1",
                "signature": "sig-abc",
            }
            assert assistant_content[1]["type"] == "tool_use"

    def test_signatureless_thinking_block_dropped_with_warning(self, caplog):
        """Signature-less ThinkingBlock is dropped during replay AND a
        warning is logged (review action S1, formerly deferred). The drop
        itself is preserved — the API rejects unsigned thinking blocks
        when extended thinking is active, so dropping is correct; the
        warning makes the loss diagnosable instead of invisible.
        """
        import logging
        with patch("agent.llm._anthropic.anthropic") as mock_sdk:
            provider = _make_anthropic(mock_sdk)
            history = [
                {
                    "role": "assistant",
                    "content": [
                        ThinkingBlock(thinking="step 1"),  # signature=None
                        TextBlock(text="hello"),
                    ],
                },
            ]
            with caplog.at_level(logging.WARNING, logger="agent.llm._anthropic"):
                converted = provider.convert_messages(history)
            assistant_content = converted[0]["content"]
            assert len(assistant_content) == 1
            assert assistant_content[0] == {"type": "text", "text": "hello"}
            warning_messages = [
                r.getMessage() for r in caplog.records
                if r.levelno == logging.WARNING
            ]
            assert any("ThinkingBlock" in m for m in warning_messages), (
                f"expected a warning naming ThinkingBlock; got: {warning_messages}"
            )


# ============================================================================
# Non-Anthropic providers — accept thinking_budget, do not forward
# ============================================================================


def _make_openai_provider_with_stream_response():
    """Build an OpenAIProvider whose chat.completions.create returns a minimal
    non-streaming-style completion (the OpenAI provider buffers the stream
    internally via stream=True)."""
    pytest.importorskip("openai", reason="openai SDK not installed")
    with patch("agent.llm._openai.openai") as mock_sdk:
        mock_sdk.OpenAI.return_value = MagicMock()
        mock_sdk.__bool__ = lambda self: True
        from agent.llm._openai import OpenAIProvider

        provider = OpenAIProvider()

    # Minimal usage-only stream chunk so the stream loop exits cleanly
    usage_chunk = SimpleNamespace(
        choices=[],
        model="gpt-test",
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
    )
    final_chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=None, tool_calls=None),
                finish_reason="stop",
            )
        ],
        model="gpt-test",
        usage=None,
    )
    provider._client.chat.completions.create.return_value = iter(
        [final_chunk, usage_chunk]
    )
    return provider


def _make_ollama_provider_with_stream_response():
    pytest.importorskip("openai", reason="openai SDK not installed (Ollama uses it)")
    with patch("agent.llm._ollama.openai") as mock_sdk:
        mock_sdk.OpenAI.return_value = MagicMock()
        mock_sdk.__bool__ = lambda self: True
        from agent.llm._ollama import OllamaProvider

        provider = OllamaProvider()

    usage_chunk = SimpleNamespace(
        choices=[],
        model="llama3.1",
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
    )
    final_chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=None, tool_calls=None),
                finish_reason="stop",
            )
        ],
        model="llama3.1",
        usage=None,
    )
    provider._client.chat.completions.create.return_value = iter(
        [final_chunk, usage_chunk]
    )
    return provider


class TestOpenAIIgnoresThinkingBudget:
    def test_stream_accepts_thinking_budget_without_raising(self):
        provider = _make_openai_provider_with_stream_response()
        resp = provider.stream(
            model="gpt-test",
            max_tokens=100,
            system="sys",
            tools=[],
            messages=[{"role": "user", "content": "hi"}],
            thinking_budget=4000,
        )
        assert isinstance(resp, LLMResponse)
        # OpenAI's chat-completions API does not accept "thinking" — verify
        # the provider does not forward it.
        kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert "thinking" not in kwargs
        assert "thinking_budget" not in kwargs

    def test_create_accepts_thinking_budget_without_raising(self):
        pytest.importorskip("openai", reason="openai SDK not installed")
        with patch("agent.llm._openai.openai") as mock_sdk:
            mock_sdk.OpenAI.return_value = MagicMock()
            mock_sdk.__bool__ = lambda self: True
            from agent.llm._openai import OpenAIProvider

            provider = OpenAIProvider()

        # Non-streaming create() — returns a completion-shaped object
        msg = SimpleNamespace(content="ok", tool_calls=None)
        choice = SimpleNamespace(message=msg, finish_reason="stop")
        completion = SimpleNamespace(
            choices=[choice],
            model="gpt-test",
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )
        provider._client.chat.completions.create.return_value = completion

        resp = provider.create(
            model="gpt-test",
            max_tokens=100,
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            thinking_budget=4000,
        )
        assert isinstance(resp, LLMResponse)
        kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert "thinking" not in kwargs
        assert "thinking_budget" not in kwargs


class TestOllamaIgnoresThinkingBudget:
    def test_stream_accepts_thinking_budget_without_raising(self):
        provider = _make_ollama_provider_with_stream_response()
        resp = provider.stream(
            model="llama3.1",
            max_tokens=100,
            system="sys",
            tools=[],
            messages=[{"role": "user", "content": "hi"}],
            thinking_budget=4000,
        )
        assert isinstance(resp, LLMResponse)
        kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert "thinking" not in kwargs
        assert "thinking_budget" not in kwargs


class TestGeminiIgnoresThinkingBudget:
    """Gemini does not natively expose extended thinking through the same
    parameter shape. The provider should accept thinking_budget and ignore
    it; the test asserts the call completes and does not raise.
    """

    def test_stream_accepts_thinking_budget_without_raising(self):
        pytest.importorskip(
            "google.genai", reason="google-genai SDK not installed"
        )

        with patch("agent.llm._gemini.genai") as mock_genai, patch(
            "agent.llm._gemini.genai_types"
        ) as mock_types:
            mock_genai.Client.return_value = MagicMock()
            mock_types.GenerateContentConfig = MagicMock()
            mock_types.HttpOptions = MagicMock()
            mock_types.FunctionDeclaration = MagicMock()
            mock_types.Tool = MagicMock()
            mock_types.Part.from_text = lambda text: SimpleNamespace(
                text=text, thought=False, function_call=None
            )

            from agent.llm._gemini import GeminiProvider

            provider = GeminiProvider()

            # Wire generate_content_stream to yield one terminal chunk
            terminal = SimpleNamespace(
                candidates=[
                    SimpleNamespace(
                        content=SimpleNamespace(parts=[]),
                        finish_reason=SimpleNamespace(name="STOP"),
                    )
                ],
                usage_metadata=SimpleNamespace(
                    prompt_token_count=1, candidates_token_count=1
                ),
                model_version="gemini-test",
            )
            provider._client.models.generate_content_stream.return_value = iter(
                [terminal]
            )

            resp = provider.stream(
                model="gemini-test",
                max_tokens=100,
                system="sys",
                tools=[],
                messages=[{"role": "user", "content": "hi"}],
                thinking_budget=4000,
            )
            assert isinstance(resp, LLMResponse)
