"""subgraph_gguf.py — subgraph-aware GGUF DiT swap for ComfyUI 0.23 UI workflows.

These workflows wrap the pipeline in definitions.subgraphs[]. Inside, CheckpointLoaderSimple loads
the oversized LTX-2.3-22B dev/dev-fp8 model and its MODEL output (slot 0) feeds the sampler. We add a
UnetLoaderGGUF node INSIDE the subgraph and repoint the MODEL link(s) to it, leaving CheckpointLoaderSimple
for its VAE. Writes <stem>_GGUF.json; ORIGINALS NEVER MODIFIED. Link format: object
{id,origin_id,origin_slot,target_id,target_slot,type}; node outputs[].links lists link ids.
"""
import glob
import json
import os
import sys

WF_DIR = r"G:\COMFY\ComfyUI\user\default\workflows"
GGUF = "LTX-2.3-dev-Q4_K_S.gguf"
TARGETS = {"ltx-2.3-22b-dev.safetensors", "ltx-2.3-22b-dev-fp8.safetensors"}


def rewrite(path):
    g = json.load(open(path, encoding="utf-8"))
    defs = g.get("definitions", {})
    subs = defs.get("subgraphs", []) if isinstance(defs, dict) else []
    if not subs:
        return ("no-subgraphs", 0)
    swaps = 0
    for s in subs:
        nodes = s.get("nodes", [])
        links = s.get("links", [])
        if not nodes:
            continue
        maxid = max([n.get("id", 0) for n in nodes] + [0])
        for ck in list(nodes):
            if ck.get("type") != "CheckpointLoaderSimple":
                continue
            wv = ck.get("widgets_values") or []
            if not wv or wv[0] not in TARGETS:
                continue
            outs = ck.get("outputs", [])
            if not outs:
                continue
            model_out = outs[0]  # MODEL = slot 0
            model_links = list(model_out.get("links") or [])
            if not model_links:
                continue  # MODEL unused (only VAE/CLIP) -> nothing to swap
            maxid += 1
            gid = maxid
            cpos = ck.get("pos", [0, 0])
            nodes.append({
                "id": gid, "type": "UnetLoaderGGUF",
                "pos": [cpos[0], cpos[1] - 130], "size": [290, 60], "flags": {},
                "order": ck.get("order", 0), "mode": 0, "inputs": [],
                "outputs": [{"name": "MODEL", "type": "MODEL", "links": model_links, "slot_index": 0}],
                "properties": {"Node name for S&R": "UnetLoaderGGUF", "cnr_id": "ComfyUI-GGUF"},
                "widgets_values": [GGUF],
            })
            for L in links:
                if L.get("id") in model_links and L.get("origin_id") == ck.get("id"):
                    L["origin_id"] = gid
                    L["origin_slot"] = 0
            model_out["links"] = []
            swaps += 1
    if swaps == 0:
        return ("no-target-ckpt-MODEL-edge", 0)
    json.dump(g, open(path[:-5] + "_GGUF.json", "w", encoding="utf-8"), indent=2)
    return ("OK", swaps)


files = sys.argv[1:]
if not files:
    for wf in sorted(glob.glob(os.path.join(WF_DIR, "*.json"))):
        if wf.endswith("_GGUF.json"):
            continue
        try:
            txt = open(wf, encoding="utf-8").read()
        except OSError:
            continue
        if any(t in txt for t in TARGETS) and '"subgraphs"' in txt:
            files.append(wf)

ok = 0
for wf in files:
    try:
        status, n = rewrite(wf)
    except Exception as e:
        status, n = f"ERR:{type(e).__name__}:{e}", 0
    if status == "OK":
        ok += 1
    print(f"  [{status:28s}] {os.path.basename(wf)}  swaps={n}")
print(f"\n{ok}/{len(files)} subgraph workflows -> _GGUF variants written")
