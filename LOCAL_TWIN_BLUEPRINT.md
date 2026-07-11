# LOCAL TWIN BLUEPRINT — Comfy-Cozy Build Program

```
+== PROGRAM CAPSULE: local-twin ============================================+
| WHERE WE ARE:        Strategy ratified (see chat, 2026-07-11). This doc   |
|                      is the forge spec for the build track.              |
| MILE MARKER:         Mile 0 of 4. Four tracks, four weeks, hard gate.    |
| THE THESIS:          Comfy.org shipped Cloud MCP (June 29) and publicly  |
|                      punts local agent control to community servers.     |
|                      Comfy-Cozy becomes the production-grade local twin  |
|                      of Comfy Cloud MCP.                                 |
| NEXT ACTION:         WP-1.1 scout (PyPI name + path-assumption audit).   |
| RUNS PARALLEL TO:    Matt Miller / Comfy.org outreach (chat track — not  |
|                      in this doc).                                       |
| BLOCKERS:            None. All Week-1 work is unblocked today.           |
| GATE:                External signal by ~Aug 8 or program winds down     |
|                      cleanly. Criteria in §GATE.                         |
+===========================================================================+
```

**Public-safe:** this document is committable. All IP-adjacent mechanisms
(LIVRPS, recipes, provenance) are referenced only at the level already
public in `README.md`. Mechanism depth beyond that goes under NDA only.

---

## For the Claude Code session reading this cold

This is a **forge spec**, not a discussion doc. The strategic decision is
made: Comfy-Cozy is being packaged, positioned, and hardened as the local
counterpart to Comfy Cloud MCP, targeting the vacancy Comfy.org's own docs
describe ("What about local ComfyUI?" → community servers, local on
roadmap). Don't re-litigate direction. Each Work Package (WP) below is an
execution unit: **Scout items run before Build items, always.** Every
state-mutating chain terminates in Scribe (commit + doc update + CHANGELOG).

**Ratification status:** D1–D4 ratified as recommended, 2026-07-11.
**Revision R1 (same day, Joe-directed):** WP-4.0 latency trace scout
added, Track 5 (brain router) added, Track-4 optimization ordering made
evidence-gated. **All 17 WPs are cleared to forge.** Sequencing blocks
(scout-before-forge dependencies) still apply where noted.

---

## Mission / positioning (one paragraph)

Comfy Cloud MCP runs ComfyUI workflows on cloud GPUs from any MCP client.
Comfy-Cozy already runs them on **your** GPU with 133 tools, a default-deny
safety gate, reversible edits, provenance sidecars, and millisecond
zero-LLM recipes. The program: make Comfy-Cozy installable in one line,
speak Cloud MCP's dialect where the surfaces overlap, package it as a
Claude Code plugin, and publish the demo + numbers that prove the
local-twin claim. Everything a studio needs that a thin relay doesn't have.

---

## Hard constraints (apply to every WP)

