# COMFY-COZY LATENCY HARNESS
### Whole-Pipeline · LTX 2.3 · RTX 4090
*Refactored from the AUTOSCIENTIST × K+S trial harness. Same two defenses, recolored for latency.*
*Recon baked in from a clone of `JosephOIbrahim/Comfy-Cozy` @ shallow HEAD. Every claim cites `file:line`.*

────────────────────────────────────────────────────────

## WHY THIS EXISTS  (read first — every rule serves one of two defenses)

A latency-optimization loop fails in exactly two ways. This harness catches both:

- **Believed-but-unmeasured speedup** — the latency version of hallucinated completion.
  "It feels faster." "FP4 should be quicker." A number with no reproducible measurement
  behind it is decoration. *Lab-green is not real-green* — a passing micro-benchmark on a
  warm cache is not the cold path the user actually hits.
  → Defense: **no latency claim is believed without a reproducible measurement that
    beats the champion outside noise.**
- **Grinding one bucket past the point it pays** — premature convergence. Sinking a week
  into shaving 8ms off agent dispatch while inference is 60 seconds.
  → Defense: **the budget is split three ways; a bucket that stops paying gets its budget
    reallocated, not pushed harder.**

If a rule below doesn't trace to one of these, it's ceremony. Cut it.

────────────────────────────────────────────────────────

## THE BAR — FALSIFIABILITY

Before you change anything, state the measurement that would show it **didn't help — or made
it worse.** Latency has a property code-correctness doesn't: *regressions are silent and
common.* A change can speed the warm path and wreck the cold path. So every proposal names:

- the metric it claims to move (which bucket, p50 or p95, warm or cold),
- the measurement that confirms the win,
- the measurement that would reveal a regression elsewhere.

A speedup with no disproof, and no regression check, is not progress.

> **Do not set a numeric target before the baseline is measured.** A target picked before
> measurement is a guess, and the bar forbids guesses. Baseline first → targets are
> `baseline − X%` or an absolute ceiling, set *after* the seed champion exists.

────────────────────────────────────────────────────────

## THE BUDGET  (the core specialization — this replaces the generic SPEC outcome)

"Whole-pipeline latency" is not one number. It is a sum of three independently-attackable
budgets. You measure the split **first**, then attack the fattest bucket. The split itself
is the first deliverable.

    TOTAL (prompt → finished video)
      =  COLD-START      model/workflow load, first-run-only cost
      +  AGENT-DISPATCH  Comfy-Cozy's own overhead: submit, poll, parse, return
      +  INFERENCE       ComfyUI executing the LTX 2.3 graph (DiT sampling + VAE decode + audio)

Each summand maps to one independent line (see MODE → THE THREE LINES). The discipline:
**measure the split before optimizing.** You cannot reallocate a budget you haven't sized.

