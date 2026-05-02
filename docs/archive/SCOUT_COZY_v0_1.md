# SCOUT_COZY_v0_1.md — Cozy × Moneta Integration Map

**Scope:** Read-only inventory of `G:/Comfy-Cozy/` (= the "Cozy" repo, branded as "Comfy Cozy").
**Substrate target:** `Moneta(MonetaConfig(storage_uri=...))` context manager (treated as external ground truth).
**Method:** Twelve-step pass per `MISSION_scout_cozy_v0_1.md`. Code reads only — no edits, no installs, no git mutations.

---

## [1/12] Top-Level Layout

`[1/12] Top-level inventory…`

| Entry | One-line role |
|---|---|
| `agent/` | Main Python package — agent loop, tools, brain, stage, llm, knowledge, memory, panel/UI server adapters. Installed as `comfyui-agent` (entry point `agent`). |
| `cognitive/` | Standalone cognitive library (does NOT import `agent.*`). LIVRPS delta engine, ExperienceChunk accumulator, CognitiveWorldModel, autonomous pipeline. |
| `panel/` | Native ComfyUI sidebar bridge — aiohttp routes mounted on ComfyUI's `PromptServer`, plus WebSocket chat. Symlinked into ComfyUI/custom_nodes. |
| `ui/` | Frontend assets (sidebar HTML/JS/CSS), separate symlink target for ComfyUI. |
| `tests/` | 4081 tests collected (3860 passing, 161 skipped, 27 errors all in `test_provisioner.py` — USD-optional dep), 38 deselected integration. ~6:32 wall, mocked. |
| `tests/integration/` | 10 files using `@pytest.mark.integration` — concurrent sessions, discovery, execution flow, metrics, trigger dispatch, websocket, persistence. |
| `agent/templates/` | 8 starter workflows (txt2img SD1.5/SDXL, img2img, LoRA, controlnet_depth, depth_normals_beauty, ltx2 video, wan2 video). |
| `workflows/` | User-imported workflow JSON. |
| `sessions/` | Persisted session state (`*.json`), outcome history (`*_outcomes.jsonl`), optional `.usda`/`.ratchet.json`/`.experience.json` siblings. |
| `assets/`, `scripts/`, `logs/` | Logo, helper PS1, runtime logs. |
| `pyproject.toml` | Hatchling build, Python ≥3.10, deps: `anthropic>=0.52`, `mcp>=1.20`, `httpx`, `websockets`, `aiohttp`, `jsonpatch`, `jsonschema`, `typer`, `rich`, `Pillow`, `networkx`, `pyyaml`, `python-dotenv`. Dev: `pytest`, `pytest-asyncio`, `ruff`, `mypy`. Optional `[stage]`: `usd-core>=24.0`. |
| `requirements.txt` | Mirror of pyproject deps for non-pip-install workflows. |
| `Dockerfile` | python:3.11-slim, runs `agent run` as non-root, mounts `/app/sessions` and `/app/logs`. |
| `docker-compose.yml` | Single `agent` service, env-driven (LLM_PROVIDER, COMFYUI_HOST), `host.docker.internal` for ComfyUI passthrough. |
| `.env.example` | 2.8KB template covering all four LLM providers + ComfyUI paths. |
| `README.md` | 47KB — three usage modes (Claude Code MCP, CLI, sidebar), four-LLM matrix, autonomous pipeline section. |
| `CHANGELOG.md` | Active. Unreleased ⊃ vision evaluator, auto-retry, CWM recalibration, semantic knowledge retrieval (TF-IDF), 132 LLM provider tests, 40+ integration tests. v3.1.0 → multi-provider. v3.0.0 → renamed from comfyui-agent. |
| `CLAUDE.md` | 17KB project guide for Claude Code agents. Lists ~103 tools, ~3600 tests claim (now ~3900), git-authority map. |
| `SPONSORS.md`, `LICENSE` (MIT), `.github/` | Standard OSS hygiene. |
| Root `.md` exhibits | `MIGRATION_MAP*.md`, `PHASE_*.md`, `MOE_ARCHITECTURE.md` (76KB), `COGNITIVE_COMFYUI_ARCHITECTURE.md` (80KB), `EXECUTION_SPEC.md`, etc. — large historical design docs, not load-bearing for integration. |

**Build system:** Hatchling. **Test framework:** pytest + pytest-asyncio (`asyncio_mode = "auto"`). **Lint:** ruff (line 99). **Entry point:** `agent = "agent.cli:app"` (Typer).

**Runtime entrypoints (four):**
1. `agent run` — interactive CLI, streaming agent loop.
2. `agent mcp` — MCP server over stdio, exposes ~103 tools to Claude Code / Claude Desktop.
3. `agent inspect | parse | sessions | search | orchestrate | autoresearch` — read-only/one-shot CLI subcommands.
4. **ComfyUI sidebar** — `panel/server/routes.py` mounts ~48 aiohttp routes on the running ComfyUI's `PromptServer`; `panel/server/chat.py` runs a per-WebSocket conversation loop.

---

## [2/12] Cozy Shape

`[2/12] What is Cozy, structurally…`

**One paragraph, end-to-end.** A user (artist) types natural language into one of three transports — terminal CLI, ComfyUI sidebar chat, or an MCP client like Claude Code — and Cozy turns it into a sequence of tool calls against ComfyUI. Concretely: the user message lands in a streaming agent loop (`agent/main.py:run_agent_turn()`) which calls a pluggable LLM provider (`agent/llm/{anthropic,openai,gemini,ollama}.py`) with the system prompt assembled by `agent/system_prompt.py:build_system_prompt()` and the live tool registry (`agent/tools/__init__.py:ALL_TOOLS`). The model emits text and/or `ToolUseBlock`s; the loop dispatches tool calls in parallel via a `ThreadPoolExecutor` (`main.py:_run_tool`) into `agent.tools.handle(name, input)`, which routes across three layers — intelligence (~53 tools, REST/filesystem operations on ComfyUI: load_workflow, set_input, validate_before_execute, execute_workflow, discover, …), brain (~27 tools: vision analysis via Claude Vision, planner, memory/outcome learning, optimizer), stage (~23 tools: USD scene composition, foresight, hyperagent, provision). Tool results feed back into the LLM in the next turn until it produces a final text response. Side effects of interest: workflow patches accumulate in a per-connection `WorkflowSession` (with undo history), outcomes append to `sessions/{name}_outcomes.jsonl`, experience chunks append to `${COMFYUI_DATABASE}/comfy-cozy-experience.jsonl`, session state persists to `sessions/{name}.json` on save. ComfyUI itself runs as a separate process at `${COMFYUI_HOST}:${COMFYUI_PORT}` and is reached over HTTP (`httpx`) and WebSocket (`websockets`) for /prompt, /history, /system_stats, and execution progress events.

**Classification:** **library + agent + plugin** (multi-modal). Most precisely: a Python **library** (`agent/`, `cognitive/`) that ships three distinct frontends — a **CLI agent**, an **MCP server**, and a **plugin** for ComfyUI's `custom_nodes/`. There is no separate hosted service; the panel server runs *inside* ComfyUI's process via `PromptServer`-mounted aiohttp routes.

**Who is the user?** Three concurrent answers:
1. **A human VFX artist** at a terminal (`agent run`) or in the ComfyUI sidebar chat — the README's stated audience.
2. **An LLM agent** consuming Cozy as an MCP toolset — the recommended (default) path per README §"Three Ways to Use It".
3. **Programmatic Python** — `from cognitive.pipeline import create_default_pipeline` (autonomous mode, no human in loop).

---

## [3/12] State & Memory

`[3/12] Current state and memory mechanism…`

