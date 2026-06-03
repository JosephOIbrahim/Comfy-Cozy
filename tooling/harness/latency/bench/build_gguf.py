"""build_gguf.py — GGUF-DiT variant of the champion graph (one-edge swap).

Adds UnetLoaderGGUF(LTX-2.3-dev-Q4_K_S.gguf) and rewires ONLY the LoraLoaderModelOnly (267:232)
model input from CheckpointLoaderSimple[0] -> the GGUF DiT. Everything else (CheckpointLoaderSimple
kept for the video VAE, audio/text loaders, distilled LoRA, seeds 42/23) is unchanged.
Single variable vs champion: the DiT goes from 44GB fp16 (offloaded) to 15.9GB Q4 (resident).
"""
import json

SRC = r"G:\COMFY\ComfyUI\user\default\workflows\video_ltx2_3_t2v_STABLE.json"
DST = r"G:\Comfy-Cozy\tooling\harness\latency\bench\wf_gguf.json"
GGUF_FILE = "LTX-2.3-dev-Q4_K_S.gguf"
GGUF_NODE = "300"
GGUF_FIELD = "unet_name"  # city96 UnetLoaderGGUF input; verified vs get_node_info before run

with open(SRC, encoding="utf-8") as f:
    g = json.load(f)

g[GGUF_NODE] = {
    "class_type": "UnetLoaderGGUF",
    "_meta": {"title": "GGUF DiT (Q4_K_S)"},
    "inputs": {GGUF_FIELD: GGUF_FILE},
}

old = g["267:232"]["inputs"]["model"]
g["267:232"]["inputs"]["model"] = [GGUF_NODE, 0]
print("added UnetLoaderGGUF node", GGUF_NODE, "->", GGUF_FILE)
print("rewired 267:232 (LoraLoaderModelOnly).model:", old, "->", g["267:232"]["inputs"]["model"])

with open(DST, "w", encoding="utf-8") as f:
    json.dump(g, f, indent=2)
print("WROTE", DST)
