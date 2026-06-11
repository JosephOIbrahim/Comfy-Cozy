"""EndpointPool — health-checked failover across ComfyUI workers (hardening 3.5).

A floor runs several ComfyUI instances; ``COMFYUI_HOST:PORT`` assumed one.
The pool is itself an ``IAIEngine``: each call goes to the first endpoint
that serves it, failing over on connection/availability errors. There is
no separate health prober — every endpoint adapter carries its own
per-endpoint circuit breaker, and the breaker's OPEN → HALF_OPEN →
CLOSED cycle (recovery_timeout re-probes automatically) IS the health
check: an OPEN endpoint fast-fails with ``EngineUnavailableError`` and
the pool simply tries the next one.

Affinity: a queued prompt lives on ONE worker, so the pool remembers
which endpoint served ``queue_prompt`` (keyed by both prompt_id and
client_id, bounded FIFO) and routes ``get_history`` / ``subscribe_ws`` /
``interrupt`` for that job back to the same endpoint.

Aggregate signal: the legacy shared "comfyui" breaker is still what the
pre-dispatch gate reads for system health. The pool mirrors into it —
success on any endpoint records success; ALL endpoints failing records a
failure — so gate health keeps meaning "can we reach ComfyUI at all".
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from contextlib import AbstractContextManager
from typing import Iterator

from ._base import IAIEngine
from ._types import EngineConnectionError, EngineEvent, EngineUnavailableError
from .comfyui_adapter import ComfyUIAdapter

log = logging.getLogger(__name__)

_AFFINITY_MAX = 256


def _normalize_endpoint(raw: str) -> str:
    """Accept "host:port" or a full URL; return a scheme-qualified URL."""
    e = raw.strip().rstrip("/")
    if not e.startswith(("http://", "https://")):
        e = f"http://{e}"
    return e


class EndpointPool(IAIEngine):
    """Failover façade over one ``ComfyUIAdapter`` per configured endpoint."""

    def __init__(self, endpoints: list[str]) -> None:
        urls = [_normalize_endpoint(e) for e in endpoints]
        if not urls:
            raise ValueError("EndpointPool needs at least one endpoint.")
        self._adapters: list[ComfyUIAdapter] = [ComfyUIAdapter(url=u) for u in urls]
        self._affinity: OrderedDict[str, ComfyUIAdapter] = OrderedDict()
        self._affinity_lock = threading.Lock()

    # ------------------------------------------------------------------
    # affinity bookkeeping
    # ------------------------------------------------------------------

    def _remember(self, key: str | None, adapter: ComfyUIAdapter) -> None:
        if not key:
            return
        with self._affinity_lock:
            self._affinity[key] = adapter
            self._affinity.move_to_end(key)
            while len(self._affinity) > _AFFINITY_MAX:
                self._affinity.popitem(last=False)

    def _recall(self, key: str | None) -> ComfyUIAdapter | None:
        if not key:
            return None
        with self._affinity_lock:
            return self._affinity.get(key)

    # ------------------------------------------------------------------
    # failover core
    # ------------------------------------------------------------------

    def _try_each(self, op, *, pinned: ComfyUIAdapter | None = None):
        """Run ``op(adapter)`` on the pinned endpoint, else each in order.

        A pinned (affinity) endpoint is authoritative for its job — a
        prompt queued on worker A does not exist on worker B, so affinity
        misses fail rather than silently asking the wrong worker.
        """
        from ..circuit_breaker import COMFYUI_BREAKER

        if pinned is not None:
            result = op(pinned)
            COMFYUI_BREAKER().record_success()
            return result

        last_err: Exception | None = None
        for adapter in self._adapters:
            try:
                result = op(adapter)
            except (EngineConnectionError, EngineUnavailableError) as e:
                # The adapter's own per-endpoint breaker already recorded
                # the failure; move on to the next worker.
                log.warning("Endpoint %s unavailable, failing over: %s", adapter._url, e)
                last_err = e
                continue
            COMFYUI_BREAKER().record_success()
            return result
        COMFYUI_BREAKER().record_failure()
        raise last_err or EngineUnavailableError(
            "No healthy ComfyUI endpoint in the pool."
        )

    # ------------------------------------------------------------------
    # IAIEngine
    # ------------------------------------------------------------------

    def queue_prompt(self, *, workflow: dict, client_id: str) -> str:
        chosen: dict = {}

        def op(adapter: ComfyUIAdapter) -> str:
            pid = adapter.queue_prompt(workflow=workflow, client_id=client_id)
            chosen["adapter"] = adapter
            return pid

        prompt_id = self._try_each(op)
        self._remember(prompt_id, chosen["adapter"])
        self._remember(client_id, chosen["adapter"])
        return prompt_id

    def interrupt(self, *, prompt_id: str | None = None) -> None:
        pinned = self._recall(prompt_id)
        return self._try_each(lambda a: a.interrupt(prompt_id=prompt_id), pinned=pinned)

    def get_history(self, *, prompt_id: str | None = None) -> dict:
        pinned = self._recall(prompt_id)
        return self._try_each(lambda a: a.get_history(prompt_id=prompt_id), pinned=pinned)

    def subscribe_ws(
        self, *, client_id: str
    ) -> AbstractContextManager[Iterator[EngineEvent]]:
        pinned = self._recall(client_id)
        return self._try_each(lambda a: a.subscribe_ws(client_id=client_id), pinned=pinned)

    def close(self) -> None:
        """Close every endpoint adapter's pooled client (test-reset hook)."""
        for adapter in self._adapters:
            try:
                adapter.close()
            except Exception:
                pass
