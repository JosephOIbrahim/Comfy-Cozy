# Diagnosis Slice — Offline Demo Runbook

The five-beat runbook from `DISPATCH_DEMO_WEEK.md`, rewritten so it can be **rehearsed
with ComfyUI DOWN and no API key**. Outputs below are from real runs of
`demo/seed_diagnosis_demo.py` + `agent diagnose` on 2026-07-12 (ComfyUI at
127.0.0.1:8188 was refused; nothing here required a live render). Two fidelity notes so
nothing on stage surprises you: **(1)** the pretty report renders `·`/`—` cleanly only
with UTF-8 forced (see Setup) — on a raw console they show as `�`; **(2)** the raw
`--json` stream is ASCII-escaped for pipe-safety (an em-dash ships as the literal
`—`), shown rendered here for readability. `diagnosisId` UUIDs vary per run.

On stage this is "run report", "explained gaps", "environment fingerprint" — the
project's internal codenames stay off the slides and script (DISPATCH D6).

---

## Setup (once, before rehearsal)

```powershell
$env:PYTHONUTF8 = "1"; [Console]::OutputEncoding = [Text.Encoding]::UTF8  # clean ·/— glyphs
$env:DIAGNOSIS_DIR = "$env:TEMP\cozy_demo"   # optional; the seeder prints its default
python demo/seed_diagnosis_demo.py           # keyless, no torch — seeds 3 clean + 1 OOM
```

Real seeder output (UUID suffixes vary per run):

```
DIAGNOSIS_DIR = C:\Users\User\AppData\Local\Temp\cozy_demo
envHash       = 59a135a492c27143ee3fa31ce8a09481
workflowHash  = ef5dea12795325df44deb799f8322081

  seeded clean run 1 : 59a135a4_fc569658-...json
  seeded clean run 2 : 59a135a4_9c6a3629-...json
  seeded clean run 3 : 59a135a4_d5902a5d-...json
  seeded OOM run   : 59a135a4_85f81730-...json  (latest, critical)
```

> **envHash `59a135a492c27143ee3fa31ce8a09481`** is the `nominal` cross-repo handshake
> vector in `schema/handshake/env_hash_vectors.json` — the seeded box is literally the
> canonical fingerprint, so parity is visible for free.

---

## Beat-by-beat

Legend: **[OFFLINE]** reproducible now via the seed store · **[SERVER-GATED]** needs a
live ComfyUI render.

### Beat 1 — Headless, keyless *(fingerprint [OFFLINE] · live connect banner [SERVER-GATED])*

> "No API key was involved in anything you're about to see on this path."

- **Live (stage):** `agent inspect` → the connect banner prints the environment
  fingerprint + "0 known findings". `agent inspect` queries the worker's `/system_stats`,
  so the **banner itself is server-gated**.
- **Offline substitute:** the fingerprint is the **first line** of `agent diagnose --last`,
  and the seeder prints the same `envHash`. Both are keyless — no LLM, no key read anywhere
  in the path (Demo Gate cond. 2, certified).

```powershell
agent diagnose --last
```
```
env 59a135a4 · 127.0.0.1:8188 · 2026-07-12T22:28:29Z
  Windows-11 · python 3.12.10 · torch 2.7.1+cu128 (cu128) · driver 576.88 · ComfyUI 0.3.44
```
*(Glyphs render clean only with UTF-8 forced per Setup; on a raw console `·`/`—` show as
`�` — a display artifact only, the CLI raises no exception and exits 0.)*

### Beat 2 — Run + see *(**[SERVER-GATED]** — live per-node render timing)*

> "Which node ate the render?"

- **Live only:** queue a workflow from the CLI, then `agent diagnose --last` prints the
  per-node `stages[]` timing table and "baseline N clean runs". The table is populated by
  the execution bridge during a **real render** — there is no offline path to a live timing
  table.
- **What the seed carries:** the 3 clean baseline docs already hold synthetic stage timings
  (`4:CheckpointLoaderSimple 640ms · 3:KSampler 11200ms · 8:VAEDecode 560ms`), so the store
  shape is exactly what the live table renders from. Use this to confirm the renderer, not
  to fake a live number.

### Beat 3 — Break it *(rehearsal **[OFFLINE]** · live OOM **[SERVER-GATED]**)*

> "Every gap explained."

- **Live (stage):** run the deterministic breaker workflow → OOM on the 4090 → ComfyUI
  survives → `agent diagnose --last`. Firing the real OOM needs ComfyUI.
- **Offline substitute:** the seeded OOM doc **is** the latest, so `agent diagnose --last`
  reproduces the exact critical report for rehearsal:

```powershell
agent diagnose --last
```
```
run error · 3.2s · workflow ef5dea12 · baseline 3 clean runs
  no per-node timing (bridge not installed) — stages: []
triggers: execution_error, oom
  CRITICAL vram_pressure — The run failed with an out-of-memory error — the
  workflow's VRAM demand exceeded what the device could serve.
    fix: Reduce resolution or batch size, enable model offload (--lowvram), or
    use tiled VAE decode.
```

**Strict gate** (CI beat — exit 1 on any critical finding). Note: `--strict` **renders the
full report first**, then sets the exit code — it is a gate, not a quiet check:
```powershell
agent diagnose --last --strict ; "LASTEXITCODE=$LASTEXITCODE"
```
```
env 59a135a4 · 127.0.0.1:8188 · 2026-07-12T22:28:29Z
  Windows-11 · python 3.12.10 · torch 2.7.1+cu128 (cu128) · driver 576.88 · ComfyUI 0.3.44
run error · 3.2s · workflow ef5dea12 · baseline 3 clean runs
  no per-node timing (bridge not installed) — stages: []
triggers: execution_error, oom
  CRITICAL vram_pressure — The run failed with an out-of-memory error — ...
LASTEXITCODE=1
```

