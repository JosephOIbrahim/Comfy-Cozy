"""Session-scoped state container for the ComfyUI Agent.

Replaces all module-level mutable state with per-session containers.
Each MCP connection (or CLI session) gets its own SessionContext with
isolated workflow state, brain config, and circuit breakers.

The SessionRegistry manages lifecycle: create, get, destroy, GC.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .workflow_session import WorkflowSession


@dataclass
class SessionContext:
    """Per-session state container.

    Holds all mutable state that was previously module-level singletons.
    Each field corresponds to a specific module's state that has been
    migrated to session scope.
    """

    session_id: str
    workflow: WorkflowSession = field(default=None)  # type: ignore[assignment]
    intent_state: dict[str, Any] = field(default_factory=dict)
    iteration_state: dict[str, Any] = field(default_factory=dict)
    demo_state: dict[str, Any] = field(default_factory=dict)
    orchestrator_tasks: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)

    def __post_init__(self):
        if self.workflow is None:
            self.workflow = WorkflowSession(self.session_id)

    def touch(self):
        """Update last_activity timestamp."""
        self.last_activity = time.time()

    def age_seconds(self) -> float:
        """Seconds since last activity."""
        return time.time() - self.last_activity


class SessionRegistry:
    """Thread-safe registry of active sessions with GC support."""

    def __init__(self):
        self._sessions: dict[str, SessionContext] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str = "default") -> SessionContext:
        """Get existing session or create a new one. Thread-safe."""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionContext(session_id=session_id)
            ctx = self._sessions[session_id]
            ctx.touch()
            return ctx

    def get(self, session_id: str) -> SessionContext | None:
        """Get existing session or None."""
        with self._lock:
            ctx = self._sessions.get(session_id)
            if ctx is not None:
                ctx.touch()
            return ctx

    def destroy(self, session_id: str) -> bool:
        """Remove a session. Returns True if it existed."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def list_sessions(self) -> list[str]:
        """List all active session IDs."""
        with self._lock:
            return list(self._sessions.keys())

    def gc_stale(self, max_age_seconds: float = 3600.0) -> int:
        """Remove sessions idle longer than max_age_seconds. Returns count removed."""
        now = time.time()
        to_remove = []
        with self._lock:
            for sid, ctx in self._sessions.items():
                if sid == "default":
                    continue  # never GC the default session
                if now - ctx.last_activity > max_age_seconds:
                    to_remove.append(sid)
            for sid in to_remove:
                del self._sessions[sid]
        return len(to_remove)

    @property
    def count(self) -> int:
        """Number of active sessions."""
        with self._lock:
            return len(self._sessions)

    def clear(self) -> None:
        """Remove all sessions. For testing only."""
        with self._lock:
            self._sessions.clear()


# ---------------------------------------------------------------------------
# Global registry singleton (process-level, not session-level)
# ---------------------------------------------------------------------------
_registry = SessionRegistry()


def get_session_context(session_id: str = "default") -> SessionContext:
    """Get or create a session context. Convenience wrapper."""
    return _registry.get_or_create(session_id)


def get_registry() -> SessionRegistry:
    """Get the global session registry."""
    return _registry