**Reference workload (the champion's fixed graph):** LTX 2.3 on RTX 4090.
Verified facts that constrain the workload:
- 22B-parameter diffusion transformer; audio + video in a **single forward pass** (you cannot
  cheaply skip audio to save time unless a video-only mode is confirmed in the node set).
- **FP8 quantization is effectively mandatory** to fit 22B in 24GB VRAM. An FP4/NVFP4 variant
  exists (smaller, faster, quality-risk). Which one you run is a Line C variable, not a given.
- Resolution **width and height must be divisible by 32**.
- Ceiling is 4K @ 50fps @ 20s — that is *not* a 4090 operating point. Your champion runs a
  realistic local config (lower res, fewer frames, fewer steps); that config is part of the recipe.

────────────────────────────────────────────────────────

## PRINCIPLES  (the six, recolored for latency)

1. **Benchmarks gate progress.** No "faster" without a re-runnable benchmark. No benchmark for
   a bucket? Building it is your first action — for a latency trial the **benchmark harness IS
   the first deliverable.**
2. **One champion config, always.** One current-best configuration + the exact recipe to
   reproduce its number. New configs earn the throne only by beating it outside noise. A noisy
   win is re-run on a fresh cold boot before you believe it.
3. **Critique before you build.** A speculative optimization dies on paper first. "FP4 will be
   faster" is a hypothesis with a quality risk — interrogate it before you spend an afternoon
   re-quantizing.
4. **Regressions are memory.** Log every config tried, its number, AND what it regressed. Read
   the log before proposing. Never re-discover that 0.1s polling pegs a CPU core twice.
5. **Don't privilege one bucket.** Hold all three budgets visible. Let the measured split — not
   your hunch about where the time goes — decide what gets attacked.
6. **Stall → reallocate.** A bucket that stops yielding (N configs, no gain outside noise) is
   telling you its budget is near its floor. Move the effort to the fattest remaining bucket.
   Grinding a near-floor bucket is the trap.

────────────────────────────────────────────────────────

## STATE — FILES FOR THIS TRIAL

- **`SPEC.md`** — the latency contract (scaffold below). Outcome · acceptance predicates ·
  out of scope · falsification conditions.
- **`CHAMPION.md`** — current best config + the **exact recipe** to reproduce its number:
  hardware state (cold/warm), workflow JSON ref, model + quant, res/frames/steps, the command,
  and the measured split.
- **`LOG.md`** — append-only. Every config tried, its three-bucket numbers, and regressions.
  Tag dead ends: `DEAD-END | <config> | <number> | <why rejected / what it regressed>`.
- **`bench/`** — the benchmark harness itself (the re-runnable measurement). This is a
  deliverable, not scaffolding. If it isn't re-runnable and noise-aware, the trial has no floor.

────────────────────────────────────────────────────────

## SPEC.md — SCAFFOLD (fill the `<FILL>` slots after baseline)

    # SPEC — Comfy-Cozy whole-pipeline latency (LTX 2.3 / RTX 4090)

    ## Outcome (what's true when this ships)
    The same fixed LTX 2.3 workflow, run from Comfy-Cozy on the 4090, completes
    prompt→finished-video in <FILL: target total, set AFTER baseline> on the warm path,
    with the cold path no worse than <FILL>, and the agent-dispatch share held under <FILL>%.

    ## Reference workload (frozen — the champion's recipe)
    - Workflow: <FILL: path to the .json you benchmark — one fixed graph>
    - Model + quant: LTX 2.3, <FILL: FP8 | FP4/NVFP4>
    - Resolution: <FILL ×32-divisible>  Frames: <FILL>  Steps: <FILL>  FPS: <FILL>
    - Audio: <FILL: on (single-pass default) | video-only if a mode exists>
    - Seed: fixed (<FILL>) so inference time is comparable run-to-run

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
    - Multi-GPU / cloud burst (that's the roadmap's Option D, a different trial).
    - Replacing ComfyUI's executor (Option B — Rust shim — is a separate, later harness).
    - ComfyUI-internal allocator behaviour beyond what keep-warm can influence.

    ## Falsification conditions (what would prove the approach wrong)
    - The measured split shows >90% of warm latency is INFERENCE and inference is already at
      the FP4 quality floor → the agent layer cannot deliver the win; the lever is the model,
      not Comfy-Cozy. Stop and say so.
    - Cold-start is dominated by ComfyUI model load that warmup cannot preempt (Dynamic VRAM
      already keeps it resident) → Line A is a no-op; retire it.
    - Dispatch is already <5% of total → Line B is near floor before it starts; don't grind it.

────────────────────────────────────────────────────────

## THE LOOP

    FRAME → SKETCH → ( PROPOSE ⇄ BUILD ⇄ MEASURE )* → INTEGRATE → STRESS → SHIP
                            ↑__________________|
                     reallocate budget on stall; loop until SPEC clears or budget spent

**FRAME** *(gate — DONE for this trial)* — Brief restated, lines marked ASSERTED vs INFERRED,
SPEC scaffold written above. ASSERTED by you: whole-pipeline; LTX 2.3 on 4090; clone + map.
INFERRED (confirm at SKETCH): the realistic res/frames/steps, the quant, the numeric targets.

**SKETCH** *(gate)* — The seed champion is **your current measured config** — the baseline. You
do not invent it; you measure it (see ON-RAMP). The load-bearing pieces and the riskiest
unknown per line are pre-mapped from recon below. Score confidence 0–1 per predicate after the
baseline lands.

**PROPOSE ⇄ BUILD ⇄ MEASURE** *(the core — not a march)*
  · *Propose:* a config change against the champion, on one line. Cross-check the regression log.
    Critique it — kill the ones with obvious quality or regression risk on paper.
  · *Build:* apply the smallest version of the change. State the change + the benchmark you'll run
    + the bucket you expect to move + the regression you'll watch.
  · *Measure:* run the benchmark. Beats the champion **outside the noise band**? Re-run cold to
    confirm it's not noise, then promote: update CHAMPION + LOG. Doesn't? Log it; if the line is
    exhausted, mark DEAD-END and reallocate budget.

**INTEGRATE** *(gate)* — Stack the per-line wins and measure the WHOLE pipeline. Three buckets
each faster in isolation does NOT mean the total dropped — a warmup that helps cold can tax warm;
a tighter poll can starve a CPU the sampler wants. Re-measure end-to-end, cold and warm.

**STRESS** *(gate)* — Attack the real, integrated config: sustained back-to-back runs (thermal
throttle on the 4090 is real and shifts inference time), queue depth >1, a second model forcing
VRAM pressure, a long-clip config near the 24GB ceiling. Sort each finding: showstopper (reopen) /
bounded weakness (document) / out of scope.

**SHIP** *(gate)* — Report predicate-by-predicate: the final split, what was promoted on each
line, what was abandoned and why, known regressions, measured-vs-not. Ask: ship, iterate, or
escalate.

────────────────────────────────────────────────────────

## VERIFIER LADDER  (climb only as high as the contract demands)

1. **Runs & reproducible** — the benchmark executes and the same config returns the same number
   within the noise band over N runs.                                          *(must pass)*
2. **Measures the predicate** — it times the right bucket, the right percentile, the right
   thermal/cache state (warm vs cold declared, not assumed).                    *(must pass)*
3. **Robust** — variance characterised across N≥5 cold boots; thermal drift noted; first-run
   vs steady-state separated.
4. **Intent** — moves *perceived* latency, not just a microbenchmark. Time-to-first-progress and
   time-to-final both matter to a user watching a video render.
5. **Adversarial** — sustained load, queue depth, VRAM pressure, long-clip ceiling. (STRESS's artillery.)

> **GPU latency is noisy.** Thermal state, the OS scheduler, and VRAM residency all move the
> number run-to-run. A within-noise "win" is not a win until a fresh cold boot confirms it.
> Report a noise band (e.g. ±5%) and hold every claim to it.

────────────────────────────────────────────────────────

## MODE — HONEST READOUT: **SIMULATED**, 3 lines

Mode is a readout of how many genuinely independent lines exist — not an ambition setting.

The three budgets are **genuinely independent**: each can be proposed, built, and measured
without touching the other two. Cold-start residency, agent-dispatch overhead, and inference
config share only the total — not their mechanisms. That is more than one line → not SOLO.
There is no need for a real parallel launcher yet → not ORCHESTRATED.

**So: SIMULATED.** One context, three lines held open, attention round-robin. Report which line
you're on. You are *interleaved, not parallel.*

> **Honesty constraint:** a single context cannot run three benchmark agents at once. Never
> narrate simultaneous lines you aren't running. Work A, then B, then C; say which one. Faking
> parallelism is the believed-but-unmeasured failure wearing a different coat.

**Graduation path (not now):** this repo already carries orchestration machinery —
`harness/ledger/`, `.claude/agents/`, `AGENT_TEAM_BLUEPRINT.md`. If the SOLO/SIMULATED run proves
the method earns its keep, the three lines graduate to ORCHESTRATED agents: one agent per bucket
+ a standing benchmark/analyst, coordinating through the shared `SPEC/CHAMPION/LOG` state. That is
the harness's documented scaling step — taken *after* a champion beats its seed, never before.

────────────────────────────────────────────────────────

## THE THREE LINES  (seed proposals from recon — `file:line` grounded)

### LINE A — COLD-START  (model residency + startup)
**Owns:** the first-run-only cost — model load into VRAM, object_info fetch, startup disk scans.

**Recon / seed proposals:**
- **A1 — Warmup workflow at startup.** No keep-warm mechanism exists today (grep: only unrelated
  hits; `health.py:75` reads `get_free_memory` but nothing manages residency). Proposal: submit a
  minimal LTX workflow on first connect to force the 22B model resident *before* the user's first
  real request — converting cold→warm proactively.
- **A2 — object_info residency across processes.** `discovery_cache.py` caches the (large)
  `/object_info` payload process-level with `ttl_seconds=300`. A fresh CLI process pays the cold
  fetch again (`comfy_api.py:243` / `comfy_discover.py:1281`, 30s timeout ceiling). Proposal:
  persist or eager-prime it so a new process doesn't re-pay.
- **A3 — Startup scan trim.** `startup.py:run_auto_init` disk-scans workflows + models
  (`_scan_workflows_to_stage`, `_scan_models_to_stage`). Proposal: defer/parallelize if they block
  first response.

**Verifier:** cold run (after ComfyUI restart) wall-clock to first video vs warm run. A1 wins only
if it shrinks the cold gap **without adding to the warm path.**
**Riskiest unknown:** does **Dynamic VRAM already keep LTX resident**, making A1 a no-op? (Dynamic
VRAM shipped ~Mar 2026 specifically to mitigate eviction.)
**Falsification:** warmup taxes the warm path, OR the cold gap is ComfyUI load that warmup can't
preempt → retire Line A.

### LINE B — AGENT-DISPATCH  (Comfy-Cozy's own overhead — the part you own)
**Owns:** everything between "user intent" and "ComfyUI starts executing," plus completion detection.

**Recon / seed proposals:**
- **B1 — Confirm WS is actually used, not silently falling back.** `websockets==15.0.1` IS
  installed (`requirements.txt:142`), so the fast path *should* be on — but `comfy_execute.py`
  falls back to polling if WS is unavailable at runtime, and the adapter's WS `recv` uses
  `timeout=2.0` (`comfyui_adapter.py:239`). Proposal: instrument which path real runs take; if
  it's falling back, that's the single biggest dispatch win.
- **B2 — Poll interval.** Completion is detected by `_poll_completion` with
  `poll_interval=1.0` (`comfy_execute.py:231`, `time.sleep(poll_interval)` at 261/266/271/323).
  On the polling path, the job's finish isn't seen for up to a full second. Proposal: shorten
  (e.g. 0.25s) or adapt (tight early, loosen late). Watch the regression: a hot poll loop steals
  a CPU core the pipeline may want.
- **B3 — Pool the hot HTTP path.** Introspection already pools
  (`comfy_api.py:33`: `max_keepalive_connections=5`), but the execution adapter constructs a
  fresh `httpx.Client()` three times (`comfyui_adapter.py:105/159/191`) — its own comment claims
  it matches `comfy_api._get_client`, but it doesn't. Proposal: route through a pooled client.
  *Honest scale: small on localhost (connection setup is single-digit ms); cheap, do it, don't oversell it.*

**Verifier:** dispatch = (Comfy-Cozy wall-clock) − (ComfyUI's reported exec time) − (cold load).
Measure before/after each change.
**Riskiest unknown:** the dispatch split itself — is it the poll tail, the client setup, or MCP
serialization? Needs the baseline decomposition.
**Falsification (pre-wired stall rule):** dispatch already <5% of warm total → near floor; stop,
reallocate to Line C.

### LINE C — INFERENCE  (ComfyUI + LTX — lever = workflow params + compile-cache)
**Owns:** the model's own execution time — DiT sampling, VAE decode, audio synthesis.

**Recon / seed proposals:**
- **C1 — Quantization.** FP8 (likely required to fit 22B in 24GB) vs FP4/NVFP4 (smaller, faster,
  quality risk). Measure speed AND quality at equal config.
- **C2 — Workflow params.** Resolution (÷32), frame count, step count, fps. The 4K@50fps@20s
  ceiling is not a 4090 operating point — find the realistic config that meets the quality floor.
- **C3 — VAE decode.** LTX 2.3's rebuilt video VAE is heavy; tiled / temporal-tiled decode is a
  speed-vs-VRAM tradeoff worth timing as its own stage.
- **C4 — LIVRPS compile-cache.** Comfy-Cozy-side, not model-side. If the resolved workflow
  rebuilds on every parameter touch, cache the compiled-per-intent graph so re-runs skip
  re-resolution (the roadmap's Action 3, applied as a latency lever). Touches caching above the
  LIVRPS engine — **do not alter the priority semantics** (patent-load-bearing).

**Verifier:** ComfyUI's own reported execution time for a fixed prompt/seed (from `/history` or
WS per-step), configs compared at equal quality.
**Riskiest unknown:** does **DiT sampling or VAE decode dominate**? Different levers. And does FP4
hold quality for your use? Needs per-stage timing.
**Falsification:** a config is faster but fails the quality floor → out of scope, or documented as
a bounded tradeoff — not a silent promotion.

────────────────────────────────────────────────────────

## ON-RAMP — SEED THE CHAMPION (run this on the 4090; I cannot — only your box has the GPU)

The seed champion is **measured, not invented.** Before any optimization, get the baseline split.
PowerShell (your shell). Direct redirect, no `Tee-Object` pipes. `Measure-Command` for wall-clock;
ComfyUI's `/history` for the model's own exec time.

    # 0. Freeze ONE workflow as the reference graph. Fill SPEC's reference-workload block.

    # 1. COLD run — restart ComfyUI first so the LTX model is NOT resident.
    #    (start G:\COMFY\ComfyUI on :8188, fresh)
    Measure-Command { <your Comfy-Cozy execute command for the frozen workflow> } *>&1 |
      Tee-Object cold_run.log   # acceptable here: this is a shell command, not pytest
    #    Then pull ComfyUI's reported execution time for that prompt_id from GET /history.

    # 2. WARM runs — same command, x2, model now resident.
    Measure-Command { <same execute command> } *>&1 > warm_run_1.log 2>&1
    Measure-Command { <same execute command> } *>&1 > warm_run_2.log 2>&1

    # 3. Compute the split and write CHAMPION.md:
    #    INFERENCE   ≈ ComfyUI's reported exec time (≈ same cold & warm)
    #    DISPATCH    ≈ warm wall-clock − INFERENCE
    #    COLD-START  ≈ cold wall-clock − warm wall-clock   (the model-load delta)

    # 4. Repeat warm run N≥5 times → record the noise band (AP2). Only now set numeric targets.

When `CHAMPION.md` holds a real split and a noise band, FRAME is truly cleared and the
PROPOSE ⇄ BUILD ⇄ MEASURE core opens on whichever bucket the split shows is fattest.

────────────────────────────────────────────────────────
*Provenance: refactored from AUTOSCIENTIST × K+S harness. Recon from `JosephOIbrahim/Comfy-Cozy`*
*shallow clone; LTX 2.3 specs web-verified (Lightricks, Mar 2026). Numbers are yours to measure.*
