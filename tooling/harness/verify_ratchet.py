#!/usr/bin/env python
"""verify_ratchet.py — the single mechanical accept authority for the v2 build.

One gate, run identically by agents, humans, and CI (which recomputes
independently — agent-reported numbers are never trusted).

AUTHORITY MODEL (post skeptic round 1, LEDGER V2-E0B-R1):
- The judging CODE and the THRESHOLDS both come from master, never the candidate:
  --check reads baselines via `git show origin/master:tooling/harness/v2/baselines.json`.
  The branch-local file is compared byte-wise; a mismatch must be explained exactly
  by same-branch baseline_deltas.jsonl rows or the verdict refuses.
  Bootstrap (master has no baselines yet): local file is used and the verdict
  carries baselines_source="branch-bootstrap" so reviewers see it.
- known_flakes authority is the IN-SCRIPT constant only; the copy in baselines.json
  is documentation. A branch cannot add its broken test to the flake list.
- Test counts come from pytest's --junitxml file (machine-written, uuid-named in
  scratch), not from parsing stdout — in-repo code cannot inject a crafted
  summary line. The stdout log is kept for humans (D-10).
- pytest ERRORS refuse acceptance (errors == 0 required; error node ids reported).
- Disclosure scan: --check derives origin/master..HEAD when --range is absent;
  scanner absent or range underivable => NOT_RUN => never accepts. CI, where the
  local-only scanner legitimately cannot exist, runs `--brightline skip`: the
  verdict then carries disclosure_certified=false — CI green does NOT certify
  disclosure; the main-checkout scan + fail-closed hooks do (ORCHESTRATOR §8).

Modes:
  --baseline [--with-coverage] [--reset-original]   measure + write baselines.json
        --reset-original re-seeds the delta-reconciliation anchor and is a
        Joe-reviewed act (harness-maintenance); without it, 'original' is preserved.
  --check [--range A..B] [--with-coverage] [--brightline auto|skip] [--json PATH]

Exit codes: 0 accept-eligible, 1 refused, 2 usage/error.  Stdlib only. Windows-first.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import statistics
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V2_DIR = ROOT / "tooling" / "harness" / "v2"
BASELINES = V2_DIR / "baselines.json"
BASELINES_REPO_PATH = "tooling/harness/v2/baselines.json"
DELTAS = V2_DIR / "baseline_deltas.jsonl"
SCANNER = ROOT / "scripts" / "brightline_scan.py"
IMPORT_BUDGET_FACTOR = 1.25
COVERAGE_BAND_PP = 0.5

# The single tolerated flake, BY FULL PYTEST NODE ID. Authority lives HERE (the
# script runs from master's copy) — never in baselines.json, which a candidate
# branch controls. --baseline asserts each id actually collects, so a renamed
# or moved flake fails loudly instead of silently disabling the tolerance.
KNOWN_FLAKES = [
    "tests/test_cozy_persistence.py::TestCrashResume::test_kill_after_flush_resumes_cleanly",
]


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, **kw)


def _scratch() -> Path:
    p = Path(os.environ.get("TEMP", str(V2_DIR))) / "ratchet"
    p.mkdir(parents=True, exist_ok=True)
    return p


def measure_tests(tag: str) -> dict:
    """Full mocked suite. Counts/names come from the junit XML pytest itself
    writes (uuid path in scratch — not injectable by in-repo stdout tricks);
    the redirected stdout log is kept for humans (D-10)."""
    run_id = uuid.uuid4().hex[:12]
    junit = _scratch() / f"junit-{tag}-{run_id}.xml"
    log = _scratch() / f"run-{tag}-{run_id}.log"
    with open(log, "w", encoding="utf-8", errors="replace") as f:
        subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-m", "not integration",
             "-q", "-rfE", f"--junitxml={junit}"],
            cwd=ROOT, stdout=f, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
    if not junit.exists():
        return {"ok": False, "reason": f"junit file not written (see {log})"}
    suite = ET.parse(junit).getroot()
    if suite.tag == "testsuites":
        suite = suite.find("testsuite")
    total = int(suite.get("tests", -1))
    failures = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))
    bad_names = []
    for case in suite.iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            cls = (case.get("classname") or "").replace(".", "/")
            # classname is dotted module(.Class); reconstruct the node id shape
            name = case.get("name") or ""
            bad_names.append(f"{cls}::{name}" if cls else name)
    return {"ok": True, "total": total, "passed": total - failures - errors - skipped,
            "failed": failures, "errors": errors, "skipped": skipped,
            "bad_names": bad_names, "log": str(log)}


def _flake_match(bad_name: str) -> bool:
    """junit classnames lose the .py suffix and use dots — match on the stable
    tail (Class::test) plus module stem so both spellings of a node id hit."""
    for flake in KNOWN_FLAKES:
        parts = flake.split("::")
        stem = Path(parts[0]).stem
        tail = "::".join(parts[1:])
        if tail and tail in bad_name and stem in bad_name:
            return True
    return False


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
    try:
        p = _run([sys.executable, "-m", "ruff", "check", "agent/", "tests/"])
    except FileNotFoundError:
        return {"ok": False, "detail": "ruff not importable in this interpreter"}
    return {"ok": p.returncode == 0, "detail": (p.stdout or p.stderr).strip()[-400:]}


def derive_range() -> str | None:
    p = _run(["git", "rev-parse", "--verify", "origin/master"])
    if p.returncode != 0:
        return None
    return "origin/master..HEAD"


def check_brightline(commit_range: str | None, mode: str) -> dict:
    """Fail-closed by default. mode='skip' is for CI where the local-only
    scanner cannot exist — the verdict then refuses to certify disclosure."""
    if mode == "skip":
        return {"status": "EXCLUDED_BY_FLAG", "ok": True, "certifies": False,
                "detail": "CI mode: disclosure is certified by the main-checkout "
                          "scan + fail-closed hooks, never by this run"}
    rng = commit_range or derive_range()
    if rng is None:
        return {"status": "NOT_RUN", "ok": False, "certifies": False,
                "detail": "no --range and origin/master not resolvable"}
    if not SCANNER.exists():
        return {"status": "NOT_RUN", "ok": False, "certifies": False,
                "detail": "scanner absent (worktree/fresh clone) — accept impossible; "
                          "authoritative scan runs from the main checkout"}
    p = _run([sys.executable, str(SCANNER), "--range", rng, "--quiet"])
    return {"status": "CLEAN" if p.returncode == 0 else "FLAGGED",
            "ok": p.returncode == 0, "certifies": p.returncode == 0, "range": rng}


def check_coverage(baseline_pct: float | None) -> dict:
    r1 = _run([sys.executable, "-m", "coverage", "run", "-m", "pytest",
               "tests/", "-m", "not integration", "-q"])
    if r1.returncode not in (0, 1):
        return {"status": "ERROR", "ok": False, "detail": (r1.stderr or r1.stdout)[-400:]}
    r2 = _run([sys.executable, "-m", "coverage", "report"])
    m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+(?:\.\d+)?)%", r2.stdout)
    if not m:
        return {"status": "UNPARSEABLE", "ok": False}
    pct = float(m.group(1))
    if baseline_pct is None:
        return {"status": "NO_BASELINE_MEASURED", "ok": False, "pct": pct,
                "detail": "no coverage floor pinned — run --baseline --with-coverage"}
    return {"status": "OK", "ok": pct >= baseline_pct - COVERAGE_BAND_PP,
            "pct": pct, "floor": baseline_pct - COVERAGE_BAND_PP}


def load_master_baselines() -> tuple[dict | None, str]:
    """Thresholds come from master, never the candidate (authority model)."""
    p = _run(["git", "show", f"origin/master:{BASELINES_REPO_PATH}"])
    if p.returncode == 0 and p.stdout.strip():
        try:
            return json.loads(p.stdout), "origin/master"
        except json.JSONDecodeError:
            return None, "corrupt-on-master"
    return None, "absent-on-master"


def check_baseline_integrity(master_base: dict | None) -> dict:
    """The branch-local baselines.json must match master's byte-for-byte unless
    same-branch delta rows explain the difference exactly."""
    if master_base is None:
        return {"status": "BOOTSTRAP", "ok": True,
                "detail": "master has no baselines yet; local file is provisional"}
    local = json.loads(BASELINES.read_text(encoding="utf-8")) if BASELINES.exists() else None
    if local == master_base:
        return {"status": "MATCHES_MASTER", "ok": True}
    rows = []
    if DELTAS.exists():
        rows = [json.loads(ln) for ln in DELTAS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    bad = [r for r in rows if not r.get("ledger_id") or not r.get("approved_by")]
    removed = sum(int(r.get("tests_removed", 0)) for r in rows)
    coll_delta = sum(int(r.get("collected_delta", 0)) for r in rows)
    explained = (local is not None and not bad
                 and master_base.get("tests_passed", 0) - removed == local.get("tests_passed", -1)
                 and master_base.get("collected", 0) - coll_delta == local.get("collected", -1))
    return {"status": "DELTA_EXPLAINED" if explained else "UNEXPLAINED_DIVERGENCE",
            "ok": explained, "delta_rows": len(rows), "unattributed_rows": len(bad)}


def git_head() -> str:
    return _run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()


def assert_flakes_collect() -> list[str]:
    """Each known flake must actually exist — a renamed flake fails loudly."""
    p = _run([sys.executable, "-m", "pytest", "tests/test_cozy_persistence.py",
              "--collect-only", "-q"])
    missing = []
    for flake in KNOWN_FLAKES:
        tail = flake.split("::", 1)[1] if "::" in flake else flake
        if tail not in p.stdout:
            missing.append(flake)
    return missing


def do_baseline(args) -> int:
    V2_DIR.mkdir(parents=True, exist_ok=True)
    missing = assert_flakes_collect()
    if missing:
        print(f"REFUSED: known flakes do not collect (renamed/moved?): {missing}",
              file=sys.stderr)
        return 2
    print("[1/4] full suite (junit-sourced counts; ~8 min)...")
    tests = measure_tests("baseline")
    if not tests.get("ok"):
        print(f"REFUSED to write baselines: {tests.get('reason')}", file=sys.stderr)
        return 2
    print(f"      total {tests['total']} / passed {tests['passed']} / failed {tests['failed']}"
          f" / errors {tests['errors']} / skipped {tests['skipped']}")
    print("[2/4] cold-import median-of-3...")
    import_ms = measure_import_ms()
    print(f"      {import_ms} ms")
    print("[3/4] registry count...")
    registry = measure_registry_count()
    print(f"      {registry}")
    if import_ms < 0 or registry < 0 or tests["total"] < 0:
        print("REFUSED to write baselines: a measurement failed (sentinel -1)", file=sys.stderr)
        return 2
    coverage_pct = None
    if args.with_coverage:
        print("[4/4] coverage (slow)...")
        cov = check_coverage(baseline_pct=None)
        coverage_pct = cov.get("pct")
        if coverage_pct is None:
            print("REFUSED to write baselines: coverage measurement failed", file=sys.stderr)
            return 2
        print(f"      {coverage_pct}%")
    else:
        print("[4/4] coverage skipped (--with-coverage to pin the floor)")

    prior = json.loads(BASELINES.read_text(encoding="utf-8")) if BASELINES.exists() else {}
    flake_allowance = len(KNOWN_FLAKES) if tests["failed"] <= len(KNOWN_FLAKES) else 0
    data = {
        "measured_at": {"commit": git_head(), "node": platform.node(),
                        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        "tests_passed": tests["passed"] - flake_allowance + tests["failed"],
        "known_flakes_doc": KNOWN_FLAKES,  # documentation; authority is the script constant
        "skipped": tests["skipped"],
        "collected": tests["total"],       # junit total (executed + skipped)
        "import_ms": import_ms,
        "registry_count": registry,
        "coverage_pct": coverage_pct if coverage_pct is not None else prior.get("coverage_pct"),
        "coverage_leg": "windows-latest/py3.12",
    }
    if args.reset_original or "original" not in prior:
        data["original"] = {"tests_passed": data["tests_passed"], "collected": data["collected"]}
        if args.reset_original:
            print("NOTE: --reset-original re-seeded the reconciliation anchor "
                  "(Joe-reviewed, harness-maintenance act).")
    else:
        data["original"] = prior["original"]  # preserved: re-baselining never self-launders
    BASELINES.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"baselines written: {BASELINES}")
    return 0


def do_check(args) -> int:
    master_base, source = load_master_baselines()
    if master_base is not None:
        base = master_base
    elif BASELINES.exists():
        base = json.loads(BASELINES.read_text(encoding="utf-8"))
        source = "branch-bootstrap"
    else:
        print("ERROR: no baselines on master or locally — run --baseline first", file=sys.stderr)
        return 2

    tests = measure_tests("check")
    if not tests.get("ok"):
        print(json.dumps({"all_green": False, "error": tests.get("reason")}, indent=2))
        return 1
    unexpected = [n for n in tests["bad_names"] if not _flake_match(n)]
    tests_ok = (tests["passed"] >= base["tests_passed"]
                and tests["errors"] == 0
                and not unexpected
                and tests["failed"] <= len(KNOWN_FLAKES))
    collected_ok = tests["total"] >= base["collected"]
    skips_ok = tests["skipped"] <= base.get("skipped", tests["skipped"])
    ruff = check_ruff()
    import_ms = measure_import_ms()
    same_node = platform.node() == base.get("measured_at", {}).get("node")
    if same_node:
        import_check = {"ok": 0 < import_ms <= base["import_ms"] * IMPORT_BUDGET_FACTOR,
                        "median": import_ms,
                        "budget": round(base["import_ms"] * IMPORT_BUDGET_FACTOR, 1)}
    else:
        import_check = {"ok": import_ms > 0, "median": import_ms, "status": "REPORTED_ONLY",
                        "detail": "baseline pinned on a different machine; wall-clock "
                                  "budget not enforced here"}
    registry = measure_registry_count()
    drift_ok = registry == base["registry_count"]
    brightline = check_brightline(args.range, args.brightline)
    coverage = check_coverage(base.get("coverage_pct")) if args.with_coverage \
        else {"status": "SKIPPED", "ok": True}
    integrity = check_baseline_integrity(master_base)

    verdict = {
        "commit": git_head(),
        "baselines_source": source,
        "disclosure_certified": bool(brightline.get("certifies")),
        "checks": {
            "tests": {"ok": tests_ok, "passed": tests["passed"], "failed": tests["failed"],
                      "errors": tests["errors"], "unexpected_failures": unexpected,
                      "baseline": base["tests_passed"], "log": tests["log"]},
            "collected": {"ok": collected_ok, "count": tests["total"], "baseline": base["collected"]},
            "skips": {"ok": skips_ok, "count": tests["skipped"], "baseline": base.get("skipped")},
            "ruff": ruff,
            "import_ms": import_check,
            "doc_drift": {"ok": drift_ok, "registry": registry, "baseline": base["registry_count"]},
            "brightline": brightline,
            "coverage": coverage,
            "baseline_integrity": integrity,
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
    ap.add_argument("--brightline", choices=["auto", "skip"], default="auto",
                    help="'skip' is for CI only (scanner is local-only); the verdict "
                         "then carries disclosure_certified=false")
    ap.add_argument("--with-coverage", action="store_true")
    ap.add_argument("--reset-original", action="store_true",
                    help="re-seed the delta-reconciliation anchor (Joe-reviewed act)")
    ap.add_argument("--json", default=None, metavar="PATH")
    args = ap.parse_args()
    return do_baseline(args) if args.baseline else do_check(args)


if __name__ == "__main__":
    sys.exit(main())
