"""Multi-provider LLM abstraction layer.

Usage:
    from agent.llm import get_provider
    provider = get_provider()  # Uses LLM_PROVIDER env var
    response = provider.stream(model=..., ...)

Supported providers: anthropic, openai, gemini, ollama, nvidia, custom.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from ._base import LLMProvider
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

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

__all__ = [
    "get_provider",
    "clear_provider_cache",
    "DEFAULT_MODELS",
    "LLMProvider",
    "LLMResponse",
    "TextBlock",
    "ThinkingBlock",
    "ToolUseBlock",
    "ToolResultBlock",
    "ImageBlock",
    "LLMError",
    "LLMRateLimitError",
    "LLMConnectionError",
    "LLMServerError",
    "LLMAuthError",
]

# Default models per provider. Single-sourced from agent.config — this
# module re-exports the canonical table so callers that import it from
# the LLM layer (e.g. tests, downstream tooling) hit the same dict.
from ..config import _DEFAULT_AGENT_MODELS as DEFAULT_MODELS

_provider_cache: dict[str, LLMProvider] = {}
_provider_lock = threading.Lock()


def get_provider(name: str | None = None) -> LLMProvider:
    """Get an LLM provider instance (cached per name).

    Thread-safe: double-checked locking prevents duplicate instantiation
    when two threads call get_provider() simultaneously on first access.

    Args:
        name: Provider name. If None, reads LLM_PROVIDER env var (default: "anthropic").

    Returns:
        An LLMProvider instance ready to use.

    Raises:
        ValueError: Unknown provider name.
        LLMAuthError: Missing API key for the requested provider.
    """
    if name is None:
        from ..config import LLM_PROVIDER
        name = LLM_PROVIDER

    name = name.lower().strip()

    if name in _provider_cache:
        return _provider_cache[name]

    with _provider_lock:
        if name in _provider_cache:  # Re-check after acquiring lock
            return _provider_cache[name]
        provider = _create_provider(name)
        _provider_cache[name] = provider
        log.info("LLM provider initialized: %s", name)
        return provider


def _create_provider(name: str) -> LLMProvider:
    """Lazy-import and instantiate a provider."""
    if name == "anthropic":
        from ._anthropic import AnthropicProvider
        return AnthropicProvider()

    elif name == "openai":
        from ._openai import OpenAIProvider
        return OpenAIProvider()

    elif name == "gemini":
        from ._gemini import GeminiProvider
        return GeminiProvider()

    elif name == "ollama":
        from ._ollama import OllamaProvider
        return OllamaProvider()

    elif name == "nvidia":
        from ._nvidia import NvidiaProvider
        return NvidiaProvider()

    elif name == "custom":
        from ._custom import CustomProvider
        return CustomProvider()

    else:
        raise ValueError(
            f"Unknown LLM provider: {name!r}. "
            f"Supported: anthropic, openai, gemini, ollama, nvidia, custom"
        )


def clear_provider_cache(name: str | None = None) -> None:
    """Drop cached provider instance(s).

    Required after a runtime provider swap: get_provider() caches per provider
    NAME and never self-invalidates on env/config change, so a swap must clear
    the cache for the new provider to be constructed on the next call.
    """
    with _provider_lock:
        if name is None:
            _provider_cache.clear()
        else:
            _provider_cache.pop(name.lower().strip(), None)
