"""SEE verb engine — terminal telemetry for a workflow run.

WP-SEE v1 (HARNESS_CLI_20260714.md): a step-time Braille sparkline plus a
*static* VRAM snapshot from one ``/system_stats`` poll. VRAM-over-time and
loss series are **cut, not faked** — no live source carries them.

Two feeds into one collector:

* **Live** — :meth:`StepTimeCollector.install` subscribes to the existing
  ``TriggerRegistry`` singleton as a second consumer (mirroring the
  diagnosis subscriber: idempotent, observe-only, never intercepts). The
  execute loop already dispatches every parsed WebSocket event through the
  registry, so PROGRESS events arrive with no execute-path changes.
* **Post-hoc** — :meth:`StepTimeCollector.ingest_progress_log` replays the
  ``progress_log`` list that error/timeout result dicts already carry
  (``{event, node_id, value, max, pct, elapsed_s}`` entries).

Timing note: ``ExecutionEvent.elapsed_ms`` mixes epoch and monotonic clocks
(documented at ``agent/diagnosis/diagnosis.py``) and is never trusted here.
Live samples are timed by deltas of ``event.timestamp`` — all from the same
clock, so differences are sound even though absolutes are not.

Rendering is delegated to the pure helpers in ``agent/_render.py``. The
``/system_stats`` poll is isolated in :func:`vram_snapshot` and injected
into :func:`render_run_summary` so tests (and offline runs) can replace it.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from agent._render import braille_sparkline, format_step_times, vram_bar

log = logging.getLogger(__name__)

_BYTES_PER_GB = 1024.0**3


# ---------------------------------------------------------------------------
# Samples + pure series math
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StepSample:
    """One observed sampler-progress tick.

    Attributes:
        node_id: Node emitting the progress event ("" when unknown).
        value: Current step number (1-based from ComfyUI).
        max_value: Total steps for this node.
        at_s: Seconds on a single self-consistent clock (deltas are what
            matter; the absolute origin is arbitrary).
    """

    node_id: str
    value: int
    max_value: int
    at_s: float


def _durations(samples: list[StepSample]) -> list[float]:
    """Per-step elapsed seconds from consecutive same-node samples.

    The first tick of each node (or of a value reset, e.g. a second sampler
    pass on the same node) seeds the baseline and yields no duration.
    Negative deltas are clamped to 0 — never propagate clock jitter.
    """
    out: list[float] = []
    for prev, curr in zip(samples, samples[1:]):
        if curr.node_id == prev.node_id and curr.value > prev.value:
            out.append(max(0.0, curr.at_s - prev.at_s))
    return out


def step_durations_from_progress_log(entries: list[dict]) -> list[float]:
    """Pure: per-step durations from a ``progress_log`` list.

    Consumes the ``{"event": "progress", "node_id", "value", "max",
    "elapsed_s"}`` entries built by the execute loop (other events are
    ignored). Malformed entries are skipped, never raised on.
    """
    samples: list[StepSample] = []
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("event") != "progress":
            continue
        try:
            samples.append(
                StepSample(
                    node_id=str(entry.get("node_id") or ""),
                    value=int(entry.get("value", 0)),
                    max_value=int(entry.get("max", 0)),
                    at_s=float(entry.get("elapsed_s", 0.0)),
                )
            )
        except (TypeError, ValueError):
            continue
    return _durations(samples)


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------


class StepTimeCollector:
    """Accumulates per-step timing during a run. Thread-safe, observe-only.

    Hand :meth:`on_event` to the TriggerRegistry (via :meth:`install`) and
    read :meth:`step_durations` after the run. The collector never blocks,
    never raises out of its callback, and never alters execution — it is a
    second consumer in the sanctioned diagnosis-subscriber pattern.

    Args:
        prompt_id: When set, live events carrying a *different* prompt_id
            are ignored. Events without one (ComfyUI progress data often
            omits it) are always accepted.
    """

    def __init__(self, prompt_id: str | None = None) -> None:
        self._prompt_id = prompt_id
        self._samples: list[StepSample] = []
        self._origin: float | None = None
        self._lock = threading.Lock()
        self._trigger_id: str | None = None

    # -- accumulation --------------------------------------------------

    @property
    def sample_count(self) -> int:
        """Number of progress ticks recorded so far."""
        with self._lock:
            return len(self._samples)

    def add_sample(self, node_id: str, value: int, max_value: int, at_s: float) -> None:
        """Record one progress tick (pure data path — used by both feeds)."""
        with self._lock:
            self._samples.append(
                StepSample(node_id=node_id, value=value, max_value=max_value, at_s=at_s)
            )

    def on_event(self, event: Any) -> None:
        """TriggerRegistry callback: record PROGRESS events, ignore the rest.

        Duck-typed against ``cognitive.transport.events.ExecutionEvent`` so
        this module imports cleanly without the cognitive package. Timing
        uses ``event.timestamp`` deltas against the first event seen — the
        event's own ``elapsed_ms`` mixes clocks and is deliberately unused.
        Failures are swallowed: telemetry must never disturb a render.
        """
        try:
            kind = getattr(getattr(event, "event_type", None), "value", None)
            if kind != "progress":
                return
            event_pid = getattr(event, "prompt_id", "") or ""
            if self._prompt_id and event_pid and event_pid != self._prompt_id:
                return
            ts = getattr(event, "timestamp", None)
            if not isinstance(ts, (int, float)):
                ts = time.time()
            with self._lock:
                if self._origin is None:
                    self._origin = float(ts)
                self._samples.append(
                    StepSample(
                        node_id=str(getattr(event, "node_id", "") or ""),
                        value=int(getattr(event, "progress_value", 0)),
                        max_value=int(getattr(event, "progress_max", 0)),
                        at_s=float(ts) - self._origin,
                    )
                )
        except Exception:
            log.debug("SEE collector sample dropped — suppressed", exc_info=True)

    def ingest_progress_log(self, entries: list[dict]) -> int:
        """Replay a ``progress_log`` list (error/timeout result dicts carry one).

        Returns the number of samples added. Safe to call on anything —
        malformed input adds nothing.
        """
        if not isinstance(entries, list):
            return 0
        added = 0
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("event") != "progress":
                continue
            try:
                self.add_sample(
                    node_id=str(entry.get("node_id") or ""),
                    value=int(entry.get("value", 0)),
                    max_value=int(entry.get("max", 0)),
                    at_s=float(entry.get("elapsed_s", 0.0)),
                )
                added += 1
            except (TypeError, ValueError):
                continue
        return added

    # -- registry lifecycle (mirrors diagnosis.install_subscriber) -----

    def install(self) -> bool:
        """Idempotently subscribe to PROGRESS events on the shared registry.

        Registers on the existing ``TriggerRegistry`` singleton — a second
        consumer, not a second registry, and zero execute-path changes.
        Returns True when subscribed (or already subscribed); False when
        the cognitive transport is unavailable (fail-soft, run continues
        without live telemetry).
        """
        if self._trigger_id is not None:
            return True
        try:
            from cognitive.transport.triggers import on_progress

            self._trigger_id = on_progress(self.on_event)
        except Exception:
            log.debug("SEE subscriber not installed — suppressed", exc_info=True)
            return False
        return True

    def uninstall(self) -> None:
        """Remove the subscription. Idempotent; safe if never installed."""
        if self._trigger_id is None:
            return
        try:
            from cognitive.transport.triggers import unregister

            unregister(self._trigger_id)
        except Exception:
            log.debug("SEE subscriber removal failed — suppressed", exc_info=True)
        self._trigger_id = None

    # -- series --------------------------------------------------------

    def step_durations(self) -> list[float]:
        """Per-step elapsed seconds (see :func:`_durations` for the rule)."""
        with self._lock:
            samples = list(self._samples)
        return _durations(samples)


# ---------------------------------------------------------------------------
# VRAM snapshot (the one poll — isolated so tests replace it)
# ---------------------------------------------------------------------------


def vram_snapshot() -> dict | None:
    """One ``/system_stats`` poll -> ``{"name", "used_gb", "total_gb"}``.

    Static snapshot only — the design cut VRAM-over-time (no live source).
    Routes through the ``comfy_api`` tool handler (loopback only). Returns
    None when ComfyUI is unreachable or reports no VRAM-bearing device;
    callers render a friendly line instead of an error.
    """
    try:
        from agent.tools.comfy_api import handle as _api_handle

        raw = json.loads(_api_handle("get_system_stats", {}))
    except Exception:
        return None
    if not isinstance(raw, dict) or "error" in raw:
        return None
    for device in raw.get("devices") or []:
        if not isinstance(device, dict):
            continue
        total = device.get("vram_total")
        free = device.get("vram_free")
        if isinstance(total, (int, float)) and total > 0 and isinstance(free, (int, float)):
            used_gb = max(0.0, (float(total) - float(free)) / _BYTES_PER_GB)
            return {
                "name": str(device.get("name") or "GPU"),
                "total_gb": round(float(total) / _BYTES_PER_GB, 2),
                "used_gb": round(used_gb, 2),
            }
    return None


# ---------------------------------------------------------------------------
# Summary rendering
# ---------------------------------------------------------------------------


def _format_node_slice(node_timing: list[dict], top_nodes: int) -> str:
    """ "KSampler 12.4s · VAEDecode 1.1s" from the success dict's timing list."""
    parts: list[str] = []
    for entry in node_timing[:top_nodes]:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("class_type") or entry.get("node_id") or "node")
        try:
            dur = float(entry.get("duration_s", 0.0))
        except (TypeError, ValueError):
            dur = 0.0
        parts.append(f"{name} {dur:.1f}s")
    return " · ".join(parts)


