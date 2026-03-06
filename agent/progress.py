"""Progress reporting for long-running MCP tool calls.

Bridges synchronous tool handlers back to the async MCP event loop
to send ``notifications/progress`` messages.  MCP clients (Claude Code,
Claude Desktop) render these as a progress indicator so artists know
what's happening during execution, discovery, and other slow operations.

Usage inside a synchronous handler::

    def _handle_execute(tool_input, progress=None):
        progress = progress or ProgressReporter.noop()
        progress.report(0, 100, "Queuing workflow...")
        ...
        progress.report(50, 100, "KSampler — step 10/20")
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

log = logging.getLogger(__name__)


class ProgressCallback(Protocol):
    """Minimal interface that handlers depend on."""

    def report(
        self,
        progress: float,
        total: float | None = None,
        message: str | None = None,
    ) -> None: ...


class ProgressReporter:
    """Bridge from sync handler threads to async MCP progress notifications.

    Created in ``mcp_server.call_tool`` and passed into synchronous handlers
    that run inside ``loop.run_in_executor``.  Calls
    ``asyncio.run_coroutine_threadsafe`` to send notifications without
    blocking the handler thread.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        session: object,  # mcp ServerSession
        progress_token: str | int | None,
        request_id: str | int | None = None,
    ):
        self._loop = loop
        self._session = session
        self._token = progress_token
        self._request_id = request_id

    # ------------------------------------------------------------------

    def report(
        self,
        progress: float,
        total: float | None = None,
        message: str | None = None,
    ) -> None:
        """Send a progress notification (fire-and-forget).

        Safe to call from any thread.  If there is no progress token
        (client didn't request progress) this is a silent no-op.
        """
        if self._token is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self._session.send_progress_notification(
                    progress_token=self._token,
                    progress=progress,
                    total=total,
                    message=message,
                ),
                self._loop,
            )
        except Exception:
            # Progress is best-effort — never let it crash the handler
            log.debug("Progress notification failed", exc_info=True)

    # ------------------------------------------------------------------

    @staticmethod
    def noop() -> "ProgressCallback":
        """Return a silent reporter for non-MCP contexts (CLI, tests)."""
        return _NoopReporter()


class _NoopReporter:
    """Drop-in replacement that silently discards progress reports."""

    def report(
        self,
        progress: float,
        total: float | None = None,
        message: str | None = None,
    ) -> None:
        pass
