# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

`pip install comfy-cozy` now means what it says: the distribution takes the
project's real name, the version has one source of truth, and an installed
wheel behaves like a good citizen — state lives in `~/.comfy-cozy`, not in
site-packages.

### Added
- **`comfy-cozy` + `cozy` console scripts** — both launch the same Typer app;
  `agent` is kept as a deprecated alias (see Changed).
- **Packaging gate** — CI builds the wheel, installs it into a clean venv, and
  runs the test suite against the *installed* package (data families
  knowledge/, profiles/, schemas/, templates/ asserted present; suite runs
  minus `tests/test_provisioner.py`, matching the long-standing release.yml
  exclusion).
- **PyPI trusted-publishing lane** — release workflow wired for OIDC publish,
  dormant until enabled.
- **User-home state dir for installed packages** — sessions, logs, and
  `BLOCKER.md` land in `~/.comfy-cozy` (override with `COMFY_COZY_HOME`).

### Changed
- **Distribution renamed `comfyui-agent` → `comfy-cozy`** (the `agent` import
  package is unchanged).
- **Version single-sourced** from `agent.__version__` via
  `[tool.hatch.version]`; the static `version` line in `pyproject.toml` is gone.
- `.env` discovery now checks the home config dir (`~/.comfy-cozy/.env`) then
  the checkout root, most specific last; a CWD `.env` is deliberately excluded
  (untrusted-directory hardening).
- `agent` console script deprecated (kept as an alias; removal in a future
  major release — the `--help` epilog says so).
- NIM warm-state dot-dir unified to `~/.comfy-cozy`.

### Removed
- `LOCAL_WORKFLOWS_DIR` config constant (dead — zero consumers).

### Fixed
- Installed packages no longer write sessions/logs/`BLOCKER.md` into
  site-packages.
- `validate_path` no longer whitelists site-packages when running from a wheel.
- `cognitive` no longer climbs into `agent/templates` — it ships its own copy
  and falls back loudly.
- Build identity (`agent/_build.py`) can no longer report a *foreign* repo's
  HEAD: the git probe only runs when the install root is actually this repo.

## [5.6.0] - 2026-07-08 — Switchboard

Pick any engine, keep your pick, and see which ones are actually live. Runtime
model switching grew a capability-aware selector — ported from SYNAPSE's panel
design onto the existing atomic swap core: a sixth "bring-your-own" engine, a
gate that won't hand you a model that can't run the tools, a choice that survives
restarts, and a health column that tells you which engines answer. All additive —
the atomic, rollback-on-bad-key swap core is untouched.

### Added
- **Custom engine — 6th LLM provider** (`LLM_PROVIDER=custom`, `agent/llm/_custom.py`).
  Point `CUSTOM_BASE_URL` / `CUSTOM_API_KEY` / `CUSTOM_MODEL` at any OpenAI-compatible
  endpoint — self-hosted vLLM/SGLang, LM Studio, LiteLLM, OpenRouter, or your own
  gateway. A plain passthrough (no Nemotron `<think>` handling), so a local endpoint
  isn't mislabeled `nvidia` anymore.
- **Capability-aware model gate** (`agent/llm/swap.py`). A swap refuses a model that
  can't tool-call *before* mutating any state (no half-swap), and warns on a vision
  swap to a text-only engine. A no-op for every existing (tool-capable) alias.
- **Persisted model selection** (`agent/llm/_selection.py`). Your last swap is
  remembered across restarts at `~/.comfy-cozy/model_selection.json`
  (`MODEL_SELECTION_PATH` to relocate); an explicit `--model` still wins. Boot replay
  is best-effort — a missing/corrupt file degrades to defaults, never crashes.
- **Preflight health column** (`agent/llm/_health.py`). `list_models_available` now
  returns a per-alias `status`: `configured` (free, static — is the key/endpoint set?)
  always, plus opt-in `reachable` / `latency_ms` via `probe=true` — a bounded,
  concurrent, read-only ping that never touches the active selection.

### Changed
- **5 → 6 LLM providers** (added `custom`). README, config table, provider keywords,
  and the provider-abstraction diagram updated to match.
