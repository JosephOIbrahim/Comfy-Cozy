"""Common types for the AI execution-engine abstraction.

These types decouple the agent's execution path from any specific
backend (ComfyUI today; future backends — e.g. a remote queue, a
mock engine for tests, an alternate generator — re-use the same
interface).

Mirrors the structure of agent/llm/_types.py so the two abstraction
layers stay symmetric.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Engine events — provider-agnostic shape for streamed messages
# ---------------------------------------------------------------------------

@dataclass
class EngineEvent:
    """A single event surfaced by an engine's WS subscription.

    `type` is the event family ("status", "execution_start", "executing",
    "progress", "execution_error", ...). `data` is the parsed payload.
    `raw` carries the original message dict so callers that need the
    full envelope (e.g. cognitive.transport.triggers.dispatch) don't
    have to reconstruct it.
    """
    type: str
    data: dict
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Error hierarchy — adapters catch native errors and re-raise as these
# ---------------------------------------------------------------------------

class EngineError(Exception):
    """Base error for all engine adapter errors."""


class EngineConnectionError(EngineError):
    """Network / connection failure — transient, retry may help."""


class EngineTimeoutError(EngineError):
    """Operation exceeded its deadline."""


class EngineValidationError(EngineError):
    """Engine rejected the request (e.g. ComfyUI node_errors)."""

    def __init__(self, message: str, node_errors: dict | None = None):
        super().__init__(message)
        self.node_errors = node_errors or {}


class EngineServerError(EngineError):
    """Server-side error (5xx) — transient, retry may help."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class EngineUnavailableError(EngineError):
    """Engine is temporarily unavailable (e.g. circuit breaker open)."""
