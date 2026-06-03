"""sweep_gguf.py — GGUF reproducibility / noise-band sweep (seed-varied, cache-busting).

Runs N seed-varied GGUF renders, reads ComfyUI /history exec time for each, reports the band.
Also validates that CONSECUTIVE runs stay fast (the thing fp16 failed — it thrashed).
"""
import json
import os
import tempfile
import urllib.request

from agent.tools import comfy_execute

WF = r"G:\Comfy-Cozy\tooling\harness\latency\bench\wf_gguf.json"
URL = "http://127.0.0.1:8188"
SEEDS = [1000, 2000, 3000, 4000]
NOISE = ("267:216", "267:237")


def hist_exec(pid):
    with urllib.request.urlopen(f"{URL}/history/{pid}", timeout=30) as r:
        h = json.load(r)
    e = h.get(pid)
    if not e:
        return None
    s = f = None
    for m in e["status"]["messages"]:
        if m[0] == "execution_start":
            s = m[1]["timestamp"]
        if m[0] == "execution_success":
            f = m[1]["timestamp"]
    return round((f - s) / 1000.0, 3) if (s and f) else None


execs = []
for seed in SEEDS:
    g = json.load(open(WF, encoding="utf-8"))
    for i, n in enumerate(NOISE):
        if n in g and "noise_seed" in g[n]["inputs"]:
            g[n]["inputs"]["noise_seed"] = seed + i
    tmp = os.path.join(tempfile.gettempdir(), f"wf_gguf_{seed}.json")
    json.dump(g, open(tmp, "w", encoding="utf-8"))
    res = json.loads(comfy_execute.handle("execute_workflow", {"path": tmp, "timeout": 600}))
    pid, st = res.get("prompt_id"), res.get("status")
    ex = hist_exec(pid) if pid else None
    if ex:
        execs.append(ex)
    print(f"seed={seed} status={st} exec_s={ex} pid={pid}", flush=True)

if execs:
    sr = sorted(execs)
    print(f"NOISE_BAND exec_s min={sr[0]} median={sr[len(sr) // 2]} max={sr[-1]} "
          f"N={len(sr)} mean={round(sum(sr) / len(sr), 2)}")