**This is the load-bearing question.** Cozy already has *six* discrete persistence stores spread across four directories. None use a vector database. None use neural embeddings. This is where Moneta has the largest replacement footprint.

### Persistent stores

| Store | Location | Format | Owner module | Purpose |
|---|---|---|---|---|
| Session state | `sessions/{name}.json` | JSON, schema_version=2 | `agent/memory/session.py` | Workflow path/format/base/current, typed notes (preference/observation/decision/tip), metadata. Atomic write (tmp + os.replace + fsync). |
| Outcome history | `sessions/{name}_outcomes.jsonl` | JSONL, append-only, rotated at 10 MB × 5 backups | `agent/brain/memory.py` | One line per workflow execution: timestamp, key_params, model_combo, render_time_s, quality_score, vision_notes, user_feedback. |
| Experience accumulator | `${COMFYUI_DATABASE}/comfy-cozy-experience.jsonl` | JSONL, atomic save | `cognitive/experience/accumulator.py` | `ExperienceChunk` per generation: parameters, checkpoint, `QualityScore` (technical/aesthetic/prompt_adherence/overall), source ("counterfactual" / "live"), decay_weight, timestamp. Cap 10000, evicts lowest-quality. |
| USD stage (optional) | `sessions/{name}.usda` | USD flat file | `agent/stage/cognitive_stage.py` | Only if `usd-core` installed. Mirrors `/experience/`, `/predictions/`, `/foresight/` prims. |
| Ratchet history | `sessions/{name}.ratchet.json` | JSON | `agent/stage/ratchet.py` (saved by `agent/memory/session.py:save_ratchet`) | Decision history (delta_id, kept, axis_scores, composite, timestamp), threshold, weights. |
| Experience replay | `sessions/{name}.experience.json` | JSON | `agent/memory/session.py:save_experience` / `load_experience` | Lightweight summary of USD `/experience/` prims for fast reload without USD. |

### In-memory state (per-connection)

| Container | Module | Lifetime |
|---|---|---|
| `WorkflowSession` | `agent/workflow_session.py` | Held in `_sessions: dict[str, WorkflowSession]` keyed by session_id. Max 100, FIFO-evicts non-default. Each session has `loaded_path`, `base_workflow`, `current_workflow`, `history` (50-item undo stack), `_engine` (CognitiveGraphEngine), per-session `RLock`. |
| `ConversationState` | `panel/server/chat.py` | Per-WebSocket connection. Holds `messages: list[dict]`, `system_prompt`, busy flag, `cancelled` event. Cap 20 connections. |
| `_conn_session` ContextVar | `agent/_conn_ctx.py` | Per asyncio task / executor thread. Stores the session-id string. Set explicitly by mcp_server, panel routes, and CLI. |
| Module-level `_conversations` dict | `panel/server/chat.py` | Indexed by 8-hex `conv.id`. |
| Module-level `_provider_cache` | `agent/llm/__init__.py` | LLM provider instances cached per name (anthropic/openai/gemini/ollama). |

### Identity model

- **No user/tenant concept.** No accounts, no auth context propagated into tool calls.
- **Optional bearer token** (`MCP_AUTH_TOKEN`) on panel/HTTP routes; advisory only on stdio MCP.
- **"Session" = a string name.** `_validate_session_name()` rejects path separators, `..`, null bytes, >255 chars. The name is used directly in filenames.
- **MCP-server-instance scoping:** Each `agent mcp` process generates `_SERVER_SESSION_ID = f"conn_{uuid.uuid4().hex[:8]}"` once at startup. All tool calls from that process share that session namespace.
- **Per-connection scoping:** Panel WebSocket and HTTP routes thread `current_conn_session()` through the executor; falls back to `"default"` when unset (CLI, tests).

### Candidate Moneta-handle ownership site

The natural ownership site is **already there** — there are *two* candidates, depending on integration tier:

1. **Per-connection (preferred for Mike-credible demo):** A `Moneta(config)` handle constructed alongside each `WorkflowSession`/`ConversationState`. Lifecycle aligns with the existing per-connection ContextVar. Co-locate in `agent/session_context.py` (already a session-scoped factory: `get_session_context(name)` returns a context object that lazily ensures stage and ratchet — adding `ensure_moneta()` matches the existing pattern exactly).

2. **Process-singleton (preferred for minimum demo):** One Moneta handle per agent process, stored in a module-level cache parallel to `_provider_cache`. Conflicts with the substrate's exclusivity lock if two `agent mcp` instances run on the same `storage_uri` — but matches `_SERVER_SESSION_ID`'s "one UUID per process" pattern cleanly.

Either way: the ownership site is ergonomic. The seam is not synthetic — `agent/session_context.py` is the *exact* shape (`SessionContext` with `ensure_stage()`, `ensure_ratchet()`, `ensure_foresight()` factories) into which `ensure_moneta()` would slot.

---

## [4/12] Retrieval Surface

`[4/12] Retrieval surface and embedder posture…`

**Headline finding: Cozy has retrieval, but it has zero neural embeddings today.** The EmbeddingGemma drop-in spike is greenfield — nothing to displace, only sites to plug into.

### Three concurrent retrieval mechanisms

| Mechanism | File:line | Vectorization | Index | Query |
|---|---|---|---|---|
| **TF-IDF over knowledge markdown** | `agent/knowledge/embedder.py:KnowledgeIndex` | Sparse `dict[str, float]` term→tf·idf, no neural net | Built once at first `_semantic_search()` call (system_prompt.py:160), cached in module-level `_semantic_index`, `is_stale()` checks file mtimes, `rebuild_incremental()` for changed files | `_semantic_search(query_text)` from `agent/system_prompt.py:_detect_relevant_knowledge` — keyword triggers first, TF-IDF fills gaps if <2 matches |
| **Discrete signature similarity** over experience chunks | `cognitive/experience/signature.py:GenerationContextSignature` + `cognitive/experience/accumulator.py:ExperienceAccumulator.retrieve` | Categorical buckets (cfg_bucket, steps_bucket, denoise_bucket, model_family, sampler, scheduler, has_controlnet, has_lora, has_ipadapter) | List scan with similarity = matches/total filled fields, sorted by `sim * quality * decay_weight` | Triggered from autonomous pipeline (`cognitive/pipeline/autonomous.py:_get_experience_patterns`) and by `mcp__comfyui-agent__get_learned_patterns` |
| **Aggregation over outcomes JSONL** | `agent/brain/memory.py:_best_model_combos`, `_optimal_params`, `_speed_analysis`, `_quality_trends`, `_avoid_negative_patterns` | None — group-by + temporal-decay weighting (`_temporal_weight`, ln(2)/7d half-life) | None — read-on-each-query of full JSONL | `get_learned_patterns`, `get_recommendations`, `detect_implicit_feedback` brain tools |

### Where retrieval is invoked

Five concrete call sites (file:line):
1. `agent/system_prompt.py:144` — `_detect_relevant_knowledge` → TF-IDF semantic search to choose which knowledge `*.md` files to include in the system prompt at build time.
2. `agent/system_prompt.py:225` — proactive memory recommendations from `MemoryAgent.get_recommendations()` — outcomes-aggregation, top 3 with confidence ≥0.7 are inlined into the prompt.
3. `agent/system_prompt.py:253` — `reconstruct_context` from last output PNG metadata — reads creative-intent metadata via `agent/tools/image_metadata.py`.
4. `cognitive/pipeline/autonomous.py:_get_experience_patterns` — pulls patterns from accumulator on each `COMPOSE` stage.
5. Brain memory tools — invoked by the agent loop on demand.

### Embedder posture

