# SCOUT: Comfy-Cozy for Moneta Bridge

**Mission:** `MISSION_scout_comfy_cozy_for_bridge.md`
**Mode:** Read-only inventory pass — no modifications
**Repo state captured:** 2026-04-29, branch `master`, head `8827772`
**Scope:** Comfy-Cozy only. Moneta and ComfyUI not touched.

---

## [1/8] On-disk state surface

The mission's prior assumption was that runtime state lives in `sessions/`,
`substrate/`, and `orchestra/`. Inventory disagrees: `substrate/` and
`orchestra/` **do not exist** at the repo root. Runtime state lives in three
places.

**Where state actually lives:**

| Location | Tracked? | File types present | Purpose | Write cadence |
|---|---|---|---|---|
| `sessions/` (in-repo) | Ignored (`*.json`, `*.jsonl`, `*.jsonl.*`) | `*.json` (named sessions, goal artifacts), `*_outcomes.jsonl` (outcome streams) | Per-name session state and outcome streams. Single source for "what happened in this session." | Append on every `record_outcome` tool call; full-rewrite on every `save_session`/`add_note`/`save_ratchet`. |
| `G:/COMFYUI_Database/comfy-cozy-experience.jsonl` (configured via `COMFYUI_DATABASE` env, default `G:/COMFYUI_Database`) | Outside repo entirely | one `.jsonl` (currently 428 bytes, 1 sample line) | Cognitive autonomous-pipeline experience persistence. Independent of `sessions/`. | Full-rewrite (truncate `"w"`) on each pipeline `save()`, not append. |
| `logs/` (in-repo) | Ignored | `agent.log` (~1.3 MB), `mcp.log` (~30 KB) | Diagnostic log. Not state. Not relevant to bridge. | Streaming append. |

**Top-level dirs that exist but are NOT state surfaces:** `agent/`,
`cognitive/`, `tests/`, `docs/`, `panel/`, `scripts/`, `ui/`,
`video-recreation-agent/`, `assets/` (single logo image), `workflows/` (empty,
`.gitkeep` only), plus the usual `.git/`, `.venv312/`, `.pytest_cache/`,
`.ruff_cache/`, `.benchmarks/`, `.claude/` (worktrees + slash-command config),
`.github/`.

**Top-level dirs the mission asked about that are absent:** `substrate/`,
`orchestra/`, `data/`, `state/`, `experience/`, `cache/`, `outputs/`, `runs/`,
`artifacts/`. None exist.

**`.gitignore` runtime carve-outs:** `sessions/*.json`, `sessions/*.jsonl`,
`sessions/*.jsonl.*`, `logs/`, `.env`. Confirms session output and logs are
deliberately untracked — the bridge consumes from a runtime-only directory.

**`sessions/` listing (15 files, 2026-04-29):**

| File | Type | Classification |
|---|---|---|
| `default_outcomes.jsonl` | 1.0 MB, 2,575 lines | Primary outcome stream (session = `"default"`). |
| `qs-test_outcomes.jsonl` | 107 KB | Outcome stream for session `"qs-test"`. |
| `test_all_outcomes.jsonl` | 418 B | Outcome stream for session `"test_all"`. |
| `c42_*.json`, `c43_*.json`, `c44_*.json`, `diag1_*.json`, `diag2_*.json`, `cleanup_test.json` | small JSON | Goal artifacts written by the planner module (`{session}_goals.json` pattern), plus a few diagnostic/test fixtures persisted by past test runs. Not session capsules. |
| (none) | `.usda`, `.ratchet.json`, `.experience.json` | Code path exists in `agent/memory/session.py` (`save_stage`, `save_ratchet`, `save_experience`) but the writes are gated on `usd-core` being installed. None present on disk today. |

---

## [2/8] Outcome stream schema

`sessions/default_outcomes.jsonl` is a stable, append-only, line-delimited JSON
log. First, middle (line 2000), and last lines all share the same key set with
no schema drift.

