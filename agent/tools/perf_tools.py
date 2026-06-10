"""Latency-measurement MCP tools.

Exposes the agent/perf/ library through the standard TOOLS+handle()
dispatch pattern so every Cozy specialist can request benchmarks,
profiles, comparisons, and full canonical-set baselines.

Constitutional context: .claude/LATENCY_CONSTITUTION.md.
"""

from __future__ import annotations

from pathlib import Path

from ._util import to_json

TOOLS: list[dict] = [
    {
        "name": "benchmark_tool",
        "description": (
            "Time an MCP tool call N times and return p50/p95/p99/mean/std "
            "+ peak memory. Use this BEFORE proposing any latency optimization "
            "(Article I of the Latency Constitution: measurement precedes "
            "mutation). The result is also appended to "
            "agent/perf/baselines/<op>.jsonl with a hardware fingerprint."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Tool to benchmark, e.g. 'get_node_info'.",
                },
                "input": {
                    "type": "object",
                    "description": "Tool arguments dict (same shape as a normal call).",
                },
                "n": {
                    "type": "integer",
                    "description": "Sample count (default 30, must be >= 1).",
                },
                "warmup": {
                    "type": "integer",
                    "description": "Untimed warmup iterations (default 3).",
                },
                "tag": {
                    "type": "string",
                    "description": (
                        "Baseline tag — e.g. 'baseline', 'after', 'smoke'. "
                        "Recorded with the measurement."
                    ),
                },
                "record": {
                    "type": "boolean",
                    "description": (
                        "Append a record to baselines/. Default true. Set "
                        "false for exploratory runs you don't want logged."
                    ),
                },
            },
            "required": ["name", "input"],
        },
    },
    {
        "name": "profile_tool",
        "description": (
            "Generate a cProfile trace for one call of an MCP tool. Returns "
            "the trace path + a top-N functions-by-cumulative-time summary. "
            "Use to identify hot paths before proposing an optimization "
            "(Article V: profile-or-it-didn't-happen)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "input": {"type": "object"},
                "profiler": {
                    "type": "string",
                    "enum": ["cprofile", "py-spy"],
                    "description": "Profiler backend (default 'cprofile').",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of hottest functions to return (default 20).",
                },
            },
            "required": ["name", "input"],
        },
    },
    {
        "name": "compare_baselines",
        "description": (
            "Diff two baseline JSONL records on p50/p95/p99/mem; return "
            "Article II verdict (accept | refine | reject) with reasons. "
            "Article VIII: refuses to compare across different hardware "
            "fingerprints."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "before_path": {
                    "type": "string",
                    "description": "Path to baseline JSONL file (before).",
                },
                "after_path": {
                    "type": "string",
                    "description": "Path to baseline JSONL file (after).",
                },
                "before_tag": {
                    "type": "string",
                    "description": (
                        "Filter the 'before' file to records matching this tag "
                        "(default 'baseline')."
                    ),
                },
                "after_tag": {
                    "type": "string",
                    "description": (
                        "Filter the 'after' file to records matching this tag "
                        "(default 'after')."
                    ),
                },
            },
            "required": ["before_path", "after_path"],
        },
    },
    {
        "name": "latency_baseline",
        "description": (
            "Run the canonical operation set (PRD §5.3) and append baselines. "
            "profile='quick' runs only stdlib-bound operations; profile='full' "
            "also runs ComfyUI-dependent operations (skipped if ComfyUI offline)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "profile": {
                    "type": "string",
                    "enum": ["quick", "full"],
                    "description": "Operation set to baseline (default 'quick').",
                },
                "tag": {
                    "type": "string",
                    "description": "Tag for every record in this run (default 'baseline').",
                },
                "n": {
                    "type": "integer",
                    "description": "Samples per operation (default 30).",
                },
                "warmup": {
                    "type": "integer",
                    "description": "Warmup iters per operation (default 3).",
                },
            },
            "required": [],
        },
    },
]


def _make_call_for_tool(name: str, tool_input: dict):
    """Wrap a tool dispatch as a zero-arg callable for the benchmark loop."""
    # Lazy import: tool_handle is in this same package, but we need to
    # avoid the circular import that happens if perf_tools is imported
    # during agent.tools.__init__'s module-collection loop.
    def call():
        from agent.tools import handle as tool_handle
        return tool_handle(name, dict(tool_input))
    return call


