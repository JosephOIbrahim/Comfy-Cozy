#!/usr/bin/env python
"""verify_ratchet.py — the single mechanical accept authority for the v2 build.

One gate, run identically by agents, humans, and CI (which recomputes
independently — agent-reported numbers are never trusted). Crucible and CI
execute THIS script from master's copy, never from a candidate branch, so a
branch cannot weaken its own judge (v2 plan section 4.17).

Modes:
  --baseline            measure everything, write tooling/harness/v2/baselines.json
  --check               run all checks vs baselines; exit 0 = accept-eligible
    [--range A..B]      also brightline-scan the commit range (fail-closed)
    [--with-coverage]   include the coverage floor check (slow; epoch-close only)
    [--json PATH]       write the JSON verdict to PATH as well as stdout

Checks (fail fast is NOT used — all checks run so the verdict is complete):
  1. tests      full mocked suite via redirected log (D-10), final summary only:
                passed >= baseline AND failed <= known-flake constant
  2. collected  pytest --collect-only count >= baseline (anti-gaming tripwire)
                + skipped <= baseline skipped (skip-count diff)
  3. ruff       ruff check agent/ tests/ clean
  4. import     cold `import agent.tools` median-of-3 <= baseline * 1.25
                (measured noise band ~13%)
  5. doc_drift  registered tool count == baseline snapshot (no-NEW-drift mode;
                flips to strict generated-docs diff when the doc-truth epoch lands)
  6. coverage   (--with-coverage) total % >= baseline - 0.5, canonical leg only
  7. brightline (--range) scripts/brightline_scan.py --range A..B --quiet.
                Scanner absent (worktree / fresh clone) => NOT_RUN => NEVER accepts.

Baseline decreases are legitimate only via tooling/harness/v2/baseline_deltas.jsonl
rows citing LEDGER IDs, committed in the SAME commit that deletes tests; this
script verifies the arithmetic reconciles exactly (v2 plan section 7).

Stdlib only. Windows-first. Exit codes: 0 accept-eligible, 1 refused, 2 usage/error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2_DIR = ROOT / "tooling" / "harness" / "v2"
BASELINES = V2_DIR / "baselines.json"
DELTAS = V2_DIR / "baseline_deltas.jsonl"
SCANNER = ROOT / "scripts" / "brightline_scan.py"
IMPORT_BUDGET_FACTOR = 1.25
COVERAGE_BAND_PP = 0.5

SUMMARY_RE = re.compile(r"(\d+) (passed|failed|skipped|xfailed|xpassed|error|errors|warnings?)")
FAILED_RE = re.compile(r"^FAILED (\S+)", re.MULTILINE)

# The single tolerated flake, BY NAME. A failure not on this list refuses the
# ratchet even when total counts look fine — count-based allowances let a real
# failure hide behind a flake's budget on a day the flake happens to pass.
KNOWN_FLAKES = ["tests/test_cozy_persistence.py::test_kill_after_flush_resumes_cleanly"]


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, **kw)


def measure_tests(log_path: Path) -> dict:
    """Full mocked suite, redirected log (D-10), parse the final summary line only."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8", errors="replace") as f:
        subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-m", "not integration", "-q", "-rf"],
            cwd=ROOT, stdout=f, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    text = log_path.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    summary = next((ln for ln in reversed(lines) if SUMMARY_RE.search(ln)), "")
    counts = {key: int(num) for num, key in SUMMARY_RE.findall(summary)}
    return {"passed": counts.get("passed", 0), "failed": counts.get("failed", 0),
            "skipped": counts.get("skipped", 0), "summary_line": summary,
            "failed_names": FAILED_RE.findall(text)}


def measure_collected() -> int:
    p = _run([sys.executable, "-m", "pytest", "tests/", "-m", "not integration",
              "-q", "--collect-only"])
    text = p.stdout + p.stderr
    m = (re.search(r"(\d+)/\d+ tests collected", text)
         or re.search(r"(\d+) tests collected", text)
         or re.search(r"collected (\d+)", text))
    return int(m.group(1)) if m else -1