**One line, annotated (re-formatted; on disk it is single-line, sorted keys):**

```json
{
  "schema_version": 1,
  "timestamp": 1777309726.1684496,         // unix epoch float, server local time
  "session": "default",                     // session string carried in tool input
  "goal_id": null,                          // optional planner correlation id
  "workflow_summary": "MoE accepted: \"dreamier\" on sdxl-base (1 iteration)",
  "workflow_hash": "e387419df4d2bf39",      // sha256(canonical(key_params))[:16]
  "key_params": {"model": "sdxl-base"},     // dict, REQUIRED, validates as dict
  "model_combo": ["sdxl-base"],             // list[str]
  "render_time_s": null,                    // optional, finite non-negative float if present
  "quality_score": 0.9,                     // optional, in [0, 1] if present
  "vision_notes": ["verify_decision: accept"],  // list[str]
  "user_feedback": "neutral"                // string; defaults to "neutral"
}
```

**Field list:**

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | Currently `1`. `_migrate_outcome` exists for upgrades. |
| `timestamp` | float | Server `time.time()` when written. |
| `session` | str | Tool-input `session` (default `"default"` if caller omits). NOT the in-memory `SessionContext.session_id`. |
| `goal_id` | str \| null | Optional planner correlation. |
| `workflow_summary` | str | Human-readable line. |
| `workflow_hash` | str | First 16 hex chars of sha256 over `json.dumps(key_params, sort_keys=True)`. |
| `key_params` | dict | Required. Used for hash and aggregation. |
| `model_combo` | list[str] | Models that participated. |
| `render_time_s` | float \| null | Validated finite non-negative if present. |
| `quality_score` | float \| null | Validated in `[0.0, 1.0]` if present. |
| `vision_notes` | list[str] | Free-form notes from vision evaluator. |
| `user_feedback` | str | `"neutral"` default. |

**Schema stability:** confirmed across first/middle/last lines. Same key set,
same types. No event-type discriminator — every line is the same "outcome
recorded" event.

**Writer module:** `agent/brain/memory.py`

- Class: `MemoryAgent` (subclass of `BrainAgent`)
- Tool: `record_outcome` → `_handle_record_outcome` (line 334)
- Append: `_append_outcome` (line 295) — opens with mode `"a"`, calls `f.flush()` + `os.fsync()`
- Lock: per-session `threading.Lock` via `WeakValueDictionary` (`_outcomes_locks`, line 37)
- Path: `sessions/{session}_outcomes.jsonl` (line 240)
- Rotation: triggered when `path.stat().st_size > OUTCOME_MAX_BYTES` (10 MB).
  Files rotate as `.jsonl` → `.jsonl.1` → `.jsonl.2` → … keeping
  `OUTCOME_BACKUP_COUNT = 5` backups; the oldest is unlinked. Rotation
  function at line 602.
- **Strictly append-only between rotations.** No code path rewrites past lines.

---

## [3/8] USD inside Comfy-Cozy

**Result:** USD is present **as opt-in code only**, not as a written runtime
artifact. The bridge does not need to parse USD.

**Files:**

- No `.usda` / `.usdc` / `.usd` / `.usdz` files exist as runtime state. The
  only matches in the tree are inside `.venv312/Lib/site-packages/pxr/pluginfo/`
  — the `usd-core` package's own internal schema descriptors. Not Comfy-Cozy's
  output.

**Imports:**

- `pyproject.toml`: `usd-core>=24.0` is in `[project.optional-dependencies] stage`,
  i.e. **opt-in via `pip install -e ".[stage]"`**. Not in default runtime deps.
- Every `from pxr import …` in `agent/stage/` is wrapped in `try/except ImportError`
  with a `HAS_USD: bool` flag. Modules: `compositor.py`, `cognitive_stage.py`,
  `counterfactuals.py`, `creative_profiles.py`, `experience.py`.
