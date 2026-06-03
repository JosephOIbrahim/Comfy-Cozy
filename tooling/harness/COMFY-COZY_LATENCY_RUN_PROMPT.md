# EXECUTION PROMPT — Comfy-Cozy Latency Harness · Baseline Run
### Paste into Claude Code launched from `G:\Comfy-Cozy\tooling\harness\`
*Drives FRAME → SKETCH (measured seed champion) → STOP. No source mutation. Freeze-safe.*

────────────────────────────────────────────────────────

## 0 · ORIENTATION  (corrected-premise block — read before acting)

You are **Claude Code**, working in `G:\Comfy-Cozy\tooling\harness\`.

The control document is at:

    G:\Comfy-Cozy\tooling\harness\COMFY-COZY_LATENCY_HARNESS.md

**Read it in full before anything else.** FRAME is already ratified inside it — do not
re-litigate the decision or the three-bucket budget.

**Your mandate this run is SKETCH only:** produce the *measured seed champion* — the
baseline latency split (cold / dispatch / inference) for the frozen LTX 2.3 workflow on
the 4090. Then **STOP at the gate.** You do **not** propose, build, or optimize this run.

Prove you read the doc: restate, in one line, the three budget buckets and the declared
mode. Then proceed to constraints.

────────────────────────────────────────────────────────

## HARD CONSTRAINTS  (forbidden-operations — non-negotiable)

- **Shell is PowerShell.** Direct redirect (`> log 2>&1`, `*>&1 | Tee-Object`). Backtick
  for line continuation, never `\`. Tee is fine for these CLI runs; **never** pipe pytest
  through `Tee-Object | Select-Object`.
- **NO source mutation this run.** You create exactly three files —
  `SPEC.md`, `CHAMPION.md`, `LOG.md` — in `G:\Comfy-Cozy\tooling\harness\`. Optionally a
  `bench\baseline.ps1` in that same folder to make the measurement reproducible. Nothing
  under `agent\`, `cognitive\`, or anywhere else is edited.
- **FREEZE:** `agent\stage\` is frozen through **June 16** (Mike Gold window). Do not touch
  it. This run mutates no source at all, so the freeze is satisfied by construction — do not
  drift into "quick fixes."
- **GIT:** no commits unless explicitly asked; **never push**; no force-push; no history
  rewrite. This run should need zero git.
- **VERIFY AGAINST THE LIVE INSTALL.** Never assert a CLI command, an HTTP endpoint, or a
  JSON shape from memory — confirm each against the running install before relying on it.
  Every finding cites `file:line` or the live response that backs it.
- **Falsifiability over optimism.** If a bucket can't be measured cleanly, say so — do not
  fabricate a number. *Lab-green is not real-green.* A warm-cache micro-number is not the
  cold path the user hits.

────────────────────────────────────────────────────────

## PHASE 0 · FRAME RATIFICATION  (gate)

`Mile 0 of ~3`

1. Confirm the control doc is readable at the path above; restate the 3 buckets + mode.
2. **Freeze the reference workload.** List candidate LTX 2.3 workflow JSONs:

       Get-ChildItem -Recurse G:\Comfy-Cozy\workflows\*.json | Select-Object FullName, Length

   Surface the candidates. **Ask Joe to confirm exactly ONE** as the frozen reference graph.
   Do not measure anything until he names it. Record it as `$wf` and write it into
   `SPEC.md`'s reference-workload block.

> **STOP** — do not pass this gate until the reference workflow is confirmed.

────────────────────────────────────────────────────────

## PHASE 1 · LIVE-INSTALL VERIFICATION  (gate — read-only recon)

`Mile 1 of ~3`

Confirm the world is as the harness assumes. Read-only. Cite the live response for each.

1. **ComfyUI up?**

       Invoke-RestMethod http://127.0.0.1:8188/system_stats

   Report GPU, total/free VRAM. If unreachable, STOP and report (start `G:\COMFY\ComfyUI` on :8188).

2. **LTX 2.3 present and loadable?** Introspect `/object_info` (or the Comfy-Cozy discover
   command — see step 4). Confirm the LTX nodes + the quantized 22B checkpoint the frozen
   workflow references (FP8 or FP4) are actually installed. If anything the workflow needs is
   missing, STOP and report — do not substitute.

3. **Line B riskiest-unknown probe (WS vs poll fallback).** The fast WebSocket path *should*
   be on — `websockets==15.0.1` is in `requirements.txt:142` — but `agent\tools\comfy_execute.py`
   falls back to a `poll_interval=1.0` loop (`comfy_execute.py:231`) if WS is unavailable at
   runtime. In the project venv (`.venv312`):
   - confirm `python -c "import websockets; print(websockets.__version__)"` succeeds, and
   - inspect the execute path to determine whether a real run uses WS or the 1.0s poll.
   Report which path baseline runs will actually take. This decides how big Line B is.

4. **Discover the real execute command.** Do not guess it.

       agent --help

   Identify the single-workflow path that does load → validate → execute → verify (the
   pipeline at `agent\cli.py:498` calls `comfy_execute.handle("execute_workflow", ...)` and
   prints `Queued as {prompt_id}` at `cli.py:561`). Report the exact command + flags.

> **STOP** — emit the recon table (ComfyUI status, VRAM, LTX presence, WS-vs-poll, the execute
> command). Confirm green before measuring.

────────────────────────────────────────────────────────

## PHASE 2 · SKETCH — BASELINE MEASUREMENT  (the seed champion)

`Mile 2 of ~3` — show progress markers; never run silent.

Measure the split for `$wf`. PowerShell. `Measure-Command` for wall-clock; ComfyUI `/history`
for the model's own execution time.

    $wf = "<the confirmed reference workflow path>"

    # --- COLD: restart ComfyUI first so LTX is NOT resident, then run once ---
    $cold = Measure-Command { agent <execute-cmd> --workflow $wf *>&1 | Tee-Object cold.log }
    # prompt_id is in cold.log ("Queued as ..."). Pull ComfyUI's own exec time:
    $pid_cold = (Select-String 'Queued as' cold.log).Line  # extract the id
    $h = Invoke-RestMethod "http://127.0.0.1:8188/history/$promptId"
    # inference_ms = execution_success.timestamp - execution_start.timestamp
    #   from $h.<id>.status.messages — VERIFY these keys against the live response;
    #   if /history lacks timestamps on this build, capture timing off the WS stream instead.

    # --- WARM x2 (model resident) ---
    $warm1 = Measure-Command { agent <execute-cmd> --workflow $wf *>&1 > warm1.log 2>&1 }
    $warm2 = Measure-Command { agent <execute-cmd> --workflow $wf *>&1 > warm2.log 2>&1 }

    # --- NOISE BAND: repeat warm to N>=5; record min/median/max ---

**Compute the split** (write to `CHAMPION.md`):

    INFERENCE   ≈ ComfyUI reported exec time   (≈ same cold & warm)
    DISPATCH    ≈ warm wall-clock − INFERENCE
    COLD-START  ≈ cold wall-clock − warm wall-clock   (the model-load delta)

**Also capture, from the same runs (free signal for Lines A & C):**
- **Line A:** after the cold run, is LTX still resident before warm runs — i.e. does ComfyUI /
  Dynamic VRAM keep it loaded? If yes, a warmup workflow is a **no-op** — note it, it kills Line A.
- **Line C:** if `/history` or the WS stream breaks out per-node timing, record DiT-sampling
  time vs VAE-decode time. Whichever dominates is the Line C lever.

**Write the three state files** into `G:\Comfy-Cozy\tooling\harness\`:
- `SPEC.md` — the harness scaffold with the reference-workload block filled; **leave numeric
  targets blank** (targets come after baseline, per the bar).
- `CHAMPION.md` — the measured split + the exact recipe to reproduce it (hardware state,
  `$wf`, model+quant, res/frames/steps, the command, the numbers).
- `LOG.md` — every run with its numbers + the noise band; tag anomalies.

────────────────────────────────────────────────────────

## PHASE 3 · STOP & REPORT  (the gate — end of this run)

`Mile 3 of ~3`

Emit a tight report:
- The **three-bucket split** (cold / dispatch / inference), median + the noise band.
- **Which bucket is fattest** — the one the optimization loop will open on.
- **Line B finding:** WS or 1.0s poll on real runs.
- **Line A finding:** is LTX resident across runs → is warmup a no-op?
- **Line C finding:** DiT-sampling vs VAE-decode dominance (if measurable).
- VRAM headroom at this config (distance to the 24GB ceiling).

Then **STOP.** State verbatim:

> "Baseline seeded. Split + noise band in CHAMPION.md. Fattest bucket: **<X>**. Targets are
> Joe's to set — the bar forbids targets before baseline. Awaiting go for PROPOSE ⇄ BUILD ⇄
> MEASURE on **<X>**."

**Forbidden this run:** no source edits, no optimization, no invented targets, no second bucket
started. One job: hand back a measured baseline.

────────────────────────────────────────────────────────
*Run prompt for COMFY-COZY_LATENCY_HARNESS.md. Recon-grounded against `JosephOIbrahim/Comfy-Cozy`.*
