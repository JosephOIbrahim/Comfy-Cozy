# DEADENDS — latency trial (pre-seeded + appended)

Read before proposing. Do not re-discover these.

## Measured dead-ends
- **DEAD-END | fp8-dev-allinone swap | OOM @ 267:215 | torch.OutOfMemoryError in fp8 dequant path**
  (comfy_kitchen/fp8.py). The 27.8GB fp8 all-in-one needs MORE peak VRAM than the 44GB fp16 because
  fp8 weights dequantize to bf16 for compute (~2x transient). fp16's mature streaming-offload completes
  (1047.9s); fp8 OOMs after ~1205s. Smaller file, worse outcome. (prompt c269d3b2)
- **DEAD-END | warm keep-resident (44GB) | thrash | >1800s** — a 2nd seed-varied gen with the 44GB model
  pinned has no VRAM for activations -> thrashes slower than cold. No cheap warm path for an unfitted model.
- **DEAD-END | identical-seed re-run as "warm" benchmark | 0.265s | ComfyUI node-cache hit = 0 compute**.
  Lab-green only; vary the seed to measure a real warm render.

## Pre-seeded traps (from scout + recon)
- **NVFP4 on RTX 4090 (Ada)** — fits (21.7GB) but Blackwell-only HW accel; software-emulated on Ada,
  ~2x SLOWER than fp8. Do NOT pursue NVFP4 on this card. (Lightricks/LTX-2.3-nvfp4)
- **int8 (~29GB), MXFP8mixed (29.7GB), fp8 all-in-one (27.8GB)** — all exceed 24GB. Skip.
- **agent orchestrate** — Step-2 validate_before_execute false-positives on ComfyMathExpression
  `values.a` dynamic inputs -> Exit(1) before executing. Use poll-path execute_workflow (run_once.py).
- **execute_workflow timeout (900s default) & circuit breaker (3 poll-timeouts)** — both abort the agent
  on long/heavy renders while ComfyUI keeps going. Measure via /history directly for >900s renders.
- **/free {unload_models,free_memory}** — does NOT reclaim the resident model on this build; a clean-cold
  state needs a ComfyUI process restart. Post-OOM, torch holds a 38.9GB oversubscribed pool.

## Out-of-software-scope (escalations, not iterations)
- T_execute (the dominant 99.8%) is model/VRAM-bound. Comfy-Cozy code cannot reduce it. The levers are
  the MODEL (resident quant: GGUF Q4) or HARDWARE (bigger VRAM / Blackwell for NVFP4) — the latter is
  board/capital allocation.

## 2026-06-03 (global phase)
- **DEAD-END | --use-sage-attention on LTX-2.3 GGUF | warm 135.96s vs 46.0s | 2.96x REGRESSION**.
  SageAttention 1.0.6 = Triton int8 attention tuned for long LLM sequences; the int8 quant overhead
  dominates for LTX video attention shapes on Ada. NOT a global win. Reverted. (May still help
  long-sequence / high-res models — re-test per family, never assume global.)
