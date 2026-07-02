"""H2 caching-race bench — validate->fix->re-validate cycle (ledger H0.3 method).

One fresh process per invocation = one cold run. Outer loop (x3) lives in the shell.
Measures, against live ComfyUI at COMFYUI_URL:

  t_import_ms     wall time of `import agent.tools`
  t_validate1_ms  validate_before_execute on the session workflow (cold)
  t_fix_ms        set_input (KSampler seed) on the session workflow
  t_validate2_ms  validate_before_execute again (re-validate after fix)
  t_cycle_ms      validate1 + fix + validate2
  poll_ms         engine.get_history round-trip, first call + 9 warm repeats

Reference workload: agent/templates/txt2img_sd15.json (7 nodes).
Output: one JSON line to stdout (provenance: agent.__file__, git SHA).
"""

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))  # bench the tree this script lives in, not the editable install


def main() -> None:
    t0 = time.perf_counter()
    import agent.tools  # noqa: F401  (timed import)
    t_import_ms = (time.perf_counter() - t0) * 1000

    from agent.tools import handle

    template = REPO / "agent" / "templates" / "txt2img_sd15.json"
    from agent.tools.workflow_patch import load_workflow_from_data

    err = load_workflow_from_data(json.loads(template.read_text()), source=str(template))
    if err:
        print(json.dumps({"error": f"session load failed: {err}"}))
        sys.exit(1)

    t0 = time.perf_counter()
    v1 = handle("validate_before_execute", {})
    t_validate1_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    handle("set_input", {"node_id": "5", "input_name": "seed", "value": 424242})
    t_fix_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    v2 = handle("validate_before_execute", {})
    t_validate2_ms = (time.perf_counter() - t0) * 1000

    from agent.engine import get_engine

    engine = get_engine()
    poll_ms = []
    for _ in range(10):
        t0 = time.perf_counter()
        engine.get_history()
        poll_ms.append(round((time.perf_counter() - t0) * 1000, 2))

    sha = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()

    warm = sorted(poll_ms[1:])
    print(json.dumps({
        "agent_file": agent.tools.__file__,
        "git_sha": sha,
        "t_import_ms": round(t_import_ms, 1),
        "t_validate1_ms": round(t_validate1_ms, 1),
        "t_fix_ms": round(t_fix_ms, 2),
        "t_validate2_ms": round(t_validate2_ms, 1),
        "t_cycle_ms": round(t_validate1_ms + t_fix_ms + t_validate2_ms, 1),
        "valid1": json.loads(v1).get("valid"),
        "valid2": json.loads(v2).get("valid"),
        "poll_first_ms": poll_ms[0],
        "poll_warm_median_ms": warm[len(warm) // 2],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
