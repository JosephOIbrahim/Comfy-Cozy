# MISSION: Scout Comfy-Cozy for Moneta Bridge

**Role:** `[SCAFFOLD × SCOUT]`
**Type:** Read-only inventory pass — no FORGE actions
**Repo:** `G:\Comfy-Cozy`
**Output:** `SCOUT_COMFY_COZY_FOR_BRIDGE.md` at the repo root

---

## Why this exists

We are building `moneta-comfy-bridge` — a third public-facing repo that wires Comfy-Cozy's experience output into Moneta's persistence layer **without modifying either repo**. Comfy-Cozy is frozen as law (its README claims the experience loop works). Moneta is frozen as law (rc1 closed 4.27, free-threading guard 4.28).

The bridge tails Comfy-Cozy's session output, ingests it into Moneta on write, and hydrates Moneta state back into the format Comfy-Cozy expects on startup. Before we can write a single line of bridge code, we need ground-truth on:

1. **Where session-relevant state lives** on disk (not just `sessions/`).
2. **The schema of those writes** — fields, identifiers, how a "session" is reconstructed.
3. **Trigger points in the codebase** — what code path causes the writes.
4. **Whether the Claude Agent SDK and/or Claude Code SDK already live inside Comfy-Cozy as runtime dependencies.** ← **Critical, called out below.**

This is a tighter mission than a v1.0 categorization scout. Single deliverable: enough information to write the bridge.

---

## To Start

Drop this file into `G:\Comfy-Cozy\` and open Claude Code at that directory. Paste:

```
Execute MISSION_scout_comfy_cozy_for_bridge.md. Read-only scout pass.
Output to SCOUT_COMFY_COZY_FOR_BRIDGE.md at the repo root.
Marathon markers every step. Stop and report on any block.
```

Full mission below.

---

## Hard Constraints

1. **Read-only.** Zero file modifications. Zero git operations. Zero installs. Zero refactors. Zero "while I'm here" cleanups.
2. **No speculation.** Map only what exists. If something is unclear, note the question — do not guess.
3. **Read actual source.** Do not rely on README summaries alone. If a README claim conflicts with code, flag it.
4. **Comfy-Cozy only.** Do not touch the Moneta repo, do not modify ComfyUI, do not run Comfy-Cozy.
5. **Stop on blocks.** If anything blocks the pass (broken import, missing file, ambiguous architecture), STOP at that step, write what you found up to that point, note the block, do not fix.

---

## Output Format

Write one file: `SCOUT_COMFY_COZY_FOR_BRIDGE.md` at the repo root.

Each section header is a marathon marker: `## [N/8] {section name}`
Plain prose + tables. No diagrams.
Progress indicator format before each section: `[N/8] {section name}...`

---

## Steps

### [1/8] On-disk state surface — full picture

