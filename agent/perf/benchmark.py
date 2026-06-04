"""N-iter benchmark runner with p50/p95/p99/mean/std.

Pure stdlib. Takes any zero-arg callable, runs it warmup+N times, returns
a BenchmarkResult. Designed to satisfy Article I (measurement precedes
mutation) and Article V (profile-or-it-didn't-happen) of the Latency
Constitution.

GC is disabled during the timed loop (toggleable) so pauses don't pollute
samples. Memory peak via resource.ru_maxrss — Linux returns KB, macOS
returns bytes; we normalize to MB.
"""

from __future__ import annotations

import gc
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

try:
    import resource  # POSIX-only; absent on Windows
except ImportError:
    resource = None


def _ru_maxrss_to_mb(ru_maxrss: int) -> float:
    if sys.platform == "darwin":
        return ru_maxrss / (1024 * 1024)
    return ru_maxrss / 1024


def _peak_rss_mb() -> float:
    """Peak resident-set size in MB, cross-platform.

    POSIX: resource.getrusage(ru_maxrss). Windows (no resource module): the
    psapi GetProcessMemoryInfo PeakWorkingSetSize, via ctypes — still pure stdlib.
    """
    if resource is not None:
        return _ru_maxrss_to_mb(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    try:
        import ctypes
        from ctypes import wintypes

        class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        # Declare signatures — without these the 64-bit HANDLE is truncated to int.
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

        counters = _PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
        if psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            return counters.PeakWorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    return 0.0


def _pct(sorted_samples: list[float], pct: float) -> float:
    if not sorted_samples:
        return 0.0
    if len(sorted_samples) == 1:
        return sorted_samples[0]
    rank = (pct / 100.0) * (len(sorted_samples) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_samples) - 1)
    frac = rank - lo
    return sorted_samples[lo] + frac * (sorted_samples[hi] - sorted_samples[lo])


def compute_stats(samples_ns: list[int]) -> dict[str, float]:
    """Compute p50/p95/p99/mean/std/min/max from ns samples; return ms."""
    if not samples_ns:
        return {
            "n_samples": 0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0,
            "mean_ms": 0.0, "std_ms": 0.0, "min_ms": 0.0, "max_ms": 0.0,
            "coefficient_of_variation": 0.0,
        }
    samples_ms = [s / 1_000_000 for s in samples_ns]
    sorted_ms = sorted(samples_ms)
    mean = statistics.mean(samples_ms)
    std = statistics.stdev(samples_ms) if len(samples_ms) > 1 else 0.0
    return {
        "n_samples": len(samples_ms),
        "p50_ms": _pct(sorted_ms, 50),
        "p95_ms": _pct(sorted_ms, 95),
        "p99_ms": _pct(sorted_ms, 99),
        "mean_ms": mean,
        "std_ms": std,
        "min_ms": sorted_ms[0],
        "max_ms": sorted_ms[-1],
        "coefficient_of_variation": (std / mean) if mean > 0 else 0.0,
    }


@dataclass
class BenchmarkResult:
    operation: str
    n_samples: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    std_ms: float
    min_ms: float
    max_ms: float
    coefficient_of_variation: float
    mem_peak_mb: float
    warmup: int
    raw_samples_ns: list[int] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "raw_samples_ns"}
        return d


def run_benchmark(
    fn: Callable[[], object],
    *,
    operation: str,
    n: int = 30,
    warmup: int = 3,
    gc_disable: bool = True,
    keep_raw_samples: bool = False,
) -> BenchmarkResult:
    """Run fn n times after warmup runs; return stats.

    Article VI: caller is responsible for choosing inputs that include
    worst-case scenarios. This primitive measures whatever fn does — it
    does not synthesize inputs.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    if warmup < 0:
        raise ValueError("warmup must be >= 0")

    for _ in range(warmup):
        fn()

    samples_ns: list[int] = []
    mem_before_mb = _peak_rss_mb()

    was_enabled = gc.isenabled()
    if gc_disable:
        gc.collect()
        gc.disable()
    try:
        for _ in range(n):
            t0 = time.perf_counter_ns()
            fn()
            samples_ns.append(time.perf_counter_ns() - t0)
    finally:
        if gc_disable and was_enabled:
            gc.enable()

    mem_after_mb = _peak_rss_mb()
    mem_peak_mb = max(mem_before_mb, mem_after_mb)

    stats = compute_stats(samples_ns)
    return BenchmarkResult(
        operation=operation,
        n_samples=stats["n_samples"],
        p50_ms=stats["p50_ms"],
        p95_ms=stats["p95_ms"],
        p99_ms=stats["p99_ms"],
        mean_ms=stats["mean_ms"],
        std_ms=stats["std_ms"],
        min_ms=stats["min_ms"],
        max_ms=stats["max_ms"],
        coefficient_of_variation=stats["coefficient_of_variation"],
        mem_peak_mb=mem_peak_mb,
        warmup=warmup,
        raw_samples_ns=list(samples_ns) if keep_raw_samples else [],
    )