- `cognitive/` (the standalone library) **does not import `pxr` at all**.
- All callers of stage functions check `HAS_USD` first and degrade silently:
  `startup.py:136`, `startup.py:299`, `cli.py:535`, `cli.py:738`,
  `memory/session.py:349`, `session_context.py:104`.

**Role when active:** When `usd-core` IS installed, `CognitiveWorkflowStage`
(`agent/stage/cognitive_stage.py`) holds an in-memory `Usd.Stage` with LIVRPS
sublayer composition. `agent/memory/session.py:save_stage` flushes that stage
to `sessions/{name}.usda`; `load_stage` loads it back. Same module also writes
optional `sessions/{name}.ratchet.json` and `sessions/{name}.experience.json`
sibling files (Ratchet decision log; flat experience-prim summary).

**On the current machine, `pxr` IS installed in `.venv312/`** (the pluginfo
glob hit). However, no `*.usda` / `*.ratchet.json` / `*.experience.json`
sidecars exist in `sessions/`, meaning either USD-saving paths haven't been
exercised, or the stage was created in-memory only and never flushed.

**Bottom line for the bridge:** USD is a possible-but-currently-dormant
sidecar, not a transport. The bridge can ignore `.usda` for the v0 contract;
if it ever appears, it lives at `sessions/{name}.usda` next to the JSON.

---

## [4/8] Session semantics

Sessions in Comfy-Cozy are **implicit**, **string-keyed**, and **lazy**. There
is no explicit start/end event.

**In-memory definition:** `SessionContext` dataclass at
`agent/session_context.py:19` — fields: `session_id: str`, `workflow:
WorkflowSession`, plus per-session containers for intent / iteration / demo /
orchestrator state, lazy `_stage` / `_ratchet` / `_cwm` / `_arbiter`.

**Registry:** `SessionRegistry` (`agent/session_context.py:244`). Process-level
singleton at `agent/session_context.py:322` (`_registry`). Sessions are created
on demand via `get_session_context(session_id="default")`
(line 325) — returns existing or constructs new under one lock.

**Lifecycle:**

- **Start:** No "start" call. First touch via `get_session_context()` creates
  the in-memory `SessionContext`. If `session_id == "default"` AND
  `_initialized` is false at the module level in `startup.py`, this triggers
  `run_auto_init(ctx)` exactly once per process.
- **End:** No explicit "end" call. `SessionRegistry.gc_stale()` runs at the
  start of every `get_session_context()` and evicts contexts idle longer than
  `max_age_seconds=3600` (1 hour) — except `"default"`, which is never GC'd.
- **Persistence:** Strictly tool-driven. The `save_session` / `add_note` /
  `save_stage` / `save_ratchet` / `save_experience` functions write to disk
  when called. Otherwise state is in-memory only.

**Two distinct identifiers — important for the bridge:**

| Identifier | Where | Lifetime | Example |
|---|---|---|---|
| `session_id` (in-memory `SessionContext.session_id`) | `mcp_server.py:35` mints `_SERVER_SESSION_ID = f"conn_{uuid.uuid4().hex[:8]}"` per process. Tool callers may also pass `_session_id` in arguments. | Process-lifetime (MCP) or until GC. | `conn_a1b2c3d4` |
| `session` (the JSONL field, the saved-file name) | Passed in the `session` field of `record_outcome` tool input (`agent/brain/memory.py:342`); defaults to `"default"`. Also the `name` arg of `save_session`/`load_session`. | Persistent identifier on disk. | `"default"`, `"qs-test"` |

The two are decoupled. A connection with `session_id=conn_a1b2c3d4` records
outcomes to `sessions/default_outcomes.jsonl` unless the caller explicitly
passes a different `session` value in the tool input.

**ID propagation into `default_outcomes.jsonl`:** Yes, every line carries a
`session` field. No `session_id` (the in-memory connection id) is recorded —
which means **the JSONL stream is not bridge-able back to the originating MCP
connection** without a separate correlation channel.

**Streaming vs end-of-session writes:** Streaming. Every `record_outcome` tool
call appends a line on the spot, with `flush()` + `fsync()`. No batching.