def _handle_benchmark_tool(inp: dict) -> str:
    from ..perf.benchmark import run_benchmark
    from ..perf.baseline import append_baseline, record_from_benchmark

    name = inp["name"]
    tool_input = inp.get("input", {}) or {}
    n = int(inp.get("n", 30))
    warmup = int(inp.get("warmup", 3))
    tag = inp.get("tag", "exploratory")
    record = bool(inp.get("record", True))

    fn = _make_call_for_tool(name, tool_input)
    op_label = f"tool.{name}"
    result = run_benchmark(fn, operation=op_label, n=n, warmup=warmup)

    payload: dict = {
        "operation": op_label,
        "tag": tag,
        "n_samples": result.n_samples,
        "p50_ms": result.p50_ms,
        "p95_ms": result.p95_ms,
        "p99_ms": result.p99_ms,
        "mean_ms": result.mean_ms,
        "std_ms": result.std_ms,
        "min_ms": result.min_ms,
        "max_ms": result.max_ms,
        "coefficient_of_variation": result.coefficient_of_variation,
        "mem_peak_mb": result.mem_peak_mb,
        "warmup": result.warmup,
    }

    if record:
        rec = record_from_benchmark(result, tag=tag)
        path = append_baseline(rec)
        payload["baseline_path"] = str(path)

    # Surface noisy benchmarks so the caller can rerun with larger N.
    if result.coefficient_of_variation > 0.3:
        payload["warning"] = (
            f"high variance (CV={result.coefficient_of_variation:.2f}) — "
            f"consider rerunning with larger n"
        )

    return to_json(payload)


def _handle_profile_tool(inp: dict) -> str:
    from ..perf.profile import profile_call

    name = inp["name"]
    tool_input = inp.get("input", {}) or {}
    profiler = inp.get("profiler", "cprofile")
    top_n = int(inp.get("top_n", 20))

    fn = _make_call_for_tool(name, tool_input)
    result = profile_call(fn, operation=f"tool.{name}", profiler=profiler, top_n=top_n)
    return to_json(result)


def _handle_compare_baselines(inp: dict) -> str:
    from ..perf.baseline import compare, load_baseline

    before_path = Path(inp["before_path"])
    after_path = Path(inp["after_path"])
    before_tag = inp.get("before_tag", "baseline")
    after_tag = inp.get("after_tag", "after")

    before_records = load_baseline(before_path)
    after_records = load_baseline(after_path)

    def _last_with_tag(recs: list[dict], tag: str) -> dict | None:
        for r in reversed(recs):
            if r.get("tag") == tag:
                return r
        return recs[-1] if recs else None

    before = _last_with_tag(before_records, before_tag)
    after = _last_with_tag(after_records, after_tag)
    if before is None or after is None:
        return to_json({
            "error": (
                f"missing records — before={before is not None}, "
                f"after={after is not None}"
            ),
        })

    return to_json(compare(before, after))


def _handle_latency_baseline(inp: dict) -> str:
    from ..perf.benchmark import run_benchmark
    from ..perf.baseline import append_baseline, record_from_benchmark
    from ..perf.canonical import get_canonical

    profile = inp.get("profile", "quick")
    tag = inp.get("tag", "baseline")
    n = int(inp.get("n", 30))
    warmup = int(inp.get("warmup", 3))

    ops = get_canonical(profile)
    results: list[dict] = []
    skipped: list[str] = []
    for op_name, fn in ops:
        if fn is None:
            skipped.append(op_name)
            continue
        bench = run_benchmark(fn, operation=op_name, n=n, warmup=warmup)
        rec = record_from_benchmark(bench, tag=tag)
        path = append_baseline(rec)
        results.append({
            "operation": op_name,
            "p50_ms": bench.p50_ms,
            "p95_ms": bench.p95_ms,
            "p99_ms": bench.p99_ms,
            "mem_peak_mb": bench.mem_peak_mb,
            "baseline_path": str(path),
        })

    return to_json({
        "profile": profile,
        "tag": tag,
        "n": n,
        "warmup": warmup,
        "results": results,
        "skipped": skipped,
    })


def handle(name: str, tool_input: dict) -> str:
    """Dispatch a perf tool call."""
    try:
        if name == "benchmark_tool":
            return _handle_benchmark_tool(tool_input)
        if name == "profile_tool":
            return _handle_profile_tool(tool_input)
        if name == "compare_baselines":
            return _handle_compare_baselines(tool_input)
        if name == "latency_baseline":
            return _handle_latency_baseline(tool_input)
        return to_json({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return to_json({"error": f"{type(e).__name__}: {e}"})