**There is no embedder.** No `sentence-transformers`, no `numpy`, no `sklearn`, no `faiss`. Grep for `embedding` and `EmbeddingGemma` returns hits only in:
- `agent/brain/intent_collector.py` — "metadata embedding" = embedding intent JSON into PNG metadata (image-format embedding, not vector).
- `agent/brain/iteration_accumulator.py` — same.
- `agent/knowledge/comfyui_core.md` — documents ComfyUI's `/embeddings` REST endpoint (textual embeddings *for diffusion conditioning*, completely unrelated to retrieval).

The TF-IDF index in `agent/knowledge/embedder.py` is **named** `embedder.py` but is pure-Python sparse counting. It is the natural drop-in target for EmbeddingGemma: replace `_compute_tf` + `_cosine_similarity` with a vector encoder, change the index from `dict[str, float]` to `list[float]` per chunk, and Moneta becomes the storage backend.

### Substitute for retrieval today (when retrieval doesn't apply)

For *conversation context* across sessions there is no retrieval — `messages: list[dict]` is reset on every `agent run` invocation. Continuity comes via:
- `--session NAME` reloads the workflow + notes + reconstructs system-prompt context.
- The system prompt re-injects past outcome recommendations and last-output metadata.
- The model-side `messages` list is not persisted server-side (this is a real gap, called out in §6).

---

## [5/12] Agent Loop

`[5/12] Agent loop architecture…`

**Loop:** `agent/main.py:run_agent_turn` and `run_interactive`.

**SDK in use:** `anthropic>=0.52` (vendored as `agent/llm/_anthropic.py`). The other three providers (`_openai.py`, `_gemini.py`, `_ollama.py`) implement the same `LLMProvider` ABC (`agent/llm/_base.py`). **No `claude_code_sdk`. No `claude_agent_sdk`. No `langchain`.** The agent loop is hand-rolled around the raw provider streaming API. This matches the Moneta surface's expectation: "No Anthropic/Claude Agent SDK imports inside Moneta — the consumer drives the agent loop." Cozy already drives its own loop.

**Loop shape:** **Streaming, turn-based, multi-tool-per-turn.** Each turn:
1. `mask_processed_results(messages)` + `compact(messages, COMPACT_THRESHOLD=120k tokens)` — context management before each call.
2. `_stream_with_retry(provider.stream(...))` — exponential backoff (`API_MAX_RETRIES=3`, base 1s) on rate limit / connection / 5xx; aborts mid-retry if any text already emitted (`content_emitted` guard).
3. Collects all `ToolUseBlock`s from the response. If >1, dispatches via `ThreadPoolExecutor(max_workers=4)` with `contextvars.copy_context()` so the `_conn_session` ContextVar propagates into each worker thread (essential for session isolation).
4. Tool failures return `{"error": str(e)}` — the turn continues, the agent sees the error.
5. `MAX_AGENT_TURNS=30` cap per user message; `_shutdown` event for graceful SIGTERM.

**Tool exposure:** `ALL_TOOLS` is the union of intelligence (~53), brain (~27, lazy-loaded behind `BRAIN_ENABLED`), and stage (~23, soft-loaded — modules that fail to import are logged and skipped). Schemas are Anthropic-format (`name`, `description`, `input_schema`); `mcp_server.py:_convert_schema()` translates to MCP `inputSchema` 1:1.

**Conversation context (where it lives):**
- **CLI (`agent run`):** `messages: list[dict]` lives entirely in the local Python process scope of `run_interactive`. **Not persisted.** Restart = fresh conversation.
- **Panel sidebar:** Per-WebSocket `ConversationState.messages` (also `list[dict]`). Lives in `_conversations` dict, evicted when WS disconnects (`_conversations.pop(conv.id, None)`).
- **MCP server:** **Cozy holds NO conversation history.** The MCP client (Claude Code) owns it. Each `call_tool` is stateless from Cozy's side beyond the per-process `_SERVER_SESSION_ID` and the per-session `WorkflowSession`.
- **Autonomous pipeline:** No conversation — direct `pipeline.run(PipelineConfig(intent=...))` call.

**Gates / human-in-the-loop:**
- `agent/gate/` directory exists (referenced by `_HANDLERS` in tools/__init__.py). `GATE_ENABLED` env flag.
- `cognitive/prediction/arbiter.py:SimulationArbiter.decide()` — returns a `DeliveryMode` (SILENT / NUDGE / INTERRUPT) and `should_interrupt`. The autonomous pipeline respects `INTERRUPTED` as a halt state. **This is the closest thing to HITL in Cozy.** Not user-facing today; arbiter outputs are logged.
- No `await user_approval(...)`-style hooks. No interactive confirmation in the autonomous path.
- The CLI `run` is conversational, so the human is in the loop by default. The autonomous pipeline (`cognitive/pipeline/autonomous.py`) has *zero* HITL.

**Where Moneta-backed memory feeds the loop.** Three concrete touchpoints, in order of integration weight:
- **`agent/system_prompt.py:225-247`** — proactive recommendations block. Already pulls from `MemoryAgent.get_recommendations()`; replacing/augmenting that with `substrate.read(query=..., session=...)` is a single-block surgery.
- **Pre-tool-call retrieval in `agent/main.py:run_agent_turn`** — currently absent. Inserting a `substrate.read(latest_user_msg)` between context-compact and `_stream_with_retry` would make every turn memory-aware. This is invasive but small (single insertion point).
- **`cognitive/pipeline/autonomous.py:_get_experience_patterns`** — already a memory-blending function in COMPOSE stage. Becomes `substrate.read(signature=...)` instead of `accumulator.retrieve(signature)`.

---

## [6/12] Demo Path

`[6/12] The "it remembered" demo path…`

**Current query→answer path (CLI mode, the cleanest demo surface):**

```
$ agent run --session portrait-shoot
> "make it dreamier"
  → run_interactive
    → build_system_prompt(session_context={notes, workflow, last_output_path})
      ↳ pulls past notes, last creative-intent metadata, top-3 confident
        recommendations from MemoryAgent.get_recommendations(session)
    → run_agent_turn loop
      ↳ tool calls: load_workflow, set_input(cfg=6, sampler="dpmpp_2m", ...),
        validate_before_execute, execute_workflow
    → on completion: agent calls record_outcome (brain/memory.py)
      ↳ appends to sessions/portrait-shoot_outcomes.jsonl
    → on quit: session_tools.save_session(name="portrait-shoot")
      ↳ writes sessions/portrait-shoot.json (workflow + notes)
```

**Same query, second run, "it remembered":**

```
$ agent run --session portrait-shoot   # same name
> "make it dreamier"
  → load_session → session_context populated
  → build_system_prompt sees: 14 prior outcomes, 3 high-confidence recs
                              (e.g. "use dpmpp_2m_sde + 25 steps for this model")
  → first tool call already biased by past success
  → result: arrives at lower CFG / better sampler with fewer back-and-forths
```

**The demo already works for parameter-learning continuity** — `system_prompt.py:225-247` proactively injects MemoryAgent recommendations with confidence ≥0.7. The "it remembered" loop is real today, just *not narrated as such* in any UI.

### Gap list against a 60–90s "it remembered" demo

| Gap | Severity | Note |
|---|---|---|
| **Conversation thread is reset between runs.** `messages: list[dict]` not persisted. | Medium | Mitigated by system-prompt re-injection — the agent doesn't remember *what was said*, but it does remember *what worked*. For the demo, the system-prompt path is sufficient; conversation persistence is upside, not table-stakes. |
| **Recommendations require ≥3-sample confidence.** First few generations don't trigger the proactive block. | Low | Demo footage can be primed: pre-record 3+ outcomes before the take-2 query. |
| **No visible "Cozy is loading memory…" UX.** Recommendations land silently in the system prompt. | Medium | For a Loom-raw demo, narration substitutes. For polish, add a `--verbose-memory` flag or a panel-side "memory pill" UI element. |
| **Two parallel memory layers.** outcomes JSONL and experience JSONL store overlapping signals; pre-Moneta the demo can pick one (outcomes is more mature). | Low | Doesn't block the demo; it does mean the integration design has to pick which to route through Moneta first. |
| **No embedder.** TF-IDF over markdown ≠ semantic memory of past *intents*. | Low for demo, high for spike | The "it remembered" demo doesn't need EmbeddingGemma yet — keyword/recommendation paths work. The spike is the tier above. |