- `list_models_available` now returns `capabilities` + `status` alongside `aliases`;
  `swap_model` persists the choice and enforces the tool-calling gate.
- Fixed a latent `create(timeout=…)` path in the OpenAI-family provider that dropped
  the custom `base_url` (now derived via `with_options`).

### Fixed
- `agent/__init__.py` `__version__` synced `5.4.0` → `5.6.0` (was two releases stale);
  `agent/mcp_server.py` now advertises the correct version and
  `scripts/validate_project.py`'s pyproject↔`__init__` check passes.
- 6-provider consistency sweep — `custom` added to the `CLAUDE.md` provider table,
  `docs/DIRECTION.md`, `.env.example`, and the `config.py` / `llm/__init__.py` /
  `main.py` provider enumerations.

### Verified
- 4,744 passed / 2 skipped across independent full-suite runs; CI green on the full
  matrix (Ubuntu + Windows × Python 3.10–3.13) for the code merge (PR #86). The
  A+B+C+D port was adversarially reviewed twice (build + safety) — the health surface
  provably never mutates the active selection, hangs, or raises.

## [5.5.0] - 2026-07-02 — Zero-LLM Recipes

"Dreamier", "sharper", "faster" now land in milliseconds: the most common artist
intents apply as deterministic parameter macros with **no LLM round-trip** — and
the machinery that will build the 6.0 line moved into the repo, adversarially
verified by its own skeptic panel.

### Added
- **Zero-LLM recipe layer** (`agent/recipes/`) — 14+ built-in recipes: intent
  macros (dreamier, sharper, faster, ...) plus build recipes for common workflow
  assemblies. Every expanded step re-enters the dispatcher, so the existing
  safety gate vets each one; every change is one `undo_workflow_patch` away.
  Tools: `apply_recipe`, `list_recipes`.
- **v2 build-harness runway** (`tooling/harness/`, dev-infra) — the mechanical
  accept gate `verify_ratchet.py` (junit-sourced counts, name-exact flake
  tolerance, master-pinned thresholds, delta-reconciled baselines, fail-closed
  disclosure scan), the binding 75-core tool census, and the ORCHESTRATOR_v2
  constitution governing how the 6.0 line gets built. Its first commit was
  refuted 3/3 by its own adversarial panel, rebuilt, and re-judged — the gate
  earned its job before getting it.

### Changed
- Tool count 131 → **133** (`apply_recipe`, `list_recipes` — READ_ONLY
  dispatchers; the steps they expand are individually gated).
- README: ADHD-friendly pass — scannable intro, one-fact-per-line TL;DR,
  jump-to navigation, a new Zero-LLM Recipes section, and counts trued against
  the live registry across four mermaid diagrams. Repo description refreshed.
- `.claude/settings.local.json` untracked and gitignored — machine-personal
  permission state no longer ships in history; `.env.bak` / `*.log` gitignored.

### Verified
- 4,686 passed / 0 failed across three independent full-suite runs on the merged
  content; CI 9/9 per merge (Ubuntu + Windows × Python 3.10–3.13). Coverage
  floor measured and pinned at 85.0% (windows/py3.12 canonical leg).

## [5.4.0] - 2026-06-24 — Brain Swap

NVIDIA Nemotron joins the lineup as a fifth LLM provider, and you can now swap the
reasoning model at launch or mid-conversation — no restart.

### Added
- **NVIDIA Nemotron provider** (`agent/llm/_nvidia.py`) — endpoint-agnostic,
  OpenAI-compatible, serving NVIDIA NIM cloud, OpenRouter, and self-hosted
  vLLM/SGLang from one provider. Nemotron's `<think>` reasoning is stripped from
  the visible stream **and** the replayed history (off by default); tool-call
  errors are translated to plain language; streaming usage feeds context
  compaction. Aliases `nemotron` (super-120b), `nemotron-ultra` (550b),
  `nemotron-nano` (30b) — model ids verified live against NVIDIA's `/v1/models`.
- **Runtime model swap** — `agent run --model <alias>` / `--provider`, plus the
  `swap_model` / `list_models_available` MCP/CLI tools. Atomic (rolls back on a
  bad key via a 1-token live probe), reaches the live loop per-turn, and never
  moves vision off a multimodal provider (`VISION_PROVIDER`, default `anthropic`).
- **Provider-aware context window** — `NVIDIA_CONTEXT_WINDOW` opt-in lets a
  long-context Nemotron use its window instead of the default compaction floor.

### Changed
- Tool count 129 → **131** (the two model-swap tools, risk-classified in the gate).
  The provider abstraction now spans **five** providers with full conformance parity.
- CLI key gate is provider-aware; `agent/brain/vision.py` reads `VISION_PROVIDER`
  so swapping the loop to a text-only model never breaks `analyze_image`.

### Verified
- Full mocked suite green (4,600+ tests); CI 8/8 (Ubuntu + Windows × Python
  3.10–3.13). Live end-to-end against NVIDIA NIM cloud — completion + tool-calling
  + reasoning filter, across the super and nano tiers.

## [5.3.1] - 2026-06-11 — Panel Hardening

The L-PANEL adversarial pass — the cap-killed UI dimension probed against live
source, the verifiable defects fixed.

### Security
- **The `/agent/*` canvas-bridge routes were unauthenticated mutation surface.**
  `push_workflow_to_canvas` reloads every connected tab's canvas and
  `canvas_changed` seeds the buffer the agent later trusts — both ungated while
  every `/comfy-cozy/*` route was already gated. They now use the same
  Origin-first gate as the audited sidebar WebSocket (browser must be
  same-origin; non-browser callers must carry the Bearer token when
  `MCP_AUTH_TOKEN` is configured). The agent's own calls send the token
  automatically. Verified by unit tests and a live push → hand-edit round-trip
  against ComfyUI 0.24.

### Fixed
- **Raw exception text no longer leaks into the chat transcript.** Five
  chat/WebSocket error paths put the raw `str(e)` (internal paths,
  `[WinError …]`, dict KeyErrors) into the bubble the browser renders; they now
  emit a generic message while the full detail is logged server-side.

### Docs
- `docs/L-PANEL_ADVERSARIAL_PASS_JUNE_2026.md` records the full pass: two fixes,
  one refuted finding (the "`MCP_AUTH_TOKEN` 401s the bridge" claim was false),
  and three real-but-browser-bound findings (streaming render, tab-switch, dead
  modules) parked forge-ready with exact diffs.
- `docs/rfcs/RFC-001`: drop networkx — a 323 ms single-consumer core dependency
  — from the static Workflow-Intelligence DAG (design only; forge gated to the
  June-16 stage-freeze lift).

## [5.3.0] - 2026-06-11 — Shot-Ready

The second half of the production-hardening order (#69–#73): long jobs,
linear EXR, reproducibility, multi-worker floors, and the closing
lead-conversion round. Every performance/behavior claim was reproduced
live before the fix and verified after.

### Long jobs are normal jobs (#69)
- **Per-tool MCP dispatch budgets** replace the blanket 120 s kill that
  orphaned worker threads while telling the client the call failed. Budgets
  honor caller-supplied timeouts (clamped to 24 h); `nim_run` gets its full
  cold-pull window (~21 min), downloads wait unbounded (byte-bounded with
  per-read liveness), and the vision tools keep their inner-timeout-wins
  invariant. Timeout messages now state the budget and how to check on
  background completion.
- **WebSocket hardening**: 16 MiB frame cap (previews over 1 MiB used to
  close the socket with code 1009), pings that survive model-load stalls,
  mid-stream disconnects translated to the engine's error family, and
  `nim_run` now falls back to history polling instead of failing a queued
  run when the socket dies — warm-state timing is only recorded when it
  was actually observed.

### The VFX-specific gap (#70)
- **Linear EXR ingestion for the vision loop**: ACEScg→sRGB display
  transform (header-chromaticity aware) in front of `analyze_image` /
  `compare_outputs` / `hash_compare_images`; data/utility passes (Z,
  normals) are refused with a channel-naming message instead of being
  judged as images; unknown image formats now error actionably instead of
  being sent to the API mislabeled as PNG. New optional extra:
  `pip install comfyui-agent[exr]`.

### Reproducibility (#71)
- **`workflow.lock` sidecar**: `save_workflow` pins every referenced model
  file's SHA-256, every custom pack's installed git commit, and the ComfyUI
  version next to the saved graph; `validate_before_execute` warns when
  anything drifted since the lock. Drift informs — it never blocks. Hashes
  are stat-cached so re-saves never re-hash a 12 GB checkpoint.

### Multi-artist floors (#72)
- **`COMFYUI_ENDPOINTS` engine pool**: per-host circuit breakers (one
  unhealthy worker never opens the circuit for its siblings), failover with
  the breaker's recovery cycle as the health check, and job affinity —
  history/ws/interrupt for a prompt route back to the worker that queued it.
  Single-endpoint mode is byte-identical to before.

### Honesty round (#73)
- `provision_pipeline_status` could never report missing nodes from real
  data (same wrong-key class as the original repair bug) — fixed.
- A sidebar-injected graph no longer inherits the previous graph's
  validation consent.
- `model_compat`: WAN 2.2 recognized; boundary-checked family matching (no
  more `mysd15_style_sdxl` → sd15); unknown families surfaced instead of
  silently passing.
- A POSIX-only kill in an e2e teardown aborted cleanup mid-`finally` on
  Windows, leaking adapter state into bystander tests — fixed, plus a
  vacuous never-awaited MCP test now drives the real handler, and four
  rotten integration tests were realigned to current reality.

## [5.2.0] - 2026-06-11 — The Production Floor

### Performance (measured, reproduce records in `tooling/harness/`)
- **Validate → fix → re-validate: 7.2 s → 0.48 s (−93%).** `/object_info` is
  now fetched class-scoped (KB instead of 4.6 MB) behind a TTL+invalidate
  cache in `comfy_api.py`; a re-validate after a fix costs ~1 ms. All seven
  fetch sites converted; node-pack install/uninstall invalidate the cache.
- **Status polls: ~170 ms → 0.3 ms.** The engine adapter keeps one pooled
  HTTP client instead of a fresh TLS handshake per 1 s poll.
- **Cold `import agent.tools`: ~500 ms → ~195 ms.** Stage modules
  (networkx + pxr) lazy-register importer-side.
- **`discover`: external sources concurrent + 120 s memo** (was serial,
  worst ~45 s per identical re-query).

### Reliability
- **Experience log is append-only and fsync'd** — one line per run instead
  of a full 10.9 MB rewrite; compaction bounds the file. The
  `EXPERIENCE_FILE` default fork between the agent and cognitive layers is
  resolved (one canonical path; the panel and the pipeline finally read the
  same file).
- **NIM warm-state lost-update race closed** (lock across read-prune-rewrite,
  fsync before atomic replace); a transient read error no longer silently
  wipes history.
- **Interrupted model downloads resume** from the partial via HTTP Range
  (SHA-256 still covers the whole file), report real progress per MB, and
  the confirmation prompt identifies host/destination/resume state with
  zero pre-consent network. Transient failures keep the partial.
- The dispatcher forwards progress signature-aware — a TypeError inside a
  confirmed download can no longer re-execute the full fetch.

### CI honesty
- CI installs the USD stage extra: 21 stage-layer test files and
  `test_provisioner.py` (33 tests) now actually run on every leg instead of
  silently skipping, with an explicit `from pxr import Usd` check.
- Python 3.13 added to the matrix (advertised since 5.0, tested never).
- Integration tests excluded explicitly per the marker definition (they
  previously stayed out of CI only by every one of them happening to skip).
- The test suite no longer writes the developer's real experience store
  (~56 pipeline call sites now isolated to tmp dirs).

## [5.1.0] - 2026-06-10 — The Honest Gate

- Safety gate fails **closed** on import failure; live circuit-breaker state
  and per-session action history wired into its checks; all dispatched tools
  explicitly risk-classified with a drift-stopper test.
- Session-workflow execution requires a passing `validate_before_execute`
  (gate-enforced consent flag, cleared on every mutation).
- `repair_workflow` reads the live `find_missing_nodes` contract (the mocks
  had hidden a key mismatch); the cross-module seam test is now a standing
  merge requirement.
- CLI system prompt rule 5 mirrors the canonical confirm-gated install flow.
- Vision economics: shared SDK client, ≤1568 px downscale (40.6 → 3.9 MB
  payloads), real API-limit guard, prompt-keyed cache, rule-era tagging.
- NVIDIA NIM lifecycle wrapper (`nim_preflight` / `nim_run` / `nim_state`).

## [5.0.0] - 2026-05-31 — The Autonomous Co-Pilot

### Added
- **Opus 4.7 LLM upgrade**: three-tier model selection — `AGENT_MODEL` (main agent loop), `FAST_MODEL` (short triage / classification), and `VISION_MODEL` (vision tools) — each independently overridable via env, backed by canonical `_DEFAULT_AGENT_MODELS` and `_DEFAULT_FAST_MODELS` tables in `agent/config.py`. Extended thinking enabled by default on Anthropic via new `THINKING_BUDGET` (4000 tokens per agent turn) and `VISION_THINKING_BUDGET` (2000 tokens) env vars; signature-bearing `ThinkingBlock`s are replayed verbatim across multi-turn so extended-thinking + tool-use stays valid. `build_system_prompt_blocks` returns up to three structured system blocks with explicit `cache_control: ephemeral` breakpoints so Anthropic prompt caching hits across stable prefix + topical knowledge + volatile session context.
- **Observability**: `agent/metrics.py` — Counter, Histogram, Gauge (thread-safe, pure stdlib). 7 pre-registered metrics. JSON + Prometheus text export. Tool dispatch and all 4 LLM providers instrumented with timing and counters.
- **Vision evaluator**: Multi-axis quality scoring (technical, aesthetic, prompt adherence) via injected `vision_analyzer` callback. Auto-wires when brain is available.
- **Auto-retry loop**: Pipeline re-executes when quality < threshold. Adjusts parameters (steps +10, CFG nudge). Up to 3 attempts. Circuit breaker consulted before each retry.
- **CWM recalibration**: Rolling accuracy window (size 10). Confidence thresholds self-adjust by CALIBRATION_STEP based on prediction accuracy. Cross-session JSON persistence.
- **Adaptive CWM alpha**: SNR-weighted blending — low experience variance increases trust, high variance halves it. Per-axis computation.
- **Auto-provision check**: Scans workflow for `ckpt_name`/`lora_name`/`vae_name`, warns on missing models before execution.
- **Counterfactual feedback**: `validate()` returns `ExperienceChunk` with `source="counterfactual"` for CWM learning.
- **Event trigger system**: `cognitive/transport/triggers.py` — TriggerRegistry with register/unregister/dispatch, filter matching, once-triggers, webhook support. Wired into execution WebSocket loop.
- **Semantic knowledge retrieval**: `agent/knowledge/embedder.py` — pure-Python TF-IDF with cosine similarity. Hybrid detection: keywords first, semantic search fills gaps.
- **LLM provider tests**: 132 tests across OpenAI, Gemini, Ollama + parameterized conformance suite. Found dead-code bug in Gemini error mapping.
- **Integration test harness**: `tests/integration/` with session-scoped fixtures, clean skip when ComfyUI unavailable. 40+ integration tests covering discovery, execution flow, metrics, triggers, concurrent sessions.
- **VFX templates**: `depth_normals_beauty.json` (multi-pass compositing), `controlnet_depth.json`, `video_ltx2.json`, `video_wan2.json`
- **Knowledge depth**: `controlnet_patterns.md` expanded 36→174 lines (preprocessor guide, strength scheduling, stacking). `flux_specifics.md` expanded 36→172 lines (FluxGuidance, T5, Schnell vs Dev). New `compositing_multipass.md` (119 lines, Nuke/AE/Fusion integration).
- End-to-end integration test suite (`tests/test_e2e_pipeline.py`)
- Release workflow (`.github/workflows/release.yml`)
- This changelog

### Changed
- Health endpoint now includes metrics summary (total calls, error rate, p50/p99 latency)
- Pipeline evaluator selection: explicit > vision_analyzer > brain auto-wire > default rule-based
- CWM blending: fixed alpha replaced with SNR-adaptive alpha when experience scores available

### Fixed
- **Write-gate deadlock (reversibility gate fail-open)**: a loaded-but-unmutated workflow deadlocked — every `REVERSIBLE` write (`apply_workflow_patch`/`set_input`/`add_node`/`save_workflow`/`undo`) was denied with "no undo capability… load or save first." Cause: `has_undo` required a non-empty `history` (empty right after a load) and, on the SessionContext (sidebar/MCP) path, read only `ctx.workflow`, which diverged from the registry `WorkflowSession` the loaders write to. The gate now reads **both** stores and treats a **loaded** workflow as reversible (undoable via `reset_workflow` → `base_workflow`); a genuinely unloaded session still fails closed. `agent/tools/__init__.py` (non-stage). See `docs/gate-reversibility-failopen.md`.
- Concurrent session integration test bypasses gate (uses workflow_patch.handle directly)
- Provision check test covers all model variants the compose step references
- **Anthropic provider — multi-turn `ThinkingBlock` reliability**: signature-less drops now emit a WARNING-level log instead of being silent (was a known-fragile path documented in the README Cycle-20/Opus 4.7 evolution paragraph). Extracted `_build_thinking_kwarg` helper; raises `ValueError` early when `thinking_budget > 0` and `max_tokens <= 1024` (the prior clamp formula produced `budget_tokens == max_tokens`, which the Anthropic API rejects).
- **HuggingFace Xet CDN downloads** (#26): `download_model` rejected legitimate public HF files — HF serves `resolve/main/...` via its Xet CDN (`cas-bridge.xethub.hf.co`), which isn't a `huggingface.co` subdomain and so failed the per-hop host allowlist. Added `xethub.hf.co` to `_ALLOWED_DOWNLOAD_HOSTS`.
- **`.env` precedence** (#32): `agent/config.py` now loads `.env` with `override=True`, so the project `.env` wins over pre-set OS/shell env vars (a stale shell var can no longer silently shadow `.env`). Two config tests were made hermetic (`patch("dotenv.load_dotenv")`) so they no longer depend on the absence of a real `.env`.

### Security
- **Provision / RCE hardening** (#21, `agent/tools` + `agent/gate` — non-stage): closed the prompt→autonomous-fetch / prompt→RCE surface. The pre-dispatch gate's ESCALATE tier now **blocks** code-executing PROVISION ops (`download_model`, `install_node_pack`, `provision_model`, stage `provision_download`) unless an explicit `confirm` token is supplied — no more silent fall-through. `download_model` enforces a **host allowlist** (`_ALLOWED_DOWNLOAD_HOSTS`; previously dead code), **refuses pickle-format weights** (`.ckpt/.pt/.pth/.bin`) unless `allow_pickle=true`, verifies an optional **`expected_sha256`**, and follows redirects manually with per-hop SSRF + allowlist re-validation. `repair_workflow(auto_install)` and `provision_model` are confirm-gated; `check_scope` enforces **https-only** on URL keys; the download success message no longer falsely claims "available immediately." Closure-proof crucibles added (`tests/test_gate_escalate_confirm.py`, `tests/test_provision_hardening.py`). Stage-layer SSRF / source-injection residue is captured as design-only RFCs (`docs/rfc-stage-provisioner-ssrf.md`, `docs/rfc-stage-write-injection.md`) pending the Path-D freeze lift.
- **`confirm` reachable through the MCP interface** (#31): the #21 keystone blocked PROVISION ops unless `tool_input["confirm"]` was `True`, but `confirm` was never declared in those tools' MCP input schemas — a schema-validating client dropped it, so provisioning was **unusable via the primary MCP interface** with no approval path. `confirm` is now a declared boolean on the `download_model` / `install_node_pack` / `repair_workflow` / `provision_model` schemas, and the keystone parses it leniently (bool `True` or `"true"/"1"/"yes"`). Added `tests/test_provision_confirm_schema.py`. (Surfaced by a live smoke test; the original crucible missed it by calling `handle()` directly with Python `True`.)

## [3.1.0] - 2026-04-03

### Added
- Multi-provider LLM abstraction (Anthropic, OpenAI, Gemini, Ollama)
- Panel chat WebSocket with real streaming conversations in the sidebar
- Bidirectional canvas bridge -- agent mutations appear on ComfyUI canvas live
- 23 new panel routes (18 to 50 total) for discovery, provisioning, repair, sessions
- Auto-wire intelligence (`wire_model`, `suggest_wiring`)
- Unified provisioning pipeline (`provision_model`, `provision_status`, `provision_verify`)
- Quick actions bar in APP mode (Repair, Save, Browse, Wiring)
- Model browser overlay with CivitAI + HuggingFace search
- Self-healing workflow status bar with repair/migrate buttons
- Queue Prompt button in panel header
- Rate limiting + auth middleware on all panel routes
- Health check with ComfyUI + LLM provider status
- Execution progress streaming over WebSocket
- 42 LLM provider tests, 19 middleware tests, 6 health tests
- Shared test fixtures (`conftest.py`)
- `LOG_FORMAT=json` env var for structured logging

### Changed
- Rebranded from "Super Duper" to "Comfy Cozy"
- Removed all Pentagram design references
- Panel routes now return generic errors (no more `str(e)` leaking)

### Fixed
- 12 production hardening fixes (XSS, unbounded structures, atomic writes, etc.)
- CI green across 6 matrix combos (Python 3.10-3.12, Ubuntu + Windows)
- Cross-platform test fixes (httpx mocks, path assertions, cache timing)

### Security
- XSS sanitizer with HTML tag allowlist in panel markdown renderer
- 10 MB request size limits on all POST routes
- Bearer token authentication (optional, via `MCP_AUTH_TOKEN`)
- Rate limiting per route category (execute, discover, download, mutation, read)

## [3.0.0] - 2026-03-31

### Added
- Initial Comfy Cozy release (renamed from comfyui-agent)
- 113 tools across intelligence, brain, and stage layers
- Panel UI with APP and GRAPH modes
- CivitAI and HuggingFace model search
- Workflow delta patching with LIVRPS composition
- Vision analysis (Claude Vision API)
- Session persistence and experience learning
- Cognitive architecture: planner, memory, MoE router, orchestrator, foresight
- USD-native stage layer with non-destructive delta composition
- Pre-dispatch safety gate (5-check pipeline)
- Graceful degradation with kill switches
- 2350+ tests, all mocked

### Changed
- Bumped version to 3.0.0 for production release

## [0.2.0] - 2026-02-19

### Added
- Brain layer with 27 tools (planner, memory, MoE router, orchestrator, verify, refine)
- Stage layer with USD cognitive state
- Model profile registry (Flux, SDXL, SD 1.5, LTX-2, WAN 2.x)
- Creative metadata layer: intent capture, iteration tracking, PNG embedding
- Pipeline engine, 3D/audio discovery, planner templates
- Rich CLI with progress indicators
- GitHub releases integration
- Proactive surfacing of relevant models and nodes
- Web UI design system with rich text renderer
- Sidebar workflow context injection
- 796 tests

### Fixed
- He2025 determinism violations (sorted iteration, stable tiebreakers)

## [0.1.0] - 2026-02-10

### Added
- Initial release: ComfyUI Agent with all 5 phases complete
- 40+ tools across UNDERSTAND, DISCOVER, PILOT, VERIFY phases
- MCP server for Claude Desktop integration
- Workflow loading, parsing, patching with full undo
- Node discovery and model search (CivitAI, registry)
- Execution with progress monitoring (HTTP polling + WebSocket)
- Session persistence and outcome recording
- Streaming agent loop with context management
