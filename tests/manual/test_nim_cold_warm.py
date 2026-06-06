"""
test_nim_cold_warm.py

End-to-end smoke test for nim_lifecycle.py against a real ComfyUI + NIM install.

It does four things:
  1. Loads the NIMnodes example workflow (FLUX_Dev_NIM_Workflow.json) from disk
     -- the shipped file is the source of truth, nothing here is hand-faked.
  2. Prints the REAL class_type strings it finds, so you can paste the exact
     generate/load/install node names back into nim_lifecycle.py's
     NIM_GENERATE_NODES / NIM_LOAD_NODES / NIM_INSTALL_NODES sets (the #1 seam).
  3. Patches prompt / seed / width / height / steps, sets the Load NIM
     offloading_policy to None (best perf on your 24 GB 4090).
  4. Runs nim_run COLD (forces the container pull), then WARM (uses the short
     warmup budget from the warm-state record), and prints the timing collapse.

USAGE
-----
    # confirm node detection + patching without the slow cold pull:
    python test_nim_cold_warm.py --dry-run

    # full cold -> warm run:
    python test_nim_cold_warm.py --prompt "a cinematic portrait, golden hour"

    # point at an explicit workflow file (API format -- see note below):
    python test_nim_cold_warm.py --workflow C:/path/to/FLUX_Dev_NIM_Workflow.json

ONE-TIME PREREQ (not automatable)
---------------------------------
The very first cold run only works once NIMSetup.exe is already installed. The
Install NIM node can *download* it but the GUI installer can't be clicked through
headlessly. Run NIMSetup.exe once (see install steps), then this script's "cold"
run just does the per-model container pull, which IS automatable.

WORKFLOW FORMAT NOTE
--------------------
ComfyUI's /prompt endpoint -- and therefore nim_run -- wants the API format
(the {node_id: {class_type, inputs}} dict), not the UI graph (nodes + links).
If your JSON is the UI export, this script will say so. Easiest fix: in ComfyUI,
Settings -> enable Dev mode, open the workflow, "Save (API Format)", point
--workflow at that file. (Or wire the Comfy-Cozy loader at the SEAM below.)
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import pytest

# Skip this manual smoke test cleanly when nim_lifecycle is absent (e.g. master
# checkout). importorskip imports + caches the module for the SEAM import below,
# or raises Skipped at collection time so pytest never hard-errors.
pytest.importorskip("agent.tools.nim_lifecycle")

# SEAM: same package path as the wrapper.
from agent.tools.nim_lifecycle import (
    nim_run,
    nim_state,
    nim_preflight,
    NIM_INSTALL_NODES,
    NIM_LOAD_NODES,
    NIM_GENERATE_NODES,
)

# NIM FLUX node accepts only these discrete width/height values.
VALID_DIMS = [672, 704, 736, 768, 800, 832, 864, 896, 928, 960, 992, 1024,
              1056, 1088, 1120, 1152, 1184, 1216, 1248, 1280, 1312, 1344,
              1376, 1408, 1440, 1472, 1504, 1536, 1568]

EXAMPLE_FILENAME = "FLUX_Dev_NIM_Workflow.json"


# ---------------------------------------------------------------------------
# locate + load
# ---------------------------------------------------------------------------

def find_workflow(explicit: Optional[str]) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.exists():
            sys.exit(f"--workflow not found: {p}")
        return p

    # search under the ComfyUI custom_nodes tree (handles NIMnodes / comfyui_nim naming)
    roots = []
    if os.environ.get("COMFYUI_DATABASE"):
        roots.append(os.environ["COMFYUI_DATABASE"])
    roots += [r"G:\COMFY\ComfyUI", "."]  # SEAM: your default ComfyUI path
    for root in roots:
        hits = glob.glob(os.path.join(root, "custom_nodes", "**", EXAMPLE_FILENAME),
                         recursive=True)
        if hits:
            return Path(hits[0])
    sys.exit(
        f"Couldn't find {EXAMPLE_FILENAME} under custom_nodes. "
        f"Pass it explicitly with --workflow."
    )


def is_api_format(d: Any) -> bool:
    """API format = top-level dict of {node_id: {'class_type': ..., 'inputs': ...}}."""
    if not isinstance(d, dict) or not d:
        return False
    sample = next(iter(d.values()))
    return isinstance(sample, dict) and "class_type" in sample


def load_api_workflow(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))

    if is_api_format(raw):
        return raw

    # UI graph -> try the Comfy-Cozy converter; otherwise instruct.
    try:
        # SEAM: wire your real loader/converter here if you'd rather not export
        # API format by hand. The repo already has a to_api_json() path.
        from agent.tools.workflow_patch import ui_graph_to_api  # type: ignore
        return ui_graph_to_api(raw)
    except Exception:
        sys.exit(
            f"{path.name} looks like a UI graph, not API format.\n"
            f"In ComfyUI: Settings -> enable Dev mode -> open it -> "
            f"'Save (API Format)', then re-run with --workflow on that file."
        )


# ---------------------------------------------------------------------------
# introspect + patch
# ---------------------------------------------------------------------------

def classify(workflow: dict) -> dict[str, list[str]]:
    """Map each NIM role to the node ids present, and print the real class_types."""
    buckets = {"install": [], "load": [], "generate": [], "other": []}
    print("\n── node inventory (class_type → id) ──")
    for node_id, node in workflow.items():
        cls = node.get("class_type", "?")
        if cls in NIM_INSTALL_NODES or "install" in cls.lower() and "nim" in cls.lower():
            buckets["install"].append(node_id); tag = "INSTALL"
        elif cls in NIM_LOAD_NODES or ("load" in cls.lower() and "nim" in cls.lower()):
            buckets["load"].append(node_id); tag = "LOAD"
        elif cls in NIM_GENERATE_NODES or ("flux" in cls.lower() and "nim" in cls.lower()) \
                or "nimflux" in cls.lower():
            buckets["generate"].append(node_id); tag = "GENERATE"
        else:
            buckets["other"].append(node_id); tag = ""
        print(f"  {cls:<28} {node_id:<6} {tag}")

    print("\n── paste these into nim_lifecycle.py if they differ ──")
    for role, key in (("install", "NIM_INSTALL_NODES"),
                      ("load", "NIM_LOAD_NODES"),
                      ("generate", "NIM_GENERATE_NODES")):
        names = sorted({workflow[i]["class_type"] for i in buckets[role]})
        status = "✓" if names else "✗ NOT FOUND — fix the heuristic / check /object_info"
        print(f"  {key} = {set(names) or '{}'}   {status}")
    return buckets


def snap_dim(v: int) -> int:
    return min(VALID_DIMS, key=lambda d: abs(d - v))


def patch(workflow: dict, buckets: dict, *, prompt: str, seed: int,
          width: int, height: int, steps: int, cfg: float) -> None:
    w, h = snap_dim(width), snap_dim(height)
    if (w, h) != (width, height):
        print(f"\nnote: snapped size to valid NIM dims {w}x{h}")

    for gid in buckets["generate"]:
        ins = workflow[gid].setdefault("inputs", {})
        ins.update(prompt=prompt, seed=seed, width=w, height=h,
                   steps=steps, cfg_scale=cfg)

    for lid in buckets["load"]:
        ins = workflow[lid].setdefault("inputs", {})
        ins.setdefault("operation", "Start")
        ins["offloading_policy"] = "None"   # best perf on 24GB+; 4090 qualifies

    if not buckets["generate"]:
        sys.exit("No NIM generate node found — can't set the prompt. Fix detection first.")


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

def _show(label: str, r) -> None:
    print(f"\n[{label}] ok={r.ok} phase={r.phase.value} "
          f"warmup={r.warmup_seconds}s cook={r.cook_seconds}s")
    if r.images:
        print(f"        images: {r.images}")
    if r.reason:
        print(f"        reason: {r.reason}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", default=None)
    ap.add_argument("--prompt", default="a cinematic portrait, golden hour, 85mm")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--cfg", type=float, default=3.5)
    ap.add_argument("--model", default="flux-dev")
    ap.add_argument("--dry-run", action="store_true",
                    help="detect + patch only; skip the actual run")
    args = ap.parse_args()

    wf_path = find_workflow(args.workflow)
    print(f"workflow: {wf_path}")
    workflow = load_api_workflow(wf_path)

    # --- preflight (read-only gate) ---
    pre = nim_preflight(args.model)
    print(f"\npreflight: pack_present={pre.node_pack_present} "
          f"vram_free={pre.vram_free_gb}GB precision={pre.recommended_precision} "
          f"warm={pre.warm} comfy_alive={pre.comfy_alive}")
    if pre.note:
        print(f"  → {pre.note}")

    buckets = classify(workflow)
    patch(workflow, buckets, prompt=args.prompt, seed=args.seed,
          width=args.width, height=args.height, steps=args.steps, cfg=args.cfg)

    if args.dry_run:
        gen = buckets["generate"][0]
        print(f"\n[dry-run] generate node {gen} inputs now: "
              f"{json.dumps(workflow[gen]['inputs'], indent=2)}")
        print("[dry-run] detection + patch look good. Re-run without --dry-run for the real test.")
        return

    if not pre.node_pack_present:
        sys.exit("\nNIM node pack not installed/visible — do the install steps first.")

    # --- COLD: forces the container pull (first run is slow, by design) ---
    print("\n=== COLD RUN (expect a long warmup while the container pulls) ===")
    r_cold = nim_run(workflow, model=args.model)
    _show("cold", r_cold)

    print(f"\nwarm-state after cold run: {nim_state(args.model)}")

    # --- WARM: same call; the wrapper auto-picks the short warmup budget ---
    print("\n=== WARM RUN (container already live; warmup should collapse) ===")
    r_warm = nim_run(workflow, model=args.model)
    _show("warm", r_warm)

    # --- the proof ---
    print("\n────────── cold → warm ──────────")
    print(f"  cold warmup: {r_cold.warmup_seconds:>7}s")
    print(f"  warm warmup: {r_warm.warmup_seconds:>7}s")
    if r_cold.ok and r_warm.ok and r_warm.warmup_seconds < r_cold.warmup_seconds:
        print("  ✓ warmup collapsed on the warm run — wrapper is doing its job.")
    else:
        print("  ⚠ inspect above: one run failed or warmup didn't drop. Check the seams.")


if __name__ == "__main__":
    main()