### Beat 4 — Show the contract *(**[OFFLINE]** — fully)*

> "An unexplained gap isn't a bug report we forgot to file — it's structurally invalid."

Dump the document (stdout stays JSON-pure for pipes, DISPATCH D1):
```powershell
agent diagnose --last --json
```
```json
{"createdAt":"2026-07-12T22:17:15Z","diagnosisId":"e7a2a0c8-...","env":{"comfyuiVersion":"0.3.44","driver":"576.88","os":"Windows-11","python":"3.12.10","torch":"2.7.1+cu128","torchCuda":"cu128"},"envHash":"59a135a492c27143ee3fa31ce8a09481","findings":[{"actionable":true,"code":"vram_pressure","context":{"cozy":{"error":"RuntimeError CUDA out of memory. Tried to allocate 2.50 GiB (GPU 0; 24.00 GiB total capacity; 22.10 GiB already allocated)"}},"explanation":"The run failed with an out-of-memory error — the workflow's VRAM demand exceeded what the device could serve.","fixHint":"Reduce resolution or batch size, enable model offload (--lowvram), or use tiled VAE decode.","severity":"critical"}],"nodeId":"127.0.0.1:8188","run":{"durationS":3.2,"promptId":"break-oom","stages":[],"status":"error","vramPeakGb":null,"workflowHash":"ef5dea12795325df44deb799f8322081"},"schemaVersion":"0.1.0","triggers":["execution_error","oom"]}
```

The theater beat — a fired trigger with empty findings is **rejected by schema AND model,
live** (Demo Gate cond. 4, certified). Reproduce offline:
```powershell
python -m pytest tests/diagnosis/test_schema_goldens.py -v
```
```
tests/diagnosis/test_schema_goldens.py::TestWatchedFail::test_silent_trigger_rejected_by_the_invariant_and_nowhere_else PASSED
======================== 11 passed, 1 warning in 0.53s =========================
```
`INVALID_silent_trigger.json` (triggers=`["vram_threshold"]`, findings=`[]`) fails the
Draft-2020-12 schema (`allOf[0]` findings `minItems:1`) *and* raises pydantic
`ValidationError` ("invariant violated: fired trigger(s) with no findings").

### Beat 5 — The upstream ask *(**[OFFLINE]** — fully)*

> One slide: this JSON as an attachment format for ComfyUI issue triage — structured env +
> findings instead of "it's slow, help." We reduce their tracker load.

**The best line** (keyless, one pipe):
```powershell
agent diagnose --last --json | jq .findings
```
> `jq` is **not installed on this rehearsal box** — the line is the on-stage form; verify it
> where `jq` exists. Keyless python fallback that produces the identical `.findings`:
```powershell
agent diagnose --last --json | python -c "import sys,json; print(json.dumps(json.load(sys.stdin)['findings'], indent=2))"
```
```json
[
  {
    "actionable": true,
    "code": "vram_pressure",
    "context": {"cozy": {"error": "RuntimeError CUDA out of memory. Tried to allocate 2.50 GiB (GPU 0; 24.00 GiB total capacity; 22.10 GiB already allocated)"}},
    "explanation": "The run failed with an out-of-memory error — the workflow's VRAM demand exceeded what the device could serve.",
    "fixHint": "Reduce resolution or batch size, enable model offload (--lowvram), or use tiled VAE decode.",
    "severity": "critical"
  }
]
```

---

## Demo Gate status

| # | Demo Gate condition | Kind | Status |
|---|---------------------|------|--------|
| 1 | Five-beat script runs end-to-end twice on the frozen box, zero manual intervention | **[SERVER-GATED]** | pending live box |
| 2 | Keyless path verifiably keyless (`.env` blanked; no LLM/key read in path) | **[OFFLINE]** | **certified** |
| 3 | Fail-soft: diagnosis force-broken → render byte-identical | **[OFFLINE]** | **certified** (4/4) |
| 4 | Watched-fail recorded; `INVALID_silent_trigger` rejected by schema **and** model | **[OFFLINE]** | **certified** (11/11) |
| 5 | Bridge-absent path: `stages: []` renders gracefully | **[OFFLINE]** | **certified** |
| 6 | Backup video exists; demo-box envHash recorded + asserted morning-of | **[SERVER-GATED]** | assert mechanism BUILT (`--assert-env`); video + live box pending |

The four offline conditions (2–5) were certified by verifier agents on 2026-07-12 with real
captured evidence. Conditions 1 and 6 require the frozen live box and cannot be closed while
ComfyUI is down — do not mark them from an offline rehearsal.

## What is NOT rehearsable offline (say it plainly, don't fake it)

- **Beat 2 live timing table** — needs a real render + execution bridge.
- **Beat 3 live OOM** — needs the breaker workflow to actually exhaust the 4090 (and ComfyUI
  to survive it). The seeded OOM doc rehearses the *report*, never the *break*.
- **Beat 1 live connect banner** (`agent inspect`) — queries the worker's `/system_stats`.
- **Demo Gate 1 & 6** — twice-through on the frozen box + backup video. *(The morning-of
  envHash assertion is now one command: record the hash at Thursday rehearsal with
  `agent diagnose --last --json`, then Friday run `agent diagnose --assert-env <hash>` —
  exit 0 = unchanged, 3 = the box drifted.)*

If asked for a live number while ComfyUI is down: say it's server-gated and show the seeded
report shape. Never invent a render result.
