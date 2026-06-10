"""cProfile wrapper. py-spy hook is conditional on the binary being available.

Article V (profile-or-it-didn't-happen): every optimization proposal
that targets a hot path must cite a profile. This module produces .prof
files; ``snakeviz`` or ``flameprof`` are external rendering tools.
"""

from __future__ import annotations

import cProfile
import datetime as _dt
import pstats
import shutil
import subprocess
from io import StringIO
from pathlib import Path
from typing import Callable

PROJECT_DIR = Path(__file__).parent.parent.parent
TRACES_DIR = PROJECT_DIR / "agent" / "perf" / "traces"


def _safe_filename(operation: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in operation)


def profile_call(
    fn: Callable[[], object],
    *,
    operation: str,
    profiler: str = "cprofile",
    output_dir: Path | None = None,
    top_n: int = 20,
) -> dict:
    """Profile a single call and emit a .prof dump + a top-N text summary.

    Returns: { trace_path, summary_text, top_n_functions: [...] }.

    profiler='cprofile' is always available. profiler='py-spy' requires
    the py-spy binary on PATH; if missing, returns a structured error
    rather than crashing.
    """
    out = output_dir if output_dir is not None else TRACES_DIR
    out.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    base = _safe_filename(operation)

    if profiler == "cprofile":
        trace_path = out / f"{base}_{stamp}.prof"
        pr = cProfile.Profile()
        pr.enable()
        try:
            fn()
        finally:
            pr.disable()
        pr.dump_stats(str(trace_path))

        buf = StringIO()
        stats = pstats.Stats(pr, stream=buf).sort_stats("cumulative")
        stats.print_stats(top_n)
        summary = buf.getvalue()

        top: list[dict] = []
        for func, (cc, nc, tt, ct, _callers) in sorted(
            stats.stats.items(), key=lambda kv: -kv[1][3]
        )[:top_n]:
            file_, line, name = func
            top.append({
                "function": name,
                "file": file_,
                "line": line,
                "cumulative_s": ct,
                "total_s": tt,
                "ncalls": nc,
            })

        return {
            "profiler": "cprofile",
            "operation": operation,
            "trace_path": str(trace_path),
            "summary_text": summary,
            "top_n_functions": top,
        }

    if profiler == "py-spy":
        if shutil.which("py-spy") is None:
            return {
                "error": (
                    "py-spy not on PATH. Install with `pip install py-spy` "
                    "or fall back to profiler='cprofile'."
                ),
                "operation": operation,
            }
        trace_path = out / f"{base}_{stamp}.svg"
        # py-spy record requires sampling a running process. For a single
        # call we use record --output --duration with a small duration —
        # the caller's fn() runs in the foreground while py-spy samples
        # this process. Not as clean as cProfile for short calls; cprofile
        # is the recommended default.
        try:
            import os as _os
            proc = subprocess.Popen([
                "py-spy", "record",
                "--pid", str(_os.getpid()),
                "--output", str(trace_path),
                "--duration", "1",
                "--format", "flamegraph",
            ])
            fn()
            proc.wait(timeout=10)
        except (subprocess.SubprocessError, OSError) as e:
            return {"error": f"py-spy failed: {e}", "operation": operation}
        return {
            "profiler": "py-spy",
            "operation": operation,
            "trace_path": str(trace_path),
            "summary_text": "py-spy flamegraph generated; open the SVG to inspect.",
            "top_n_functions": [],
        }

    return {"error": f"unknown profiler: {profiler}", "operation": operation}