| # | Constraint | Enforcement |
|---|-----------|-------------|
| C1 | `agent/stage/**` is frozen (design-only RFC window). No forge mutations. | Parity/plugin/bench work must not touch stage tools. WP-2.3 has an explicit check. |
| C2 | Patent-gated files stay gitignored; `feature/moneta-memory` stays local-only. | Tripwire already committed. New WPs never reference those paths. |
| C3 | Git discipline: atomic commits, merge commits (no squash), per-call approval for every push/remote op. Force-push forbidden. | Scribe step of every chain. |
| C4 | `$env:ANTHROPIC_API_KEY` stays empty at runtime (Max routing). | Never set in scripts, CI is the only exception (uses repo secrets, not local env). |
| C5 | Every new dispatched tool gets an explicit risk classification. `tests/test_gate_completeness.py` must pass. | WP-2.3 acceptance criterion. |
| C6 | No numeric performance claims before a measured baseline exists. | WP-4.1 lands before any README/benchmark numbers are published. |
| C7 | PowerShell syntax in all Windows commands/docs (backtick continuation, never `\`). | Doc review in Scribe. |
| C8 | Scout before forge: verify live API shapes, file:line citations, and install behavior before building on them. | Every WP lists its Scout items first. |

---

## Program map

| Week | Track 1 — Distribution | Track 2 — The Mirror | Track 3 — Plugin | Track 4 — Proof & Perf | Track 5 — Brains |
|------|------------------------|----------------------|------------------|------------------------|------------------|
| **1** | WP-1.1 PyPI · WP-1.2 sidebar cmd · WP-1.3 README fold | WP-2.1 schema scout | WP-3.1 comfy-skills scout | — | — |
| **2** | polish / fixes | WP-2.2 profiles · WP-2.3 parity tools · WP-2.4 outputs | WP-3.2 plugin build | WP-4.0 latency trace scout | WP-5.1 routing scout |
| **3** | — | contract tests green | plugin E2E | WP-4.1 bench · WP-4.2 run_intent · WP-4.5 demo kit | WP-5.2 brain router |
| **4** | — | — | marketplace ask | WP-4.3 / WP-4.4 in WP-4.0's ranked order · publish numbers | router stretch (evidence-gated) |

Rough total: ~20–24 forge-days across 4 weeks — **the month is now
full.** If anything slips, drop order: WP-4.4 first, then WP-5.2's
stretch tier (auto-routing), then WP-4.3. The gate artifacts (PyPI,
plugin, parity, demo, numbers) never drop. All Week-1/Week-2 scouts are
independent, parallel-safe sessions.

---

# TRACK 1 — DISTRIBUTION (kill the friction)

## WP-1.1 — PyPI package `[RATIFIED]`

**Objective:** `pip install comfy-cozy` and `uvx comfy-cozy` work on a
clean machine. The clone-and-editable-install funnel is where adoption
dies; the leading community competitor installs via one `npx` line.

**Scout first:**
- PyPI name availability: `comfy-cozy` (and fallback `comfycozy`).
- Audit `pyproject.toml`: current entry points, extras (`[dev]`,
  `[stage]`, `[embed]`), packaging includes.
- Grep the tree for repo-root path assumptions: `__file__`-relative
  climbs, `os.getcwd()` reliance, `.env` discovery, knowledge-file loads
  (`agent/knowledge/` or equivalent), recipe definitions, workflow
  templates, `panel/` + `ui/` asset paths. Produce a findings list with
  file:line before touching anything.
- Check what `agent` as a console-script name collides with on a clean
  system (it is a generically-named binary on PATH).

**Build:**
- Wheel-safe resource loading via `importlib.resources` for every asset
  the scout flags (knowledge files, templates, recipes, panel/ui assets).
- Console scripts: add `comfy-cozy` (primary) and `cozy` (short alias),
  keep `agent` for back-compat with a one-line deprecation notice in
  `--help`. (Final naming per D1.)
- Single-source version: `pyproject.toml` ↔ `agent.__version__`.
- sdist/wheel hygiene: exclude `sessions/`, `harness/` run artifacts,
  demo media. Tests ship in sdist only.
- CI publish: GitHub Actions **trusted publishing** to PyPI on version
  tag. No long-lived tokens.
- Keep heavy extras opt-in exactly as today: `[embed]` (torch CPU wheel),
  `[stage]` (USD). Base install stays light.

**Acceptance:**
- Clean venv, Windows + Ubuntu: `pip install comfy-cozy` →
  `comfy-cozy mcp` starts, connects to ComfyUI on `:8188`, dispatches a
  read-only tool successfully.
- `uvx comfy-cozy inspect` works with zero prior setup.
- Existing 4,680-test suite passes against the installed (non-editable)
  package in CI, not just the checkout.

**DEADENDS pre-seed:**
- Editable-install path assumptions (the known trap — this is why the
  scout audit is mandatory first).
- Bundling torch in the base wheel (never — keep `[embed]` opt-in).
- `agent` console-script collision reports from users → answer is the
  new primary name, not fighting for `agent`.

**Effort:** M (3–4 days incl. CI).

---

## WP-1.2 — `install-sidebar` command `[RATIFIED]`

**Objective:** replace the run-as-Administrator `mklink` instructions with
one command that needs no elevation.

**Build:**
- `comfy-cozy install-sidebar [--comfyui <path>] [--with-bridge] [--uninstall]`
- Windows: **directory junctions** (no admin required — this matches the
  prior installer decision; never symlinks on Windows). POSIX: symlinks.
- ComfyUI auto-detection: port existing `_find_comfyui.ps1` logic into
  Python; `--comfyui` overrides.
- `--with-bridge` also links `node_pack/comfy_agent_bridge`.
- Idempotent: re-running repairs broken links; `--uninstall` removes only
  what it created.

**Acceptance:** fresh ComfyUI install, non-elevated PowerShell, one
command, restart ComfyUI → sidebar tab present; bridge routes registered
when `--with-bridge` used. Covered by an integration test that fakes a
ComfyUI tree.

**Effort:** S (1 day).

---

## WP-1.3 — README top-fold repositioning `[RATIFIED]`

**Objective:** the first screen of the README sells the local twin in
10 seconds; depth stays below the fold (current depth is an asset — keep
all of it).

**Build:**
- New top fold: one-line positioning ("the production-grade local
  counterpart to Comfy Cloud MCP — your GPU, your models, reversible,
  provable"), the one-liner install, a 60-second Claude Code path, the
  demo video slot (fills in Week 3).
- Comparison table (honest, no swipes): Cloud MCP / Comfy-Cozy / raw
  comfy-cli — execution locus, custom workflows, undo, provenance,
  offline, cost model.
- C6 applies: no latency numbers in the README until WP-4.1 produces them.

**Effort:** S (half day). Runs after WP-1.1 so the install line is real.

---

# TRACK 2 — THE MIRROR (cloud-parity surface)

## WP-2.1 — Live Cloud MCP schema capture `[RATIFIED]`

**Objective:** the parity layer is built against **verified live schemas**,
not blog posts. (Scout-before-forge is the whole WP.)

**Scout:**
- Connect an MCP inspector (or Claude Code `/mcp`) to
  `https://cloud.comfy.org/mcp` and dump the tool list: exact names,
  input schemas, return shapes, and the prompt set
  (`generate-image`, `search-models`, …). Requires a Comfy account —
  if beta access blocks, fall back to the public
  `Comfy-Org/comfy-skills` plugin source, which encodes the same surface.
- Record casing convention (tool names vs. prompt names differ — verify
  `run_saved_workflow` / `submit_workflow` spelling from the wire, not
  coverage articles).
- Note documented limitations verbatim-adjacent (conversion rough edges,
  shell-download outputs) — these are the gaps the local twin closes and
  they go in the map.

**Deliverable:** `docs/CLOUD_PARITY_MAP.md` — one row per Cloud tool:
name · params · returns · Comfy-Cozy equivalent path · gap notes ·
parity decision (mirror / adapt / omit-v1).

**Effort:** S (half–1 day). **Blocks WP-2.3.**

---

## WP-2.2 — MCP tool profiles `[RATIFIED]`

**Objective:** tool-surface discipline. 133 tools flooding a client
agent's context is itself a latency and cost problem; Cloud MCP ships ~16.
Profiles make Comfy-Cozy polite in Claude Code without amputating the
full surface.

**Build:**
- `comfy-cozy mcp --profile {parity|core|vfx|full}` (+ `MCP_PROFILE` env).
  - `parity` ≈ the Cloud-mirror set (WP-2.3) + `undo` + `list_recipes` /
    `apply_recipe` — the polite default for client agents.
  - `vfx` = parity + EXR/vision + provenance + profiling tools.
  - `full` = all 133 (current behavior, remains repo default — no
    behavior change for existing users; the plugin ships `parity`).
- Filtering applies to MCP tool *listing*; the dispatcher and gate remain
  complete underneath (a filtered-out tool called explicitly returns a
  clear "not in this profile" error, not a crash).
- Gate completeness test still covers all 133 regardless of profile.

**Acceptance:** profile flag changes the advertised tool list; parity
profile lists ≤ ~22 tools; all existing tests pass with `full`.

**Effort:** S–M (1–2 days).

---

## WP-2.3 — Parity alias tools `[RATIFIED, blocked by WP-2.1]`

**Objective:** an agent pointed at Comfy-Cozy can use the same tool
vocabulary it learned on Cloud MCP — swap the server, keep the prompts.
This is the "we can help each other" mechanism made concrete: Comfy-Cozy
becomes the local dialect of *their* contract instead of a divergent
ecosystem.

**Build — `agent/tools/parity.py` (new module, TOOLS-list dispatch):**

| Cloud tool (verify in WP-2.1) | Delegates to (existing Cozy path) | Notes |
|---|---|---|
| `generate_image` | template compose → validate → execute (pipeline path) | family auto-detect stays |
| `generate_video` | LTX-2 / WAN template path | only if local template validates on scout hardware |
| `upscale_image` | existing upscale workflow path | |
| `remove_background` | existing template if present; else **omit v1** | honest-surface rule |
| `search_templates` | `workflows/` + template library search | |
| `search_models` | existing discovery (CivitAI + HF + local) | local disk results are the differentiator — include them |
| `search_nodes` | registry search (31k index) | |
| `run_saved_workflow` | load → validate → execute by filename | |
| `submit_workflow` | execute API-format graph | validate-first gate still applies |
| `help` | profile-aware capability summary | |

**Rules:**
- **Aliases are routing, not new capability.** Every alias dispatches
  through `handle()` so the safety gate applies unchanged. Nothing
  bypasses validate-before-execute; installs/downloads still escalate for
  confirmation. No exceptions for parity's sake.
- **Honest surface:** if local can't genuinely serve a Cloud tool
  (`generate_audio`, `generate_3d` v1), **omit it** rather than stub it.
  The gap column in `CLOUD_PARITY_MAP.md` is the roadmap, not a fake tool.
- **C1 check:** none of the parity set may route into `agent/stage/**`.
  Confirm at design review before forge.
- Each alias gets an explicit risk classification (C5).

**Acceptance:**
- Side-by-side prompt test: a fixed set of natural-language asks that
  work against Cloud MCP produce equivalent results against
  `--profile parity` (documented transcript in `docs/`).
- Contract tests per alias (mocked ComfyUI), gate completeness green,
  full suite green.

**Effort:** M–L (3–4 days).

---

## WP-2.4 — Output ergonomics `[RATIFIED]`

**Objective:** exploit the structural local advantage — Cloud MCP outputs
require a shell download step; local outputs are already on disk.

**Build:** consistent return shape for every executing tool: absolute
output path(s), dimensions/format, elapsed, and the session/undo handle.
No download dance, ever. Small module-level change + tests.

**Effort:** S (half–1 day).

---

# TRACK 3 — CLAUDE CODE PLUGIN

## WP-3.1 — Scout `Comfy-Org/comfy-skills` structure `[RATIFIED]`

**Scout:** clone the public repo; record the plugin anatomy exactly —
`plugin.json` fields, `commands/`, `skills/`, hooks, marketplace
registration mechanics, naming conventions. Deliverable: one-page
`docs/PLUGIN_ANATOMY.md` with file:line references. **Blocks WP-3.2.**

**Effort:** S (half day).

---

## WP-3.2 — `comfy-cozy` plugin `[RATIFIED, blocked by WP-3.1]`

**Objective:** installation and daily driving inside the exact surface
Comfy.org demoed — `/plugin marketplace add …` → `/plugin install
comfy-cozy` → talking to a local ComfyUI.

**Build (dedicated repo `JosephOIbrahim/comfy-cozy-skills`, mirroring the
Comfy-Org convention — per D3):**
- Bundled MCP config: `uvx comfy-cozy mcp --profile parity` (zero-install
  path courtesy of WP-1.1).
- Slash commands:
  - `/comfy-cozy:setup` — checks ComfyUI, installs package, runs
    `install-sidebar`, registers MCP.
  - `/comfy-cozy:generate-image`, `/comfy-cozy:run-workflow`,
    `/comfy-cozy:validate`, `/comfy-cozy:undo`, `/comfy-cozy:status`
  - `/comfy-cozy:recipe <name>` — the demo-friendly one: instant
    deterministic edits by name (dreamier / sharper / faster / …).
- One plugin skill: distilled model-family knowledge + house rules for
  driving Comfy-Cozy (validate-then-run, installs always confirm),
  condensed from the existing knowledge files.

**Acceptance:** cold machine with ComfyUI running: marketplace add →
install → `/comfy-cozy:setup` → `/comfy-cozy:generate-image` produces an
image. Recorded as part of the Week-3 demo.

**Effort:** M (2–3 days).

---

# TRACK 4 — PROOF & PERFORMANCE (measure first, then move)

## WP-4.0 — Latency trace scout `[RATIFIED — R1]`

**Objective:** know where the seconds actually live before spending forge
days moving them. First principles — one Comfy-Cozy interaction crosses
six layers, and any of them can hide the bottleneck:

| Layer | What it is | Existing hook |
|---|---|---|
| **L1** | Client-agent round trips (turn count × model latency) | — (count per scenario) |
| **L2** | Model inference: TTFT, tok/s, thinking budget, prompt size, cache hit rate | `llm_call_duration_seconds` per-provider metrics |
| **L3** | Transport: stdio/HTTP framing, serialization, polling gaps | — |
| **L4** | Cozy server: dispatch, gate checks, tool bodies, cold imports, object_info fetch | per-session correlation IDs |
| **L5** | ComfyUI: queue wait, model load, execution (GPU-bound — attribute it, don't own it) | `get_execution_profile` per-node timing |
| **L6** | Perceived: time-to-first-signal vs time-to-completion | streaming callbacks |

L2's biggest silent tax is tool-schema volume in the client prompt —
WP-2.2 profiles are a **latency lever**, not just etiquette. This scout
records the prompt-size and turn-latency delta of `parity` vs `full` as
evidence.

**Scout:**
- Diff methodology against SYNAPSE's `LATENCY_PLAN.md` +
  `_benchmark_latency.py` (local checkout) — portfolio prior art. Reuse
  what transfers; note where MCP client/server topology diverges from
  SYNAPSE's inside-out shape (SYNAPSE's Mile-5 style budget-per-hop
  framing transfers directly).
- Inventory existing instrumentation (LLM metrics, correlation IDs,
  execution profiler) and add span-level timing where layers are dark —
  L3 and L4 dispatch/gate especially. Spans ride the existing logging +
  correlation-ID rails; no new observability framework.
- Trace six representative interactions end-to-end, N runs, cold + warm:
  recipe edit · LLM-mediated edit · validate→run · full intent→image ·
  model swap · server cold start.

**Deliverable:** `docs/LATENCY_MAP.md` — per-layer attribution per
scenario, ranked hotspot list, and a **binding recommendation**: the
order in which WP-4.2 / 4.3 / 4.4 (and any newly discovered lever) land.
Track-4 build order follows this document, not the original guess.

**DEADENDS pre-seed:** L5 internals are upstream's lane (Dynamic VRAM
era — don't re-litigate ComfyUI memory management); no third-party
tracing frameworks; the scout instruments, it does not refactor.

**Effort:** S–M (1.5–2 days). **Binds the ordering of WP-4.3/4.4.**
WP-4.2 may forge in parallel — its round-trip math is structural and
doesn't need the map to be justified.

---

## WP-4.1 — Benchmark harness `[RATIFIED, consumes WP-4.0 instrumentation]`

**Objective:** turn "next-gen latency" from claim into table. C6: harness
and baseline first; published numbers only after.

**Build — `tooling/bench/`:**
- Scenarios (median of N, hardware + versions recorded):
  1. Recipe apply (`apply_recipe dreamier`) — wall-clock ms, tokens = 0.
  2. Equivalent edit via LLM round-trip (same mutation through the model).
  3. Validate cold / re-validate warm.
  4. Intent → first image, end-to-end local (fixed workflow, fixed seed).
  5. Same workflow submitted via raw `comfy-cli` path (the two-layer
     comparison an agent would otherwise ride).
  6. *(Optional, account-dependent)* same intent via Cloud MCP — queue +
     execution + download, fairly measured, clearly labeled.
- Output: `BENCHMARKS.md` (auto-generated) + `benchmark_log.jsonl`
  (append-only, matches existing champion-tracking convention).
- Methodology section written before results exist — no target numbers
  anywhere until runs complete.

**Effort:** M (2 days).

---

## WP-4.2 — Composite tool: `run_intent` `[RATIFIED]`

**Objective:** the biggest *agent-perceived* latency lever is client
round-trips, not server ms. One call: validate → auto-fix (within
existing rules) → execute → return outputs + timings + what-was-fixed.

**Build:**
- New tool wrapping the existing lifecycle; execution-class risk;
  validate-before-execute satisfied internally; **installs still escalate
  to the user — never auto-confirmed inside a composite. No exceptions.**
- Returns structured failure with repair options when it can't proceed
  (missing packs → the list, awaiting confirmation).
- Measure round-trip count vs. the discrete-tool path; feed WP-4.1.

**Acceptance:** single tool call from Claude Code yields image or
structured next-step; gate tests green; bench shows the round-trip delta.

**Effort:** M (2 days).

---

## WP-4.3 — MCP progress notifications `[RATIFIED, order per WP-4.0]`

**Objective:** live progress in the client without polling.

**Scout:** confirm progress-notification support in the MCP server
implementation currently in use (SDK version + client behavior in Claude
Code/Desktop).

**Build:** wire the existing `ExecutionEvent` / trigger registry stream
into MCP progress notifications for executing tools (step %, node names,
queue position). Fallback silently when a client ignores them.

**Effort:** S–M (1–2 days).

---

## WP-4.4 — Schema-cache warm start `[RATIFIED, stretch — order per WP-4.0]`

**Objective:** cold-start latency. Persist the object_info-derived schema
cache to disk keyed by ComfyUI version + node-pack set hash; load warm on
boot, invalidate on key change. Mirrors the established static/volatile
split pattern. **Stretch — drop first if Week 3 runs hot.**

**Effort:** S–M (1–2 days).

---

## WP-4.5 — Demo kit `[RATIFIED]`

**Objective:** the 90-second artifact that travels.

**Build — `demo/`:**
- Curated workflow set + pinned models list (provision script, confirms
  before download per house rules).
- Beat sheet: (1) parity beat — talk to Claude Code, workflows execute
  headless on the 4090, no interface; (2) differentiators cloud can't do —
  `/comfy-cozy:recipe dreamier` landing in milliseconds, `undo`,
  `workflow.lock` drift warning firing, EXR analysis; (3) the install
  line on screen for 3 seconds.
- Recording checklist (voice via OS dictation — out of repo scope).

**Effort:** S build + a recording session.

---

# TRACK 5 — BRAINS (SYNAPSE-pattern LLM routing)

## WP-5.1 — Routing-mechanism scout `[RATIFIED — R1]`

**Objective:** extract the switching mechanism worth porting, with
file:line citations, before designing the router. The public SYNAPSE
README documents the Dispatcher and an Anthropic-only vendored SDK loop;
the routing machinery this track ports lives deeper
(`SYNAPSE-asm-routing/`, `SYNAPSE-asm-handler/`, `agents/`,
`python/synapse/cognitive/`). **Scout the local checkout, not the
README.**

**Scout:**
- SYNAPSE side: map the routing/handler surface — how a request selects
  a brain, where aliases/roles live, how a failure re-routes, what state
  survives a switch. File:line per mechanism.
- Comfy-Cozy side: inventory the current switching surface —
  `LLM_PROVIDER` + `AGENT_MODEL` / `FAST_MODEL` / `VISION_MODEL` env
  vars, `--model` aliases, `swap_model` atomic swap w/ rollback,
  per-provider `convert_messages` ThinkingBlock policies. File:line.
- Diff: what SYNAPSE does that Cozy doesn't; what Cozy already has that
  only needs unifying; where mid-session history translation is fragile
  (provider-boundary swaps mid-tool-loop is the known seam).

**Deliverable:** `docs/BRAIN_ROUTING_SCOUT.md` + a one-page design
sketch for WP-5.2. **Effort:** S (0.5–1 day). **Blocks WP-5.2.**

---

## WP-5.2 — Brain Router `[RATIFIED — R1, blocked by WP-5.1]`

**Objective:** one coherent routing layer instead of five parallel env
vars — the right brain for each call class, switchable in one gesture,
resilient to provider failure.

**Build (`agent/llm/router.py`, final shape per the 5.1 sketch):**
- **Registry — single source of truth.** Models + providers with
  capability flags (vision, tools, thinking, context window) and
  aliases. Existing env vars become *inputs* to the registry, not
  parallel truths.
- **Role table.** `planner / executor / triage / vision` → model chains.
  Formalizes the plan-down/escalate-up pattern already in daily use;
  AGENT/FAST/VISION vars map onto roles for back-compat.
- **Failover chains.** Provider error → next in chain. Bounded, logged,
  and surfaced to the user ("switched to X after Y timed out"). Extends
  the existing atomic swap + rollback; does not replace it.
- **Swap-integrity conformance tests.** Mid-session, mid-tool-loop swaps
  across every provider pair — the ThinkingBlock translation seam gets
  pinned by tests, not hope.
- **Surface.** `set_route` / `get_routes` tools + one sidebar pill
  showing the active chain. `swap_model` stays as the manual override.
- **Stretch (evidence-gated by WP-4.0):** latency/cost-aware chain
  ordering fed by the rolling per-provider stats the metrics layer
  already collects. Post-gate unless the month runs smooth.

**Acceptance:** all five providers register; role routing honored in
agent loop + sidebar + MCP modes; kill a provider mid-session → chain
fails over within one turn, visibly; conformance suite green across
provider-pair swaps; existing provider suites untouched and green.

**Constraint check:** `agent/llm/` only — no stage paths (C1); routing
never writes provider keys (C4 intact).

**Effort:** M (2.5–3 days).

---

## Explicitly parked (do not let these balloon into the month)

| Item | Status |
|---|---|
| May capsule Action 1 (collapse comfy-moneta-bridge → direct import) | **Parked behind gate.** Unblocked, still right, not this month. |
| May capsule Action 3 (LIVRPS compile-time resolution cache) | **Parked behind gate.** Pairs naturally with post-gate perf work. |
| May capsule Action 2 (real embedder) | Effectively landed (BGE shipped, opt-in). Switch-on decision post-gate. |
| Speculative low-res preview passes | Parked — WP-4.2/4.3 first. |
| Local `generate_audio` / `generate_3d` templates | Gap column in parity map; post-gate. |
| Windows GUI installer (Inno Setup) | Horizon item stays horizon. PyPI + uvx is this month's answer. |
| Shared cognitive kernel / three-ABC extraction | Separate program; untouched by this one. |
| Rust shim (Option B) | +9 months per standing decision. Not revisited. |
| Latency/cost-aware auto-routing | WP-5.2 stretch tier; evidence-gated by WP-4.0, post-gate by default. |
| Model arena / task-scored brain comparisons | Post-gate. The router's registry is the prerequisite; the arena is not. |

---

## DECISIONS — ratified 2026-07-11

| # | Decision | Recommendation | Blocks |
|---|----------|----------------|--------|
| **D1** | PyPI + console-script naming | Package `comfy-cozy`; scripts `comfy-cozy` (primary) + `cozy` (alias); keep `agent` with deprecation notice | WP-1.1 |
| **D2** | Parity naming + default profile | Mirror Cloud names **exactly** in the parity profile (native names live on in `full`); repo default stays `full`, plugin ships `parity` | WP-2.2, 2.3 |
| **D3** | Plugin home | Dedicated repo `comfy-cozy-skills`, mirroring Comfy-Org's marketplace convention | WP-3.2 |
| **D4** | Benchmark v1 scope | Local + comfy-cli comparison ships regardless; Cloud numbers only if account access lands, clearly labeled | WP-4.1 scope |

**All four ratified as recommended.** Table retained as the decision
record — D1's naming details are binding spec for WP-1.1; D2's profile
split is binding for WP-2.2/2.3; D3 fixes the plugin repo; D4 fixes
bench-v1 scope.

---

## GATE (≈ Aug 8)

**Table stakes (in our control — shipping these is not the gate):**
PyPI package live · plugin installable · parity profile passing the
side-by-side transcript · demo recorded · benchmarks published.

**The gate (external signal — any ONE):**
1. Engagement from Comfy.org (Matt, Discord `#comfy-mcp-and-cli`,
   issue/PR response).
2. Listing — docs "What about local ComfyUI?" section or skills
   marketplace.
3. Adoption inflection — first real external users filing issues, or a
   step-change in installs.

One of three → the lane is real, continue (and un-park the capsule
actions). Zero of three → wind down to maintenance mode cleanly. Both
outcomes are progress; the gate exists so August starts with an answer
instead of a feeling.

---

## MOE dispatch guide (per WP)

| WP | Chain |
|----|-------|
| 1.1 | `[PACKAGING × SCOUT]` → `[PACKAGING × FORGE]` → `[PACKAGING × CRUCIBLE]` → `[PACKAGING × SCRIBE]` |
| 1.2 | `[PACKAGING × FORGE]` → `[CRUCIBLE]` → `[SCRIBE]` |
| 1.3 | `[POSITIONING × SCRIBE]` (doc-only) |
| 2.1 | `[PARITY × SCOUT]` → `[SCRIBE]` (map doc) |
| 2.2 | `[PARITY × ARCHITECT]` → `[FORGE]` → `[CRUCIBLE]` → `[SCRIBE]` |
| 2.3 | `[PARITY × ARCHITECT]` → `[FORGE]` → `[CRUCIBLE]` → `[SCRIBE]` |
| 2.4 | `[PARITY × FORGE]` → `[CRUCIBLE]` → `[SCRIBE]` |
| 3.1 | `[PLUGIN × SCOUT]` → `[SCRIBE]` |
| 3.2 | `[PLUGIN × FORGE]` → `[CRUCIBLE]` → `[SCRIBE]` |
| 4.0 | `[PERF × SCOUT]` → `[SCRIBE]` (latency map doc) |
| 4.1 | `[PERF × ARCHITECT]` → `[FORGE]` → `[CRUCIBLE]` → `[SCRIBE]` |
| 4.2 | `[AUTONOMY × ARCHITECT]` → `[FORGE]` → `[CRUCIBLE]` → `[SCRIBE]` |
| 4.3 | `[TRANSPORT × SCOUT]` → `[FORGE]` → `[CRUCIBLE]` → `[SCRIBE]` |
| 4.4 | `[PERF × FORGE]` → `[CRUCIBLE]` → `[SCRIBE]` |
| 4.5 | `[POSITIONING × FORGE]` → `[SCRIBE]` |
| 5.1 | `[BRAINS × SCOUT]` → `[SCRIBE]` (routing scout doc) |
| 5.2 | `[BRAINS × ARCHITECT]` → `[FORGE]` → `[CRUCIBLE]` → `[SCRIBE]` |

Gemini red-teams the WP-2.3, WP-4.2, and WP-5.2 diffs (safety-gate and
provider-seam adjacency) before merge. Diffs only; Gemini never authors
or executes.

---

## Appendix A — Cloud MCP surface as currently documented
*(to be replaced by WP-2.1 verified capture)*

Server: `https://cloud.comfy.org/mcp` · OAuth (Claude Code/Desktop) or
API key (`X-API-Key`, Cursor/headless) · public beta since 2026-06-29.
Prompt set: generate-image, generate-video, generate-audio, generate-3d,
upscale-image, remove-background, search-templates, search-models,
search-nodes, help. Workflow execution: `run_saved_workflow` (by
filename, server converts), `submit_workflow` (API-format graph; metadata
embedding imperfect). Known launch limitations: editor→executable
conversion rough edges; outputs require a shell download step; complex
multi-node builds may need retries. Local ComfyUI: explicitly out of
scope, on roadmap; community servers recommended in the interim.

```
+== END BLUEPRINT ==========================================================+
| Generated: 11 Jul 2026 · Source: Zerospace intel + live-docs research    |
| Revised R1: 11 Jul 2026 — WP-4.0 latency trace scout · Track 5 brain    |
| router · Track-4 ordering evidence-gated. 17 WPs total.                  |
| Companion track (not in this doc): Matt Miller outreach, NDA if the     |
| conversation reaches mechanism depth.                                    |
+===========================================================================+
```
