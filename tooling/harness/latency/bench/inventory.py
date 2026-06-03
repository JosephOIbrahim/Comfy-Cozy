"""inventory.py — global work-list discovery for the latency harness.

Scans every ComfyUI workflow, extracts the distinct MODEL files each references (any nesting,
API or UI format), cross-references on-disk sizes, and classifies models as OVERSIZED (>22GB,
won't fit 24GB resident -> offload/thrash, the remediation target) vs FITS. Usage count = how
many workflows inherit each model's fix.
"""
import glob
import json
import os
from collections import defaultdict

WF_DIR = r"G:\COMFY\ComfyUI\user\default\workflows"
MODEL_ROOTS = [r"G:\COMFYUI_Database\Models", r"G:\COMFY\ComfyUI\models"]
EXTS = (".safetensors", ".gguf", ".ckpt", ".pt", ".sft", ".bin")
FIT_GB = 22.0  # headroom under 24GB for activations

sizes = {}
for root in MODEL_ROOTS:
    if not os.path.isdir(root):
        continue
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.lower().endswith(EXTS):
                try:
                    sizes[f] = max(sizes.get(f, 0), os.path.getsize(os.path.join(dp, f)) / (1024**3))
                except OSError:
                    pass


def walk(o, out):
    if isinstance(o, dict):
        for v in o.values():
            walk(v, out)
    elif isinstance(o, list):
        for v in o:
            walk(v, out)
    elif isinstance(o, str) and o.lower().endswith(EXTS):
        out.add(os.path.basename(o.replace("\\", "/")))


model_wfs = defaultdict(set)
wf_files = sorted(glob.glob(os.path.join(WF_DIR, "*.json")))
for wf in wf_files:
    try:
        g = json.load(open(wf, encoding="utf-8"))
    except Exception:
        continue
    refs = set()
    walk(g, refs)
    for m in refs:
        model_wfs[m].add(os.path.basename(wf))

rows = sorted(((m, sizes.get(m), len(w)) for m, w in model_wfs.items()),
              key=lambda r: -(r[1] or 0))
print(f"{len(wf_files)} workflows, {len(model_wfs)} distinct model refs\n")
print("=== OVERSIZED (>22GB -> offload/thrash, REMEDIATION TARGETS) ===")
for m, sz, n in rows:
    if sz and sz > FIT_GB:
        print(f"  {sz:6.1f}GB  x{n:2d} wf  {m}")
print("\n=== FITS RESIDENT (<=22GB) ===")
for m, sz, n in rows:
    if sz and sz <= FIT_GB:
        print(f"  {sz:6.1f}GB  x{n:2d} wf  {m}")
print("\n=== referenced but NOT on disk / non-model ===")
for m, sz, n in rows:
    if not sz:
        print(f"   ?      x{n:2d} wf  {m}")