---

## [5/8] Anthropic SDK surface inside Comfy-Cozy

**The critical answer.**

| Capability | Inside Comfy-Cozy? | Evidence |
|---|---|---|
| **Claude Agent SDK** (`claude-agent-sdk` / `claude_agent_sdk`) | **No.** | Zero imports in source. Not in `pyproject.toml`, not in `requirements.txt`. |
| **Claude Code SDK** (`claude-code-sdk` / `claude_code_sdk` / `claude_code`) | **No.** | Zero imports in source. Not in `pyproject.toml`, not in `requirements.txt`. |
| **Bare Anthropic Python SDK** (`anthropic`) | **Yes.** | `pyproject.toml:24` declares `"anthropic>=0.52.0"`. `requirements.txt:9` pins `anthropic==0.75.0`. Used by exactly one file: `agent/llm/_anthropic.py:12 import anthropic`, instantiated at line 36 as `anthropic.Anthropic()`. |
| **MCP server (Comfy-Cozy as server)** | **Yes.** | `pyproject.toml:32` declares `"mcp>=1.20.0,<2.0"`. `agent/mcp_server.py:23-25` imports `from mcp.server import Server`, `from mcp.server.stdio import stdio_server`, `import mcp.types as types`. Server constructed at line 136 (`server = Server("comfyui-agent")`); registers `@server.list_tools()` and `@server.call_tool()` (lines 138, 165); served over stdio at line 318. CLI entry: `agent mcp`. |
| **MCP client (consuming external MCP servers)** | **No.** | No use of `mcp.client.*` discovered in source. Comfy-Cozy speaks MCP outward, not inward. |
| **Multi-provider LLM router** | **Yes.** | `agent/llm/` package: `_anthropic.py`, `_openai.py`, `_gemini.py`, `_ollama.py`, `_base.py`, `_types.py`. Factory at `agent/llm/__init__.py` selects provider by name. |
| **Direct Anthropic API call at runtime** | **Yes**, when `LLM_PROVIDER=anthropic`. | Same `_anthropic.py:36` client. |

**Hardcoded model strings (live tree only):**

| Model | File | Line | Role |
|---|---|---|---|
| `claude-sonnet-4-20250514` | `agent/llm/__init__.py` | 55 | Anthropic provider default |
| `claude-sonnet-4-20250514` | `agent/config.py` | 50, 55 | `AGENT_MODEL` default when `LLM_PROVIDER=anthropic` |
| `claude-sonnet-4-20250514` | `agent/brain/_sdk.py` | 76 | `BrainAgent` default model |
| `claude-opus-4-6-20250929` | `agent/config.py` | 57 | Mentioned in a comment as override example |
| `gpt-4o` | `agent/llm/__init__.py` | 56; `agent/config.py` 51 | OpenAI provider default |
| `gemini-2.5-flash` | `agent/llm/__init__.py` | 57; `agent/config.py` 52 | Gemini provider default |
| `llama3.1` | `agent/llm/__init__.py` | 58; `agent/config.py` 53 | Ollama provider default |

**Runtime LLM provider picture:** Comfy-Cozy is provider-agnostic at the
agent loop level. `LLM_PROVIDER` env var (default `anthropic`) picks one of
four implementations at startup. `AGENT_MODEL` env var (default per provider)
selects the model. Each provider is a thin adapter over its native SDK and
implements the `LLMProvider` protocol in `agent/llm/_base.py`. The Anthropic
provider is the reference implementation; the others mirror its API surface.

**Implication for bridge design:** Comfy-Cozy carries the **bare Anthropic
SDK** (not the higher-level Claude Agent SDK or Claude Code SDK) and runs **its
own MCP server** as its primary integration surface. A bridge does **not**
need to depend on Anthropic at all to consume Comfy-Cozy's outputs — the
file-watch path is fully decoupled from the LLM provider. Conversely, if the
bridge wants to ride alongside Comfy-Cozy as a co-resident agent, the natural
seam is the **MCP server interface**, not an Agent SDK attachment point — that
attachment point doesn't exist here.

