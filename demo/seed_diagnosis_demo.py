#!/usr/bin/env python
"""Offline demo seeder for the keyless diagnosis slice.

ComfyUI can be DOWN and no API key is required: this path is deterministic code
only (no LLM, no torch import). It reproduces the demo store so the five-beat
runbook rehearses without a live render:

    3 clean baseline runs of one workflow  +  1 OOM error run (becomes 'latest').

Usage (PowerShell):
    $env:DIAGNOSIS_DIR = "$env:TEMP\\cozy_demo"   # optional; script prints its default
    python demo/seed_diagnosis_demo.py
    agent diagnose --last
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

# Isolated store: honor an existing DIAGNOSIS_DIR, else a printed default under TEMP.
_default = str(Path(os.getenv("TEMP") or "/tmp") / "cozy_diagnosis_demo")
os.environ.setdefault("DIAGNOSIS_DIR", _default)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root importable
from agent.diagnosis.diagnosis import build_diagnosis, emit, env_hash, workflow_hash

ENV = {  # the six-field worker env block (drives envHash)
    "os": "Windows-11", "python": "3.12.10", "torch": "2.7.1+cu128",
    "torchCuda": "cu128", "driver": "576.88", "comfyuiVersion": "0.3.44",
}
WORKFLOW = {  # a minimal SD1.5 graph — only its resolved hash matters here
    "3": {"class_type": "KSampler", "inputs": {"steps": 20, "cfg": 7.0}},
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd15.safetensors"}},
    "8": {"class_type": "VAEDecode", "inputs": {}},
}
WHASH = workflow_hash(WORKFLOW)
NODE = "127.0.0.1:8188"
STAGES = [  # synthetic per-node timing baked into the clean baseline (beat-2 table shape)
    {"stage": "4:CheckpointLoaderSimple", "ms": 640.0},
    {"stage": "3:KSampler", "ms": 11200.0},
    {"stage": "8:VAEDecode", "ms": 560.0},
]
OOM = ("RuntimeError CUDA out of memory. Tried to allocate 2.50 GiB "
       "(GPU 0; 24.00 GiB total capacity; 22.10 GiB already allocated)")


def _clean(i: int) -> dict:
    return {"promptId": f"clean-{i}", "workflowHash": WHASH, "status": "completed",
            "durationS": 12.0 + i * 0.4, "vramPeakGb": None, "stages": STAGES}


def main() -> None:
    store = Path(os.environ["DIAGNOSIS_DIR"])
    shutil.rmtree(store, ignore_errors=True)  # idempotent: baseline stays exactly 3
    print(f"DIAGNOSIS_DIR = {store}")
    print(f"envHash       = {env_hash(ENV)}")
    print(f"workflowHash  = {WHASH}\n")
    for i in range(1, 4):  # 3 clean baseline runs of the same workflow
        p = emit(build_diagnosis(ENV, _clean(i), NODE))
        print(f"  seeded clean run {i} : {p.name}")
        time.sleep(0.03)  # guarantee strict mtime ordering -> OOM is newest
    oom_run = {"promptId": "break-oom", "workflowHash": WHASH, "status": "error",
               "durationS": 3.2, "vramPeakGb": None, "stages": []}
    p = emit(build_diagnosis(ENV, oom_run, NODE, error_text=OOM))
    print(f"  seeded OOM run   : {p.name}  (latest, critical)\n")

    print("Presenter commands (set UTF-8 first so separators render clean, not as �):")
    print('  console utf-8        : $env:PYTHONUTF8="1"; [Console]::OutputEncoding=[Text.Encoding]::UTF8')
    print("  beat 1  fingerprint  : agent diagnose --last          # first line = env <hash>")
    print("  beat 3  the break    : agent diagnose --last          # critical vram_pressure")
    print("  beat 4  the contract : agent diagnose --last --json")
    print("  beat 5  the best line: agent diagnose --last --json | jq .findings   # jq optional; see fallback")
    print("  beat 5  no-jq fallback: agent diagnose --last --json | "
          "python -c \"import sys,json;print(json.dumps(json.load(sys.stdin)['findings'],indent=2))\"")
    print("  gate    strict exit  : agent diagnose --last --strict  # renders report, then exit code 1")


if __name__ == "__main__":
    main()
