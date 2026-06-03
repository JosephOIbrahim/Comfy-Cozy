"""Concurrent-call contention measurement.

Article IV (Latency Constitution): every optimization to shared state
must pass a 4-thread × 1000-call contention benchmark with < 2x
degradation vs. single-threaded p50.

Pure stdlib (threading + queue). Returns per-thread stats and an
aggregate degradation factor.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from .benchmark import _pct, compute_stats


@dataclass
class ContentionResult:
    operation: str
    threads: int
    calls_per_thread: int
    single_p50_ms: float
    concurrent_p50_ms: float
    concurrent_p95_ms: float
    concurrent_p99_ms: float
    degradation_factor: float
    per_thread_p50_ms: list[float] = field(default_factory=list)
    errors: int = 0
    verdict: str = "unknown"
    reason: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def run_contention(
    fn: Callable[[], object],
    *,
    operation: str,
    threads: int = 4,
    calls_per_thread: int = 1000,
    warmup: int = 3,
    single_thread_samples: int = 30,
) -> ContentionResult:
    """Run fn under N-thread contention; compare to single-threaded p50.

    Article IV verdict:
      degradation_factor = concurrent_p50 / single_p50
      < 2.0  : accept
      2.0-3.0: refine
      > 3.0  : reject
    """
    if threads < 1:
        raise ValueError("threads must be >= 1")
    if calls_per_thread < 1:
        raise ValueError("calls_per_thread must be >= 1")

    for _ in range(warmup):
        fn()

    single_samples_ns: list[int] = []
    for _ in range(single_thread_samples):
        t0 = time.perf_counter_ns()
        fn()
        single_samples_ns.append(time.perf_counter_ns() - t0)
    single_stats = compute_stats(single_samples_ns)
    single_p50 = single_stats["p50_ms"]

    per_thread_samples: list[list[int]] = [[] for _ in range(threads)]
    errors_counter = [0]
    errors_lock = threading.Lock()
    start_barrier = threading.Barrier(threads)

    def worker(idx: int) -> None:
        start_barrier.wait()
        local = per_thread_samples[idx]
        for _ in range(calls_per_thread):
            t0 = time.perf_counter_ns()
            try:
                fn()
                local.append(time.perf_counter_ns() - t0)
            except Exception:
                with errors_lock:
                    errors_counter[0] += 1

    ts = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    all_samples = [s for thread_samples in per_thread_samples for s in thread_samples]
    conc_stats = compute_stats(all_samples)
    per_thread_p50: list[float] = []
    for ts_ns in per_thread_samples:
        if not ts_ns:
            per_thread_p50.append(0.0)
            continue
        sorted_ms = sorted(s / 1_000_000 for s in ts_ns)
        per_thread_p50.append(_pct(sorted_ms, 50))

    degradation = (conc_stats["p50_ms"] / single_p50) if single_p50 > 0 else float("inf")
    if degradation < 2.0:
        verdict, reason = "accept", f"degradation {degradation:.2f}x within Article IV budget"
    elif degradation < 3.0:
        verdict, reason = "refine", f"degradation {degradation:.2f}x — refine before shipping"
    else:
        verdict, reason = "reject", f"degradation {degradation:.2f}x exceeds 3x limit"

    return ContentionResult(
        operation=operation,
        threads=threads,
        calls_per_thread=calls_per_thread,
        single_p50_ms=single_p50,
        concurrent_p50_ms=conc_stats["p50_ms"],
        concurrent_p95_ms=conc_stats["p95_ms"],
        concurrent_p99_ms=conc_stats["p99_ms"],
        degradation_factor=degradation,
        per_thread_p50_ms=per_thread_p50,
        errors=errors_counter[0],
        verdict=verdict,
        reason=reason,
    )
