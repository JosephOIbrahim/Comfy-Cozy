"""Live V1 verification of the three bridge capabilities (L-PANEL / PR #74).

Drives the worktree's (auth-gated) agent tools against the running ComfyUI to
prove the auth change did not break the agent's own bridge calls and that all
three advertised capabilities work end-to-end. No token configured here, so
bridge_auth_headers() == {} and the round-trip exercises the default path.
"""

import copy
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import httpx  # noqa: E402

from agent.tools import canvas_bridge, exec_profile  # noqa: E402

COMFY = "http://127.0.0.1:8188"
TEMPLATE = json.loads((REPO / "agent" / "templates" / "txt2img_sd15.json").read_text())


def ok(label, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    return cond


results = []

# --- Capability 1: load a workflow straight onto the canvas -----------------
r1 = json.loads(canvas_bridge.handle(
    "push_workflow_to_canvas",
    {"workflow": TEMPLATE, "reason": "L-PANEL live verify (PR #74)"},
))
results.append(ok("push_workflow_to_canvas", r1.get("pushed") is True, json.dumps(r1)[:120]))

# --- Capability 2: see the edits you make by hand (round-trip) ---------------
edited = copy.deepcopy(TEMPLATE)
edited["5"]["inputs"]["seed"] = 13371337  # simulate one hand edit
# the browser would POST this on a canvas change; emulate that here
post = httpx.post(f"{COMFY}/agent/canvas_changed", json={"workflow": edited}, timeout=10.0)
results.append(ok("canvas_changed accepts edit", post.status_code == 200, f"HTTP {post.status_code}"))
r2 = json.loads(canvas_bridge.handle("get_canvas_state", {}))
got = r2.get("workflow") or {}
seed_back = got.get("5", {}).get("inputs", {}).get("seed")
results.append(ok("get_canvas_state reads the hand edit back", seed_back == 13371337,
                  f"seed read back = {seed_back}"))

# --- Capability 3: which node ate your render time --------------------------
wf = copy.deepcopy(TEMPLATE)
wf["1"]["inputs"]["ckpt_name"] = "sdxl_v10VAEFix.safetensors"  # an installed checkpoint
wf["4"]["inputs"]["width"] = 1024
wf["4"]["inputs"]["height"] = 1024
wf["5"]["inputs"]["seed"] = int(time.time()) % 2_000_000_000  # vary -> no cache hit
queue = httpx.post(f"{COMFY}/prompt", json={"prompt": wf}, timeout=15.0)
pid = queue.json().get("prompt_id") if queue.status_code == 200 else None
results.append(ok("execution queued", pid is not None, f"prompt_id={pid} (HTTP {queue.status_code})"))

if pid:
    deadline = time.time() + 120
    done = False
    while time.time() < deadline:
        hist = httpx.get(f"{COMFY}/history/{pid}", timeout=10.0).json()
        if hist.get(pid, {}).get("status", {}).get("completed"):
            done = True
            break
        time.sleep(1.0)
    results.append(ok("execution completed", done, f"within {'120' if not done else '<120'}s"))
    r3 = json.loads(exec_profile.handle("get_execution_profile", {"prompt_id": pid}))
    nodes = r3.get("nodes") or []
    results.append(ok("get_execution_profile returns per-node timing", len(nodes) > 0,
                      f"{len(nodes)} nodes; slowest="
                      + (max(nodes, key=lambda n: n.get('seconds', 0)).get('class_type', '?')
                         if nodes else 'n/a')))

print("\n=== RESULT:", f"{sum(results)}/{len(results)} live checks passed ===")
sys.exit(0 if all(results) else 1)
