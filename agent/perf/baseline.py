"""Hardware fingerprint capture + JSONL baseline records.

Article VIII (hardware honesty): every measurement names the box it ran
on. ``capture_hardware()`` returns a dict + a stable hash; baselines are
appended as one JSONL line per measurement.

The hash is *stable across runs on the same box* — built from CPU model,
GPU model, OS, hostname. This lets compare_baselines() refuse to compare
across hardware (Article VIII enforcement).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent.parent
BASELINES_DIR = PROJECT_DIR / "agent" / "perf" / "baselines"


@dataclass(frozen=True)
class HardwareFingerprint:
    platform: str
    python: str
    cpu_model: str
    cpu_count: int
    gpu: str
    hostname: str
    fingerprint_hash: str

    def to_dict(self) -> dict:
        return asdict(self)


def _read_cpu_model_linux() -> str:
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def _read_cpu_model_darwin() -> str:
    try:
        out = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"], timeout=2, text=True
        )
        return out.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def _read_gpu() -> str:
    if shutil.which("nvidia-smi") is None:
        return "no-nvidia-smi"
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            timeout=3,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        lines = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
        return " | ".join(lines) if lines else "nvidia-smi-empty"
    except (subprocess.SubprocessError, OSError):
        return "nvidia-smi-failed"


def capture_hardware() -> HardwareFingerprint:
    """Capture a hardware fingerprint for the current host.

    Designed to be cheap (< 50 ms) so it can be embedded in every
    measurement record.
    """
    cpu_model = ""
    if sys.platform == "linux":
        cpu_model = _read_cpu_model_linux()
    elif sys.platform == "darwin":
        cpu_model = _read_cpu_model_darwin()
    if not cpu_model:
        cpu_model = platform.processor() or "unknown"

    gpu = _read_gpu()
    plat = platform.platform()
    py = platform.python_version()
    cpu_count = os.cpu_count() or 0
    hostname = socket.gethostname()

    # Stable hash across runs on the same box.
    fp_input = "|".join([plat, cpu_model, str(cpu_count), gpu, hostname])
    fp_hash = hashlib.sha256(fp_input.encode("utf-8")).hexdigest()[:16]

    return HardwareFingerprint(
        platform=plat,
        python=py,
        cpu_model=cpu_model,
        cpu_count=cpu_count,
        gpu=gpu,
        hostname=hostname,
        fingerprint_hash=fp_hash,
    )


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_DIR,
            text=True,
            timeout=2,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


@dataclass
class BaselineRecord:
    operation: str
    tag: str
    ts: str
    hardware: dict
    git_sha: str
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
    notes: str = ""
    extra: dict = field(default_factory=dict)


def record_from_benchmark(
    bench_result,
    *,
    tag: str,
    hardware: HardwareFingerprint | None = None,
    notes: str = "",
    extra: dict | None = None,
) -> BaselineRecord:
    hw = hardware if hardware is not None else capture_hardware()
    return BaselineRecord(
        operation=bench_result.operation,
        tag=tag,
        ts=_dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        hardware=hw.to_dict(),
        git_sha=_git_sha(),
        n_samples=bench_result.n_samples,
        p50_ms=bench_result.p50_ms,
        p95_ms=bench_result.p95_ms,
        p99_ms=bench_result.p99_ms,
        mean_ms=bench_result.mean_ms,
        std_ms=bench_result.std_ms,
        min_ms=bench_result.min_ms,
        max_ms=bench_result.max_ms,
        coefficient_of_variation=bench_result.coefficient_of_variation,
        mem_peak_mb=bench_result.mem_peak_mb,
        warmup=bench_result.warmup,
        notes=notes or bench_result.notes,
        extra=extra or {},
    )


def _safe_filename(operation: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in operation)


def append_baseline(record: BaselineRecord, *, baselines_dir: Path | None = None) -> Path:
    """Append a record as one JSON line to ``<dir>/<safe_operation>.jsonl``.

    Atomic-enough for sequential measurement runs: open with append,
    fsync, close. We don't promise crash-safe concurrent appends — those
    happen at the contention runner's seam, not in real workflows.
    """
    bd = baselines_dir if baselines_dir is not None else BASELINES_DIR
    bd.mkdir(parents=True, exist_ok=True)
    path = bd / f"{_safe_filename(record.operation)}.jsonl"
    line = json.dumps(asdict(record), sort_keys=True, allow_nan=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    return path


def load_baseline(path: Path) -> list[dict]:
    """Read a baseline JSONL file into a list of dicts."""
    if not path.exists():
        return []
    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def compare(before: dict, after: dict) -> dict:
    """Compare two baseline records on the canonical metrics.

    Returns improvement percentages and Article II verdict
    (accept/refine/reject). Negative pct_change means slower; positive
    means faster.

    Article VIII: refuses to compare across different hardware
    fingerprints unless ``before["hardware"]["fingerprint_hash"]`` ==
    after's hash. Cross-hardware comparison is meaningless.
    """
    if before.get("hardware", {}).get("fingerprint_hash") != after.get(
        "hardware", {}
    ).get("fingerprint_hash"):
        return {
            "verdict": "reject",
            "reason": (
                "hardware fingerprint mismatch — measurements taken on "
                "different boxes are not comparable (Article VIII)"
            ),
        }

    def _pct_improve(b: float, a: float) -> float:
        if b == 0:
            return 0.0
        return (b - a) / b * 100.0

    deltas = {
        "p50_pct_change": _pct_improve(before["p50_ms"], after["p50_ms"]),
        "p95_pct_change": _pct_improve(before["p95_ms"], after["p95_ms"]),
        "p99_pct_change": _pct_improve(before["p99_ms"], after["p99_ms"]),
        "mem_ratio": (
            after["mem_peak_mb"] / before["mem_peak_mb"]
            if before["mem_peak_mb"] > 0
            else 1.0
        ),
    }

    # Article II rubric:
    #   - improvement_p50 >= 10%  (primary target)
    #   - no adjacent metric regressed > 2%
    #   - mem_peak <= 1.5 x baseline
    primary_ok = deltas["p50_pct_change"] >= 10.0
    no_regression = (
        deltas["p50_pct_change"] >= -2.0
        and deltas["p95_pct_change"] >= -2.0
        and deltas["p99_pct_change"] >= -2.0
    )
    mem_ok = deltas["mem_ratio"] <= 1.5

    if primary_ok and no_regression and mem_ok:
        verdict, reason = "accept", "improvement >= 10%, no regression, mem within budget"
    elif no_regression and mem_ok:
        verdict, reason = "refine", "no regression but improvement < 10%"
    else:
        reasons = []
        if not no_regression:
            reasons.append("adjacent metric regressed > 2%")
        if not mem_ok:
            reasons.append(f"mem ratio {deltas['mem_ratio']:.2f}x exceeds 1.5x")
        verdict, reason = "reject", "; ".join(reasons) or "below thresholds"

    return {
        "verdict": verdict,
        "reason": reason,
        **deltas,
        "before": {k: before.get(k) for k in (
            "operation", "tag", "p50_ms", "p95_ms", "p99_ms", "mem_peak_mb"
        )},
        "after": {k: after.get(k) for k in (
            "operation", "tag", "p50_ms", "p95_ms", "p99_ms", "mem_peak_mb"
        )},
    }