def measure_import_ms(samples: int = 3) -> float:
    times = []
    for _ in range(samples):
        p = _run([sys.executable, "-c",
                  "import time;t=time.perf_counter();import agent.tools;"
                  "print((time.perf_counter()-t)*1000)"])
        try:
            times.append(float(p.stdout.strip().splitlines()[-1]))
        except (ValueError, IndexError):
            return -1.0
    return round(statistics.median(times), 1)


def measure_registry_count() -> int:
    p = _run([sys.executable, "-c",
              "from agent import tools; print(len(tools.ALL_TOOLS))"])
    try:
        return int(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return -1


def check_ruff() -> dict:
    p = _run(["ruff", "check", "agent/", "tests/"])
    return {"ok": p.returncode == 0, "detail": (p.stdout or p.stderr).strip()[-400:]}


def check_brightline(commit_range: str | None) -> dict:
    """Fail-closed: absent scanner => NOT_RUN, which can never accept."""
    if commit_range is None:
        return {"status": "SKIPPED", "ok": True}  # no range requested (e.g. pre-merge unit use)
    if not SCANNER.exists():
        return {"status": "NOT_RUN", "ok": False,
                "detail": "scanner absent (worktree/fresh clone) — accept impossible; "
                          "authoritative scan runs from the main checkout"}
    p = _run([sys.executable, str(SCANNER), "--range", commit_range, "--quiet"])
    return {"status": "CLEAN" if p.returncode == 0 else "FLAGGED", "ok": p.returncode == 0}


def check_coverage(baseline_pct: float | None) -> dict:
    if baseline_pct is None:
        return {"status": "NO_BASELINE", "ok": False}
    r1 = _run([sys.executable, "-m", "coverage", "run", "-m", "pytest",
               "tests/", "-m", "not integration", "-q"])
    if r1.returncode not in (0, 1):  # 1 = test failures (tests check catches those)
        return {"status": "ERROR", "ok": False, "detail": (r1.stderr or r1.stdout)[-400:]}
    r2 = _run([sys.executable, "-m", "coverage", "report"])
    m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%", r2.stdout)
    if not m:
        return {"status": "UNPARSEABLE", "ok": False}
    pct = float(m.group(1))
    return {"status": "OK", "ok": pct >= baseline_pct - COVERAGE_BAND_PP,
            "pct": pct, "floor": baseline_pct - COVERAGE_BAND_PP}


def check_deltas(baselines: dict) -> dict:
    """Every baseline decrease must be explained exactly by LEDGER-cited delta rows."""
    original = baselines.get("original", {})
    if not DELTAS.exists() or not original:
        return {"ok": True, "rows": 0, "note": "no deltas recorded"}
    rows = [json.loads(ln) for ln in DELTAS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    bad = [r for r in rows if not r.get("ledger_id") or not r.get("approved_by")]
    removed = sum(int(r.get("tests_removed", 0)) for r in rows)
    collected_delta = sum(int(r.get("collected_delta", 0)) for r in rows)
    tests_ok = original.get("tests_passed", 0) - removed == baselines.get("tests_passed", 0)
    coll_ok = original.get("collected", 0) - collected_delta == baselines.get("collected", 0)
    return {"ok": not bad and tests_ok and coll_ok, "rows": len(rows),
            "unattributed_rows": len(bad),
            "tests_reconcile": tests_ok, "collected_reconcile": coll_ok}


def git_head() -> str:
    return _run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()


def do_baseline(args) -> int:
    V2_DIR.mkdir(parents=True, exist_ok=True)
    scratch = Path(os.environ.get("TEMP", str(V2_DIR))) / "ratchet_baseline_run.log"
    print("[1/5] full suite (this takes ~3 min)...")
    tests = measure_tests(scratch)
    print(f"      {tests['summary_line']}")
    print("[2/5] collected count...")
    collected = measure_collected()
    print(f"      {collected}")
    print("[3/5] cold-import median-of-3...")
    import_ms = measure_import_ms()
    print(f"      {import_ms} ms")
    print("[4/5] registry count...")
    registry = measure_registry_count()
    print(f"      {registry}")
    coverage_pct = None
    if args.with_coverage:
        print("[5/5] coverage (slow)...")
        cov = check_coverage(baseline_pct=0.0)
        coverage_pct = cov.get("pct")
        print(f"      {coverage_pct}%")
    else:
        print("[5/5] coverage skipped (--with-coverage to include)")
    data = {
        "measured_at": {"commit": git_head(), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        # Floor tolerates the named flakes failing even if they passed on the
        # measurement run — a flake-day run must not refuse a clean build.
        "tests_passed": tests["passed"] - len(KNOWN_FLAKES) + tests["failed"]
                        if tests["failed"] <= len(KNOWN_FLAKES) else tests["passed"],
        "known_flakes": KNOWN_FLAKES,
        "skipped": tests["skipped"],
        "collected": collected,
        "import_ms": import_ms,
        "registry_count": registry,
        "coverage_pct": coverage_pct,
        "coverage_leg": "windows-latest/py3.12",
    }
    data["original"] = {"tests_passed": data["tests_passed"], "collected": data["collected"]}
    BASELINES.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"baselines written: {BASELINES}")
    return 0


def do_check(args) -> int:
    if not BASELINES.exists():
        print(f"ERROR: no baselines at {BASELINES} — run --baseline first", file=sys.stderr)
        return 2
    base = json.loads(BASELINES.read_text(encoding="utf-8"))
    scratch = Path(os.environ.get("TEMP", str(V2_DIR))) / "ratchet_check_run.log"

    tests = measure_tests(scratch)
    known = set(base.get("known_flakes", KNOWN_FLAKES))
    unexpected = [f for f in tests["failed_names"] if f not in known]
    # Name-based: every failure must be a named known flake. Counts alone are
    # gameable (a real failure hides in the flake budget on a good day).
    tests_ok = (tests["passed"] >= base["tests_passed"]
                and not unexpected
                and tests["failed"] <= len(known))
    collected = measure_collected()
    collected_ok = collected >= base["collected"]
    skips_ok = tests["skipped"] <= base.get("skipped", tests["skipped"])
    ruff = check_ruff()
    import_ms = measure_import_ms()
    import_ok = 0 < import_ms <= base["import_ms"] * IMPORT_BUDGET_FACTOR
    registry = measure_registry_count()
    drift_ok = registry == base["registry_count"]
    brightline = check_brightline(args.range)
    coverage = check_coverage(base.get("coverage_pct")) if args.with_coverage \
        else {"status": "SKIPPED", "ok": True}
    deltas = check_deltas(base)

    verdict = {
        "commit": git_head(),
        "checks": {
            "tests": {"ok": tests_ok, "passed": tests["passed"], "failed": tests["failed"],
                      "unexpected_failures": unexpected,
                      "baseline": base["tests_passed"], "summary": tests["summary_line"]},
            "collected": {"ok": collected_ok, "count": collected, "baseline": base["collected"]},
            "skips": {"ok": skips_ok, "count": tests["skipped"], "baseline": base.get("skipped")},
            "ruff": ruff,
            "import_ms": {"ok": import_ok, "median": import_ms,
                          "budget": round(base["import_ms"] * IMPORT_BUDGET_FACTOR, 1)},
            "doc_drift": {"ok": drift_ok, "registry": registry, "baseline": base["registry_count"]},
            "brightline": brightline,
            "coverage": coverage,
            "baseline_deltas": deltas,
        },
    }
    verdict["all_green"] = all(c.get("ok", False) for c in verdict["checks"].values())
    out = json.dumps(verdict, indent=2)
    print(out)
    if args.json:
        Path(args.json).write_text(out + "\n", encoding="utf-8")
    return 0 if verdict["all_green"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--baseline", action="store_true")
    mode.add_argument("--check", action="store_true")
    ap.add_argument("--range", default=None, metavar="A..B")
    ap.add_argument("--with-coverage", action="store_true")
    ap.add_argument("--json", default=None, metavar="PATH")
    args = ap.parse_args()
    return do_baseline(args) if args.baseline else do_check(args)


if __name__ == "__main__":
    sys.exit(main())
