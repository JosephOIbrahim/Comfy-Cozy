# Architecture Reference — ComfyUI Comfy Cozy Agent

> Detailed architecture, brain layer internals, agent loop, and historical roadmap.
> For day-to-day coding guidance, see the project root `CLAUDE.md`.

---

## Architecture Diagram

```
┌──────────────────── COMFY COZY AGENT v0.4.0 ──────────────────────┐
│                                                                    │
│  BRAIN LAYER (27 tools)                                            │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌───────┐ ┌───────┐ ┌───────┐ │
│  │PLANNER │ │ VISION │ │ MEMORY │ │ ORCH  │ │OPTIM  │ │ DEMO  │ │
│  │4 tools │ │4 tools │ │4 tools │ │2 tools│ │4 tools│ │2 tools│ │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬───┘ └───┬───┘ └───┬───┘ │
│  ┌────────┐ ┌──────────┐ ┌──────────┐                           │
│  │ITER_REF│ │ INTENT   │ │ITERATION │                           │
│  │1 tool  │ │ 2 tools  │ │ 3 tools  │                           │
│  └───┬────┘ └────┬─────┘ └────┬─────┘                           │
│      └───────────┴────────┬───┴───────────────────────────┘     │
│                   _protocol.py (BrainMessage)                     │
│      ┌──────────────┬──┴───────┬──────────────┐                   │
│                                                                    │
│  INTELLIGENCE LAYERS (53 tools)                                    │
│  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐    │
│  │ UNDERSTAND│  │ DISCOVER  │  │  PILOT   │  │   VERIFY     │    │
│  │ 13 tools  │  │  6 tools  │  │ 13 tools │  │  10 tools    │    │
│  └─────┬─────┘  └─────┬─────┘  └────┬─────┘  └──────┬───────┘    │
│        └──────────────┴──────┬───────┴───────────────┘            │
│                    ┌─────────▼─────────┐                          │
│                    │    TRANSPORT      │  <- Thin, swappable      │
│                    │  (HTTP/WS + MCP)  │                          │
│                    └─────────┬─────────┘                          │
└──────────────────────────────┼────────────────────────────────────┘
                    ┌──────────▼──────────┐
                    │   ComfyUI Instance  │
                    │   (localhost:8188)   │
                    └─────────────────────┘
```

---

## Layer -> Module Mapping

| Layer | Module | Tools | Status |
|-------|--------|-------|--------|
| **UNDERSTAND** | `tools/workflow_parse.py` | 3 | loads, detects format, traces connections, extracts editable fields |
| **UNDERSTAND** | `tools/comfy_inspect.py` | 4 | filesystem scanning, `list_models` with progressive disclosure |
| **UNDERSTAND** | `tools/comfy_api.py` | 6 | live HTTP queries, `format` param for progressive disclosure |
| **DISCOVER** | `tools/comfy_discover.py` | 4 | unified `discover` + ComfyUI Manager registries + HuggingFace + freshness tracking + install instructions |
| **DISCOVER** | `tools/workflow_templates.py` | 2 | starter workflows in `agent/templates/` |
| **DISCOVER** | `tools/civitai_api.py` | 2 | CivitAI model details, trending models + local cross-ref |
| **DISCOVER** | `tools/model_compat.py` | 2 | model family identification (SD1.5/SDXL/Flux/SD3), compatibility checking |
| **PILOT** | `tools/node_replacement.py` | 3 | `get_node_replacements`, `check_workflow_deprecations`, `migrate_deprecated_nodes` |
| **PILOT** | `tools/workflow_patch.py` | 9 | RFC6902 patching (6) + semantic: `add_node`, `connect_nodes`, `set_input` (3) |
| **PILOT** | `tools/session_tools.py` | 4 | save/load/list sessions via `memory/session.py` |
| **VERIFY** | `tools/comfy_execute.py` | 4 | `validate_before_execute`, `execute_workflow`, `get_execution_status`, `execute_with_progress` |
| **VERIFY** | `tools/verify_execution.py` | 2 | `get_output_path`, `verify_execution` |
| **DISCOVER** | `tools/github_releases.py` | 2 | `check_node_updates`, `get_repo_releases` |
| **BRAIN:VISION** | `brain/vision.py` | 4 | `analyze_image`, `compare_outputs`, `suggest_improvements`, `hash_compare_images` |
| **BRAIN:PLANNER** | `brain/planner.py` | 4 | `plan_goal`, `get_plan`, `complete_step`, `replan` |
| **BRAIN:MEMORY** | `brain/memory.py` | 4 | `record_outcome`, `get_learned_patterns`, `get_recommendations`, `detect_implicit_feedback` |
| **BRAIN:ORCH** | `brain/orchestrator.py` | 2 | `spawn_subtask`, `check_subtasks` |
| **BRAIN:OPTIM** | `brain/optimizer.py` | 4 | `profile_workflow`, `suggest_optimizations`, `check_tensorrt_status`, `apply_optimization` |
| **BRAIN:DEMO** | `brain/demo.py` | 2 | `start_demo`, `demo_checkpoint` |
| **BRAIN:INTENT** | `brain/intent_collector.py` | 2 | `capture_intent`, `get_current_intent` |
| **BRAIN:ITERATION** | `brain/iteration_accumulator.py` | 3 | `start_iteration_tracking`, `record_iteration_step`, `finalize_iterations` |
| **VERIFY** | `tools/image_metadata.py` | 3 | `write_image_metadata`, `read_image_metadata`, `reconstruct_context` |
| **TRANSPORT** | `mcp_server.py` | -- | MCP server exposing all 80 tools via Model Context Protocol |

