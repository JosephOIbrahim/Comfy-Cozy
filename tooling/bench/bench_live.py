"""Live latency bench — the deferred L-1 scenarios (requires ComfyUI on :8188).

Sizes WP-4.4 (object_info cold fetch / validate cold-vs-warm) against WP-4.3
(execution time-to-first-signal vs completion) per docs/LATENCY_MAP.md's
binding-order question. DEADENDS honored: seeds vary per run (prompt cache),
completion truth comes from /history polling (ws detection is unreliable),
cold terms sample in a fresh process each. Appends to benchmark_log.jsonl.

Usage (PowerShell, ComfyUI running):
  .venv312/Scripts/python.exe tooling/bench/bench_live.py --all
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bench_offline import REPO, PY, _log, _summ  # noqa: E402

import httpx  # noqa: E402

BASE = "http://127.0.0.1:8188"
CKPT = "sdxl_v10VAEFix.safetensors"


def _require_live() -> dict:
    r = httpx.get(f"{BASE}/system_stats", timeout=5.0)
    r.raise_for_status()
    return r.json()


# --------------------------------------------------------------------------
# LB1 — object_info cold (fresh process) vs warm (WP-4.4 sizing)
# --------------------------------------------------------------------------

def bench_lb1() -> None:
    print("LB1 object_info full fetch: cold (fresh proc) vs warm (in-proc cache)")
    code = (
        "import time, json; from agent.tools import comfy_api; "
        "t0=time.perf_counter(); d=comfy_api.get_object_info(); "
        "cold=(time.perf_counter()-t0)*1000; "
        "t1=time.perf_counter(); comfy_api.get_object_info(); "
        "warm=(time.perf_counter()-t1)*1000; "
        "print(json.dumps({'cold_ms': cold, 'warm_ms': warm, 'classes': len(d)}))"
    )
    cold, warm, classes = [], [], 0
    for _ in range(5):
        out = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=REPO)
        r = json.loads(out.stdout.strip().splitlines()[-1])
        cold.append(r["cold_ms"])
        warm.append(r["warm_ms"])
        classes = r["classes"]
    _log("lb1_object_info", {"leg": "cold_fresh_proc", "classes": classes}, _summ(cold))
    _log("lb1_object_info", {"leg": "warm_cached"}, _summ(warm))


# --------------------------------------------------------------------------
# LB2 — validate_before_execute cold vs warm through the product path
# --------------------------------------------------------------------------

def bench_lb2() -> None:
    print("LB2 validate_before_execute: cold (first validate, fresh proc) vs warm")
    code = (
        "import time, json, sys; sys.path.insert(0, r'%s'); "
        "from bench_offline import _seed_session, REPO; "
        "from agent.tools import handle; "
        "wf = json.loads((REPO/'agent'/'templates'/'txt2img_sdxl.json').read_text(encoding='utf-8')); "
        "wf['1']['inputs']['ckpt_name'] = '%s'; _seed_session(wf); "
        "t0=time.perf_counter(); r1=handle('validate_before_execute', {}); "
        "cold=(time.perf_counter()-t0)*1000; "
        "t1=time.perf_counter(); handle('validate_before_execute', {}); "
        "warm=(time.perf_counter()-t1)*1000; "
        "ok = 'error' not in json.loads(r1) or not json.loads(r1).get('error'); "
        "print(json.dumps({'cold_ms': cold, 'warm_ms': warm, 'ok': ok}))"
    ) % (str(Path(__file__).resolve().parent), CKPT)
    cold, warm = [], []
    for _ in range(5):
        out = subprocess.run([PY, "-c", code], capture_output=True, text=True, cwd=REPO)
        if out.returncode != 0:
            raise RuntimeError(f"lb2 child failed: {out.stderr[-400:]}")
        r = json.loads(out.stdout.strip().splitlines()[-1])
        cold.append(r["cold_ms"])
        warm.append(r["warm_ms"])
    _log("lb2_validate", {"leg": "cold_first"}, _summ(cold))
    _log("lb2_validate", {"leg": "warm_revalidate"}, _summ(warm))


# --------------------------------------------------------------------------
# LB3 — boot handshake, live regime (complements offline refused/blackhole)
# --------------------------------------------------------------------------

def bench_lb3() -> None:
    print("LB3 boot handshake with ComfyUI UP (n=5)")
    from bench_offline import _jsonrpc  # noqa: E402
    import os
    marks = {"initialize": [], "tools_list_1": [], "ping": []}
    for _ in range(5):
        env = {**os.environ, "COMFYUI_HOST": "127.0.0.1", "COMFYUI_PORT": "8188"}
        t0 = time.perf_counter()
        proc = subprocess.Popen(
            [PY, "-c", "import sys; sys.argv=['agent','mcp']; from agent.cli import app; app()"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, cwd=REPO, env=env)
        try:
            _jsonrpc(proc, 1, "initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {}, "clientInfo": {"name": "bench", "version": "0"}})
            marks["initialize"].append((time.perf_counter() - t0) * 1000)
            proc.stdin.write(json.dumps(
                {"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            proc.stdin.flush()
            t1 = time.perf_counter()
            _jsonrpc(proc, 2, "tools/list")
            marks["tools_list_1"].append((time.perf_counter() - t1) * 1000)
            t2 = time.perf_counter()
            _jsonrpc(proc, 3, "tools/call", {"name": "comfyui_agent_ping", "arguments": {}})
            marks["ping"].append((time.perf_counter() - t2) * 1000)
        finally:
            proc.kill()
    for mark, samples in marks.items():
        _log("lb3_boot_live", {"regime": "live", "mark": mark}, _summ(samples))


# --------------------------------------------------------------------------
# LB4 — execution: queue -> first ws signal -> first preview -> complete
# --------------------------------------------------------------------------

def _exec_workflow(seed: int, steps: int = 12, size: int = 768) -> dict:
    wf = json.loads((REPO / "agent" / "templates" / "txt2img_sdxl.json")
                    .read_text(encoding="utf-8"))
    wf["1"]["inputs"]["ckpt_name"] = CKPT
    wf["5"]["inputs"]["seed"] = seed
    wf["5"]["inputs"]["steps"] = steps
    wf["4"]["inputs"]["width"] = size
    wf["4"]["inputs"]["height"] = size

    async def run() -> dict:
        import websockets
        client_id = uuid.uuid4().hex
        marks: dict = {}
        async with websockets.connect(
                f"ws://127.0.0.1:8188/ws?clientId={client_id}", max_size=2**24) as ws:
            t0 = time.perf_counter()
            r = httpx.post(f"{BASE}/prompt",
                           json={"prompt": wf, "client_id": client_id}, timeout=30.0)
            r.raise_for_status()
            pid = r.json()["prompt_id"]
            end = t0 + 300
            while time.perf_counter() < end:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                else:
                    now = (time.perf_counter() - t0) * 1000
                    if isinstance(msg, bytes):
                        marks.setdefault("first_preview_ms", now)
                        continue
                    ev = json.loads(msg)
                    t = ev.get("type")
                    if t == "execution_start":
                        marks.setdefault("execution_start_ms", now)
                    elif t == "progress":
                        marks.setdefault("first_progress_ms", now)
                # completion truth: /history, not ws
                h = httpx.get(f"{BASE}/history/{pid}", timeout=5.0).json()
                if pid in h and h[pid].get("status", {}).get("completed"):
                    marks["complete_ms"] = (time.perf_counter() - t0) * 1000
                    break
        return marks

    return asyncio.run(run())


def bench_lb4() -> None:
    print("LB4 execution (SDXL 768x768, 12 steps, seed-varied, n=3): "
          "queue->start->first-signal->preview->complete")
    runs = [_exec_workflow(seed=1000 + i) for i in range(3)]
    for mark in ("execution_start_ms", "first_progress_ms", "first_preview_ms",
                 "complete_ms"):
        samples = [r[mark] for r in runs if mark in r]
        if samples:
            _log("lb4_execution", {"mark": mark, "n_runs": len(runs)}, _summ(samples))
    # WP-4.3 signal-gap: how long a client waits with ZERO feedback without
    # progress notifications = first_progress (the earliest forwardable signal).
    gaps = [r["complete_ms"] - r["first_progress_ms"] for r in runs
            if "complete_ms" in r and "first_progress_ms" in r]
    if gaps:
        _log("lb4_execution", {"mark": "progress_window_ms",
                               "note": "first-signal..complete span WP-4.3 would fill"},
             _summ(gaps))


SCENARIOS = {"lb1": bench_lb1, "lb2": bench_lb2, "lb3": bench_lb3, "lb4": bench_lb4}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--scenario", nargs="*", default=[])
    ap.add_argument("--mode", default="live-baseline")
    a = ap.parse_args()
    import bench_offline
    bench_offline._MODE = a.mode
    stats = _require_live()
    dev = stats["devices"][0]
    print(f"live: comfyui {stats['system']['comfyui_version']} on {dev['name'][:30]} "
          f"({round(dev['vram_free'] / 2**30, 1)} GB free)")
    for name in (list(SCENARIOS) if a.all else a.scenario):
        SCENARIOS[name]()


if __name__ == "__main__":
    main()
