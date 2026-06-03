"""build_fp8.py — controlled FP8 variant of the champion graph.

Single variable vs champion (video_ltx2_3_t2v_STABLE.json): swap the 3 loader ckpt_name fields
44GB full-precision -> 27.8GB fp8. Everything else (seeds 42/23, prompt, res, steps) held.
"""
import json

SRC = r"G:\COMFY\ComfyUI\user\default\workflows\video_ltx2_3_t2v_STABLE.json"
DST = r"G:\Comfy-Cozy\tooling\harness\latency\bench\wf_fp8.json"
FP8 = "ltx-2.3-22b-dev-fp8.safetensors"
LOADER_NODES = ("267:236", "267:221", "267:243")  # checkpoint, audio-VAE, text-enc

with open(SRC, encoding="utf-8") as f:
    g = json.load(f)

for nid in LOADER_NODES:
    old = g[nid]["inputs"]["ckpt_name"]
    g[nid]["inputs"]["ckpt_name"] = FP8
    print(f"{nid}: {old} -> {g[nid]['inputs']['ckpt_name']}")

print("control seeds: 267:216 =", g["267:216"]["inputs"]["noise_seed"],
      "| 267:237 =", g["267:237"]["inputs"]["noise_seed"])

with open(DST, "w", encoding="utf-8") as f:
    json.dump(g, f, indent=2)
print("WROTE", DST)
