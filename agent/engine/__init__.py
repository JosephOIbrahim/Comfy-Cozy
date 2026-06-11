"""AI execution-engine abstraction.

Usage:
    from agent.engine import get_engine
    engine = get_engine()                          # uses AI_ENGINE env var
    prompt_id = engine.queue_prompt(workflow=wf, client_id=cid)

Supported engines: comfyui.

Mirrors the shape of agent/llm/__init__.py so the two abstraction
layers stay symmetric (factory + cache + lazy SDK import).
"""

from __future__ import annotations

import logging
import os
import threading

from ._base import IAIEngine
from ._types import (
    EngineConnectionError,
    EngineError,
    EngineEvent,
    EngineServerError,
    EngineTimeoutError,
    EngineUnavailableError,
    EngineValidationError,
)

log = logging.getLogger(__name__)

__all__ = [
    "get_engine",
    "IAIEngine",
    "EngineEvent",
    "EngineError",
    "EngineConnectionError",
    "EngineTimeoutError",
    "EngineValidationError",
    "EngineServerError",
    "EngineUnavailableError",
]

_DEFAULT_ENGINE = "comfyui"

_engine_cache: dict[str, IAIEngine] = {}
_engine_lock = threading.Lock()


def get_engine(name: str | None = None) -> IAIEngine:
    """Get an engine adapter instance (cached per name).

    Thread-safe: double-checked locking prevents duplicate instantiation
    when two threads call get_engine() simultaneously on first access.

    Args:
        name: Engine name. If None, reads AI_ENGINE env var (default: "comfyui").

    Returns:
        An IAIEngine instance ready to use.

    Raises:
        ValueError: Unknown engine name.
    """
    if name is None:
        name = os.getenv("AI_ENGINE", _DEFAULT_ENGINE)

    name = name.lower().strip()

    if name in _engine_cache:
        return _engine_cache[name]

    with _engine_lock:
        if name in _engine_cache:  # Re-check after acquiring lock
            return _engine_cache[name]
        engine = _create_engine(name)
        _engine_cache[name] = engine
        log.info("AI engine initialized: %s", name)
        return engine


def _create_engine(name: str) -> IAIEngine:
    """Lazy-import and instantiate an engine adapter."""
    if name == "comfyui":
        from .comfyui_adapter import ComfyUIAdapter
        return ComfyUIAdapter()

    raise ValueError(
        f"Unknown AI engine: {name!r}. Supported: comfyui"
    )


def _reset_cache_for_tests() -> None:
    """Test-only: clear the engine cache.

    Test fixtures can call this to force a fresh adapter (e.g. when
    swapping env vars or mocking the adapter class). Closes each cached
    adapter's pooled HTTP client (H2) so resets don't leak sockets.
    """
    with _engine_lock:
        for _eng in _engine_cache.values():
            _close = getattr(_eng, "close", None)
            if callable(_close):
                try:
                    _close()
                except Exception:
                    pass
        _engine_cache.clear()
