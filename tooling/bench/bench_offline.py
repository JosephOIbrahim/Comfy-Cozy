"""Offline latency bench — the measurement instrument of tooling/harness/latency/.

Every scenario runs fully offline (no ComfyUI, no LLM, no network beyond a local
blackhole socket used to simulate an unreachable ComfyUI). Cold scenarios spawn a
FRESH process per sample (the import/load happens once per process). Aggregation:
median + p95, N per scenario below. Results append to tooling/bench/benchmark_log.jsonl
({sha, scenario, params, median_ms, p95_ms, n, mode}) — append-only champion-log
convention. See tooling/harness/latency/CONSTITUTION.md Articles I-III.

Usage (PowerShell):
  .venv312/Scripts/python.exe tooling/bench/bench_offline.py --all
  .venv312/Scripts/python.exe tooling/bench/bench_offline.py --scenario b1 b3
"""

import argparse
import json
import os
import socket
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
PY = sys.executable
LOG_PATH = Path(__file__).resolve().parent / "benchmark_log.jsonl"


def _sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=REPO
        )
        return out.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def _summ(samples_ms: list[float]) -> dict:
    s = sorted(samples_ms)
    return {
        "median_ms": round(statistics.median(s), 3),
        "p95_ms": round(s[max(0, int(len(s) * 0.95) - 1)], 3),
        "n": len(s),
    }


_MODE = "baseline"


def _log(scenario: str, params: dict, summary: dict) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha": _sha(),
        "scenario": scenario,
        "params": params,
        "mode": _MODE,
        **summary,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    print(f"  {scenario} {params} -> median {summary['median_ms']} ms  "
          f"p95 {summary['p95_ms']} ms  (n={summary['n']})")


def _synthetic_workflow(n_nodes: int) -> dict:
    """Chain of API-format nodes with realistic long prompt strings."""
    wf = {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": "sd15/model.safetensors"}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": "cinematic portrait, volumetric light, " * 20,
                         "clip": ["1", 1]}},
    }
    prev = "2"
    for i in range(3, n_nodes + 1):
        nid = str(i)
        wf[nid] = {
            "class_type": "KSampler",
            "inputs": {
                "seed": i, "steps": 20, "cfg": 7.0, "sampler_name": "euler",
                "scheduler": "normal", "denoise": 1.0,
                "model": ["1", 0], "positive": [prev, 0], "negative": ["2", 0],
                "latent_image": [prev, 0],
            },
        }
        prev = nid
    return wf


# --------------------------------------------------------------------------
# In-process scenario bodies (run inside a fresh child via --scenario-child)
# --------------------------------------------------------------------------

def _seed_session(wf: dict) -> None:
    """Emulate the loaded-session precondition the MCP runtime provides via
    SessionContext: seed the registry WorkflowSession the gate consults."""
    import copy
    from agent._conn_ctx import _conn_session
    from agent.tools.workflow_patch import _get_state
    _conn_session.set("bench")
    st = _get_state()
    st["base_workflow"] = copy.deepcopy(wf)
    st["current_workflow"] = copy.deepcopy(wf)
    st["format"] = "api"


def _child_b1(n_nodes: int, n_edits: int) -> dict:
    from agent.tools import handle
    wf = _synthetic_workflow(n_nodes)
    _seed_session(wf)
    target = str(n_nodes)  # last KSampler in the chain
    times = []
    for i in range(n_edits):
        t0 = time.perf_counter()
        out = handle("set_input", {"node_id": target, "input_name": "steps",
                                   "value": 20 + (i % 10)})
        times.append((time.perf_counter() - t0) * 1000)
        if i == 0 and json.loads(out).get("error"):
            raise RuntimeError(f"set_input rejected — measuring nothing: {out[:200]}")
    head = statistics.median(times[:20])
    tail = statistics.median(times[-20:])
    return {"all": times, "head_median_ms": round(head, 3), "tail_median_ms": round(tail, 3),
            "growth_x": round(tail / head, 2) if head else 0}


