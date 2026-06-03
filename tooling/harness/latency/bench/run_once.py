"""run_once.py — drive ONE poll-path execute_workflow run and report timing.

Fresh-process invocation (matches the harness's Measure-Command { <cmd> } model: a new
process pays the object_info cold-fetch again, A2). Drives the SAME dispatch code
`agent orchestrate` would use (_queue_prompt + 1.0s _poll_completion) but skips orchestrate's
pre-validator, which false-positives on this graph's ComfyMathExpression `values.a` inputs.

Prints one line:  RESULT_JSON {json}
with handler_wall_s (time inside the execute_workflow handler), prompt_id, status, outputs.
INFERENCE itself is read separately from GET /history (keys verified live).

Usage: python run_once.py "<workflow.json>" [timeout_s]
"""
import json
import sys
import time

from agent.tools import comfy_execute


def main() -> int:
    if len(sys.argv) < 2:
        print("RESULT_JSON " + json.dumps({"error": "usage: run_once.py <wf> [timeout_s]"}))
        return 2
    wf = sys.argv[1]
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 900.0

    t0 = time.perf_counter()
    res = comfy_execute.handle("execute_workflow", {"path": wf, "timeout": timeout})
    t1 = time.perf_counter()

    try:
        d = json.loads(res)
    except Exception as e:  # pragma: no cover - defensive
        print("RESULT_JSON " + json.dumps({"error": f"unparseable handler result: {e}", "raw": res[:500]}))
        return 1

    out = {
        "handler_wall_s": round(t1 - t0, 3),
        "prompt_id": d.get("prompt_id"),
        "status": d.get("status"),
        "n_outputs": len(d.get("outputs", []) or []),
        "outputs": d.get("outputs"),
        "error": d.get("error"),
        "outputs_warning": d.get("outputs_warning"),
    }
    print("RESULT_JSON " + json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