### Sized estimate, minimum demo (assumes Moneta integration complete)

**1–2 days** to record clean footage:
- Day 1: wire `substrate.write` into `record_outcome` flow + `substrate.read` into `system_prompt.py:225` block. ~1 file each, ~30 lines net change. Run a dozen pre-roll generations to seed the substrate.
- Day 2: re-record the take-2 query, narrate the difference. Optional: add a small "Cozy remembered: …" UI element in the panel.

**The bulk of the work is the integration itself, not the demo.** The demo surface that already exists in Cozy carries the show.

---

## [7/12] Call-Site Inventory

`[7/12] Integration call-site inventory…`

Every place in Cozy that does what Moneta does. Counted, listed, sized.

| File | Line(s) | Current op | Moneta-equivalent | Invasiveness |
|---|---|---|---|---|
| `agent/memory/session.py` | 66–101 | `save_session(name, workflow_state, notes, metadata)` — JSON file write, atomic | `substrate.write(key=name, value={...}, namespace="session")` | Small — one function, single owner |
| `agent/memory/session.py` | 104–141 | `load_session(name)` — JSON file read, schema migration | `substrate.read(key=name, namespace="session")` | Small |
| `agent/memory/session.py` | 144–176 | `list_sessions()` — glob `sessions/*.json` | `substrate.list(namespace="session")` (or whatever the substrate's enumeration is) | Small |
| `agent/memory/session.py` | 179–220 | `add_note(name, note, type)` — read-modify-write under `_NOTE_LOCK` | `substrate.update(key=name, op=append_note)` or read-modify-write through substrate | Medium — TOCTOU semantics matter |
| `agent/memory/session.py` | 312–355 | `save_stage` / `load_stage` — `.usda` flat file via `usd-core` | Out of scope — USD stage is a separate, structurally different store. **Do not route through Moneta in v0.1.** | N/A |
| `agent/memory/session.py` | 357–427 | `save_ratchet` / `load_ratchet` — JSON, decision history | `substrate.write` if Ratchet history becomes part of the unified memory | Small but optional |
| `agent/memory/session.py` | 430–493 | `save_experience` / `load_experience` — replays into USD stage | Couples USD and substrate; defer | Defer |
| `agent/brain/memory.py` | 295–317 | `_append_outcome(session, outcome)` — JSONL append, fsync, rotation at 10MB | `substrate.write(key=outcome_id, value=outcome, embedding=None, namespace=f"outcome/{session}")` | Medium — 3,860 tests touch this layer indirectly, rotation semantics need substrate-side equivalent |
| `agent/brain/memory.py` | 242–293 | `_load_outcomes(session)` / `_load_all_outcomes()` — read JSONL, filter by session | `substrate.read(namespace=...)` or `substrate.query(filter=...)` | Medium — heavy aggregation downstream depends on the result shape |
| `agent/brain/memory.py` | 390–533 | `get_learned_patterns`, `get_recommendations`, `detect_implicit_feedback` — pure compute over outcome list | No change if `_load_outcomes` returns the same shape; aggregation stays consumer-side | None (downstream) |
| `cognitive/experience/accumulator.py` | 95–115 | `record(chunk)` — append to in-memory list, evict lowest-quality | `substrate.write(key=chunk_id, value=chunk, embedding=embed(chunk.intent_or_signature))` | Medium — needs an embedder seam (EmbeddingGemma drop-in target) |
| `cognitive/experience/accumulator.py` | 117–154 | `retrieve(signature, top_k, min_similarity)` — list scan with discrete bucket similarity | `substrate.read(query_embedding=embed(signature_or_intent), top_k=k)` | Medium-large — discrete bucket → continuous embedding is a semantic rewrite, but cleanly contained |
| `cognitive/experience/accumulator.py` | 185–204 | `save(path)` — JSONL atomic write | Removed (substrate is the store) | Small — deletion |
| `cognitive/experience/accumulator.py` | 206–239 | `load(path)` — JSONL read at startup | Removed (substrate is read on demand) | Small — deletion |
| `cognitive/pipeline/__init__.py` | 31 | `ExperienceAccumulator.load(EXPERIENCE_FILE)` at `create_default_pipeline()` | `substrate = Moneta(MonetaConfig(storage_uri=...))` ; pass `substrate` to pipeline as a dependency | Small — single line, single caller |
| `cognitive/pipeline/autonomous.py` | 38–41 | `EXPERIENCE_FILE` path computation | Removed | Small |
| `agent/knowledge/embedder.py` | 154–177 | `KnowledgeIndex.build(knowledge_dir)` — TF-IDF over markdown | If knowledge moves to substrate: `for chunk: substrate.write(key=chunk.id, value=chunk, embedding=embed(chunk.text))` | Medium-large — full rewrite of the embedder, but the call-site remains `_semantic_search(query)` from `system_prompt.py:144` |
| `agent/knowledge/embedder.py` | 214–246 | `KnowledgeIndex.search(query, top_k, threshold)` | `substrate.read(query_embedding=embed(query), top_k=top_k)` | Same |
| `agent/system_prompt.py` | 144 | `_semantic_search(combined)` call | Behind a feature flag, switch the underlying index from in-process TF-IDF to substrate retrieval | Small (one call site, behind a function) |
| `agent/system_prompt.py` | 225–247 | Proactive memory recommendation block | `substrate.read(query=session_context, namespace="recommendation")` — replaces the local `MemoryAgent.get_recommendations` call | Small — single block |
| `agent/system_prompt.py` | 253–276 | `reconstruct_context` from last output PNG metadata | Out of scope — PNG metadata is its own channel, not a memory store | N/A |
| `agent/workflow_session.py` | full module | In-memory `WorkflowSession` registry | **No change.** Workflow patches are in-flight transient state; persistence already lives in `sessions/{name}.json`, not here. | None — keep as-is |
| `panel/server/chat.py` | 80, 116 | `ConversationState.messages` + `_conversations` dict | `messages` could be persisted via substrate for cross-session conversation memory. **Defer to substrate-proven tier.** | Defer |
| `agent/session_context.py` | (referenced) | `get_session_context(name)` — lazy `ensure_stage()` / `ensure_ratchet()` | Add `ensure_moneta()` factory matching the existing pattern — natural Moneta-handle ownership site | Small — additive |
| `agent/main.py` | 200–301 | Agent loop turn — no memory read/write | Optional: insert `substrate.read(...)` pre-stream for global memory awareness | Medium — optional, not required for the minimum demo |

**Concentration:** Call sites are **moderately concentrated**. `agent/memory/session.py` + `agent/brain/memory.py` + `cognitive/experience/accumulator.py` carry ~80% of the weight (three files, well-defined). Knowledge index is the fourth pole (one file, isolated). The fact that all four already have a clean public API (`save_session`, `_append_outcome`, `record/retrieve`, `KnowledgeIndex.search`) means the integration is a *swap behind these boundaries*, not a scatter rewrite.

**No call-site is in the agent loop body itself.** That is good news — the loop in `agent/main.py` is memory-blind. Memory enters via the system prompt construction (lazy retrieval at turn-zero) and via brain-tool calls (LLM-decided retrieval). Both routes are surgical insertion points.

---

## [8/12] Configuration & Lifecycle

`[8/12] Configuration and lifecycle…`

**Config loading.** `agent/config.py` loads `.env` from project root via `python-dotenv` *at module import*, then exposes module-level constants. Sources:
- `.env` file (`ANTHROPIC_API_KEY`, `LLM_PROVIDER`, `COMFYUI_HOST/PORT`, `COMFYUI_DATABASE`, `MCP_AUTH_TOKEN`, `LOG_FORMAT`, `BRAIN_ENABLED`, `OBSERVATION_ENABLED`, `DAG_ENABLED`, `GATE_ENABLED`, `AGENT_MODEL`, `OLLAMA_BASE_URL`, `HF_TOKEN`, `CIVITAI_API_KEY`, `GITHUB_API_TOKEN`).
- CLI args (Typer) for run-time overrides.
- ComfyUI install auto-detection (`_default_comfyui_install()` walks candidates).

Two paths matter for Moneta:
- `COMFYUI_DATABASE` → `${COMFYUI_DATABASE}/comfy-cozy-experience.jsonl` is where the accumulator is persisted today. The Moneta `storage_uri` would replace this file.
- `SESSIONS_DIR = PROJECT_DIR / "sessions"` → both session JSON and outcome JSONL live here. Could either remain (with Moneta as a parallel substrate) or be subsumed entirely.

**Existing object lifecycle ownership candidates for `Moneta(config)`:**

| Candidate | File:line | Lifetime | Fit |
|---|---|---|---|
| **`SessionContext`** | `agent/session_context.py` | Per-session, lazy-init via `get_session_context(session_id)`. Already owns `ensure_stage()` and `ensure_ratchet()`. | **Best fit.** Add `ensure_moneta()`. Lifecycle aligns with `_conn_session` ContextVar. Multi-session works naturally. |
| **`_SERVER_SESSION_ID`** in `mcp_server.py` | `agent/mcp_server.py:35` | Process lifetime. One per `agent mcp` invocation. | Good for single-tenant MCP server. Doesn't compose for the panel sidebar. |
| **`_provider_cache`** parallel | `agent/llm/__init__.py:61` | Module-singleton per provider name. | Only if Moneta is config-singleton (one storage_uri per process). Conflicts with Moneta's per-handle exclusivity lock if multiple processes share storage. |
| **CLI `run()` scope** | `agent/cli.py:73-213` | Per CLI invocation. | Trivial for `agent run` CLI demo, doesn't help MCP/panel. |

**Existing patterns for context objects.** `agent/session_context.py:get_session_context()` is already the integration shape — lazy-instantiates subsystem handles, scopes them to a session id. Mirror this for Moneta.

**Async/sync surface.** Cozy is **fundamentally synchronous**:
- All tool handlers (`agent.tools.handle()`, brain `BrainAgent.handle()`, stage `handle()`) are sync, returning `str` (JSON).
- `LLMProvider.stream()` and `.create()` are sync.
- `agent/main.py:run_agent_turn` is sync.
- The async surface is the *transports* — `asyncio` only inside `mcp_server.py` and `panel/server/{routes,chat}.py`, which use `loop.run_in_executor(None, sync_handler)` to bridge.

**Implication:** Moneta being sync today is a **match**, not a mismatch. No async retrofit needed. If Moneta later offers `async def write_async(...)`, Cozy's transport layer would consume it natively (panel routes are already aiohttp); the tool layer would not.

**Moneta-handle lifecycle, integration shape (recommended):**
- **Single shared substrate per process** for v0.1 (one `Moneta(config)` per `agent mcp`/`agent run`/panel server). Minimum invasiveness, matches `_SERVER_SESSION_ID`.
- **Per-session "namespace" inside the substrate**, keyed by `current_conn_session()`. Substrate handles isolation; Cozy passes the session name as a `namespace` parameter to `substrate.write/read`.
- **Construction at startup**, in `mcp_server.create_mcp_server()` / `cli.run()` / `panel/server/chat.py:_lazy_load`. Context-manager opened once for process lifetime, released on shutdown (`_save_and_exit` already exists for this purpose in `cli.py:156-180`).
- **Multi-handle scenario** (per-conversation, per-user) is upside, not v0.1. Documented as Open Question §12.

---

## [9/12] Test Coverage

`[9/12] Tests and stability signal…`

**Result of running `pytest tests/ -q -m "not integration"`** (read-only, no test config touched, ~6:32 wall):

```
3860 passed, 161 skipped, 38 deselected, 19 warnings, 27 errors in 392.13s
```

**The 27 errors are all in `tests/test_provisioner.py`**, all with `agent.stage.cognitive_stage.StageError: USD not available. Install with: pip install usd-core`. The `[stage]` extra is optional per `pyproject.toml`; README explicitly says "most users skip" the ~200MB USD install. **These are not regressions** — they are missing-`pytest.mark.skipif` declarations on the stage tests. Flagged but not fixed (read-only pass).

| Subsystem | Test files | Approx test count | Stability | Integration impact (will / may / won't change during Moneta cutover) |
|---|---|---:|---|---|
| **Workflow patch / parse** | `test_workflow_patch.py`, `test_workflow_patch_engine_live.py`, `test_workflow_parse.py`, `test_workflow_session.py` | ~250 | Solid | **won't** (in-memory, ContextVar isolation already proven) |
| **Session persistence** | `test_session.py`, `test_session_tools.py`, `test_session_context.py`, `test_session_stage.py` | ~120 | Solid | **will** — every save_session/load_session/add_note assertion changes when Moneta replaces JSON files |
| **Brain memory (outcomes)** | `test_brain_memory.py` | ~50 | Solid | **will** — record_outcome / get_learned_patterns / get_recommendations / detect_implicit_feedback all proxy through Moneta |
| **Cognitive experience** | `test_cognitive_experience.py`, `test_experience.py`, `test_workflow_signature.py` | ~80 | Solid | **will** — accumulator.save/load/record/retrieve all become Moneta operations |
| **Cognitive pipeline** | `test_cognitive_pipeline.py`, `test_e2e_pipeline.py`, `test_pipeline.py`, `test_pipeline_breaker.py`, `test_pipeline_provision_check.py`, `test_pipeline_retry.py`, `test_pipeline_vision_autowire.py` | ~150 | Solid | **may** — mostly mocks executor/evaluator; substrate plumbing changes only the `_get_experience_patterns` path |
| **CWM / arbiter / counterfactual** | `test_cwm.py`, `test_cwm_adaptive_alpha.py`, `test_cwm_recalibration.py`, `test_arbiter.py`, `test_counterfactual_feedback.py`, `test_counterfactuals.py` | ~120 | Solid | **won't** (predictor is internal, no memory dep) |
| **Knowledge index** | `test_knowledge_embedder.py`, `test_triggers.py` | ~40 | Solid | **may** — only if EmbeddingGemma drops in for the index; tests assert TF-IDF semantics today |
| **LLM providers + conformance** | `test_llm_conformance.py`, plus per-provider tests | ~132 | Solid | **won't** |
| **Tool dispatch / registry** | `test_tools_registry.py`, `test_tool_scope.py`, `test_capability_registry.py` | ~80 | Solid | **won't** |
| **MCP server / panel routes / chat** | `test_mcp_server.py`, `test_panel_chat.py`, `test_panel_middleware.py`, `test_routes_panels.py`, `test_websocket_origin.py` | ~150 | Solid | **may** — only if Moneta-backed conversation memory is added in panel chat |
| **Vision / verify** | `test_brain_vision.py`, `test_verify_agent.py`, `test_verify_execution.py`, `test_vision_evaluator.py` | ~70 | Solid | **won't** |
| **Stage / USD** | `test_cognitive_stage.py`, `test_stage_tools.py`, `test_stage_session_isolation.py`, `test_compositor*.py`, `test_foresight_*.py`, `test_hyperagent*.py`, `test_provisioner.py` (errored), `test_provisioner.py`, etc. | ~300 (27 errored) | **Thin without USD installed; solid with it.** | **won't** (orthogonal to Moneta; lives at a different layer of memory) |
| **Health / metrics / circuit breaker** | `test_health.py`, `test_metrics.py`, `test_circuit_breaker.py`, `test_pipeline_breaker.py` | ~60 | Solid | **may** — if Moneta latency is a new metric label |
| **MoE / router / orchestrator** | `test_moe_*.py`, `test_router.py`, `test_brain_orchestrator.py`, `test_intent_agent.py`, `test_brain_planner.py` | ~150 | Solid | **may** |
| **Configuration & startup** | `test_config.py`, `test_constitution.py`, `test_logging_config.py`, `test_main.py`, `test_context.py` | ~80 | Solid | **may** — if `MONETA_STORAGE_URI` env var is added to config |
| **Integration (deselected)** | `tests/integration/*.py` (10 files) | 38 | Skipped without ComfyUI | **may** — `test_concurrent_sessions.py` and `test_session_persistence.py` are the most relevant |

**Summary:** The test suite is dense, mocked, fast, and stable. The Moneta cutover will primarily touch **session + brain-memory + cognitive-experience** suites — call it ~250 tests that need updating. The rest of the suite is orthogonal and serves as the integrity baseline through the cutover.

**One stability flag:** `test_provisioner.py` should grow `pytest.mark.skipif(not HAS_USD)` — orthogonal to Moneta but worth fixing in the same maintenance window. Do not fix in this scout.

---

## [10/12] Workload Profile

`[10/12] Workload characterization for benchmarking…`

**What does a "task" look like in Cozy?** Three task shapes coexist:

| Task shape | Trigger | Median bound | Bound spec |
|---|---|---|---|
| **Conversational turn** (CLI / panel / MCP) | One user message → final assistant text | 1–6 LLM calls + 0–20 tool calls | "Make it dreamier" → load_workflow → set_input(cfg) → set_input(sampler) → validate_before_execute → execute_workflow → analyze_image → record_outcome → final text |
| **Autonomous pipeline run** (`pipeline.run(intent)`) | Programmatic | 1 COMPOSE + 1 PREDICT + 1 GATE + 1–3 EXECUTE/EVALUATE retries + 1 LEARN | `cognitive/pipeline/autonomous.py` — bounded by `max_retries=2`, quality_threshold=0.6 |
| **Foresight autoresearch** (`agent autoresearch --program file.md`) | CLI | Up to `max_experiments=100`, `budget_hours=1.0`, `experiment_seconds=30s` | `agent/stage/autoresearch_runner.py:AutoresearchRunner` — many `pipeline.run` calls in sequence |

### Two representative tasks for $/task instrumentation

**Task A — "Make it dreamier" (conversational turn).** Most common, most demoable.
- Average tools per turn: ~3–6 (load, edit, validate, execute, verify, record).
- Average LLM calls per turn: 2–4 (initial response with tool calls + tool-result follow-up + possible retry).
- Token shape: system prompt ~3–8k (varies with knowledge files loaded), tool result blobs 50–500 tokens each, user msg <100 tokens.
- Wall: 5–30s, dominated by ComfyUI execution time, not LLM.
- Cost driver: number of agent turns × tokens per turn × provider price.

**Task B — Autonomous pipeline run.** Programmatic. Cost-deterministic enough for hour-over-hour drift detection.
- One vision call per execute (if `brain_available=True` or `vision_analyzer` injected).
- Up to 3 executions × 1 vision call = 3 LLM calls minimum.
- Plus prediction/arbiter — pure compute, no LLM cost.
- Cost driver: vision-API tokens per evaluation, retry count.

### Instrumentation points (where to plumb token telemetry)

The architecture already has the metric registry. Existing pre-registered metrics in `agent/metrics.py:240-263`:
- `tool_call_total{tool_name, status}` — Counter.
- `tool_call_duration_seconds{tool_name}` — Histogram.
- `llm_call_total{provider, status}` — Counter.
- `llm_call_duration_seconds{provider}` — Histogram.
- `circuit_breaker_transitions{from_state, to_state}` — Counter.
- `session_active` — Gauge.
- `pipeline_runs_total{stage_reached}` — Counter.

Wired into:
- `agent/llm/_base.py:_record_llm_metric()` — every provider's `stream()` and `create()` is instrumented at the boundary (`agent/llm/_anthropic.py`, `_openai.py`, `_gemini.py`, `_ollama.py`).
- `agent/tools/__init__.py:handle()` — every tool dispatch is timed (in the central registry).
- `panel/server/routes.py` — health endpoint serves the registry summary.

**Instrumentation gaps for the dollar-tracking story:**

| Gap | Fix size |
|---|---|
| **No per-provider input/output token counter.** Provider responses contain usage metadata (Anthropic `response.usage.input_tokens` / `output_tokens`, OpenAI `usage.prompt_tokens`/`completion_tokens`); none of this is plumbed to a Counter today. | Small — one `Counter("llm_tokens_total", labels=["provider", "kind"])` registration + 4 lines per provider |
| **No price map.** No `$/1k input tokens`, no `$/1k output tokens` constant per provider. | Small — one config dict |
| **No per-task aggregation.** Counters are per-call; "what did this conversation cost?" requires correlation. | Medium — a `task_id` label or correlation via the existing `correlation_id` (set in `logging_config.py`) |
| **No prompt-cache hit rate.** Anthropic returns cache_read_input_tokens; Cozy doesn't surface it. | Small |
| **No vision-API call separation.** Vision calls go through `LLMProvider.create()` and currently share the same `llm_call_total` counter as agent-loop calls. | Small — add a `kind` label or split metric names |

### Existing observability posture

- **Logging:** `agent/logging_config.py` with optional `LOG_FORMAT=json`. `set_correlation_id()` per-session/conn — already available for $/task aggregation.
- **Metrics export:** `agent/metrics.py` has `to_prometheus_text()` and JSON exporters. Health endpoint includes summary.
- **Tracing:** None. No OpenTelemetry, no spans.
- **Per-provider metrics:** Yes, all four labeled by `provider`.

**The instrumentation surface is mature enough that adding a usage-token Counter and a price multiplier is a 2-day spike, not a green-field build.** The bulk of the metric infrastructure already exists.

---

## [11/12] Cloud Readiness

`[11/12] Cloud-readiness, scoped to Cozy…`

**Cozy's existing deployment shape:**

| Artifact | What it does |
|---|---|
| `Dockerfile` | python:3.11-slim, non-root user, `agent` entrypoint, `agent run` default CMD, healthcheck via `agent inspect`, volumes for `/app/sessions` and `/app/logs`. |
| `docker-compose.yml` | Single `agent` service. `host.docker.internal` extra-host for ComfyUI passthrough. Env-driven multi-LLM. Healthcheck hits `localhost:8189/comfy-cozy/health` (the panel server, *not* the agent CLI — a small misalignment because the agent CLI doesn't expose an HTTP health). |
| `panel/server/routes.py` | 48 aiohttp routes mounted on ComfyUI's `PromptServer`. Includes `/comfy-cozy/health` (200 / 503), `/comfy-cozy/graph-state`, all the workflow editing routes. **This is the only HTTP surface today.** |
| `panel/server/middleware.py` | `check_auth(MCP_AUTH_TOKEN)`, `check_rate_limit(category)`, `check_size(10MB)`. |

**Today's posture:** Cozy is **local-first with optional containerization**. The Docker image bundles the agent CLI; the panel server only runs *inside* a running ComfyUI process (it depends on `PromptServer.instance`). There is no standalone web UI — the sidebar lives inside ComfyUI's browser canvas.

### Gap list for "try-without-installing" thin deployment

| Gap | Severity | Note |
|---|---|---|
| **No standalone web UI.** Sidebar is mounted inside ComfyUI; without ComfyUI, no UI. | **Large.** | The minimum thin-deployment story is "user clicks a link, types a prompt, sees output." Today that requires installing ComfyUI first. |
| **ComfyUI is the heavy dependency.** ~10GB of models, GPU drivers, custom nodes, native deps. | **Massive.** | Thin deployment has to either (a) co-host ComfyUI on the cloud GPU, or (b) ship a "Cozy without execution" mode — chat about workflows, no images. |
| **Hardcoded local paths everywhere.** `COMFYUI_DATABASE`, `WORKFLOWS_DIR`, `MODELS_DIR`, `SESSIONS_DIR = PROJECT_DIR / "sessions"`, `EXPERIENCE_FILE = COMFYUI_DATABASE / "comfy-cozy-experience.jsonl"`. | **Medium.** | All configurable via env, but they assume a single tenant on a single machine. Multi-tenant requires path namespacing — exactly what Moneta's `storage_uri` solves. |
| **Single-user assumed.** No auth context propagated to tool calls. `MCP_AUTH_TOKEN` is a shared bearer, not a user identity. | **Medium.** | Documented in §3 (Identity model). |
| **MCP stdio is the primary integration.** Stdio doesn't have an auth model; the README explicitly notes this (`mcp_server.py:198-201`). For multi-tenant cloud, switch to HTTP/SSE transport. | **Medium.** | The MCP SDK supports SSE; Cozy doesn't currently mount it. |
| **LLM API keys are in `.env`.** No per-tenant key, no broker, no rotation. | **Small** for self-hosted; **Medium** for SaaS. |
| **Sessions and experience are filesystem-coupled.** `sessions/` is a plain directory. JSONL files are local. | **Medium-large** — direct overlap with Moneta's job. |
| **No /health endpoint without ComfyUI running.** `agent run` is interactive; `agent mcp` is stdio. The only HTTP `/health` is on the in-ComfyUI panel. | **Medium** — would need a standalone health server for orchestration. |
| **Custom_Nodes symlinking is admin-elevated on Windows.** README §"Connect the Sidebar" requires `mklink /D` as administrator. | **Low** for cloud (no Windows admin) — just a docs note. |

### Warning list — code shapes that would push thin-deployment toward full-SaaS scope

These are *flags*, not blockers — you might *want* to embrace some, but they should be deliberate.

1. **Multi-tenant session isolation.** Current `_conn_session` ContextVar is per-process. Multi-tenant deployment requires a tenant-id surface upstream of the session id, propagated through every tool call. **Cost:** new authentication layer, JWT or session-cookie infra, audit. → Pulls toward "full SaaS."
2. **Persistent conversation memory.** `messages: list[dict]` reset per run is fine for self-hosted; users in a hosted "Cozy in the cloud" expect their conversations to persist. **Cost:** Moneta-backed conversation memory + UI for "list past conversations." → Pulls toward "full SaaS."
3. **Per-tenant LLM keys.** Self-hosted: one key. Hosted: either Cozy fronts a managed key (Anthropic billing on Cozy, vendor lock-in to one provider) or asks each user for their key (UX hit, support burden).
4. **Per-tenant ComfyUI binding.** Self-hosted: ComfyUI is your machine. Hosted: each tenant's workflows hit a shared GPU pool, model downloads need tenant-namespacing, output files need tenant-isolated storage. → Pulls toward "full SaaS." This is the big one.
5. **Rate limiting at the API edge.** Currently rate-limited per-route in panel. Multi-tenant needs per-tenant quotas. → Pulls toward "full SaaS."
6. **Output file storage.** `COMFYUI_OUTPUT_DIR` is a host directory today. Hosted: needs object storage (S3/R2) and signed URLs. → Pulls toward "full SaaS."

**Recommendation for the substrate-proven tier:** thin deployment is feasible for the **agent + Moneta** half (single shared GPU pool, single Anthropic key, one tenant per sandbox session). It is *infeasible* in v0.1 for the **agent + Moneta + ComfyUI multi-tenant** trifecta — that crosses into hosting GPUs and is a separate program.

---

## [12/12] Integration Synthesis & Open Questions

`[12/12] Integration synthesis…`

### A. Integration scope estimate

| Band | Cozy-side work | Days |
|---|---|---:|
| **Minimum demo** | (1) `ensure_moneta()` factory in `agent/session_context.py` with process-singleton lifecycle. (2) Replace `_append_outcome` (`agent/brain/memory.py`) and `_load_outcomes` with `substrate.write`/`substrate.read` calls (no embeddings yet — `embedding=None`). (3) Update `agent/system_prompt.py:225-247` proactive-recommendation block to query the substrate. (4) Re-record 12+ pre-roll outcomes; record the take-2 demo. (5) Update ~50 tests in `test_brain_memory.py` + `test_session.py` to mock the substrate. **No retrieval rewrite, no embedder.** | **3–5** |
| **Mike-credible** | Above + (6) replace `cognitive/experience/accumulator.py` `record/retrieve/save/load` with substrate-backed equivalents (`embedding=None` still acceptable; signature similarity moves consumer-side). (7) Add `Counter("llm_tokens_total", labels=["provider","kind"])` and price map; thread through `_record_llm_metric`. (8) Add `correlation_id` join across LLM/tool counters for per-task $/task. (9) Build a 30-min benchmark harness against the two representative tasks (Task A conversational, Task B pipeline). (10) Update ~150 tests in `test_cognitive_experience.py` + `test_cognitive_pipeline.py` + `test_e2e_pipeline.py`. **No EmbeddingGemma.** | **+5–8 (8–13 cumulative)** |
| **Substrate-proven** | Above + (11) EmbeddingGemma drop-in: replace `agent/knowledge/embedder.py:KnowledgeIndex` with neural-embedding + substrate-backed retrieval. (12) Wire `substrate.read(query_embedding=embed(intent))` into `cognitive/experience/accumulator.retrieve()` — semantic experience matching replaces discrete-bucket similarity. (13) Update ~40 tests in `test_knowledge_embedder.py`. (14) Thin cloud deployment for Cozy + Moneta only (no ComfyUI multi-tenant): Dockerfile rework, switch MCP transport to HTTP/SSE, add standalone `/health` HTTP server, single-tenant single-GPU config, persistent conversation memory in panel chat (`ConversationState.messages` → substrate). (15) Auth-token propagation through `_conn_session` (single-tenant first). | **+8–13 (16–26 cumulative)** |

**Estimate floor and ceiling:**
- **Minimum demo: 3–5 days.** Floor assumes Moneta's API surface is exactly as described, no surprises in the lifecycle context-manager, and the substrate handles concurrent writes from `ThreadPoolExecutor(max_workers=4)` cleanly. (Cozy's existing `_NOTE_LOCK` and `_outcomes_locks` semantics need to be either replicated substrate-side or replaced by substrate-side guarantees — raised in Open Questions.)
- **Mike-credible: 8–13 days cumulative.** Floor assumes the metric infrastructure already in place (it is — `agent/metrics.py`, `_record_llm_metric`) accepts new counters trivially. Ceiling assumes the benchmark harness needs both ComfyUI fixtures and a Loom-recordable output.
- **Substrate-proven: 16–26 days cumulative.** Floor assumes EmbeddingGemma is a hosted endpoint (no local model serving needed); ceiling assumes Cozy-side GPU model load + warm-up + multi-tenant routing.

**Cited evidence per band:**
- Minimum demo grounded in §3 (state mechanism — only outcomes need replumbing for take-1), §6 (demo path already uses outcome aggregation in system prompt), §7 (integration call-site invasiveness column — three "Small" rows carry minimum-demo).
- Mike-credible grounded in §10 (instrumentation gaps are all "Small" or "Medium"), §7 (cognitive accumulator rows are "Medium"), §9 (test-impact column "will" rows total ~250 tests).
- Substrate-proven grounded in §4 (embedder posture — greenfield, no displacement cost) and §11 (cloud-readiness gap list — large but bounded if scope is "Cozy + Moneta only, no ComfyUI multi-tenant").

**Assumptions, made explicit:**
1. **Moneta accepts concurrent writes from a `ThreadPoolExecutor`** without requiring extra Cozy-side serialization. Cozy's parallel-tool-call path is a real concurrency surface.
2. **EmbeddingGemma is consumer-driven** per the Moneta surface ("the consumer (Cozy) produces vectors; Moneta receives them"). Cozy hosts the embedder; Moneta is the store. **Open Question §B confirms the alternative.**
3. **Days are *senior engineer days*, not calendar days**, and assume Cozy is the primary focus (not split with Moneta-side work).
4. **Tests stay mocked.** No live-substrate test infra in v0.1; substrate calls are mocked with `unittest.mock` like all other I/O.
5. **No Cozy refactoring outside the integration boundary.** `test_provisioner.py` USD skipif fix and other hygiene items are out of scope.

### B. Open Questions for the integration design pass

**Lifecycle**
- Is the Moneta handle owned by `SessionContext` (per-session) or by the agent-process (singleton, `_SERVER_SESSION_ID`-style)? `MonetaResourceLockedError` says one handle per `storage_uri` per process — if multiple `agent mcp` processes share storage, the singleton choice forces a per-process URI suffix. What's the convention?
- Where does the `with Moneta(config) as substrate:` context-manager live for the **MCP server** path? `mcp_server.run_stdio()` is `async` and runs for the process's lifetime — does the context manager wrap the whole `await server.run(...)` call? What happens if Cozy crashes inside that block — does Moneta's release semantics handle uncrashed-but-orphaned locks?
- The CLI path already has `_save_and_exit` registered as both `signal.SIGTERM` and `atexit`. What's the equivalent shape for releasing Moneta on SIGTERM mid-stream?
- For the panel server (mounted in ComfyUI), Cozy's lifetime equals ComfyUI's lifetime. Does Moneta tolerate hour-+ context-manager scopes, or does it expect short-lived handles?

**Async / sync**
- Cozy is sync at the tool layer, async at the transport layer. Moneta is sync today. Does Moneta plan an async API? If yes, when — and does Cozy adopt it for the panel transport before Mike-credible, or defer?
- Cozy's `ThreadPoolExecutor(max_workers=4)` calls multiple tools in parallel; each tool can call `substrate.write/read`. Is one Moneta handle thread-safe for concurrent reads/writes, or does Cozy need a connection pool?

**Retrieval ownership**
- Does Cozy keep its `MemoryAgent.get_recommendations` aggregation logic (group-by + temporal decay) and just swap the *storage* underneath (substrate-as-JSONL-replacement)? Or does the substrate provide the aggregation primitives natively, removing `_best_model_combos`/`_optimal_params`/`_speed_analysis` from Cozy entirely?
- The `cognitive/experience/accumulator.py:GenerationContextSignature` discrete-bucket similarity is *categorical*. If Moneta does vector retrieval, do these signatures get embedded (one vector per signature) or does the signature concept go away in favor of full-prompt or full-workflow embeddings?
- Three retrieval mechanisms in Cozy today (TF-IDF knowledge, signature accumulator, outcomes aggregation). Does Moneta unify all three behind one API, or does Cozy keep TF-IDF (knowledge is small, structured, doesn't need a vector store) and only route experience + outcomes through Moneta?

**Embedder location**
- The Moneta surface description says the consumer produces vectors. Confirm: does Cozy host EmbeddingGemma in-process (Python load, GPU memory, one warm-up per startup), or call out to a hosted EmbeddingGemma endpoint (HTTP latency per write)? In-process is faster and more private; hosted is multi-tenant friendly. Which path matches the project's intent?
- If in-process: who pays the GPU memory for EmbeddingGemma alongside ComfyUI's checkpoint loaders? Cozy's `agent run` doesn't load any GPU model today.
- If hosted: where is the endpoint, and what auth model wraps it?
- Embedding-on-write is mandatory; is embedding-on-read also via Cozy (every query embedded before `substrate.read`), or does Moneta accept text queries and embed substrate-side? The brief implies the former.

**Identity passthrough**
- Cozy has session names but no user/tenant identity. Does `storage_uri` map 1:1 to session name, or is `storage_uri` a tenant identifier with sessions-as-namespaces inside it?
- If `storage_uri` is per-session: 100s of `storage_uri`s per process — does Moneta support the lock pattern at that fan-out, or is the design expected to share one URI with namespacing?
- Does Cozy's `_validate_session_name` (rejects path separators, `..`, null bytes) need an analogous validator for whatever Moneta accepts as a key?
- What's the migration story for *existing* `sessions/{name}.json` files when a user upgrades — does Cozy ship a one-shot migrator from filesystem to substrate?

**Test cutover scope**
- ~250 tests need updating across `test_brain_memory.py`, `test_session.py`, `test_cognitive_experience.py`, `test_cognitive_pipeline.py`. Are these mocked against a Moneta protocol stub (define an in-memory fake Moneta in `tests/conftest.py`), or do they hit a real Moneta against a temp `storage_uri`?
- Existing concurrent-session tests (`test_concurrent_sessions.py`, `test_stage_session_isolation.py`) prove Cozy's session isolation. Do these need a Moneta-aware variant, or are they orthogonal?
- Are there contract tests for the substrate API surface that Cozy can adopt directly, or does Cozy maintain its own?

**Agent loop ownership**
- Cozy's loop is hand-rolled (no `claude_agent_sdk`). Does Moneta-backed memory feed the loop **as system-prompt context** (current pattern, additive) or as **agent-callable tools** (`substrate_read` exposed to the model, the model decides when to retrieve)? Or both?
- If both: how is the cost / latency tradeoff governed? System-prompt retrieval is one pre-fetch per turn-zero; tool-driven retrieval is N retrievals per turn at the model's discretion.
- The autonomous pipeline (`cognitive/pipeline/autonomous.py`) drives Moneta directly, not via the model. Is that the intended split — conversational mode uses tools; autonomous mode uses direct calls?

---

## Bottom Line

Cozy is in remarkably good shape to be Moneta's first reference consumer. The integration surface is **moderately concentrated** in three files (`agent/memory/session.py`, `agent/brain/memory.py`, `cognitive/experience/accumulator.py`) plus one optional fourth (`agent/knowledge/embedder.py`), and Cozy already has the exact lifecycle shape — `agent/session_context.py:get_session_context()` with `ensure_stage()` / `ensure_ratchet()` factories — into which `ensure_moneta()` slots without ceremony. Memory today is *six* parallel filesystem stores with no neural embeddings anywhere; Moneta replaces the parts that are JSONL ledgers + categorical-bucket retrieval, EmbeddingGemma fills the embedder seam, and the TF-IDF knowledge index is a separable, deferable target. The agent loop is hand-rolled (no Claude Agent SDK to wrestle with), sync (matches Moneta sync), and instrumentation is mature enough that token-economics telemetry is a 2-day add. The single most important thing to get right in the integration design pass is **lifecycle ownership** — process-singleton vs. per-session — because it cascades into the multi-tenant story, the test mocking strategy, and the storage_uri identity model. Decide that first; the rest of the integration follows from it.

---

*Scout pass complete. No code modified. No git operations performed. Twelve marathon markers cleared.*