---

## [6/8] Programmatic surface

What a third repo can grip onto.

**Package-level exports** (`agent/__init__.py`): `__version__ = "3.0.0"` and
`tool_count() -> tuple[int, int, int]`. That is the entirety of the documented
public Python API.

**No `api/` / `sdk/` / `public/` modules:** confirmed absent.

**No HTTP server in the agent package:** zero matches for `FastAPI(`, `Flask(`,
`aiohttp.web`, `uvicorn.run`, etc. in `agent/`. (FastAPI/Flask appear in
`requirements.txt` because `panel/` exists as a separate UI subdir, but the
agent itself is not an HTTP service.)

**CLI entry point:** `pyproject.toml:57` declares `[project.scripts] agent =
"agent.cli:app"`. The `agent` Typer app exposes commands (decorators at lines
72, 216, 252, 347, 371, 444, 590, 767):

| Command | Purpose |
|---|---|
| `agent run` | CLI agent loop (standalone). |
| `agent mcp` | MCP server over stdio. |
| `agent inspect` | Diagnostic / status output. |
| `agent parse <path>` | Workflow parsing utility. |
| (others — 4 more `@app.command()` decorators present, not enumerated by name in this scout) | |

**Documented embed pattern:** `README.md` and `CLAUDE.md` describe the agent
purely as a tool surfaced via MCP or CLI. No "embed Comfy-Cozy in another
process" pattern is documented.

**Practical surfaces a bridge can use:**

1. **MCP server (`agent mcp`)** — primary. Stable contract: tool list +
   call_tool. Same surface Claude Desktop / Claude Code use today.
2. **CLI (`agent run`, etc.)** — secondary. Process-fork model.
3. **Direct Python import** — possible but undocumented. `agent.tools.handle()`,
   `agent.session_context.get_session_context()`, `agent.brain.memory` are all
   importable but not declared public. No backwards-compatibility guarantees.
4. **File-watch on `sessions/*_outcomes.jsonl`** — fully decoupled. No
   Comfy-Cozy code dependency at all.

---

## [7/8] Hydration path

**Yes, `AUTO_LOAD_SESSION` exists. Exact location and behavior follow.**

**Config:** `agent/config.py:155`

```
AUTO_LOAD_SESSION = os.getenv("AUTO_LOAD_SESSION", "")
```

Empty string by default — feature off unless the env var is set to a session
name.

**Trigger:** `agent/startup.py:74-75`, inside `run_auto_init(ctx)`:

```
if AUTO_LOAD_SESSION:
    results["session"] = _load_session(ctx, AUTO_LOAD_SESSION)
```

`run_auto_init` itself is called from `get_session_context()`
(`agent/session_context.py:340`) **only when the default session is being
created for the first time in this process**, and is guarded by a
`_initialized = True` flag at module scope (`agent/startup.py:43`) so it runs
exactly once per process.

**What `_load_session` does** (`agent/startup.py:343`):

```
handle_tool("load_session", {"name": session_name}, ctx=ctx)
```

— invokes the `load_session` tool with the session name as the only argument.

**Tool handler:** `agent/tools/session_tools.py:_handle_load_session` (line 162),
which calls `agent/memory/session.py:load_session` (line 104).

**Expected on-disk file:** `sessions/{name}.json`.

**Schema populated** (current `SCHEMA_VERSION = 2`, `agent/memory/session.py:25`):

```
{
  "name": str,                             # session name
  "saved_at": "YYYY-MM-DDTHH:MM:SS",       # last save timestamp
  "schema_version": 2,
  "workflow": {
    "loaded_path": str | null,             # original workflow JSON path
    "format": "api" | "ui+api" | "ui",     # detected workflow format
    "base_workflow": dict | null,          # workflow JSON pre-edits (API format)
    "current_workflow": dict | null,       # current state of workflow JSON
    "history_depth": int                   # patch-history length (full history not serialized)
  },
  "notes": [
    { "text": str, "type": "preference" | "observation" | "decision" | "tip", "added_at": str },
    ...
  ],
  "metadata": dict                         # arbitrary
}
```