def _child_b2(depth: int) -> dict:
    from agent.tools import handle
    tpl = REPO / "agent" / "templates" / "txt2img_sd15.json"
    _seed_session(json.loads(tpl.read_text(encoding="utf-8")))
    for i in range(depth - 1):
        out = handle("set_input", {"node_id": "3", "input_name": "steps",
                                   "value": 20 + (i % 10)})
        if i == 0 and json.loads(out).get("error"):
            raise RuntimeError(f"set_input rejected — depth is fake: {out[:200]}")
    t0 = time.perf_counter()
    out = handle("apply_recipe", {"name": "dreamier"})
    ms = (time.perf_counter() - t0) * 1000
    if json.loads(out).get("error"):
        raise RuntimeError(f"apply_recipe rejected: {out[:200]}")
    return {"ms": ms, "ok": True}


def _child_b3(n_calls: int) -> dict:
    import types
    import agent.tools as at
    at._HANDLERS["__bench_noop__"] = types.SimpleNamespace(
        handle=lambda name, tool_input: "{}")
    at.handle("__bench_noop__", {})  # warm
    times = []
    payload = {"x": 1}
    for _ in range(n_calls):
        t0 = time.perf_counter()
        at.handle("__bench_noop__", payload)
        times.append((time.perf_counter() - t0) * 1000)
    # Gate-inclusive floor: unknown tools bypass the gate, so also time a real
    # READ_ONLY tool with a trivial body.
    at.handle("list_recipes", {})  # warm
    gated = []
    for _ in range(n_calls):
        t0 = time.perf_counter()
        at.handle("list_recipes", {})
        gated.append((time.perf_counter() - t0) * 1000)
    return {"all": times, "gated": gated}


def _child_b7(count: int) -> dict:
    from agent import metrics, health
    h = metrics.tool_call_duration_seconds
    for i in range(count):
        h.observe(0.001 * (i % 100), labels={"tool_name": f"t{i % 20}"})
    fn = getattr(health, "_get_metrics_summary", None) or getattr(health, "get_health", None)
    if fn is None:
        return {"all": [0.0], "skipped": "no summary symbol"}
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        try:
            fn()
        except Exception:
            pass
        times.append((time.perf_counter() - t0) * 1000)
    return {"all": times}


_CHILDREN = {"b1": _child_b1, "b2": _child_b2, "b3": _child_b3, "b7": _child_b7}


def _spawn_child(name: str, env_extra: dict, **kwargs) -> dict:
    env = {**os.environ, "COMFYUI_PORT": "9", **env_extra}  # port 9 = discard, refused
    args = [PY, __file__, "--scenario-child", name, "--kwargs", json.dumps(kwargs)]
    out = subprocess.run(args, capture_output=True, text=True, env=env, cwd=REPO)
    if out.returncode != 0:
        raise RuntimeError(f"child {name} failed: {out.stderr[-800:]}")
    return json.loads(out.stdout.strip().splitlines()[-1])


# --------------------------------------------------------------------------
# Scenarios (driver side)
# --------------------------------------------------------------------------

def bench_b1() -> None:
    print("B1 edit-path (per-edit set_input; growth = tail/head within sequence)")
    for n_nodes in (10, 50, 200):
        r = _spawn_child("b1", {}, n_nodes=n_nodes, n_edits=200)
        _log("b1_edit_path", {"n_nodes": n_nodes, "n_edits": 200},
             {**_summ(r["all"]), "head_median_ms": r["head_median_ms"],
              "tail_median_ms": r["tail_median_ms"], "growth_x": r["growth_x"]})


def bench_b2() -> None:
    print("B2 apply_recipe wall-clock vs history depth")
    for depth in (1, 300):
        samples = [_spawn_child("b2", {}, depth=depth)["ms"] for _ in range(5)]
        _log("b2_recipe_depth", {"depth": depth}, _summ(samples))


def bench_b3() -> None:
    print("B3 dispatch floor (no-op handler), observation on/off, + gated READ_ONLY floor")
    for obs in ("1", "0"):
        r = _spawn_child("b3", {"OBSERVATION_ENABLED": obs}, n_calls=1000)
        _log("b3_dispatch_floor", {"observation": obs, "gate": "bypassed"}, _summ(r["all"]))
        _log("b3_dispatch_floor", {"observation": obs, "gate": "included"}, _summ(r["gated"]))


