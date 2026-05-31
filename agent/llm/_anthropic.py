"""Anthropic Claude provider — reference implementation.

Wraps the anthropic SDK to implement the LLMProvider protocol.
Handles prompt caching, streaming, tool format, and error translation.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Callable

import anthropic

from ._base import LLMProvider, _record_llm_metric
from ._types import (
    ImageBlock,
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMResponse,
    LLMServerError,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)

log = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Claude via the Anthropic SDK."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        system,                               # str | list[dict]
        tools: list[dict],
        messages: list[dict],
        on_text: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
        thinking_budget: int = 0,
    ) -> LLMResponse:
        import time

        native_tools = self.convert_tools(tools)
        native_messages = self.convert_messages(messages)
        cached_system = _cached_system(system)
        start = time.monotonic()

        stream_kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": cached_system,
            "tools": native_tools,
            "messages": native_messages,
        }
        # Streaming loop routes delta.thinking -> on_thinking;
        # ThinkingBlocks with signature emitted in final response.
        _thinking_kwargs = _build_thinking_kwargs(thinking_budget, max_tokens, model)
        stream_kwargs.update(
            _adapt_thinking_transport(_thinking_kwargs, self._client.messages.stream)
        )

        try:
            with self._client.messages.stream(**stream_kwargs) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        delta = event.delta
                        # Cycle 18: filter empty deltas. Anthropic emits
                        # zero-width content_block_delta events at content
                        # block boundaries; without the truthy check, those
                        # would fire on_text("") / on_thinking("") and (since
                        # cycle 7) set content_emitted=True, suppressing
                        # legitimate retries on transient errors.
                        if hasattr(delta, "text") and delta.text and on_text:
                            on_text(delta.text)
                        elif (
                            hasattr(delta, "thinking")
                            and delta.thinking
                            and on_thinking
                        ):
                            on_thinking(delta.thinking)
                final = stream.get_final_message()

        except anthropic.AuthenticationError as e:
            _record_llm_metric("anthropic", "error", time.monotonic() - start)
            raise LLMAuthError(str(e)) from e
        except anthropic.RateLimitError as e:
            _record_llm_metric("anthropic", "error", time.monotonic() - start)
            raise LLMRateLimitError(str(e)) from e
        except anthropic.APIConnectionError as e:
            _record_llm_metric("anthropic", "error", time.monotonic() - start)
            raise LLMConnectionError(str(e)) from e
        except anthropic.APIStatusError as e:
            _record_llm_metric("anthropic", "error", time.monotonic() - start)
            if e.status_code >= 500:
                raise LLMServerError(str(e), status_code=e.status_code) from e
            raise LLMError(str(e)) from e
        except anthropic.APIError as e:
            _record_llm_metric("anthropic", "error", time.monotonic() - start)
            raise LLMError(str(e)) from e

        _record_llm_metric("anthropic", "ok", time.monotonic() - start)
        return _to_response(final)

    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system,                               # str | list[dict]
        messages: list[dict],
        timeout: float | None = None,
        thinking_budget: int = 0,
    ) -> LLMResponse:
        import time

        native_messages = self._convert_vision_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            # If `system` is a plain str (most existing callers), pass it
            # through unchanged so old tests / providers stay compatible.
            # Structured callers (vision pipeline post-upgrade) pass a list
            # of cache blocks directly — those go straight to the API.
            "system": system,
            "messages": native_messages,
        }
        _thinking_kwargs = _build_thinking_kwargs(thinking_budget, max_tokens, model)
        start = time.monotonic()

        try:
            if timeout:
                client = anthropic.Anthropic(timeout=timeout)
            else:
                client = self._client
            kwargs.update(_adapt_thinking_transport(_thinking_kwargs, client.messages.create))
            response = client.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            _record_llm_metric("anthropic", "error", time.monotonic() - start)
            raise LLMAuthError(str(e)) from e
        except anthropic.RateLimitError as e:
            _record_llm_metric("anthropic", "error", time.monotonic() - start)
            raise LLMRateLimitError(str(e)) from e
        except anthropic.APIConnectionError as e:
            _record_llm_metric("anthropic", "error", time.monotonic() - start)
            raise LLMConnectionError(str(e)) from e
        except anthropic.APIStatusError as e:
            _record_llm_metric("anthropic", "error", time.monotonic() - start)
            if e.status_code >= 500:
                raise LLMServerError(str(e), status_code=e.status_code) from e
            raise LLMError(str(e)) from e
        except anthropic.APIError as e:
            _record_llm_metric("anthropic", "error", time.monotonic() - start)
            raise LLMError(str(e)) from e

        _record_llm_metric("anthropic", "ok", time.monotonic() - start)
        return _to_response(response)

    def convert_tools(self, tools: list[dict]) -> list[dict]:
        """Anthropic tools use MCP format natively. Add prompt caching."""
        if not tools:
            return tools
        cached = [dict(t) for t in tools]
        cached[-1] = {**cached[-1], "cache_control": {"type": "ephemeral"}}
        return cached

    def convert_messages(self, messages: list[dict]) -> list[dict]:
        """Convert common types back to Anthropic-native dicts."""
        result = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            if isinstance(content, str):
                result.append(msg)
                continue

            if isinstance(content, list):
                native_content = []
                for block in content:
                    if isinstance(block, TextBlock):
                        native_content.append({"type": "text", "text": block.text})
                    elif isinstance(block, ToolUseBlock):
                        native_content.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                    elif isinstance(block, ToolResultBlock):
                        native_content.append({
                            "type": "tool_result",
                            "tool_use_id": block.tool_use_id,
                            "content": block.content,
                        })
                    elif isinstance(block, ThinkingBlock):
                        # Extended thinking + tool use: the API requires the
                        # prior assistant turn's thinking block (with its
                        # signature) to be replayed verbatim before any
                        # tool_use block from the same turn.
                        if block.signature:
                            native_content.append({
                                "type": "thinking",
                                "thinking": block.thinking,
                                "signature": block.signature,
                            })
                        else:
                            # Drop signature-less ThinkingBlock. The API
                            # rejects unsigned thinking blocks when extended
                            # thinking is active, so replaying would 400.
                            # Warn so the drop is diagnosable instead of
                            # invisible (review action S1).
                            log.warning(
                                "Dropped signature-less ThinkingBlock during "
                                "multi-turn replay (thinking content len=%d). "
                                "Anthropic requires the prior thinking block's "
                                "signature alongside any following tool_use; "
                                "signature-less blocks indicate a legacy code "
                                "path or manually-constructed message. If "
                                "extended thinking is enabled, the next turn "
                                "may 400.",
                                len(block.thinking) if block.thinking else 0,
                            )
                    elif isinstance(block, dict):
                        native_content.append(block)
                    else:
                        native_content.append(block)
                result.append({"role": role, "content": native_content})
            else:
                result.append(msg)

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _convert_vision_messages(self, messages: list[dict]) -> list[dict]:
        """Convert messages containing ImageBlock to Anthropic vision format."""
        result = []
        for msg in messages:
            content = msg.get("content")
            if not isinstance(content, list):
                result.append(msg)
                continue
            native_content = []
            for block in content:
                if isinstance(block, ImageBlock):
                    native_content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": block.media_type,
                            "data": block.data,
                        },
                    })
                elif isinstance(block, TextBlock):
                    native_content.append({"type": "text", "text": block.text})
                elif isinstance(block, dict):
                    native_content.append(block)
                else:
                    native_content.append(block)
            result.append({"role": msg["role"], "content": native_content})
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Models that require the adaptive-thinking shape. Opus 4.7 hard-rejects
# the legacy `{type: enabled, budget_tokens}` with HTTP 400; Opus 4.6 and
# Sonnet 4.6 still accept legacy but adaptive is the forward-compatible
# path, so we route them here too. Older models (Sonnet 4.5, 3.7, etc.)
# stay on the legacy branch — adaptive is unavailable to them.
_ADAPTIVE_THINKING_MODEL_PREFIXES = (
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
)


def _uses_adaptive_thinking(model: str) -> bool:
    name = (model or "").lower()
    return any(name.startswith(p) for p in _ADAPTIVE_THINKING_MODEL_PREFIXES)


def _build_thinking_kwargs(thinking_budget: int, max_tokens: int, model: str) -> dict:
    """Compute the thinking-related kwargs for Anthropic stream/create.

    Returns a dict to merge into the call kwargs. Empty dict means thinking
    is disabled and neither `thinking` nor `output_config` should be sent.

    For adaptive-thinking models (Opus 4.7 / 4.6, Sonnet 4.6):
        {"thinking": {"type": "adaptive", "display": "summarized"},
         "output_config": {"effort": THINKING_EFFORT}}
        Opus 4.7 hard-rejects the legacy shape (HTTP 400); the older two
        accept it but adaptive is the forward-compatible path.

    For legacy models (Sonnet 4.5, 3.7, etc.):
        {"thinking": {"type": "enabled", "budget_tokens": N}} with N
        clamped so `budget_tokens < max_tokens` holds.

    Raises ValueError on the legacy path when max_tokens <= 1024 — the
    clamp floor is 1024, so the API would reject it (review action C3).
    Adaptive path has no max_tokens precondition: the model schedules its
    own reasoning under the umbrella max_tokens ceiling.
    """
    if not thinking_budget or thinking_budget <= 0:
        return {}
    if _uses_adaptive_thinking(model):
        # Lazy import so importlib.reload(agent.config) in other tests
        # doesn't bind us to a stale THINKING_EFFORT value.
        from agent import config as _agent_config

        return {
            "thinking": {"type": "adaptive", "display": "summarized"},
            "output_config": {"effort": _agent_config.THINKING_EFFORT},
        }
    if max_tokens <= 1024:
        raise ValueError(
            f"thinking_budget={thinking_budget} cannot be enabled with "
            f"max_tokens={max_tokens}: Anthropic requires budget_tokens "
            f"< max_tokens, and the budget floor is 1024. Raise "
            f"max_tokens above 1024 or pass thinking_budget=0."
        )
    return {
        "thinking": {
            "type": "enabled",
            "budget_tokens": min(thinking_budget, max(max_tokens - 1024, 1024)),
        }
    }


def _adapt_thinking_transport(thinking_kwargs: dict, target_method) -> dict:
    """Adapt _build_thinking_kwargs' output to the target SDK method's signature.

    Decision logic — WHICH params and WHAT effort — lives in
    _build_thinking_kwargs and is preserved byte-identical. This function only
    adapts HOW those params reach the SDK based on what the bound target
    method actually accepts.

    Per-key, independent of other keys:
      - native parameter name in target signature → keep as top-level kwarg
      - target has **kwargs (VAR_KEYWORD) → accept-anything, keep native
      - otherwise route into extra_body, MERGING with any existing
        extra_body (never overwrite)
      - if the target lacks both the native name AND extra_body, leave the
        kwarg in place so the SDK's TypeError surfaces loudly (don't paper
        over a truly incompatible runtime)

    Wire-side semantics: the anthropic SDK promotes ``extra_body`` keys to
    the top of the JSON request body — payload is identical to the native
    path. This guard exists because anthropic 0.75 (shipping on the deployed
    Python 3.14 user-site) does not declare ``output_config`` on
    Messages.stream / .create, even though the API accepts it. On SDKs that
    DO declare it natively (0.91+ verified), this function returns the
    helper's output unchanged — no behavior change on the modern surface.
    """
    if not thinking_kwargs:
        return thinking_kwargs
    try:
        params = inspect.signature(target_method).parameters
    except (TypeError, ValueError):
        # Couldn't introspect (e.g. a bare MagicMock with no spec). Leave
        # the kwargs alone — the SDK is the source of truth for what it
        # accepts; if it errors, that's a real signal worth surfacing.
        return thinking_kwargs

    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return thinking_kwargs  # target accepts **kwargs → every name passes

    native: dict = {}
    rerouted: dict = {}
    for key, value in thinking_kwargs.items():
        if key in params:
            native[key] = value
        else:
            rerouted[key] = value
    if not rerouted:
        return thinking_kwargs

    if "extra_body" in params:
        existing = native.get("extra_body") or {}
        if not isinstance(existing, dict):
            existing = {}
        merged = dict(existing)
        merged.update(rerouted)
        native["extra_body"] = merged
        log.info(
            "anthropic SDK %s lacks native thinking param(s) %s; routed via extra_body",
            getattr(anthropic, "__version__", "?"),
            sorted(rerouted.keys()),
        )
        return native

    return thinking_kwargs


def _cached_system(system) -> list[dict]:
    """Wrap system prompt for prompt-caching.

    Accepts either:
      - str: wraps the whole prompt in one ephemeral cache block (legacy path
        — preserves the prior behavior for tests and providers that still
        pass plain strings).
      - list[dict]: assumed to already be a list of Anthropic system blocks,
        each optionally carrying its own ``cache_control``. The caller is
        responsible for marking cache breakpoints. We pass it through so the
        agent loop can hit multi-tier caching (e.g. stable rules+tools as
        one cached block, conditional knowledge as a second cached block,
        volatile session context as an uncached tail).
    """
    if isinstance(system, list):
        return system
    return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]


def _to_response(msg) -> LLMResponse:
    """Convert Anthropic Message to LLMResponse.

    Cycle 18: handle thinking blocks. Claude 3.7+ extended-thinking and
    Claude 4 reasoning return content blocks with type=\"thinking\" alongside
    text/tool_use blocks. Without the elif branch below, those blocks were
    silently dropped — causing the model's reasoning to disappear from the
    final response object for any caller using provider.create() (vision
    pipeline, programmatic API).
    """
    content = []
    for block in msg.content:
        if block.type == "text":
            content.append(TextBlock(text=block.text))
        elif block.type == "tool_use":
            content.append(ToolUseBlock(id=block.id, name=block.name, input=block.input))
        elif block.type == "thinking":
            # `block.thinking` holds the reasoning text for Anthropic
            # extended-thinking. `block.signature` is the cryptographic
            # signature the API requires us to replay on the next turn
            # whenever a tool_use block follows the thinking block.
            # Defensive getattr in case the SDK ever renames the field.
            content.append(ThinkingBlock(
                thinking=getattr(block, "thinking", "") or "",
                signature=getattr(block, "signature", None),
            ))
    return LLMResponse(
        content=content,
        stop_reason=msg.stop_reason,
        model=msg.model,
        usage={
            "input_tokens": getattr(msg.usage, "input_tokens", 0),
            "output_tokens": getattr(msg.usage, "output_tokens", 0),
        },
    )
