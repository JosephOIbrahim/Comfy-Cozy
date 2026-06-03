"""Performance measurement library for Comfy-Cozy.

Standalone — does NOT import agent.tools. Provides primitives for:
  - benchmark.py    : N-iter timing with p50/p95/p99/mean/std
  - profile.py      : cProfile wrapper (py-spy hook)
  - baseline.py     : hardware fingerprint + JSONL append
  - contention.py   : concurrent-call degradation measurement

Governed by .claude/LATENCY_CONSTITUTION.md.
"""

from .benchmark import BenchmarkResult, compute_stats, run_benchmark
from .baseline import (
    BASELINES_DIR,
    HardwareFingerprint,
    append_baseline,
    capture_hardware,
    load_baseline,
)
from .contention import ContentionResult, run_contention
from .profile import profile_call

__all__ = [
    "BASELINES_DIR",
    "BenchmarkResult",
    "ContentionResult",
    "HardwareFingerprint",
    "append_baseline",
    "capture_hardware",
    "compute_stats",
    "load_baseline",
    "profile_call",
    "run_benchmark",
    "run_contention",
]