def bench_b4() -> None:
    print("B4 cold import per stage (fresh process each, n=10)")
    targets = ["agent.config", "agent.tools", "agent.cli", "agent.mcp_server"]
    for target in targets:
        samples = []
        for _ in range(10):
            code = ("import time; t0=time.perf_counter(); import {m}; "
                    "print((time.perf_counter()-t0)*1000)").format(m=target)
            out = subprocess.run([PY, "-c", code], capture_output=True, text=True,
                                 env={**os.environ, "COMFYUI_PORT": "9"}, cwd=REPO)
            samples.append(float(out.stdout.strip().splitlines()[-1]))
        _log("b4_cold_import", {"module": target}, _summ(samples))


class _Blackhole:
    """Local listener that accepts and never responds — simulates a hung ComfyUI."""

    def __enter__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self._stop = False
        self.conns = []

        def _accept():
            while not self._stop:
                try:
                    self.sock.settimeout(0.5)
                    c, _ = self.sock.accept()
                    self.conns.append(c)  # hold open, never respond
                except OSError:
                    continue

        self.t = threading.Thread(target=_accept, daemon=True)
        self.t.start()
        return self

    def __exit__(self, *a):
        self._stop = True
        for c in self.conns:
            try:
                c.close()
            except OSError:
                pass
        self.sock.close()


def _jsonrpc(proc, req_id, method, params=None):
    msg = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("server closed stdout")
        try:
            resp = json.loads(line)
        except json.JSONDecodeError:
            continue
        if resp.get("id") == req_id:
            return resp


def bench_b5() -> None:
    print("B5 boot-to-ready handshake (agent mcp), refused vs blackhole regimes, n=5")
    for regime in ("refused", "blackhole"):
        marks: dict[str, list[float]] = {"initialize": [], "tools_list_1": [],
                                         "tools_list_2": [], "ping": []}
        for _ in range(5):
            ctx = _Blackhole() if regime == "blackhole" else None
            port = "9"
            if ctx:
                ctx.__enter__()
                port = str(ctx.port)
            env = {**os.environ, "COMFYUI_HOST": "127.0.0.1", "COMFYUI_PORT": port}
            t0 = time.perf_counter()
            proc = subprocess.Popen(
                [PY, "-c", "import sys; sys.argv=['agent','mcp']; "
                           "from agent.cli import app; app()"],
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
                _jsonrpc(proc, 3, "tools/list")
                marks["tools_list_2"].append((time.perf_counter() - t2) * 1000)
                t3 = time.perf_counter()
                _jsonrpc(proc, 4, "tools/call",
                         {"name": "comfyui_agent_ping", "arguments": {}})
                marks["ping"].append((time.perf_counter() - t3) * 1000)
            finally:
                proc.kill()
                if ctx:
                    ctx.__exit__()
        for mark, samples in marks.items():
            if samples:
                _log("b5_boot_handshake", {"regime": regime, "mark": mark}, _summ(samples))


def bench_b7() -> None:
    print("B7 metrics/health cost vs observation count")
    for count in (1000, 10000, 100000):
        r = _spawn_child("b7", {}, count=count)
        params = {"observations": count}
        if "skipped" in r:
            params["skipped"] = r["skipped"]
        _log("b7_metrics_health", params, _summ(r["all"]))


SCENARIOS = {"b1": bench_b1, "b2": bench_b2, "b3": bench_b3,
             "b4": bench_b4, "b5": bench_b5, "b7": bench_b7}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--scenario", nargs="*", default=[])
    ap.add_argument("--scenario-child")
    ap.add_argument("--kwargs")
    ap.add_argument("--mode", default="baseline")
    a = ap.parse_args()

    if a.scenario_child:
        result = _CHILDREN[a.scenario_child](**json.loads(a.kwargs or "{}"))
        result.pop("_wf", None)
        print(json.dumps(result))
        return

    global _MODE
    _MODE = a.mode
    names = list(SCENARIOS) if a.all else a.scenario
    print(f"bench_offline @ {_sha()} mode={a.mode} scenarios={names}")
    for name in names:
        SCENARIOS[name]()


if __name__ == "__main__":
    main()
