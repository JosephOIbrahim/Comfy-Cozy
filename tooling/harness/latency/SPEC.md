# SPEC — Comfy-Cozy whole-pipeline latency (LTX 2.3 / RTX 4090)

> Status: **SKETCH in progress.** Reference-workload block filled (Phase 0 ratified 2026-06-03).
> Numeric targets intentionally **blank** — the bar forbids targets before the baseline split is
> measured. Targets become `baseline − X%` or an absolute ceiling *after* CHAMPION.md holds a real
> split + noise band.
>
> Lives in `tooling\harness\latency\` to avoid clobbering the committed K+S tool-layer trial's
> SPEC/CHAMPION/LOG in the parent folder.

## Outcome (what's true when this ships)
The same fixed LTX 2.3 workflow, run from Comfy-Cozy on the 4090, completes
prompt→finished-video in <FILL: target total, set AFTER baseline> on the warm path,
with the cold path no worse than <FILL>, and the agent-dispatch share held under <FILL>%.

## Reference workload (frozen — the champion's recipe)  ← ratified Phase 0
- Workflow (`$wf`): `G:\COMFY\ComfyUI\user\default\workflows\video_ltx2_3_t2v_STABLE.json`
  (API format, 28 nodes; lives in the ComfyUI install, NOT in the Comfy-Cozy repo —
  `G:\Comfy-Cozy\workflows\` holds only `.gitkeep`; the in-repo `agent/templates/video_ltx2.json`
  is an unrelated 2B v0.9.5 starter and is NOT the reference.)
- Execute command (live-verified): `agent orchestrate "<wf>"` (positional path; `-s`, `-v`).
  Prints `Queued as {prompt_id}` at `cli.py:561`.
- Model + quant: LTX 2.3, checkpoint `ltx-2.3-22b-dev.safetensors`.
  **On-disk reality (verified): 44 GB full-precision — NOT FP8.** With the gemma text encoder
  (9 GB), distilled LoRA (7.25 GB) and spatial upscaler (0.95 GB), the graph pulls **~61 GB of
  weights against a 24 GB 4090** → it runs via ComfyUI weight-offload into 128 GB system RAM, not
  VRAM-resident. (FP8 vs full is therefore a live Line-C lever, not a given. Files under
  `G:\COMFYUI_Database\Models\`.)
- Text encoder `gemma_3_12B_it_fp4_mixed.safetensors` (FP4 mixed) via `LTXAVTextEncoderLoader`
  (`267:243`); distilled LoRA `ltx-2.3-22b-distilled-lora-384.safetensors` @ strength 0.5
  (`267:232`); spatial upscaler `ltx-2-spatial-upscaler-x2-1.0.safetensors` (`267:233`).
- Resolution: base latent **640×360** → `LTXVLatentUpsampler` x2 → final **1280×720**
  (720 is not ÷32; graph marked STABLE so Comfy accepts it — flagged, not blocking).
- Frames: **33**   FPS: **24**  (≈1.38 s clip)
- Steps: distilled few-step — **3** base (ManualSigmas `267:211`: `0.85,0.7250,0.4219,0.0`) +
  **8** refine (`267:252`); CFG **1** (both CFGGuiders). Samplers `euler_ancestral_cfg_pp` (base) /
  `euler_cfg_pp` (refine).
- Audio: **ON** — single forward pass A/V (`LTXVEmptyLatentAudio` → `LTXVConcatAVLatent` →
  `LTXVSeparateAVLatent` → `LTXVAudioVAEDecode` → `CreateVideo`). Cannot be cheaply skipped.
- VAE decode: `VAEDecodeTiled` — tile_size 768, overlap 64, temporal_overlap 4, temporal_size 4096
  (`267:251`).
- Seeds: fixed — **42** (`267:216`) + **23** (`267:237`) so inference time is comparable run-to-run.
- t2v gate: `PrimitiveBoolean "Switch to Text to Video?" = true` (`267:201`) bypasses both
  `LTXVImgToVideoInplace` nodes. A `LoadImage` node (`269`) references
  `lumberjack_in_the_city_…png` — present in `ComfyUI\input` (verified), so LoadImage will not
  error even though its branch is bypassed. (Confirm `validate_before_execute` passes once ComfyUI
  is up, before the cold run.)

## Acceptance predicates (the checkable bar — measured, not felt)
AP1  Baseline split measured: COLD / DISPATCH / INFERENCE sizes recorded in CHAMPION.md.
AP2  Benchmark is reproducible: same config → same number within <FILL: noise band, e.g. ±5%>
    across N≥5 runs.
AP3  Warm-path total ≤ <FILL>.   (p50 and p95 both reported.)
AP4  Cold-path total ≤ <FILL>.
AP5  Agent-dispatch share ≤ <FILL>% of warm total.
AP6  No quality regression vs champion at equal config (Line C changes only).
AP7  No new regression: every promoted change re-checks the OTHER two buckets didn't worsen.

## Out of scope
- Multi-GPU / cloud burst (roadmap Option D, a different trial).
- Replacing ComfyUI's executor (Option B — Rust shim — a separate, later harness).
- ComfyUI-internal allocator behaviour beyond what keep-warm can influence.

## Falsification conditions (what would prove the approach wrong)
- The measured split shows >90% of warm latency is INFERENCE and inference is already at the FP4
  quality floor → the agent layer cannot deliver the win; the lever is the model, not Comfy-Cozy.
- Cold-start is dominated by ComfyUI model load that warmup cannot preempt (Dynamic VRAM already
  keeps it resident) → Line A is a no-op; retire it.
- Dispatch is already <5% of total → Line B is near floor before it starts; don't grind it.