The prior assumption was that Comfy-Cozy writes `.usda` plus 4 sibling JSONs into `sessions/`. The actual contents of `G:\Comfy-Cozy\sessions\` show **no `.usda` files** — only `.json` goal/test artifacts and `.jsonl` outcome streams. Either USD lives elsewhere, or USD is internal to Moneta and not the transport between the two systems.

**Inventory every directory at the repo root that could contain runtime state.** Specifically:

- `sessions/` — full listing, classify each file (goal artifact / outcome stream / test fixture / placeholder)
- `substrate/` — full listing, what's in here, file types, sizes, write cadence
- `orchestra/` — full listing, same
- Any other top-level directory that looks like state, output, cache, or experience capture (e.g. `data/`, `state/`, `experience/`, `cache/`, `outputs/`, `runs/`, `artifacts/`)
- `.gitignore` — what's deliberately *not* tracked (often where real runtime writes go)

**Output:** `On-Disk State Surface` — table of directory × file types present × purpose × write cadence (if discoverable from code) × tracked-or-ignored.

---

### [2/8] JSONL outcome stream schema

`sessions/default_outcomes.jsonl` is ~1 MB and is the suspected primary experience log. We need its actual shape.

- Read the first line, last line, and one middle line of `default_outcomes.jsonl`.
- Identify: does each line carry a session/project/correlation ID? A timestamp? An event type? Outcome data? Workflow reference? Vision evaluation result?
- Compare structure across the three lines — is the schema stable, or does it vary by event type?
- Identify: what code module produces these writes? (grep for `default_outcomes`, `outcomes.jsonl`, or the writer function.)

**Output:** `Outcome Stream Schema` — annotated example line, list of fields with types, identification of the writer module, notes on schema stability.

---

### [3/8] USD presence inside Comfy-Cozy

Settle the question that opened this scout.

- Is there *any* `.usda`, `.usdc`, `.usd`, or `.usdz` file in the repo? (Glob the whole tree.)
- Is `pxr` / `usd-core` / OpenUSD imported anywhere in the codebase? (Grep imports.)
- Are there modules named `usd*`, `stage*`, `prim*`, `livrps*`, or referencing layer composition?
- If USD is present: where is it written, where is it read, and what role does it play?
- If USD is absent: confirm explicitly. The bridge design changes significantly based on this answer.

**Output:** `USD Inside Comfy-Cozy` — explicit yes/no, with file references if yes, with import-grep summary if no.

---

### [4/8] Session boundary semantics

Bridge wiring needs a "session" definition that both repos can agree on.

- How does Comfy-Cozy define a session in code? Look for `Session`, `start_session`, `session_id`, `SessionContext`, or equivalent.
- What event marks session start? Session end?
- Is there a session ID that propagates into the `default_outcomes.jsonl` lines?
- Is there a `save_session` / `flush_session` / `persist_session` call referenced anywhere?
- Is session state held in-memory and only written at end, or written-as-it-happens (streaming)?

**Output:** `Session Semantics` — definition, lifecycle, ID propagation, in-memory vs streaming.

---

### [5/8] Claude Agent SDK + Claude Code SDK presence — INSIDE Comfy-Cozy

**This is the critical ask. Read carefully.**

The question is **not** "does Joe use Claude Code to develop Comfy-Cozy" — that's external tooling. The question is whether Comfy-Cozy itself imports or depends on the Claude Agent SDK or Claude Code SDK as part of its **runtime**, packaged inside the repo. Inside-out, not outside-in.

Concretely, check for:

- **`pyproject.toml` / `requirements*.txt` / `setup.py`** — does any of these declare `claude-agent-sdk`, `anthropic-agent-sdk`, `claude-code-sdk`, `anthropic[agent]`, or any Anthropic SDK as a runtime dependency? Distinguish runtime vs dev-only dependency groups.
- **Imports in source code** — grep the `agent/` tree (and any other source dir) for:
  - `from anthropic` (any submodule)
  - `import anthropic`
  - `claude_agent_sdk`
  - `claude_code_sdk`
  - `from claude_code` / `import claude_code`
  - any Anthropic-namespaced module
- **MCP integration** — is there an MCP server or client in Comfy-Cozy itself? (Distinct from `mcp_config.json` in the user's home directory pointing Claude Desktop at the agent.) Look for `mcp.server`, `Server(`, `@server.list_tools`, etc.
- **LLM provider abstraction** — what provider does Comfy-Cozy actually call at runtime? Is it Anthropic direct, OpenAI, Ollama, Gemini, a multi-provider router, or all of the above? Where is the provider chosen?
- **Hardcoded model strings** — grep for `claude-` / `gpt-` / `gemini-` / `llama` / `ollama`. List which model identifiers appear and in what files.

**Output:** `Anthropic SDK Surface Inside Comfy-Cozy` — clear yes/no for each of {Claude Agent SDK, Claude Code SDK, MCP server, MCP client, direct Anthropic API, multi-provider router}. For each "yes," cite the file and line. For each "no," confirm by saying so explicitly. Include the runtime LLM provider picture as a paragraph at the end.

This answer changes the bridge architecture. If the SDKs are inside, Moneta integration can ride alongside them on the same agent surface. If they are not inside, the bridge is a pure file-watching consumer with no Anthropic dependency itself.

---

### [6/8] Existing public API / programmatic surface

If a third repo wants to consume Comfy-Cozy programmatically (not just file-watch its outputs), what's available?

- `__init__.py` exports at the package root.
- Any `api/`, `sdk/`, or `public/` module.
- Any FastAPI / Flask / aiohttp server on a known port.
- Any CLI entry points (`pyproject.toml` `[project.scripts]`).
- Any documented "embed Comfy-Cozy in another process" pattern.

**Output:** `Programmatic Surface` — list of exported names / endpoints / entry points with one-line description each, or "none — file-output-only consumer pattern is the only path" if that's true.

---

### [7/8] AUTO_LOAD_SESSION + hydration path

Prior context referenced an `AUTO_LOAD_SESSION` mechanism for warm-starting Comfy-Cozy from a prior state. Verify this exists.

- Grep for `AUTO_LOAD_SESSION`, `auto_load`, `load_session`, `hydrate`.
- If found: where is it triggered, what file format does it expect, what fields does it populate?
- If not found: is there *any* startup hook that reads prior state into memory? Where is it?

**Output:** `Hydration Path` — exact code location, expected input format, populated fields. This is how the bridge will write Moneta's state back into Comfy-Cozy's expected shape.

---

### [8/8] Open questions for bridge design

End the scout with a bulleted list of every architectural question still unresolved after the inventory. **Surface, don't solve.** Examples of the shape (these are illustrations, not the actual answers):

- Does `default_outcomes.jsonl` rotate on a schedule, or grow unboundedly?
- Is there a session-end signal the bridge can hook, or must it infer session boundaries from the stream?
- Does Comfy-Cozy ever rewrite past JSONL lines (compaction, dedup), or is the file strictly append-only?
- If Claude Agent SDK is inside, does it carry conversation state that should also flow into Moneta?

**Output:** `Open Questions for Bridge` — bulleted questions, no proposed answers.

---

## Closing

End `SCOUT_COMFY_COZY_FOR_BRIDGE.md` with a one-paragraph **Bottom line**:

In plain language, what is the bridge's actual surface against Comfy-Cozy? File-watcher only? File-watcher plus SDK co-residence? Programmatic embed? What's the smallest viable bridge?

---

## What This Scout Unlocks

When `SCOUT_COMFY_COZY_FOR_BRIDGE.md` comes back:

- **Mile 2 (bridge implementation)** gets concrete file paths, schemas, and trigger points.
- **The "Anthropic SDK inside?" answer** decides whether the bridge stays pure-watcher or becomes a co-resident agent extension.
- **Hydration mechanics** stop being inferred and become a real read/write contract.
- **The third-repo design** (`moneta-comfy-bridge`) gets locked: dependencies, watch targets, ingest contracts, hydrate contracts.

No bridge code until this scout is in hand.