def render_run_summary(
    collector: StepTimeCollector | None,
    result: dict | None = None,
    *,
    poll_stats: Callable[[], dict | None] = vram_snapshot,
    width: int = 24,
    top_nodes: int = 3,
) -> str:
    """Compose the post-run telemetry block for the terminal.

    Lines (each omitted only when its source is honestly absent):

    * ``run``   — status + total time from the execute result dict.
    * ``steps`` — Braille sparkline of per-step durations + the timing
      summary line; falls back to the result's ``progress_log`` when the
      collector saw nothing (error/timeout dicts carry one).
    * ``nodes`` — top slice of the success dict's ``node_timing``.
    * ``vram``  — usage bar from one ``poll_stats()`` snapshot; a plain
      "unavailable" line when ComfyUI cannot be reached.

    Deterministic for fixed inputs: the only side effect is the injected
    ``poll_stats`` call, and every formatting path is pure.
    """
    result = result if isinstance(result, dict) else {}
    lines: list[str] = []

    status = result.get("status")
    if status:
        header = f"run    {status}"
        total_s = result.get("total_time_s")
        if isinstance(total_s, (int, float)):
            header += f" · {float(total_s):.1f} s"
        lines.append(header)

    durations = collector.step_durations() if collector is not None else []
    if not durations:
        durations = step_durations_from_progress_log(result.get("progress_log") or [])
    if durations:
        spark = braille_sparkline(durations, width=width)
        lines.append(f"steps  {spark}  {format_step_times(durations)}")
    else:
        lines.append("steps  (no step telemetry captured)")

    node_timing = result.get("node_timing")
    if isinstance(node_timing, list) and node_timing:
        node_line = _format_node_slice(node_timing, top_nodes)
        if node_line:
            lines.append(f"nodes  {node_line}")

    try:
        snapshot = poll_stats()
    except Exception:
        log.debug("VRAM poll failed — degrading to unavailable", exc_info=True)
        snapshot = None
    if snapshot and isinstance(snapshot, dict):
        bar = vram_bar(float(snapshot.get("used_gb", 0.0)), float(snapshot.get("total_gb", 0.0)))
        name = snapshot.get("name")
        lines.append(f"vram   {bar} — {name}" if name else f"vram   {bar}")
    else:
        lines.append("vram   unavailable — ComfyUI not reachable")

    return "\n".join(lines)
