"""Abstract base class for AI execution-engine adapters.

Each adapter implements the same interface for the execution path:
  queue_prompt   — submit a workflow and get back a job id
  interrupt      — cancel the currently-executing job
  get_history    — fetch completed-job results (one id or recent)
  subscribe_ws   — open a WebSocket-like stream of EngineEvent objects

Adapters handle their own SDK / protocol specifics internally. The
caller works exclusively with the common types defined in _types.py.

Mirrors agent/llm/_base.py so the two abstraction layers stay
symmetric — same factory shape, same ABC discipline, same lazy-import
pattern, same metrics seam.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Iterator

from ._types import EngineEvent


def _record_engine_metric(engine: str, op: str, status: str, elapsed: float) -> None:
    """Record engine call metrics (counter + histogram).

    Uses a lazy import so a metrics failure never breaks engine calls.
    Mirrors agent/llm/_base.py:_record_llm_metric.
    """
    try:
        from ..metrics import engine_call_total, engine_call_duration_seconds

        engine_call_total.inc(engine=engine, op=op, status=status)
        engine_call_duration_seconds.observe(elapsed, engine=engine, op=op)
    except Exception:
        pass


class IAIEngine(ABC):
    """Protocol that every AI execution-engine backend must implement.

    All methods are keyword-only — mirrors agent/llm/LLMProvider.
    """

    @abstractmethod
    def queue_prompt(
        self,
        *,
        workflow: dict,
        client_id: str,
    ) -> str:
        """Submit a workflow for execution and return the job id.

        Args:
            workflow: API-format workflow dict (node_id → {class_type, inputs}).
            client_id: Stable id used to correlate WS events with this job.

        Returns:
            The engine's job id (ComfyUI calls this `prompt_id`).

        Raises:
            EngineValidationError: Engine rejected the workflow.
            EngineConnectionError: Engine unreachable.
            EngineUnavailableError: Circuit breaker open / engine throttled.
            EngineServerError: Engine returned 5xx.
            EngineError: Other engine errors.
        """

    @abstractmethod
    def interrupt(self, *, prompt_id: str | None = None) -> None:
        """Cancel the currently-executing job (or a specific one).

        Args:
            prompt_id: If provided and the backend supports per-job
                cancel, cancel that specific job. None = cancel current.

        Raises:
            EngineConnectionError: Engine unreachable.
            EngineError: Other engine errors.
        """

    @abstractmethod
    def get_history(self, *, prompt_id: str | None = None) -> dict:
        """Fetch job history.

        Args:
            prompt_id: If provided, return only that job's record.
                If None, return recent history (engine-defined window).

        Returns:
            A dict keyed by prompt_id whose values are the engine's
            history entries (status, outputs, etc.). When `prompt_id`
            is provided and not found, returns an empty dict.

        Raises:
            EngineConnectionError: Engine unreachable.
            EngineError: Other engine errors.
        """

    @abstractmethod
    def subscribe_ws(
        self,
        *,
        client_id: str,
    ) -> AbstractContextManager[Iterator[EngineEvent]]:
        """Open a WebSocket-like stream of execution events.

        Returns a context manager. Entering it yields an iterator of
        EngineEvent objects. The context manager owns the underlying
        connection and closes it on exit.

        Adapters that don't support WS should raise EngineError so the
        caller can fall back to polling.

        Args:
            client_id: Stable id used by the engine to scope events.

        Raises:
            EngineConnectionError: Could not open the stream.
            EngineError: Adapter doesn't support WS or other failure.
        """