**Migration:** `_migrate_session` (line 238) handles v0→v1→v2 upgrades. v0
adds `schema_version`; v1→v2 normalizes notes from `list[str]` to
`list[{text, type, added_at}]`.

**Optional sibling files restored when present** (only if `usd-core` is
installed; `HAS_USD` true):

| Sibling | Loaded by | Schema |
|---|---|---|
| `sessions/{name}.usda` | `load_stage` (`memory/session.py:344`) → constructs `CognitiveWorkflowStage(path)`. | USD layer file. |
| `sessions/{name}.ratchet.json` | `load_ratchet` (`memory/session.py:405`). | `{ "threshold": float, "weights": dict, "history": [{ "delta_id", "kept", "axis_scores", "composite", "timestamp" }, ...] }` |
| `sessions/{name}.experience.json` | `load_experience` (`memory/session.py:472`). | `{ "count": int, "experiences": [chunk-dict, ...] }` — re-records each chunk into the stage's `/experience/` prims. |

**Other auto-init bootstraps** (also in `run_auto_init`, gated by env vars):

| Env var | Default | Effect |
|---|---|---|
| `AUTO_SCAN_MODELS` | `false` | Walks `MODELS_DIR`, registers each model file as a USD prim under `/models/`. Skipped if `usd-core` not installed. |
| `AUTO_SCAN_WORKFLOWS` | `false` | Hits ComfyUI's `/userdata`, `/queue`, `/history`; registers every workflow under `/workflows/` in the stage. Skipped if `usd-core` not installed. |
| `AUTO_LOAD_WORKFLOW` | `""` | Explicit path to a workflow JSON to load as active. |
| `AUTO_LOAD_SESSION` | `""` | Session name, as above. |

**For the bridge:** to hydrate a Comfy-Cozy startup from Moneta, write a JSON
file to `sessions/{name}.json` matching the schema above (and optionally the
three siblings if USD/ratchet/experience state is being carried), then launch
Comfy-Cozy with `AUTO_LOAD_SESSION={name}` set in env. The hydration path is
file-based only — there is no in-process API for "give me your state and I'll
load it."

---

## [8/8] Open questions for bridge

Architectural questions surfaced by the inventory, not solved by it.

- **Two experience streams, not one.** `sessions/*_outcomes.jsonl` (append-only,
  rotated at 10 MB) and `G:/COMFYUI_Database/comfy-cozy-experience.jsonl`
  (full-rewrite snapshot, written by `cognitive/pipeline/autonomous.py`)
  capture different views of "what happened." Does Moneta want both, or only
  the outcomes stream? They share no schema.
- **The session-id decoupling.** The `session` field in JSONL outcomes is the
  caller-supplied tool-input string (defaults to `"default"`). The MCP
  connection's in-memory `session_id` (`conn_<8 hex>`) is never written to
  outcomes. If Moneta wants to attribute a line back to a specific MCP
  connection, the bridge must add that correlation itself.
- **Default-bucket collision risk.** Most callers omit the `session` field, so
  most data ends up in `sessions/default_outcomes.jsonl`. Multiple concurrent
  Comfy-Cozy processes sharing a working directory would interleave into the
  same file. Per-session locks protect against torn lines within a process,
  but cross-process safety is not asserted in code.
- **Rotation semantics for tailers.** `_rotate_outcomes` renames `*.jsonl` →
  `*.jsonl.1` (and shifts all backups one slot). A tailer holding the
  pre-rotation file path will continue reading from the renamed `.1` file
  until it reopens by name. The bridge needs an inode/rename-aware tail or a
  rotation hook.
