# CUTLASS UTILIZATION PLAN — Comfy-Cozy / RTX 4090

> Requested by Joe 2026-06-03. Benchmark-gated per the harness. Honest bounds up front.

## 0. What CUTLASS is (and what it is NOT, here)
- **Verified install:** CUTLASS **4.5.1** C++ source at `D:\OptimizerV9\cutlass` (env `CUTLASS_PATH`
  set; also a copy on Desktop), CUDA toolkit **13.2** (`nvcc` present), torch **2.9.1+cu130** with
  `torch.compile`=True and Inductor `config.cuda.cutlass_dir` attr present. The path is real.
- CUTLASS is a **header/template library of high-performance tensor-core GEMM/conv kernels.** It is
  **NOT** a global ComfyUI "on" switch. It enters inference one of three ways:
  1. **`torch.compile` + Inductor CUTLASS GEMM backend** — autotunes the model's matmuls with CUTLASS
     kernels at compile time. ← the realistic "across workflows" lever.
  2. **CUTLASS Python DSL custom kernels** (the `python/` dir) — bespoke fused kernels. High effort.
  3. **TensorRT** engines (CUTLASS-backed internally) — per-model, heavy build.
- **Honest ceiling on a 4090 (Ada):** CUTLASS shines at bf16/fp16/int8 and **fp8** GEMM (Ada has fp8
  tensor cores). It has **no fp4 hardware** — the headline CUTLASS fp4 wins are Blackwell-only. So on
  this card CUTLASS is a **polish layer (~5–25% on matmul-bound DiT compute), quality-neutral (same
  math)** — NOT a step-change like GGUF (15.5×) or the resident-fit fix. The big wins are already banked.

## 1. Interaction with the current champion (important)
The champion is now a **GGUF Q4** model. `torch.compile`/CUTLASS autotunes **standard GEMM**; the GGUF
path runs a **custom dequant→bf16 matmul**, which Inductor may not trace cleanly. So CUTLASS likely
applies **best to RESIDENT fp16/fp8 models** (clean GEMM) and to the **bf16 matmul after dequant**.
This is the key empirical question Phase 2 answers. Do not assume CUTLASS stacks on GGUF for free.

## 2. Baselines to beat (measured)
- GGUF Q4 (LTX-2.3-dev) cold **67.5 s**, warm **46.0 s** (±0.4%). fp16 1047.9 s. Sage-attn delta: TBD.
- Gate: a CUTLASS config promotes only if it beats the warm 46.0 s **outside noise** with **zero
  quality regression** (same seed A/B) and the OTHER buckets don't worsen.

## 3. Phased plan (each phase is a benchmark-gated experiment)

**Phase A — torch.compile (Inductor DEFAULT backend) on the DiT.** Lowest-risk speed; isolates the
compile win before adding CUTLASS. Wrap the diffusion model in `torch.compile(mode="max-autotune")`
(via ComfyUI `--fast`, or a TorchCompileModel node, or model_patch). Measure cold(1st=compile cost)
+ warm. Expect 10–30% on warm. Watch: first-run compile latency (minutes), GGUF-trace failures.

**Phase B — Inductor CUTLASS GEMM backend.** Set `torch._inductor.config.cuda.cutlass_dir =
"D:/OptimizerV9/cutlass"` and `max_autotune_gemm_backends="CUTLASS,ATEN"`. Re-measure vs Phase A.
This is the actual CUTLASS lever. Keep only if it beats default Inductor outside noise.

**Phase C — apply where it helps most: a RESIDENT fp8 model (not GGUF).** Test CUTLASS autotune on a
clean-GEMM fp8 model (e.g. a 14B WAN fp8 that fits, once provisioned) where the dequant confound is
absent. This tells us whether CUTLASS belongs on the fp8 track vs the GGUF track.

**Phase D — SageAttention 2.x (CUTLASS fp8 attention).** Current is 1.0.6 (Triton int8). 2.x uses
CUTLASS fp8 attention kernels. Evaluate upgrade on Win/py3.14 (build risk high) — gated, optional.

**Phase E — TensorRT per-model engines (CUTLASS-backed).** Biggest potential, heaviest. ComfyUI TRT
path; per-model engine build. Out-of-band, only for a hot, frozen, high-volume workflow.

## 4. "Across all workflows" — the honest shape
`torch.compile`+CUTLASS is applied **per model** (compile the DiT), not as one switch. It is "global"
in that the same wrapper fits any matmul-heavy model, but each family needs its own compile+benchmark
pass, and the win interacts with the quant choice. The **truly global** speed levers remain:
1. **GGUF Q4 resident** (15.5×) — done for LTX-2.3, recipes ready for all families (see GLOBAL_PLAN).
2. **Sage attention** (`--use-sage-attention`, one flag, all workflows) — measuring.
3. **torch.compile (±CUTLASS)** — incremental, per-model — this plan.

## 5. Risks / dead-end guards
- Win/py3.14/torch2.9 + Inductor CUTLASS is bleeding-edge — expect build/trace failures; cap retries.
- CUTLASS autotune over GGUF dequant may no-op or error → that is a finding, not a failure.
- Any compile config that fails the same-seed quality A/B is rejected (same rule as quant changes).
- Compile cost is a COLD tax; report cold(compile) vs warm separately — never hide it.
