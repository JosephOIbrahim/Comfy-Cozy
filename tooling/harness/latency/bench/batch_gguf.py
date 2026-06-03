"""batch_gguf.py — propagate the GGUF DiT swap across LTX-2.3-22B dev/dev-fp8 workflows.

For every API-format workflow that loads ltx-2.3-22b-dev[-fp8].safetensors via CheckpointLoaderSimple
and feeds its MODEL output (index 0) to the sampler, insert UnetLoaderGGUF(LTX-2.3-dev-Q4_K_S.gguf)
and rewire that one model edge. CheckpointLoaderSimple stays (cheap, supplies VAE/CLIP). Audio/text
loaders untouched (slice loads). Writes <stem>_GGUF.json; ORIGINALS ARE NEVER MODIFIED. UI-format or
non-standard graphs are skipped and reported for the agent team to handle.
"""
import glob
import json
import os

WF_DIR = r"G:\COMFY\ComfyUI\user\default\workflows"
GGUF = "LTX-2.3-dev-Q4_K_S.gguf"
TARGETS = {"ltx-2.3-22b-dev.safetensors", "ltx-2.3-22b-dev-fp8.safetensors"}
SKIP = {"video_ltx2_3_t2v_GGUF_Q4.json"}


def is_api(g):
    return isinstance(g, dict) and any(
        isinstance(v, dict) and "class_type" in v for v in g.values()
    )


def consumers_of(g, src_id):
    out = []
    for nid, node in g.items():
        if not isinstance(node, dict):
            continue
        for k, v in node.get("inputs", {}).items():
            if isinstance(v, list) and len(v) == 2 and str(v[0]) == str(src_id) and v[1] == 0:
                out.append((nid, k))
    return out


results = []
for wf in sorted(glob.glob(os.path.join(WF_DIR, "*.json"))):
    base = os.path.basename(wf)
    if base in SKIP or base.endswith("_GGUF.json"):
        continue
    try:
        g = json.load(open(wf, encoding="utf-8"))
    except Exception:
        continue
    txt = json.dumps(g)
    if not any(t in txt for t in TARGETS):
        continue
    if not is_api(g):
        results.append((base, "SKIP-UI-format", "agent-team handles"))
        continue
    ckpts = [nid for nid, n in g.items()
             if isinstance(n, dict) and n.get("class_type") == "CheckpointLoaderSimple"
             and n.get("inputs", {}).get("ckpt_name") in TARGETS]
    new_g = json.loads(txt)
    swaps = 0
    gi = 0
    for ck in ckpts:
        cons = consumers_of(new_g, ck)
        if not cons:
            continue
        gid = f"gguf_dit_{gi}"
        gi += 1
        new_g[gid] = {"class_type": "UnetLoaderGGUF",
                      "_meta": {"title": "GGUF DiT (Q4_K_S)"},
                      "inputs": {"unet_name": GGUF}}
        for nid, k in cons:
            new_g[nid]["inputs"][k] = [gid, 0]
        swaps += 1
    if swaps == 0:
        results.append((base, "SKIP-no-DiT-model-edge", "model loaded elsewhere / output unused"))
        continue
    dst = os.path.join(WF_DIR, base[:-5] + "_GGUF.json")
    json.dump(new_g, open(dst, "w", encoding="utf-8"), indent=2)
    results.append((base, "OK", f"{swaps} swap -> {os.path.basename(dst)}"))

for b, s, n in sorted(results):
    print(f"  [{s:24s}] {b}   {n}")
ok = [r for r in results if r[1] == "OK"]
print(f"\n{len(ok)} variants written, {len(results) - len(ok)} need agent-team attention")
