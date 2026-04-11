"""Session + correlation propagation helpers for transport entry points.

Both `ui/server/routes.py` (sidebar) and `panel/server/chat.py` (panel)
spawn worker threads or executor tasks to run the agent loop.  Without
these helpers, those workers start with an empty `_conn_session`
ContextVar and an empty thread-local correlation ID, causing two bugs:

1. workflow_patch._get_state() and stage_tools._get_stage() fall back to
   the shared "default" session, so every conversation tramples every
   other conversation's workflow + stage state.

2. set_correlation_id() is per-thread, so log entries from worker threads
   have no correlation ID and can't be grepped end-to-end by conversation.

Both helpers wrap the worker so it sets `_conn_session` AND
`set_correlation_id` to the conversation's id before invoking the target.

Threading helper:
    spawn_with_session(target, args, session_id) -> threading.Thread

Executor helper:
    run_in_executor_with_session(loop, target, *args, session_id) -> Future

Both consume the SAME session_id for the contextvar and the correlation
id.  This is intentional: one ID per conversation, greppable end-to-end.
"""

from __future__ import annotations

import contextvars
import threading
from typing import Any, Callable

from ._conn_ctx import _conn_session
from .logging_config import set_correlation_id


def spawn_with_session(
    target: Callable[..., Any],
    args: tuple,
    session_id: str,
    *,
    daemon: bool = True,
    name: str | None = None,
) -> threading.Thread:
    """threading.Thread wrapper that sets _conn_session + correlation ID.

    The contextvar set inside `runner` mutates the *copied* context, not
    the parent thread's, so multiple concurrent spawns stay isolated.
    """
    def runner() -> Any:
        _conn_session.set(session_id)
        set_correlation_id(session_id)
        return target(*args)

    ctx = contextvars.copy_context()
    return threading.Thread(
        target=ctx.run,
        args=(runner,),
        daemon=daemon,
        name=name,
    )


def run_in_executor_with_session(
    loop: Any,
    target: Callable[..., Any],
    *args: Any,
    session_id: str,
) -> Any:
    """loop.run_in_executor wrapper that sets _conn_session + correlation ID.

    Returns the asyncio Future from `loop.run_in_executor`.  Caller awaits.
    """
    def runner() -> Any:
        _conn_session.set(session_id)
        set_correlation_id(session_id)
        return target(*args)

    ctx = contextvars.copy_context()
    return loop.run_in_executor(None, lambda: ctx.run(runner))