---

## Layer Details

### UNDERSTAND Layer (Parse + Inspect + Explain)

**Purpose:** Know what the artist has. Explain it back to them in human terms.

- `workflow_parse.py` -- loads workflows, detects format (API / UI+API / UI-only), traces connections, extracts editable fields
- `comfy_inspect.py` -- filesystem scanning, `list_models` with `format` param (`names_only`/`summary`/`full`)
- `comfy_api.py` -- live HTTP queries to ComfyUI with progressive disclosure

**Workflow Format Handling** (three formats, handled transparently):
- **API format**: `{node_id: {class_type, inputs}}` -- full support
- **UI with API**: ComfyUI default export with `extra.prompt` embedded -- agent extracts API data
- **UI-only**: Layout only, no API data -- read-only, cannot patch or execute

Format detection happens in `workflow_parse.py:_extract_api_format()`.

### DISCOVER Layer (Model Hub + Node Index + Recommend)

**Purpose:** Solve the pace problem. Track what's new, what's good, what's relevant.

**Data Sources (Real-Time ACCESS, Not Learned):**
- HuggingFace API -- model search, metadata, download counts
- ComfyUI Manager node registry -- available nodes, versions, compatibility
- Local filesystem scan -- what's already installed (via `comfy_inspect.py`)
- CivitAI API -- community models, ratings, usage stats, trending
- Freshness tracking -- registry staleness, cache management, model directory stats
- Model compatibility -- SD1.5/SDXL/Flux/SD3 family detection via regex patterns

### PILOT Layer (Natural Language -> JSON Patches)

**Purpose:** The artist says what they want. We make validated, reversible changes.

**Stateful Workflow Editing:**
`workflow_patch.py` maintains module-level state (`_state` dict) with: original workflow (immutable), working copy, undo history stack, loaded file path, and detected format. This enables multi-step editing sessions without reloading. Templates loaded via `get_workflow_template` also populate this state. State is reset between test runs via the `reset_workflow_state` fixture.

### VERIFY Layer (Pre-flight + Execute + Status)

**Purpose:** Trust but verify. Prove the change did what we said it would.

- `comfy_execute.py` -- validation, execution, status, WebSocket progress
- `brain/vision.py` -- perceptual hash A/B comparison (no API call)
- `brain/memory.py` -- behavioral signal detection

---

## Brain Layer (Hybrid B+C Architecture)

The brain layer sits above the intelligence layers and provides higher-order capabilities.
Each module lives in `agent/brain/` and registers tools through the same pattern as
intelligence layers (`TOOLS` list + `handle()` function). Modules communicate via
`_protocol.py:brain_message()`. Brain tools are lazily loaded to avoid circular imports
with `tools/_util.py`.

