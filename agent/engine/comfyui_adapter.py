"""ComfyUI adapter for the IAIEngine abstraction.

Concentrates every direct ComfyUI execution-path call (POST /prompt,
POST /interrupt, GET /history, WS /ws) behind the common IAIEngine
interface. The agent/tools/comfy_execute.py module delegates its
execution operations through this adapter; tests mock the adapter
itself rather than scattering httpx patches across call sites.

Introspection endpoints (object_info, queue, system_stats, userdata)
remain in their existing tool modules — they're discovery operations,
not execution, and live outside the engine surface by design.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from contextlib import contextmanager
from typing import Iterator

import httpx

from ._base import IAIEngine
from ._types import (
    EngineConnectionError,
    EngineError,
    EngineEvent,
    EngineServerError,
    EngineUnavailableError,
    EngineValidationError,
)

log = logging.getLogger(__name__)

# Optional websockets import at module level so tests can patch
# `agent.engine.comfyui_adapter.websockets.sync.client.connect` directly.
# Matches the pattern in agent/tools/comfy_execute.py.
try:
    import websockets
    import websockets.sync.client
    _HAS_WS = True
except ImportError:
    _HAS_WS = False
    log.debug(
        "websockets package not installed; engine WS subscription will raise EngineError "
        "(pip install websockets for real-time progress)."
    )

# Sanitise prompt_id before URL interpolation — UUIDs are 36 chars; cap at 128.
# Matches the existing tool-layer guard so we can't widen attack surface here.
_PROMPT_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]+$")
_PROMPT_ID_MAX = 128


def _validate_prompt_id(prompt_id: str) -> None:
    if not isinstance(prompt_id, str) or not prompt_id:
        raise EngineError("prompt_id must be a non-empty string.")
    if len(prompt_id) > _PROMPT_ID_MAX:
        raise EngineError(f"prompt_id too long (max {_PROMPT_ID_MAX} characters).")
    if not _PROMPT_ID_RE.match(prompt_id):
        raise EngineError(
            "prompt_id must contain only alphanumeric characters, hyphens, or underscores."
        )


class ComfyUIAdapter(IAIEngine):
    """IAIEngine adapter backed by a running ComfyUI server.

    Resolves the server URL from agent.config at construction time so
    swapping COMFYUI_URL via env requires a fresh adapter (matches the
    pattern of agent.tools.comfy_api._get_client).
    """

    def __init__(self, url: str | None = None) -> None:
        # Lazy-import config so an import-time failure in config doesn't
        # break the engine module being imported.
        from ..config import COMFYUI_HOST, COMFYUI_PORT, COMFYUI_URL

        if url is None:
            self._url = COMFYUI_URL
            self._host = COMFYUI_HOST
            self._port = COMFYUI_PORT
        else:
            # Pool-created endpoint adapter (hardening 3.5). Keeps its own
            # per-endpoint circuit breaker; the default adapter stays on the
            # shared "comfyui" breaker so gate health wiring and test resets
            # see exactly what they always did.
            from urllib.parse import urlparse
            self._url = url.rstrip("/")
            parsed = urlparse(self._url)
            self._host = parsed.hostname or self._url
            self._port = parsed.port or 8188
        self._breaker_url = None if url is None else self._url
        # H2 (ledger C-R4): one pooled client per adapter instead of a fresh
        # httpx.Client per call — the per-call TLS/TCP setup cost ~170-230 ms
        # on every 1 s status poll.
        self._client_lock = threading.Lock()
        self._client: httpx.Client | None = None

    def _http(self) -> httpx.Client:
        """Shared pooled client (lazy, thread-safe)."""
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    self._client = httpx.Client(
                        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                    )
        return self._client

    def close(self) -> None:
        """Close the pooled client (called by the test-reset hook)."""
        with self._client_lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    # ------------------------------------------------------------------
    # IAIEngine — execution operations
    # ------------------------------------------------------------------

    def queue_prompt(self, *, workflow: dict, client_id: str) -> str:
        """POST /prompt — submit a workflow, return prompt_id.

        Raises EngineValidationError if ComfyUI rejects the workflow
        (formatted node_errors when available), EngineConnectionError
        on transport failure, EngineUnavailableError when the circuit
        breaker is open.
        """
        breaker = self._breaker()
        if not breaker.allow_request():
            raise EngineUnavailableError(
                f"ComfyUI has been unreachable. Waiting {breaker.recovery_timeout:.0f}s "
                f"before retrying."
            )

        payload = {"prompt": workflow, "client_id": client_id}
        try:
            resp = self._http().post(
                f"{self._url}/prompt",
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()
            breaker.record_success()
            data = resp.json()
            prompt_id = data.get("prompt_id")
            if not prompt_id:
                raise EngineError(
                    "ComfyUI accepted the workflow but didn't return a job ID. "
                    "It may be overloaded — try again in a few seconds."
                )
            return prompt_id
        except httpx.ConnectError as e:
            breaker.record_failure()
            raise EngineConnectionError(
                f"ComfyUI not reachable at {self._url}. Is it running?"
            ) from e
        except httpx.HTTPStatusError as e:
            # ComfyUI returns validation errors in the response body.
            try:
                err_data = e.response.json()
            except Exception:
                raise EngineServerError(
                    f"HTTP {e.response.status_code}: {e.response.text[:300]}",
                    status_code=e.response.status_code,
                ) from e
            node_errors = err_data.get("node_errors") or {}
            if node_errors:
                msgs = []
                for nid, nerr in sorted(node_errors.items()):
                    class_type = nerr.get("class_type", "?")
                    for exc in nerr.get("errors", []):
                        msgs.append(
                            f"Node [{nid}] {class_type}: {exc.get('message', str(exc))}"
                        )
                raise EngineValidationError(
                    "Validation errors:\n" + "\n".join(msgs),
                    node_errors=node_errors,
                ) from e
            raise EngineError(err_data.get("error", str(err_data))) from e

    def interrupt(self, *, prompt_id: str | None = None) -> None:
        """POST /interrupt — cancel the currently-executing job.

        ComfyUI's /interrupt endpoint cancels the *current* execution
        and ignores any body, so `prompt_id` is recorded but not sent.
        Provided in the signature so future backends with per-job
        cancel can use the same shape.
        """
        try:
            resp = self._http().post(f"{self._url}/interrupt", timeout=10.0)
            resp.raise_for_status()
        except httpx.ConnectError as e:
            raise EngineConnectionError(
                f"ComfyUI not reachable at {self._url}."
            ) from e
        except httpx.HTTPStatusError as e:
            raise EngineServerError(
                f"HTTP {e.response.status_code}: {e.response.text[:300]}",
                status_code=e.response.status_code,
            ) from e

    def get_history(self, *, prompt_id: str | None = None) -> dict:
        """GET /history or /history/{prompt_id}.

        When prompt_id is provided, returns {prompt_id: entry} or {} if
        not yet known to the server. When None, returns the recent
        history dict as ComfyUI reports it.
        """
        breaker = self._breaker()
        if not breaker.allow_request():
            raise EngineUnavailableError(
                f"ComfyUI has been unreachable. Waiting {breaker.recovery_timeout:.0f}s "
                f"before retrying."
            )
        if prompt_id is not None:
            _validate_prompt_id(prompt_id)
            path = f"/history/{prompt_id}"
        else:
            path = "/history"
        try:
            resp = self._http().get(f"{self._url}{path}", timeout=10.0)
            resp.raise_for_status()
            breaker.record_success()
            try:
                return resp.json()
            except ValueError as e:
                raise EngineConnectionError(
                    f"ComfyUI returned non-JSON on {path}: {e}"
                ) from e
        except httpx.ConnectError as e:
            breaker.record_failure()
            raise EngineConnectionError(str(e)) from e
        except httpx.TimeoutException as e:
            breaker.record_failure()
            raise EngineConnectionError(str(e)) from e
        except httpx.HTTPStatusError as e:
            raise EngineServerError(
                f"HTTP {e.response.status_code}: {e.response.text[:300]}",
                status_code=e.response.status_code,
            ) from e

    @contextmanager
    def subscribe_ws(self, *, client_id: str) -> Iterator[Iterator[EngineEvent]]:
        """WS /ws?clientId={client_id} — yields a generator of EngineEvent.

        Raises EngineError when the websockets package is missing so
        callers can fall back to polling.
        """
        if not _HAS_WS:
            raise EngineError(
                "websockets package not installed; install with `pip install websockets`."
            )

        scheme = "wss" if self._url.startswith("https") else "ws"
        ws_url = f"{scheme}://{self._host}:{self._port}/ws?clientId={client_id}"

        try:
            ws_cm = websockets.sync.client.connect(ws_url, close_timeout=5, open_timeout=10)
        except Exception as e:
            raise EngineConnectionError(f"WebSocket connect failed: {e}") from e

        with ws_cm as ws:
            ws.recv_bufsize = 16 * 1024 * 1024  # 16MB for preview images

            def _events() -> Iterator[EngineEvent]:
                while True:
                    try:
                        raw = ws.recv(timeout=2.0)
                    except TimeoutError:
                        # Surface as a sentinel event so callers can
                        # check deadlines and keep going.
                        yield EngineEvent(type="__timeout__", data={}, raw={})
                        continue
                    if isinstance(raw, bytes):
                        # Preview images — skip.
                        continue
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    yield EngineEvent(
                        type=msg.get("type", ""),
                        data=msg.get("data", {}) or {},
                        raw=msg,
                    )

            yield _events()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _breaker(self):
        """Resolve the ComfyUI circuit breaker lazily.

        Lazy import keeps the engine module import-cheap and matches
        the pattern in agent/tools/comfy_execute.py (which imports the
        breaker per-call from inside its helpers). Default adapters share
        the "comfyui" breaker; pool-created ones are keyed per endpoint.
        """
        from ..circuit_breaker import COMFYUI_BREAKER
        return COMFYUI_BREAKER(self._breaker_url)
