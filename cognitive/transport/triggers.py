"""Event trigger system for ComfyUI execution events.

Register callbacks that fire when specific execution events occur.
Supports one-shot triggers, filtered dispatch, and webhook delivery.
Thread-safe via ``threading.Lock``.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Callable

from .events import EventType, ExecutionEvent

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trigger dataclass
# ---------------------------------------------------------------------------


@dataclass
class EventTrigger:
    """A registered event trigger.

    Attributes:
        trigger_id: Auto-generated UUID identifying this trigger.
        event_type: Which event type to match.
        callback: Function called with the ExecutionEvent when matched.
        filter: Optional key-value filter on event fields.
        once: If True, auto-remove after first fire.
    """

    trigger_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    event_type: EventType = EventType.UNKNOWN
    callback: Callable[[ExecutionEvent], None] = field(default=lambda e: None)
    filter: dict | None = None
    once: bool = False


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TriggerRegistry:
    """Thread-safe registry of event triggers."""

    def __init__(self) -> None:
        self._triggers: list[EventTrigger] = []
        self._lock = threading.Lock()

    def register(
        self,
        event_type: EventType,
        callback: Callable[[ExecutionEvent], None],
        filter: dict | None = None,
        once: bool = False,
    ) -> str:
        """Register a trigger and return its trigger_id."""
        trigger = EventTrigger(
            event_type=event_type,
            callback=callback,
            filter=filter,
            once=once,
        )
        with self._lock:
            self._triggers.append(trigger)
        return trigger.trigger_id

    def unregister(self, trigger_id: str) -> bool:
        """Remove a trigger by ID. Returns True if found and removed."""
        with self._lock:
            for i, t in enumerate(self._triggers):
                if t.trigger_id == trigger_id:
                    self._triggers.pop(i)
                    return True
        return False

    def dispatch(self, event: ExecutionEvent) -> int:
        """Match event against registered triggers, fire callbacks.

        Returns the count of triggers that fired.  Callback exceptions
        are logged but never propagated.  ``once=True`` triggers are
        removed after firing.
        """
        with self._lock:
            snapshot = list(self._triggers)

        fired = 0
        to_remove: list[str] = []

        for trigger in snapshot:
            if trigger.event_type != event.event_type:
                continue

            # Check optional filter
            if trigger.filter:
                match = True
                for key, expected in trigger.filter.items():
                    actual = getattr(event, key, None)
                    if actual != expected:
                        match = False
                        break
                if not match:
                    continue

            # Fire callback
            try:
                trigger.callback(event)
            except Exception:
                log.exception(
                    "Trigger %s callback raised — suppressed", trigger.trigger_id
                )

            fired += 1

            if trigger.once:
                to_remove.append(trigger.trigger_id)

        # Remove one-shot triggers that fired
        if to_remove:
            with self._lock:
                self._triggers = [
                    t for t in self._triggers if t.trigger_id not in set(to_remove)
                ]

        return fired

    def clear(self) -> None:
        """Remove all triggers."""
        with self._lock:
            self._triggers.clear()

    def count(self) -> int:
        """Return the number of registered triggers."""
        with self._lock:
            return len(self._triggers)


# ---------------------------------------------------------------------------
# Module-level singleton + delegation
# ---------------------------------------------------------------------------

_default_registry = TriggerRegistry()


def register(
    event_type: EventType,
    callback: Callable[[ExecutionEvent], None],
    filter: dict | None = None,
    once: bool = False,
) -> str:
    """Register a trigger on the default registry."""
    return _default_registry.register(event_type, callback, filter=filter, once=once)


def unregister(trigger_id: str) -> bool:
    """Unregister a trigger from the default registry."""
    return _default_registry.unregister(trigger_id)


def dispatch(event: ExecutionEvent) -> int:
    """Dispatch an event through the default registry."""
    return _default_registry.dispatch(event)


def clear() -> None:
    """Clear all triggers in the default registry."""
    _default_registry.clear()


# ---------------------------------------------------------------------------
# Built-in trigger factories
# ---------------------------------------------------------------------------


def on_execution_complete(callback: Callable[[ExecutionEvent], None]) -> str:
    """Register a trigger for EXECUTION_COMPLETE events."""
    return _default_registry.register(EventType.EXECUTION_COMPLETE, callback)


def on_execution_error(callback: Callable[[ExecutionEvent], None]) -> str:
    """Register a trigger for EXECUTION_ERROR events."""
    return _default_registry.register(EventType.EXECUTION_ERROR, callback)


def on_progress(
    callback: Callable[[ExecutionEvent], None],
    node_id: str | None = None,
) -> str:
    """Register a trigger for PROGRESS events, optionally filtered by node_id."""
    filt = {"node_id": node_id} if node_id is not None else None
    return _default_registry.register(EventType.PROGRESS, callback, filter=filt)


# ---------------------------------------------------------------------------
# Webhook support
# ---------------------------------------------------------------------------


def register_webhook(
    url: str,
    event_types: list[EventType],
) -> list[str]:
    """Register triggers that POST JSON to a webhook URL.

    Returns a list of trigger_ids (one per event type).  The POST body
    is a JSON dict with ``event_type``, ``prompt_id``, ``node_id``,
    ``progress``, and ``elapsed`` fields.
    """
    import httpx

    def _make_poster(target_url: str) -> Callable[[ExecutionEvent], None]:
        def _post(event: ExecutionEvent) -> None:
            body = {
                "elapsed": round(event.elapsed_ms / 1000.0, 3),
                "event_type": event.event_type.value,
                "node_id": event.node_id,
                "progress": event.progress_pct if event.progress_max > 0 else None,
                "prompt_id": event.prompt_id,
            }
            try:
                httpx.post(target_url, json=body, timeout=5.0)
            except Exception:
                log.exception("Webhook POST to %s failed — suppressed", target_url)

        return _post

    ids: list[str] = []
    poster = _make_poster(url)
    for et in event_types:
        tid = _default_registry.register(et, poster)
        ids.append(tid)
    return ids
