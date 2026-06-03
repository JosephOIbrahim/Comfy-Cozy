# LOG.md — append-only latency trial log

Every config tried, its three-bucket numbers, regressions. Tag dead ends:
`DEAD-END | <config> | <number> | <why rejected / what it regressed>`.

────────────────────────────────────────────────────────

## 2026-06-03 — Phase 0 · FRAME ratification
- Read control doc + run prompt in full. Buckets: COLD-START / AGENT-DISPATCH / INFERENCE. Mode: SIMULATED.
- `G:\Comfy-Cozy\workflows\` is empty (`.gitkeep` only). In-repo `agent/templates/video_ltx2.json`
  = old 2B v0.9.5 starter, generic nodes, no audio → NOT a valid LTX 2.3 reference.
- Real LTX graphs live in `G:\COMFY\ComfyUI\user\default\workflows\` (~40 files).
- Joe confirmed frozen `$wf` = `video_ltx2_3_t2v_STABLE.json` (22B dev, t2v, STABLE marker).
- Recipe extracted (see SPEC reference-workload block).

## 2026-06-03 — Phase 1 · LIVE-INSTALL VERIFICATION (read-only recon)
- **ComfyUI: DOWN** — `Invoke-RestMethod http://127.0.0.1:8188/system_stats` → connection refused.
  Measurement BLOCKED. (Step 1 STOP per run prompt.) system_stats VRAM + /object_info LTX-node
  loadability deferred until ComfyUI is up.