- **Full-rewrite cadence on `comfy-cozy-experience.jsonl`.** Saved with
  `open(tmp, "w")` then atomic replace. A naive tailer cannot follow it; the
  bridge has to diff snapshots or watch via `watchfiles` and re-read. Is that
  cost acceptable, or should the bridge ignore that file entirely and
  regenerate equivalent state from `outcomes.jsonl` + the saved-session
  capsules?
- **Session-end signal.** No explicit end event. `SessionRegistry.gc_stale`
  evicts after 1 h idle (default never), but eviction is silent and writes
  nothing. The bridge has to choose: declare session end on idle timeout, on
  process exit, or never — and live with the consequence for whichever choice
  it picks.
- **File-rewrite semantics on session JSON.** `save_session`, `add_note`,
  `save_ratchet`, `save_experience` all atomic-replace the whole file. Moneta
  cannot tail these; it has to checkpoint+diff or just always treat the
  current file as the authoritative state.
- **Optional siblings, opt-in surface.** `.usda`, `.ratchet.json`,
  `.experience.json` files only ever materialize when `usd-core` is installed
  AND the corresponding `save_*` tool is called. The bridge has to decide:
  ignore them on v0, fail loudly if they appear, or carry them through
  opaquely.
- **Goals files.** `sessions/{session}_goals.json` is written by
  `agent/brain/planner.py:352`. They're plan-state artifacts. Are these
  bridge-relevant or strictly internal to Comfy-Cozy's planner? Not surfaced
  in the README claim, but they share the `sessions/` namespace.
- **Hydration name vs. id.** `AUTO_LOAD_SESSION` takes a name string and
  populates the in-memory `SessionContext` for `session_id="default"`. If the
  bridge writes a session capsule named `proj_42`, Comfy-Cozy will load it
  into its `default` SessionContext. There is no way to start the process
  with `session_id=proj_42` in memory without changing Comfy-Cozy code. Is
  the bridge OK with this name-into-default flattening?
- **SDK co-residence.** Since the Claude Agent SDK and Claude Code SDK are
  **not** inside Comfy-Cozy, "the bridge rides alongside the agent SDK" is
  not an option here. If conversation state is to flow into Moneta, it has to
  be intercepted at the MCP-server boundary (request/response logging) or
  inside the LLM provider adapters in `agent/llm/`. Is either acceptable, or
  does the bridge stay outside the process?
- **Single MCP connection assumption.** The MCP server uses one
  `_SERVER_SESSION_ID` per process (`mcp_server.py:35`). Multiple Claude
  clients hitting the same `agent mcp` instance would share that ID. Is that
  ever a real configuration in Joe's workflow, and if so does the bridge need
  to disambiguate?
- **Rotation of `default_outcomes.jsonl` already imminent?** Current size is
  ~1.0 MB, threshold is 10 MB. First rotation event is the bridge's first
  real test of its tail/reopen logic.

---

## Bottom line

Comfy-Cozy is a **file-output-only consumer surface** for the bridge. It is
not an HTTP service, does not embed the Claude Agent SDK or Claude Code SDK,
and exposes only the bare `anthropic` Python SDK behind a four-provider
abstraction. Its experience output flows through two streams: an append-only,
rotation-aware `sessions/{name}_outcomes.jsonl` (with a stable 12-field
schema, `session`-keyed) and a full-rewrite `comfy-cozy-experience.jsonl`
snapshot in `COMFYUI_DATABASE`. Sessions are implicit, string-keyed, and
hydrate from `sessions/{name}.json` (plus optional `.usda`/`.ratchet.json`/
`.experience.json` siblings when `usd-core` is present) when the
`AUTO_LOAD_SESSION` env var names a session at startup. The smallest viable
bridge is a **file-watcher with rotation-aware tailing on
`sessions/*_outcomes.jsonl`** for ingest, and a **directory-writer producing
`sessions/{name}.json` plus an `AUTO_LOAD_SESSION` env-var contract** for
hydrate. No Anthropic dependency required. The MCP server is available as a
secondary, richer integration surface if file-watching turns out to be
insufficient — but it should not be the v0 plan, because every richer surface
adds coupling that the file contract avoids.
