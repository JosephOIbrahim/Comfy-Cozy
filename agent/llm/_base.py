"""Abstract base class for LLM providers.

Each provider implements two methods:
  stream()  — streaming message with tool use (agent loop)
  create()  — non-streaming message (vision, one-shot)

Providers handle their own SDK-specific format conversion internally.
The caller works exclusively with common types from _types.py.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from ._types import LLMResponse


def flatten_system(system) -> str:
    """Collapse a structured Anthropic-style system list into one string.

    Providers without prompt-cache breakpoints (OpenAI / Gemini / Ollama)
    receive a single system string; this helper preserves the call site's
    ability to pass a list of cache blocks without forcing each non-Anthropic
    provider to know about cache_control.
    """
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        parts: list[str] = []
        for block in system:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)
    return str(system)


def _record_llm_metric(provider: str, status: str, elapsed: float) -> None:
    """Record LLM call metrics (counter + histogram).

    Uses lazy import so a metrics failure never breaks LLM calls.
    """
    try:
        from ..metrics import llm_call_total, llm_call_duration_seconds

        llm_call_total.inc(provider=provider, status=status)
        llm_call_duration_seconds.observe(elapsed, provider=provider)
    except Exception:
        pass


class LLMProvider(ABC):
    """Protocol that every LLM backend must implement."""

    @abstractmethod
    def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        system,                                # str | list[dict] of cache blocks
        tools: list[dict],
        messages: list[dict],
        on_text: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
        thinking_budget: int = 0,
    ) -> LLMResponse:
        """Stream a message with tool use, calling callbacks for deltas.

        Args:
            model: Model identifier (e.g., "claude-opus-4-7", "gpt-4o").
            max_tokens: Maximum tokens in the response.
            system: System prompt. Either a plain string (legacy path; the
                provider applies its own caching) OR a list of structured
                content blocks the caller has already split for multi-tier
                prompt caching (Anthropic supports up to 4 cache breakpoints
                across system + tools).
            tools: Tool definitions in MCP format (name, description, input_schema).
            messages: Conversation history using common types.
            on_text: Called with each text delta during streaming.
            on_thinking: Called with each thinking delta (if supported).
            thinking_budget: If > 0, request extended thinking with this many
                budget tokens. Requires the provider/model to support it
                (Anthropic Claude 4.x+); ignored by providers that don't.

        Returns:
            LLMResponse with content blocks (TextBlock / ToolUseBlock).

        Raises:
            LLMRateLimitError: Rate limit exceeded.
            LLMConnectionError: Network failure.
            LLMServerError: Server-side error (5xx).
            LLMAuthError: Authentication failure.
            LLMError: Other provider errors.
        """

    @abstractmethod
    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system,                                # str | list[dict] of cache blocks
        messages: list[dict],
        timeout: float | None = None,
        thinking_budget: int = 0,
    ) -> LLMResponse:
        """Non-streaming message (used for vision, one-shot calls).

        Args:
            model: Model identifier.
            max_tokens: Maximum tokens.
            system: System prompt. str or list of structured cache blocks.
            messages: Messages (may contain ImageBlock in content).
            timeout: Optional request timeout in seconds.
            thinking_budget: If > 0, request extended thinking with this many
                budget tokens. Ignored by providers that don't support it.

        Returns:
            LLMResponse with content blocks.
        """

    @abstractmethod
    def convert_tools(self, tools: list[dict]) -> list[Any]:
        """Convert MCP-format tool definitions to provider-native format.

        MCP format: {"name": ..., "description": ..., "input_schema": {...}}
        """

    def convert_messages(self, messages: list[dict]) -> list[dict]:
        """Convert messages with common types to provider-native format.

        Default implementation returns messages as-is (works for Anthropic).
        Override for providers with different message formats (OpenAI, Gemini).
        """
        return messages
