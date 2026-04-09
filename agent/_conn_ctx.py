"""Per-connection MCP session name — zero external dependencies.

Each MCP connection (stdio or SSE) gets a unique ``conn_XXXXXXXX`` session
name assigned on first tool call.  The name is stored in a ContextVar so it
propagates through asyncio ``await`` chains *and* into ``loop.run_in_executor``
threads (Python copies the current context when scheduling executor tasks).

Usage
-----
    from agent._conn_ctx import current_conn_session

    name = current_conn_session()   # "conn_3f2a1b4c" — stable for this connection
"""

import contextvars

_conn_session: contextvars.ContextVar[str] = contextvars.ContextVar("_conn_session")


def current_conn_session() -> str:
    """Return this connection's session name.

    Returns the ContextVar value when inside an MCP tool handler (set
    explicitly by mcp_server._handler before dispatching to the thread).
    Returns ``"default"`` in all other contexts — CLI, tests, startup —
    so legacy code that accesses ``get_session("default")`` continues
    to work unchanged.
    """
    try:
        return _conn_session.get()
    except LookupError:
        return "default"
