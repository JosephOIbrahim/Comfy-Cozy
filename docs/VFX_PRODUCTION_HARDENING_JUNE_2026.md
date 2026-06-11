# VFX Production Hardening — First-Principles Review (June 2026)

**Scope:** Comfy-Cozy as a production tool on a VFX floor — not a demo, not a dev toy.
**Method:** every codebase claim below was verified this cycle (live probes against ComfyUI at
`127.0.0.1:8188`, reproduce→clean fixes, twice-run suites). Domain requirements come from how
production actually runs: shots, versions, farms, reviews, deadlines.
**Status keys:** ✅ shipped/verified · 🔧 fix landed this cycle (PRs #59–#64) · 🟡 queued
(harness wave named) · 🔴 gap, not yet scheduled.

> **CLOSED 2026-06-11 — every §4 item shipped.** Items 1–3 merged via PRs
> #66–#68 (v5.2.0 "The Production Floor"); items 4–8 via PRs #69–#73
> (v5.3.0 "Shot-Ready"). The edit loop measured 7.2 s → 0.48 s; downloads
> resume; learning data is append-only+fsync'd; CI tests the machine that
> ships; long jobs get real budgets; linear EXR reaches the vision loop;
> `workflow.lock` answers question #1; `COMFYUI_ENDPOINTS` pools workers.
> The 🟡/🔴 markers below are preserved as the 2026-06-09 snapshot this
> plan was executed against. Reproduce→clean records:
> `tooling/harness/LEDGER.md`.

---

## 1. First principles — what a production floor demands of any tool

A tool earns a slot in a VFX pipeline when it can answer yes to seven questions:

1. **Reproducibility** — can I re-render shot_042 exactly, three weeks later, on a different box?
2. **Determinism of failure** — when it breaks, does it break loudly, early, and recoverably?
3. **Scale** — does it survive 12 artists and a render farm, or only one laptop?
4. **Asset reality** — does it respect how studios store things (NAS, UNC paths, 12 GB models,
   license boundaries)?
5. **Color & format reality** — EXR/linear/ACES first; PNG is a preview format, not a deliverable.
6. **Review loop** — can a supervisor compare versions and trust what they're looking at?
7. **Auditability** — can production reconstruct *what made this image* without asking the artist?

Everything below is scored against those seven.

---

## 2. What the codebase already does right (verified, don't re-litigate)

- **Surgical-edit philosophy.** No full-workflow generation; validated patches with a 50-step
  undo stack and per-connection session isolation (`workflow_patch.py` ContextVar registry).
  This is the correct posture for production: artists own their graphs, the agent adjusts them.
- **Safety gate, now real.** As of this cycle the pre-dispatch gate fails **closed** on import
  failure, consumes the live circuit-breaker state and per-session action history, classifies
  every one of the 129 dispatched tools explicitly (drift pinned by a completeness test), and
  requires a passing `validate_before_execute` before session-workflow execution (#62 + the
  consent branch). Installs are confirm-gated end to end — `needs_confirmation` → human yes →
  `confirm=true` — in both the MCP rules and the CLI prompt (#60/#61). 🔧
- **Provenance primitives exist.** `write_image_metadata` / `read_image_metadata` /
  `reconstruct_context` embed and recover generation context; experience records now carry a
  `source` tag (rule-era vs future vision scoring). 🔧
- **Honest contract testing has begun.** The repair→discover seam test (real producer through
  real consumer, edge-mocked only) is the template; the standing rule is that every cross-module
  contract gets one. 🔧
- **USD-native thinking.** The stage layer (LIVRPS delta composition, SHA-256 integrity) is the
  right substrate for pipeline integration — most AI tools have nothing like it.

---

## 3. Gaps, ranked by what hurts a production first

### P0 — blocks production use today

**3.1 The edit loop costs ~12 s per change. 🟡 (H2, queued)**
Measured ×3: `validate_before_execute` ≈ 6.1–6.5 s *each*, and the re-validate after a fix pays
the full price again because `/object_info` (4.58 MB) is re-fetched uncached at 7 call sites.
The fix (one comfy_api-level TTL+invalidate cache + per-class GETs + pooled engine client) is
designed and baselined; the noise band (≤13%) is tight enough for a two-leg race. An artist
iterating "warmer… more rim light… again" feels this on every single beat. Nothing else in this
report matters if the core loop stays at 12 s.

**3.2 Downloads can't resume and report no progress. 🔴 (C-R12, slot into H4)**
A 12 GB model on studio Wi-Fi or a flaky VPN dies at 95% → restart from zero, in silence.
Production reality is NAS mirrors and overnight pulls. Required: ranged-request resume,
progress events (the schema already promises them), and size/host/destination in the
confirmation prompt. This is the single most artist-visible reliability gap left.

**3.3 Learning-data persistence loses writes under concurrency. 🟡 (H4, queued)**
The experience JSONL is rewritten whole (10.9 MB per run today, ~11 GB per 1k runs), the NIM
warm-state file does read-all/append/rewrite with a lost-update race, and neither fsyncs.
One artist = waste; two artists or one crash = silent data loss. Append-only + flush/fsync +
a save lock are already specified (H4) — they're prerequisites for trusting any learned
recommendation the agent makes.

**3.4 CI tests a machine that isn't the one that ships. 🔴 (promote from L-MISC-d)**
`usd-core` is never installed in CI, so all 21 stage-layer test files silently SKIP — the USD
substrate this product is proudest of is green-by-skip. Dev runs Python 3.14, CI tops out at
3.12, and 3.13 is advertised but never tested. Production hardening rule one: **CI must install
what the product imports.** Cheap fix, large honesty dividend.

### P1 — required before multi-artist / farm deployment

**3.5 Single-endpoint assumption.** `COMFYUI_HOST:PORT` is one instance; the circuit breaker is
one global singleton. A floor runs several ComfyUI workers (or a farm gateway). Needed, in
order: per-host breaker instances → an endpoint pool with health-checked failover → only then
farm-submission adapters (Deadline-style) as a Lead. The engine adapter (`IAIEngine`) is the
right seam; this is an adapter feature, not a rewrite.

**3.6 Timeout incoherence kills long jobs.** The MCP layer's blanket 120 s `wait_for`
contradicts the tools' own budgets (NIM warm-up alone is legitimately 900 s cold; video renders
and big upscales exceed 120 s routinely). The orphaned thread keeps working while the artist is
told it failed — worse than failing. The vision path was fixed this cycle (inner 90 s beats the
kill 🔧); the same per-tool-budget pattern needs to propagate to the MCP dispatch layer.
WebSocket hardening rides along: `ping_timeout=20 s` dies during model loads, `ConnectionClosed`
escapes untranslated, and `nim_run` has no polling fallback (C-R6).

**3.7 EXR / color management is absent. 🔴 (new — the VFX-specific gap)**
The vision tools read PNG/JPEG; the new downscaler deliberately passes other formats through
untouched, and the 5 MB guard then rejects big EXRs with a message instead of analyzing them.
A compositor's working currency is linear EXR (ACEScg). Minimum viable: an EXR→display-referred
(sRGB or OCIO-config) conversion step in front of `analyze_image`/`compare_outputs`, plus
"this is a data/linear image" detection so the vision model is never asked to judge raw linear
values. Stretch: respect a show's OCIO config when tone-mapping for review. Without this, the
whole VERIFY phase only works on previews.

**3.8 Workflow reproducibility has no lockfile. 🔴 (new)**
Re-running a workflow three weeks later is not reproducible if a node pack updated or a model
file changed underneath it. The pieces exist — pack registry with URLs, model hashes in the
registry cache, seed capture in metadata — but nothing pins them per workflow. Proposal: a
`workflow.lock` sidecar (pack name → git SHA; model name → file SHA-256; ComfyUI version)
written by `save_workflow`/`save_session` and checked by `validate_before_execute` with a
"drifted since lock" warning. That single artifact answers question #1 for production.

### P2 — quality-of-life and trust

**3.9 The UI panel dimension is entirely unverified.** Token streaming wired but never rendered,
tab-switch drops replies mid-turn, `MCP_AUTH_TOKEN` silently 401s the canvas bridge, raw
`str(e)` leaks into chat (L-PANEL, all cap-killed findings — probe scheduled H5). Treat the
panel as untested until its adversarial pass runs; artists meet the product here.
**3.10 `model_compat` heuristics misclassify.** Unanchored regexes, WAN 2.2 unrecognized,
unknowns silently pass, and the curated YAML profiles are never consulted (L-MISC-b). For a
product whose pitch includes "never mix model families," the checker should prefer profiles and
fail closed on unknown families.
**3.11 Discovery is serial and slow.** `discover` worst-cases ~45 s (CivitAI then HF, no memo,
full rglob + double stat on network shares) — H2 bundle carries the ThreadPool/memoization fix. 🟡
**3.12 License posture for found assets.** `discover` surfaces CivitAI/HF models with no license
field in the recommendation. Studios care. Surface the license in `discover` results and add a
strict mode that downranks/blocks unclear licenses (config flag, default off).
**3.13 Known sibling bugs on the ledger.** `provision_pipeline_status` reads the same wrong key
repair did (quarantined as L-PIPESTAT until probed); `load_workflow_from_data` (sidebar
injection) bypasses the validated-consent clear (L-INJECT-VALIDATED); `_openai.py` has the same
fresh-client-per-call pattern vision just shed. All have named probes; none is forge-eligible
until probed — listed so they're not forgotten.

---

## 4. Recommended order of work

| # | Item | Why this order | Vehicle |
|---|------|----------------|---------|
| 1 | H2 caching bundle (validate loop 12 s → sub-second re-validate) | The daily loop; everything compounds on it | H2 (two-leg race, baselined) |
| 2 | H4 persistence (append-only + fsync + lock) + download resume/progress | Data loss + the most visible reliability gap | H4 |
| 3 | CI installs usd-core; test the Pythons we advertise | Honesty of every green checkmark after it | small standalone PR |
| 4 | Timeout coherence (per-tool budgets through MCP) + WS hardening | Long jobs are normal jobs in VFX | H2/H3 leftovers |
| 5 | EXR/OCIO ingestion for the vision loop | Unlocks VERIFY for actual deliverables | new branch, after #63 merges |
| 6 | workflow.lock reproducibility sidecar | Question #1; cheap once registry hashes are wired | new, pairs naturally with H2's registry work |
| 7 | Multi-endpoint engine pool | Multi-artist floors | engine-adapter feature |
| 8 | H5 lead conversion (panel pass, model_compat, license mode, sibling bugs) | Probe-first discipline | H5 |

---

## 5. Measured baselines this plan is accountable to

| Metric | Today (measured ×3) | Target after #1–#2 |
|---|---|---|
| validate → fix → re-validate | 12.1–12.6 s | < 7 s first pass; re-validate < 0.5 s |
| per-poll during generation | 173–229 ms (~20% of each 1 s tick) | < 5 ms (pooled client) |
| cold `import agent.tools` | 470–536 ms | ≈ 200 ms (importer-side lazy stage) |
| vision payload, 4 K source | 3.9 MB (was 40.6 MB) 🔧 | hold |
| experience write per run | 10.9 MB rewrite | append-only delta |
| 12 GB model download interrupted at 95% | restart from 0 | resume from byte offset |

Noise band on the loop metrics is ≤13% (three-run splits recorded in the harness ledger), so
every claimed improvement above is required to clear it on a second fresh-process run before it
gets called real.

---

*Generated 2026-06-09 as part of the close-the-loop cycle (PRs #59–#64). Evidence for every
"measured/verified" claim lives in the harness ledger (`tooling/harness/LEDGER.md`) with
reproduce→clean records and branch SHAs.*
