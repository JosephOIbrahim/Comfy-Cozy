# GLOBAL LATENCY PLAN — Comfy-Cozy (RTX 4090)

> The single technique that wins everywhere: **resident GGUF Q4 DiT via city96 `UnetLoaderGGUF`**,
> + the global flag **`--use-sage-attention`**. Proven: LTX-2.3-22B-dev = **15.5×** (1047.9s → 67.5s
> cold / 46.0s warm), model resident at 15.4 GB. Inventory: 92 workflows, but only a handful of
> distinct oversized models — fix the model once, every workflow using it inherits the win.

## Tier 1 — GLOBAL (one switch, all 92 workflows)
- **`--use-sage-attention`** launch flag. Status: validating (cold pays a one-time Triton JIT compile;
  warm is the real number — see LOG). Keep iff warm beats 46.0s with no quality regression.
- **`torch.compile` (±CUTLASS GEMM)** — incremental, per-model — see `CUTLASS_PLAN.md`.

## Tier 2 — PER-MODEL GGUF swap (propagates to all workflows using that model)
Same one-edge rewire every time: replace the oversized checkpoint/diffusion loader with
`UnetLoaderGGUF(<file>.gguf)`; keep VAE / text-encoder / LoRA / sampler wiring. Place .gguf in models/unet.

| Model family | # wf | Resident GGUF (Q4) | GB | On disk | Status |
|---|---|---|---|---|---|
| **LTX-2.3-22B dev / dev-fp8** | **20** | `LTX-2.3-dev-Q4_K_S.gguf` | 15.9 | ✅ | **DONE (15.5×), applied** |
| LTX-2.3-22B distilled | 4 | unsloth `…distilled-UD-Q4_K_M.gguf` | 16.3 | ❌ | download 16.3 GB |
| LTX-2 19B (older) | ~9 | QuantStack `LTX-2-dev-Q4_K_M.gguf` | 13.4 | ❌ | dl + ComfyUI-GGUF PR#399 + own gemma/connector/VAE |
| WAN 2.2 A14B (MoE) | several | QuantStack High+Low `Q4_K_S` | 8.75 ea (1 resident) | ❌ | dl ~19.5 GB + wan_2.1_vae |
| Qwen-Image-Edit-2511 | several | unsloth `…2511-Q4_K_M.gguf` | 13.2 | ❌ | dl + qwen2.5-vl enc + qwen vae |

All four off-disk families: **fit 24 GB at Q4, all use `UnetLoaderGGUF`** (full recipes + sources in
`bench/` research result). NVFP4 ruled out on Ada everywhere; all-in-one fp8 >24 GB OOMs everywhere.

## Tier 3 — already-resident models (no swap, sage only)
13B-distilled-fp8 (14.6 GB ×15 wf), gemma/t5/umt5 encoders, SDXL, LoRAs, VAEs, upscalers — already fit.

## Execution (long-running, benchmark-gated harness)
The GPU is one card → benchmarks are SERIAL; the harness checkpoints and works the queue. The parallel
part (DONE) was the distributed research (4 family-scouts). Remaining loop, per model family:
1. (gated) provision the GGUF + any missing encoder/VAE (network → Joe's OK).
2. FORGE: one-edge rewire of the workflows using it (deterministic; spot-validate structure).
3. CRUCIBLE: cold+warm benchmark on a representative workflow; same-seed quality A/B to Joe.
4. GATE: promote (update CHAMPION/benchmark_log) or DEAD-END.
- **Reusable capability:** `bench/build_gguf.py` generalizes to "given a workflow + model→GGUF map,
  emit the swapped variant." That is the durable "optimize any workflow" tool.

## Priorities (CTO recommendation)
1. **Settle sage** (warm number) → if win, it's free global speed for everything.
2. **Propagate the on-disk LTX-2.3-dev GGUF** to the 20 dev/dev-fp8 workflows (no download). Biggest
   no-cost global win after the one already applied.
3. **Distilled-22B GGUF** (16.3 GB dl) — fixes the 4 distilled workflows; you run these.
4. WAN / Qwen / 19B — provision on demand when you want those families (downloads).
5. CUTLASS / torch.compile — polish pass on the hot models, after the above.

## Constraints carried
agent\stage\ freeze (Jun 16); no git push; network/downloads need Joe's OK; every promotion is
benchmarked + same-seed quality-checked; CUTLASS/sage cold compile-tax reported separately from warm.
