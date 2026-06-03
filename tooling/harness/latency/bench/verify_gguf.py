import glob
import json
import os

WF = r"G:\COMFY\ComfyUI\user\default\workflows"
for wf in sorted(glob.glob(os.path.join(WF, "*_GGUF.json"))):
    g = json.load(open(wf, encoding="utf-8"))
    base = os.path.basename(wf)
    if isinstance(g, dict) and any(isinstance(v, dict) and "class_type" in v for v in g.values()):
        has = any(v.get("class_type") == "UnetLoaderGGUF" for v in g.values() if isinstance(v, dict))
        print(f"  [API      gguf_node={has}] {base}")
        continue
    subs = g.get("definitions", {}).get("subgraphs", [])
    out = []
    for s in subs:
        gguf = sum(1 for n in s.get("nodes", []) if n.get("type") == "UnetLoaderGGUF")
        cks = [n for n in s.get("nodes", []) if n.get("type") == "CheckpointLoaderSimple"]
        cleared = all(not (n.get("outputs", [{}])[0].get("links")) for n in cks) if cks else "n/a"
        # any link originates from the gguf node?
        gids = {n["id"] for n in s.get("nodes", []) if n.get("type") == "UnetLoaderGGUF"}
        linked = any(L.get("origin_id") in gids for L in s.get("links", []))
        out.append(f"gguf={gguf} ckpt={len(cks)} model_cleared={cleared} gguf_linked={linked}")
    print(f"  [SUBGRAPH {' | '.join(out)}] {base}")
