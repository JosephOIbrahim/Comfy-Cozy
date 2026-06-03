"""run_seed.py — poll-path execute_workflow with the two RandomNoise seeds overridden.

Identical-seed re-runs hit ComfyUI's per-node output cache (exec ~0.27s, reuses prior file) —
that's the cache-hit path, NOT the warm render a user gets on a new generation. Varying the seed
busts the cache and forces real DiT compute while the model stays resident → true WARM inference.
Inference time is seed-independent for a distilled few-step model, so runs stay comparable.

Overrides noise_seed on 267:216 and 267:237 (the workflow's two RandomNoise nodes).

Usage: python run_seed.py "<workflow.json>" <seed> [timeout_s]
Prints: RESULT_JSON {json}
"""
import json
import os
import sys
import tempfile
import time

from agent.tools import comfy_execute

NOISE_NODES = ("267:216", "267:237")


def main() -> int:
    wf = sys.argv[1]
    seed = int(sys.argv[2])
    timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 1800.0

    with open(wf, encoding="utf-8") as f:
        g = json.load(f)
    for i, nid in enumerate(NOISE_NODES):
        node = g.get(nid, {})
        if "inputs" in node and "noise_seed" in node["inputs"]:
            node["inputs"]["noise_seed"] = seed + i
    tmp = os.path.join(tempfile.gettempdir(), f"wf_seed_{seed}.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(g, f)

    t0 = time.perf_counter()
    res = comfy_execute.handle("execute_workflow", {"path": tmp, "timeout": timeout})
    t1 = time.perf_counter()
    d = json.loads(res)
    out = {
        "handler_wall_s": round(t1 - t0, 3),
        "prompt_id": d.get("prompt_id"),
        "status": d.get("status"),
        "n_outputs": len(d.get("outputs", []) or []),
        "seed": seed,
        "error": d.get("error"),
    }
    print("RESULT_JSON " + json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