**Design:** SDK-ready agents with dependency injection. Each module defines a
`BrainAgent` subclass with `BrainConfig` for DI. `_sdk.py` provides the foundation:
`BrainConfig` (dataclass with `to_json`, `validate_path`, `sessions_dir`, etc.) and
`BrainAgent` (base class with `TOOLS`, `handle()`, `self.cfg`). Modules can be
instantiated standalone with custom config or integrated via `get_integrated_config()`.
Module-level `TOOLS` and `handle()` are preserved via lazy singleton for backward compat.

### Brain: Vision (`brain/vision.py`)
Uses separate Claude Vision API calls with 120s timeout (keeps images out of main context window).
Analyzes generated images, compares A/B outputs, suggests parameter improvements.
Returns structured JSON (quality_score, artifacts, composition, suggestions).
Also provides instant perceptual hash comparison (`hash_compare_images`) via Pillow aHash + pixel diff.

### Brain: Planner (`brain/planner.py`)
Template-based goal decomposition -- 6 patterns (build_workflow, optimize_workflow,
debug_workflow, swap_model, add_controlnet, explore_ecosystem) + generic fallback.
State persists to `sessions/{name}_goals.json`. Supports step completion, replanning.

### Brain: Memory (`brain/memory.py`)
Append-only JSONL outcomes in `sessions/{name}_outcomes.jsonl`. Aggregation-based
pattern detection: best model combos, optimal params, speed analysis, quality trends.
Contextual recommendations (workflow-aware), negative pattern avoidance, goal-specific recs.
Implicit feedback detection: reuse (positive), abandonment (negative), refinement bursts
(positive), parameter regression (negative) -- with inferred satisfaction scoring.

### Brain: Orchestrator (`brain/orchestrator.py`)
Parallel sub-tasks via ThreadPoolExecutor with thread safety (locks on `_active_tasks`).
Three tool access profiles: researcher (read-only), builder (can modify workflows),
validator (can execute + analyze). Max 3 concurrent, 60s timeout, TTL eviction of
completed tasks after 10 minutes, results in original order.

### Brain: Optimizer (`brain/optimizer.py`)
GPU profiles for RTX 4090/4080/3090/3080. TensorRT integration via ComfyUI_TensorRT
node pack detection. Optimization catalog ranked by impact/effort. Auto-apply for:
vae_tiling, batch_size, step_optimization, sampler_efficiency.

### Brain: Demo (`brain/demo.py`)
4 scripted scenarios: model_swap, speed_run, controlnet_add, full_pipeline. Each
has narration text, suggested tools, and pacing checkpoints. Module-level state
tracks active demo progress.

### Brain: Intent Collector (`brain/intent_collector.py`)
Captures artistic intent before execution: user's original request, agent's technical
interpretation, style references, and session context. Thread-safe module state with
history accumulation. Intent is consumed by `image_metadata.write_image_metadata`
after successful execution for PNG embedding.

### Brain: Iteration Accumulator (`brain/iteration_accumulator.py`)
Tracks the refinement journey across iterations. Each step records: iteration number,
type (initial/refinement/variation/rollback), trigger text, RFC6902 patches applied,
parameter snapshot, user feedback, and agent observation. Finalization marks the accepted
iteration and returns the full history ready for metadata embedding.

---

## Agent Loop

`cli.py` (Typer CLI) -> `main.py:run_interactive()` -> streaming Claude API calls -> tool dispatch -> repeat.

The agent loop in `main.py` handles: streaming responses via `client.messages.stream()`, tool call detection and dispatch, context window management (observation masking + token estimation + structured compaction at 120k tokens), parallel tool execution via ThreadPoolExecutor, and exponential backoff retry (3 retries, 1s/2s/4s delays).

### Context Engineering Pipeline

Messages flow through three stages before each API call:
1. **Observation masking** (`_mask_processed_results`): replaces large tool results from prior turns with compact references (>1500 chars), preserving the most recent results intact
2. **Compaction pass 1**: truncates tool results >2000 chars
3. **Compaction pass 2**: if still over 120k tokens, drops old messages with a structured summary (`_summarize_dropped`) that preserves user requests, tools used, and workflow context

### Session-Aware System Prompt

`build_system_prompt(session_context=...)` injects session notes and workflow state into the system prompt when resuming a named session. This places user preferences (e.g., "prefers SDXL") in privileged position before knowledge files. The `_detect_relevant_knowledge()` function loads domain-specific knowledge files (ControlNet, Flux, video, recipes) based on detected workflow node types and session notes.

---

## Transport Layer