- **Models present (no substitution needed)** — under `G:\COMFYUI_Database\Models\`:
  - `ltx-2.3-22b-dev.safetensors` = **44,011 MB (full-precision, NOT fp8)**
  - `gemma_3_12B_it_fp4_mixed.safetensors` = 9,010 MB (text_encoders)
  - `ltx-2.3-22b-distilled-lora-384.safetensors` = 7,253 MB (loras)
  - `ltx-2-spatial-upscaler-x2-1.0.safetensors` = 950 MB (latent_upscale_models)
  - input PNG `lumberjack_…png` = 1.7 MB present in `G:\COMFY\ComfyUI\input\`
  - **ANOMALY:** ~61 GB total weights vs 24 GB VRAM → RAM-offload config. Cold-start likely
    dominated by disk→RAM load + RAM↔VRAM streaming. To be measured, not assumed.
- **WS vs poll (Line B):** baseline via `agent orchestrate` uses the **1.0 s POLL** path —
  `_handle_execute_workflow` (`comfy_execute.py:709`) → `_poll_completion` (`:747`, `poll_interval=1.0`).
  The WS path `_execute_with_websocket` (`:778`) is reached only by `execute_with_progress` (`:751`),
  which orchestrate does NOT call. → ≤1.0 s completion-detection tail folds into measured DISPATCH;
  Line B (B2) has headroom out of the gate.
- **Execute command:** `agent orchestrate "<wf>"` (positional; `-s`, `-v`). `cli.py:487–574`:
  Step1 load → Step2 `validate_before_execute` (EXITS if invalid) → Step3 `execute_workflow`
  (prints `Queued as {prompt_id}` `:561`) → Step4 verify. orchestrate output does NOT include
  ComfyUI exec time → INFERENCE must come from `/history`.
- **venv:** `.venv312` has `websockets 16.0`, py 3.12.10 (`agent.exe` at `.venv312\Scripts\`).
  (Harness cited requirements.txt:142 = 15.0.1 — stale; import works either way.)

### BLOCKERS held at Phase 1 gate (round 1)
1. ComfyUI must be started on `:8188` (Joe action) before any measurement. — RESOLVED (up 06-03).
2. File-collision resolved: latency trial files go in `tooling\harness\latency\` (this folder).

## 2026-06-03 — Phase 1 · LIVE half (ComfyUI up)
- **system_stats:** RTX 4090, vram_total 24,564 MB, **vram_free 23,036 MB, torch allocated 0**
  (clean COLD state — nothing resident yet). RAM 136,910 MB total / 90,343 MB free.
  ComfyUI **0.23.0**, Python 3.14.2, torch 2.9.1+cu130.
- **ComfyUI launch argv:** `main.py --reserve-vram 1.5 --fp8_e4m3fn-text-enc`
  (text encoder cast to fp8_e4m3fn at load; 1.5 GB VRAM reserved). Material to offload/quant posture.
- **Node presence:** /object_info has **2546** node types; **all 31** workflow class_types PRESENT.
  No missing nodes. (First check showed a false "missing" due to a PSCustomObject-enumeration bug;
  re-checked via -AsHashtable → all present.)
- **MCP ping:** server 5.0.0, ComfyUI reachable, 126 tools.
- **load_workflow:** 45 nodes / 65 connections, format=api, well-formed; `values.a` dynamic inputs
  wired (`267:256/259/261 <- PrimitiveInt`).
- **⚠️ VALIDATION BLOCKER (Line B finding):** `validate_before_execute(path)` → `valid:false`,
  3 errors — `ComfyMathExpression [267:256/259/261]: missing required input 'values'`.
  This is a **validator FALSE-POSITIVE** on ComfyUI dynamic dot-notation inputs (`values.a`): the
  executor flattens them, the Comfy-Cozy validator doesn't. Graph is STABLE + has a prior completed
  live render → ComfyUI runs it. BUT `agent orchestrate` Step 2 (`cli.py:544`) does
  `raise typer.Exit(1)` on `valid:false` → **orchestrate self-aborts before executing.** Cannot fix
  (no source mutation this run). The `execute_workflow` handler itself does NOT validate, so the
  poll-path execute runs; only orchestrate's pre-gate is broken.

### Phase 1 gate decision pending (Joe): which execute path drives the baseline, since orchestrate
### is blocked by its own validator. (Recon otherwise GREEN.)

## 2026-06-03 — GLOBAL PROPAGATION (Joe: "use agent teams, do #1") — DONE
- Distributed research (Workflow, 4 agents): all families -> GGUF Q4 / UnetLoaderGGUF (GLOBAL_PLAN.md).
- Sage attention: TESTED -> REJECTED (warm 135.96s = 2.96x regression). Reverted to no-sage.
- Propagation of LTX-2.3-dev GGUF swap across the dev/dev-fp8 workflows:
  - **batch_gguf.py** (API format): 3 variants (ltx2_3_new, _pilot_refactored, t2v_STABLE). RUNTIME-PROVEN:
    ltx2_3_new_GGUF ran 67.6s end-to-end.
  - Discovered 13/14 are SUBGRAPH-wrapped (definitions.subgraphs; CheckpointLoaderSimple buried inside).
    Agent fan-out wrong tool -> built **subgraph_gguf.py** (deterministic subgraph-aware rewriter):
    inserts UnetLoaderGGUF inside the subgraph, repoints the MODEL link, clears ckpt MODEL output.
  - Result: 12 subgraph variants written + verified (verify_gguf.py: gguf node added, model link repointed,
    ckpt MODEL cleared, all True). 1 skip (i2v_RTX4090 = no CheckpointLoaderSimple->MODEL edge; needs look).
  - CAVEAT: subgraph variants are STRUCTURALLY verified but NOT headless-benchmarked (no headless
    subgraph->API expansion path). Editor will use them; recommend Joe spot-checks one in the GUI.
- NOTE: a live ComfyUI browser session re-saved STABLE.json from flattened-API to UI-subgraph form mid-run
  (autosave on restart). No corruption; champion measured via bench/wf_gguf.json (independent artifact).
- Reusable capability shipped in bench/: build_gguf.py (API), subgraph_gguf.py (subgraph), verify_gguf.py,
  inventory.py, run_once.py/run_seed.py/sweep_gguf.py (benchmark). = "optimize any LTX workflow" toolkit.
- CUTLASS: located (4.5.1 @ D:\OptimizerV9\cutlass, CUDA 13.2, torch inductor cutlass backend). Plan in
  CUTLASS_PLAN.md (per-model torch.compile polish, ~5-25%, benchmark-gated; NOT a global switch).

## Runs

### COLD #1 — seed 42/23 — prompt 506179ff-7dc5-4e84-bcd0-d746daf4a73d
- Fresh ComfyUI (torch alloc 0 pre-run). Poll-path execute_workflow via run_once.py.
- **agent handler TIMED OUT at 900s** (status=timeout, 0 outputs) — but ComfyUI kept rendering.
  → **Line B correctness finding:** execute_workflow's 900s default timeout < this graph's real
  render; CLI user sees a false "timeout/failed" while ComfyUI succeeds.
- /history (keys VERIFIED live: execution_start/execution_success, ms epoch):
  start=1780502472409, success=1780503520296 → **INFERENCE_cold = 1047.887 s (~17.5 min)**.
  execution_cached nodes:[] → true cold. Output LTX_2.3_t2v_00004_.mp4 (0.54 MB) written.
- **Per-node profile (get_execution_profile, total_ms=1,047,670 ≈ /history):**
  - `267:215` SamplerCustomAdvanced (BASE DiT pass, 8-step) = **1,023,880 ms = 97.7% of total**
  - `267:219` SamplerCustomAdvanced (refine DiT pass, 3-step) = 11,931 ms
  - `267:240` CLIPTextEncode (+prompt, gemma) = 3,527 ms · `267:233` upscaler load = 1,992 ms
  - `267:251` VAEDecodeTiled = **1,328 ms** · `75` SaveVideo = 901 ms · `267:243` text-enc load = 862 ms
  - `267:236` CheckpointLoaderSimple ("load" 44GB) = **551 ms only** · `267:220` audio VAE decode = 539 ms
  - **INTERPRETATION:** the 44GB full-precision weights materialize/cast/stream-to-GPU on the
    FIRST DiT forward (267:215), not in the loader node. 1st DiT pass = 1024s, 2nd = 12s → ~85×.
    VAE decode is NOT the bottleneck (1.3s). Line C lever = DiT/model-load (FP8), not VAE.
- **Line A residency:** post-cold VRAM ~20GB occupied (4,515 MB free / 24,564), queue empty →
  ComfyUI keeps the model largely resident after a run.

### WARM #1 (cache-hit) — seed 42/23 (identical) — prompt 03796f26-...
- handler_wall=1.869s, status=complete, returned the SAME file 00004. /history exec_delta=0.265s.
- **CACHE HIT** — identical prompt+seed → ComfyUI per-node output cache → ~0 compute. NOT a real
  warm render (lab-green). Conclusion: warm renders must VARY the seed to bust the cache.
  (run_seed.py overrides 267:216/267:237 noise_seed.)

### WARM #2 (seed-varied, cache-busting) — seed 1000/1001 — prompt 300ab0a2-...
- **ANOMALY: render exceeds 30 min and was STILL RUNNING at last check** (queue running=1) — the
  agent handler timed out at 1800s; ComfyUI kept going. VRAM ~22GB used (2.3GB free) throughout.
- **Warm (seed-varied) is SLOWER than cold (1048s), not faster.** Only the seeds differ from cold,
  so compute graph is identical → the slowdown is a MEMORY-STATE effect: the cold run left ~20GB of
  the 44GB model pinned in VRAM; a second, different generation then has too little free VRAM for
  activations and THRASHES weights RAM<->VRAM every step. The 44GB full-precision 22B has no clean
  steady state in 24GB.
- **Consequence for the buckets:**
  - There is no separable, fast "warm" path for a NEW generation. Identical re-runs are free (cache,
    0.26s); any seed/prompt change pays ~full inference (>=17-30 min) due to thrash.
  - COLD-START as "cold-minus-warm" is not cleanly measurable here (warm >= cold). The dominant cost
    is the offloaded full-precision model itself, every render — which is the harness's Line-C
    territory (FP8 to fit VRAM), and partially the Line-A falsification (residency does not yield a
    cheap warm path; if anything, consecutive residency hurts).
- **DISPATCH (clean):** from the cache-hit run, handler_wall 1.869s - exec 0.265s ≈ **1.6s** agent
  overhead (queue POST + <=1s poll tail + parse). <0.2% of any real render.

### DECISION POINT (Phase 3 gate): warm renders are 17-30+ min each and pathological on consecutive
### runs. A tight N>=5 warm noise band is an hours-long GPU commitment. Surfaced to Joe.
### → Joe's call: ACCEPT COLD AS SEED CHAMPION NOW. Warm noise band deferred. 300ab0a2 interrupted.

## 2026-06-03 — Phase 3 · SKETCH closed (seed champion sealed)
- **Seed champion = cold split** in CHAMPION.md. INFERENCE(cold)=1047.9s (97.7% first-DiT-pass),
  DISPATCH≈1.6s (<0.2%), COLD-START not separable (warm>=cold; thrash). Fattest bucket = INFERENCE.
- **AP2 gap (explicit, not silent):** N=1 cold sample; no warm noise band (warm pathology + GPU-cost
  decision). Next run: restart-isolated warm runs for the band, AFTER the FP8 Line-C swap which may
  remove the thrash entirely.
- **Open items for PROPOSE (not done this run — no source mutation / freeze):**
  1. Line C: FP8 checkpoint swap (ltx-2.3-22b-dev-fp8, on disk) — highest-value lever.
  2. Line B bug: execute_workflow 900s timeout < real render → false "timeout"/no-output.
  3. Line B bug: validate_before_execute false-positive on ComfyMathExpression `values.a` blocks
     `agent orchestrate`.
- 300ab0a2 sent /interrupt x2; wedged mid-step in offload thrash (may need a ComfyUI restart).

## 2026-06-03 — PROPOSE ⇄ BUILD ⇄ MEASURE (Joe: GO) — Line C, INFERENCE bucket

### PROPOSE C1 — FP8 checkpoint swap
- Change: 3 loader nodes (267:236 CheckpointLoaderSimple, 267:221 LTXVAudioVAELoader,
  267:243 LTXAVTextEncoderLoader) ckpt_name: `ltx-2.3-22b-dev.safetensors` (44GB fp16)
  -> `ltx-2.3-22b-dev-fp8.safetensors` (27.8GB, on disk). Sole variable vs champion (seeds 42/23 held).
- Bucket: INFERENCE (cold) — the 97.7% first-DiT-pass materialization (267:215).
- Confirms win: cold /history exec << 1047.9s; 267:215 collapses toward ~12s; peak VRAM fits.
- Regression watch: (1) quality fp8 vs fp16 (AP6 — Joe's eye); (2) FIT — 27.8GB > 24GB so may PARTIALLY
  offload (win may be partial, not total); (3) loaders — DE-RISKED: ltx2_3_new.json is the same graph
  topology already using fp8 in all 3 loaders.
- Critique: not killed — textbook fix, file present, wiring proven by an existing saved graph.

### BUILD
- bench/wf_fp8.json — champion graph, only the 3 ckpt_name -> fp8, seeds 42/23 held (build_fp8.py).
- validate_before_execute(wf_fp8.json): only the known ComfyMathExpression false-positives; NO
  missing-model error -> ComfyUI resolves the fp8 file. Good.

### MEASURE — BLOCKED on clean VRAM
- After the 300ab0a2 wedge cleared, VRAM still ~20.8GB occupied (3.7GB free). POST /free
  {unload_models, free_memory} did NOT release it (residual model pinned in cudaMallocAsync pool).
- A fair fp8 COLD run needs clean VRAM (champion cold = 1047.9s on torch-alloc-0). Running fp8 on top
  of 20GB residual would thrash (eviction+fragmentation) -> false-slow. → need a ComfyUI restart.

### MEASURE C1 (fp8 swap) — clean VRAM (Joe restarted ComfyUI; 23GB free, torch 0)
- prompt c269d3b2. Ran ~1205s then **DEAD-END: torch.OutOfMemoryError at 267:215** (base DiT sampler),
  in the fp8 dequant path (comfy_kitchen/fp8.py dequantize_per_tensor_fp8). torch oversubscribed to
  38.9GB (VRAM+system) and still OOM'd.
- ROOT CAUSE: fp8 weights dequantize to bf16 for compute → transiently ~2x footprint → the 27.8GB
  all-in-one fp8 needs MORE peak memory than the 44GB fp16 (which uses ComfyUI's mature streaming
  offload). So the *smaller* model fails where the bigger one completes.
- **VERDICT: C1 fp8-all-in-one swap REJECTED. Champion stays fp16 dev / 1047.9s.**
- Agent-layer note (3rd Line B robustness item): during the load the circuit breaker tripped at 494s
  (3 poll timeouts) and the handler returned a false "unreachable" while ComfyUI kept running.

### SCOUT (delegated agent) — fit-in-24GB options [sourced]
- **GGUF Q3/Q4 of LTX-2.3-distilled FITS RESIDENT & is the recommended path** (QuantStack/unsloth):
  Q3_K_M 14.7GB / Q4_K_S 16.7GB. DiT-only swap via city96 `UnetLoaderGGUF` (NOT installed; needs the
  node + a known LTX-2 manual patch) + separate video/audio VAE + AV text encoder (all on disk).
- **NVFP4 (Lightricks/LTX-2.3-nvfp4, 21.7GB) RULED OUT on 4090** — Blackwell-only HW accel; emulated
  on Ada ~2x slower than fp8. (Corrects the original "FP4 is the lever" hypothesis.)
- int8 (~29GB), MXFP8mixed (29.7GB) all >24GB → skip.
- On-disk no-download probes: `ltx-2.3-22b-distilled_transformer_only_fp8_..._v3` (23.3GB, tight,
  same fp8-dequant OOM risk); `ltxv-13b-0.9.8-distilled-fp8` (14.6GB, fits but older 13B, AV uncertain).
- Components already on disk for a DiT-only swap: LTX23_audio_vae_bf16 (348MB), LTX23_video_vae_bf16
  (1385MB), ltx-2.3_text_projection_bf16 (2205MB), spatial upscaler v1.0/1.1.

### NEXT (board decision pending): GGUF Q4 is the scout-validated win but needs node-install + ~16GB
### download (RED/network → Joe's OK). VRAM now dirty (torch 38.9GB post-OOM) → next GPU run needs a restart.

## 2026-06-03 — PROVISION + FORGE: GGUF Q4 (Joe approved RED)
- ComfyUI runs on **py 3.14** (C:\Python314, torch 2.9.1+cu130, user-site AppData\Roaming\Python\Python314).
- Installed city96 **ComfyUI-GGUF** into custom_nodes; `gguf 0.19.0` into py-3.14 user-site. (node loads on restart)
- Downloading **LTX-2.3-dev-Q4_K_S.gguf (15.9GB)** -> G:\COMFY\ComfyUI\models\unet\ (dev base = matches
  champion recipe; keeps distilled-LoRA; Q4_K_S balance; ~8GB VRAM headroom).
- **WIRING RESOLVED (live get_node_info):** LTXVAudioVAELoader + LTXAVTextEncoderLoader only accept FULL
  checkpoints as ckpt_name (no standalone bf16 option) — but they load only a SLICE (cold profile:
  267:221=325ms, 267:243=862ms). CheckpointLoaderSimple loader = 551ms; the 990s cost was GPU
  materialization at the SAMPLER. → The 44GB penalty lives ONLY in the DiT MODEL->sampler path.
- **MINIMAL REWIRE (single variable):** add UnetLoaderGGUF(LTX-2.3-dev-Q4_K_S.gguf); rewire ONLY
  267:232 (LoraLoaderModelOnly).model from 267:236[0] -> UnetLoaderGGUF[0]. Keep CheckpointLoaderSimple
  (cheap, supplies video VAE), audio/text loaders, distilled LoRA, seeds 42/23 — all unchanged.
- Pending: download complete -> Joe restart (load node + clean VRAM) -> introspect UnetLoaderGGUF field
  name -> build wf_gguf.json -> MEASURE cold vs 1047.9s + peak VRAM (does 267:215 collapse? does it fit?).

### RESTART (CTO-executed, Joe on mobile): killed pid 3680, relaunched pid 62484 with IDENTICAL flags
### (verified against live cmdline: C:\Python314\python.exe main.py --reserve-vram 1.5 --fp8_e4m3fn-text-enc).
### Up in 15s, clean VRAM (23GB free, torch 0). ComfyUI stdout -> bench/comfyui_run.log.

### MEASURE GGUF Q4 — clean VRAM — prompt 4a501be2 — *** 15.5x WIN ***
- UnetLoaderGGUF loaded; field `unet_name`; LTX-2.3-dev-Q4_K_S.gguf visible. Built wf_gguf.json (one edge).
- **GGUF cold exec (/history) = 67.476 s  vs  fp16 champion 1047.887 s  =  15.53x faster. status=success.**
- **VRAM: torch_total 15,392 MB (<24GB) -> FULLY RESIDENT, no offload.** That is the mechanism.
- Per-node: 267:215 base DiT **1,023,880ms -> 40,682ms (25x collapse)**; 267:219 refine 15,039ms;
  300 UnetLoaderGGUF 400ms; 267:232 distilled-LoRA-on-GGUF 160ms (compat OK); 267:251 VAEDecodeTiled 1908ms.
- Output LTX_2.3_t2v_00005_.mp4 (seeds 42/23 = same gen as champion 00004 -> clean A/B for quality).
- **Gates: speed/resident/completes/LoRA = PASS. AP6 quality vs fp16 = PENDING JOE (only blocker).**
- Sent both videos (00004 fp16 vs 00005 GGUF) to Joe for the quality call.
