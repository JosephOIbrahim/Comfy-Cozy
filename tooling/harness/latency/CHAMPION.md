# CHAMPION.md — LTX 2.3 / RTX 4090 latency

> Promote on benchmarked win outside noise AND no quality regression (AP6). Speed is proven;
> quality (AP6) is the open gate held for Joe.

## 🏆 CHAMPION — GGUF Q4 resident  (AP6 QUALITY APPROVED by Joe 2026-06-03: "can barely tell the difference")
> APPLIED: saved as `G:\COMFY\ComfyUI\user\default\workflows\video_ltx2_3_t2v_GGUF_Q4.json`.
> MAX-SPEED in progress: next lever = `--use-sage-attention` (sageattention installed; ComfyUI currently
> launched without it). Re-measuring with sage attention to push below 67.5s.

- **config_id:** `gguf-dev-Q4_K_S-resident`
- **DiT:** `LTX-2.3-dev-Q4_K_S.gguf` (15.9 GB) via `UnetLoaderGGUF` (city96 ComfyUI-GGUF).
- **Cold exec (/history): 67.476 s**  vs fp16 champion **1047.887 s  →  15.53× faster.**
- **VRAM: torch reserved 15.4 GB (< 24 GB) → FULLY RESIDENT, zero offload.** (the mechanism)
- Per-node: `267:215` base DiT **1,023,880 ms → 40,682 ms (25× collapse)**; refine 15 s; GGUF load
  400 ms; distilled-LoRA-on-GGUF 160 ms (compat ✓); VAE decode 1.9 s. total 67.3 s.
- Output: `LTX_2.3_t2v_00005_.mp4`, seeds 42/23 (same as champion → clean A/B vs `00004.mp4`).
- prompt_id 4a501be2. Status success. N=1 cold (noise band AP2 still to do — cheap now: resident).

### Gates
- Speed win outside noise: ✅ (15.5×, decisive). · Resident/no-offload: ✅ · Completes: ✅ ·
  LoRA compat: ✅ · No frozen-path mutation: ✅ · No source change (workflow-config only): ✅
- **AP6 quality vs fp16: ⏳ PENDING JOE** — the only blocker to full promotion. fp16 remains the
  QUALITY REFERENCE until sign-off.

### Reproduce
1. Fresh ComfyUI on :8188 (clean VRAM). ComfyUI-GGUF installed; `LTX-2.3-dev-Q4_K_S.gguf` in models/unet.
2. `python tooling\harness\latency\bench\run_once.py "tooling\harness\latency\bench\wf_gguf.json" 600`
3. exec: GET /history/<id> (execution_success - execution_start)/1000.  Per-node: get_execution_profile.

## QUALITY REFERENCE (the prior champion): fp16 dev offload
- `ltx-2.3-22b-dev.safetensors` (44 GB), cold exec **1047.887 s**, offload thrash, 97.7% in 267:215.
- Output `LTX_2.3_t2v_00004_.mp4` (seeds 42/23). The bar GGUF quality must match.

## How we got here (decision trail)
- fp8 all-in-one (27.8 GB): **OOM** (dequant ~2x transient) — DEAD-END.
- NVFP4 (21.7 GB): ruled out on Ada (Blackwell-only HW; ~2× slower emulated) — DEAD-END.
- GGUF Q4 (15.9 GB, resident): **15.5× win.** ← here.
- Lever was the MODEL fitting VRAM, exactly as the split predicted; Comfy-Cozy code (dispatch <0.2%)
  was never the bottleneck.