**MCP is the primary interface. HTTP/WS is the transport underneath.**

All 80 tools are exposed via Model Context Protocol using `mcp.server.Server`. MCP is a
core dependency (`pip install -e "."`). Run `agent mcp` to start the stdio transport.
Schema conversion bridges Anthropic tool schemas to MCP JSON Schema format. Sync tool
handlers are wrapped with `run_in_executor` for the async MCP runtime. Session isolation
via `WorkflowSession` enables concurrent tool calls within a single Claude Code session.

### Supported Backends (Priority Order)
1. **MCP stdio** -- `agent mcp` command, primary interface for Claude Code / Claude Desktop
2. **Direct HTTP/WS** -- ComfyUI's native API (transport layer, always works)
3. **CLI agent** -- `agent run` standalone fallback with built-in agent loop

---

## MoE Architecture

### Model Profile Registry
YAML-based model communication profiles encoding how to prompt, parameterize,
and evaluate outputs per model. Three consumers (Intent, Execution, Verify agents)
read different sections at runtime. Profiles: flux1-dev, sdxl-base + 3 architecture
fallbacks (default_dit, default_unet, default_video). Thread-safe loader with
3-tier resolution (exact -> fallback -> minimal defaults). PyYAML dependency added.

### Schema System
Loader with inheritance, validator, generator from examples.

### Specialist Agents
- **Intent Agent**: pure reasoning layer translating artistic intent into parameter mutations with conflict resolution
- **Verify Agent**: model-relative quality judgment with iteration control
- **Router**: lightweight sequencer with authority boundaries
- **iterative_refine**: brain tool wiring the full MoE pipeline with refinement loops

---

## Implementation Roadmap (Historical)

### Phase 1: Foundation -- COMPLETE
34 tools, agent loop, patch engine, session persistence, knowledge system, 169 tests.

### Phase 1.5: Brain Layer -- COMPLETE
18 brain tools: vision, planner, memory, orchestrator, optimizer, demo. 236 total tests.

### Phase 2: DISCOVER Enhancement -- COMPLETE
CivitAI integration, contextual recommendations, freshness tracking, model compatibility,
implicit feedback detection, perceptual hash comparison, WebSocket monitoring, MCP adapter. 347 tests. 61 tools.

### Phase 3: Hardening -- COMPLETE
Error handling, path sanitization, thread safety, rate limiting, structured logging, circuit breaker, Docker, CI. 397 tests.

### Phase 3.5: Intelligence Upgrade -- COMPLETE
Circuit breaker, temporal decay, goal tracking, cross-session learning, BrainMessage protocol, He2025 determinism. 429 tests.

### Phase 3.75: MCP-First Transformation -- COMPLETE
MCP as core dependency, CLAUDE.md knowledge layer, WorkflowSession, `get_install_instructions`, He2025 deep audit. 497 tests. 60 tools.

### Phase 4: Complete
Unified discovery, agent SDK extraction, rich CLI, GitHub tracking, proactive surfacing. 573 tests. 65 tools.

### Phase 5A: Pipeline + 3D + Creative Metadata -- COMPLETE
Pipeline engine, 3D/audio discovery, planner templates, creative metadata layer (PNG tEXt embedding). 762 tests. 76 tools.

### MoE Phases 1-5: COMPLETE
Model Profile Registry, Schema System, Intent/Verify/Router agents, iterative_refine pipeline. 1241 tests. 80 tools.

### Phase 5B: Demo Polish (CURRENT)
1. Wire metadata auto-embed into verify_execution (post-execution)
2. Wire metadata auto-read into session resume (pre-conversation)
3. Demo scenarios run start-to-finish without errors
4. Workflow pattern classification
5. Plain-English workflow summaries

---

## Demo Scenarios (Phase 5B Targets)

### Scenario 1: "What Do I Have?"
Artist: "What's in this workflow?" -> Agent parses, explains in plain English.

### Scenario 2: "Make It Better"
Artist: "Can we make this faster?" -> Agent analyzes, recommends, patches with confirmation.

### Scenario 3: "What's New?"
Artist: "Anything new for SDXL ControlNet?" -> Agent searches, filters, recommends with workflow relevance.

### Scenario 4: "I Broke It"
Artist: "Output looks weird" -> Agent compares outputs, diagnoses, offers revert or middle-ground.
