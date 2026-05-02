# MISSION: Scout Cozy v0.1 — Moneta Integration Surface

**Role:** `[SCAFFOLD × SCOUT]`
**Type:** Read-only inventory pass — no FORGE actions
**Repo:** *(provided at kickoff)*
**Output:** `SCOUT_COZY_v0_1.md` at the repo root

---

## Why This Exists

Moneta's singleton surgery is clearing. The substrate has a real handle (`Moneta(config)`, context manager, in-memory exclusivity lock). The next question is what it takes to make Cozy the first reference consumer — concretely, not hypothetically.

This scout mirrors the Moneta scout v0.3 pattern, inverted. Where the Moneta scout asked *"is this a substrate or a product?"*, the Cozy scout asks *"where is the seam Moneta plugs into?"* The substrate API is now ground truth. The integration boundary is what's unknown.

This pass produces the integration map that sizes:

- The Cozy × Moneta minimum demo (the "it remembered" moment)
- The EmbeddingGemma drop-in spike (consumer-side, per the brief's confirmed embedder seam)
- The benchmark + token-telemetry instrumentation against real Cozy workloads
- The Cozy-side scope of the cloud deployment path

The scout itself proposes nothing. It maps the terrain so the next planning pass commits against evidence, not assumptions.

---

## Two First-Principles Lenses

The scout is organized around two questions, applied to every step:

- **Replacement** — what does Cozy currently do for state, memory, retrieval, and agent-loop coordination, and what is Moneta replacing vs. supplementing?
- **Surface area** — how many call sites change, how invasive is the integration, and where does the integration boundary fall on the Cozy side?

Cozy-side coupling that *was* there for a reason is not a flag. Cozy-side coupling that exists because the right substrate didn't is the work this scout makes visible.

---

## To Start

Open Claude Code at the Cozy repo path and paste:

```
Execute MISSION_scout_cozy_v0_1.md. Read-only scout pass.
Output to SCOUT_COZY_v0_1.md at the repo root.
Marathon markers every step. Stop and report on any block.
```

That's the kickoff. Full mission below.

---

## Hard Constraints

1. **Read-only.** Zero file modifications. Zero git operations. Zero installs. Zero refactors. Zero "while I'm here" cleanups.

2. **No speculative integration work.** Map only what exists. Do not write Moneta-shim code. Do not propose import lines. The map sizes the work — it is not the work.

3. **Read actual source.** Do not rely on README summaries alone. If a README claim conflicts with code, flag it.

4. **Note unknowns.** If anything is unclear, write the question down — do not guess. Unknowns are first-class scout output.

5. **Cozy only.** Do not modify Moneta. Do not modify any other repo. Reference Moneta's API surface where helpful, but treat it as external — frozen ground truth.

6. **Stop on blocks.** If anything blocks the pass (missing dependency, broken import, test infrastructure failure), STOP at that step, write what you found up to that point, note the block, do not fix.

7. **Integration-seam flagging.** When a piece of Cozy code is doing what Moneta would do — managing state, persisting memory, composing retrieval, coordinating an agent loop — flag it. These are the seams. They don't all have to become Moneta calls; the question is whether Cozy currently has a concept of "where my state lives" that needs to become "where my Moneta handle is."

---

## Moneta Surface — Reference Only

For the scout's framing only. Do not validate this from inside Cozy; trust it as external ground truth.

Moneta's public surface as of this scout:

```python
from moneta import Moneta, MonetaConfig

with Moneta(MonetaConfig(storage_uri="moneta://...")) as substrate:
    substrate.write(...)    # signature per MONETA.md §2.1
    substrate.read(...)
    substrate.<other ops>(...)
```

Key constraints:

- Handle is a context manager (`with Moneta(config) as substrate`)
- Two handles on the same `storage_uri` raise `MonetaResourceLockedError`
- `embedding: List[float]` is a parameter — the consumer (Cozy) produces vectors; Moneta receives them
- No Anthropic/Claude Agent SDK imports inside Moneta — the consumer drives the agent loop
- `MonetaConfig` is frozen dataclass, kw-only, additive (existing fields preserved)

This is what Cozy will eventually import. The scout's job is to find where that import lands and what changes around it.

---

## Output Format

Write one file: `SCOUT_COZY_v0_1.md` at the repo root.

Each section header is a marathon marker: `## [N/12] {section name}`
Plain prose + tables. No diagrams.

Progress indicator format before each section:
`[N/12] {section name}...` — one line of status.

---

## Steps

### [1/12] Top-level inventory

- List every directory and file at the repo root.
- Read `README.md`, `CHANGELOG.md`, and any `*.md` at root.
- Identify: package layout, language, build system, test framework, dependency manifest, runtime entrypoints (CLI, server, notebook).

**Output:** `Top-Level Layout` — list with one-line description per entry.

---

### [2/12] What is Cozy, structurally?

- One paragraph, in plain language, sourced from code: what does Cozy *do* end-to-end? Input → processing → output. Trace the dominant path.
- What kind of artifact is it — library, application, service, agent, IDE extension, plugin, notebook front-end? Identify by entrypoint, not by README claim.
- Who is the user — code calling Cozy programmatically, a human at a terminal, an agent loop running it as a tool, something else?

**Output:** `Cozy Shape` — one paragraph plus a one-line classification (library / app / service / agent / plugin).

---

### [3/12] Current state and memory mechanism

The replacement question, asked first because it sizes everything else.

- How does Cozy persist anything across calls or sessions? Files, sqlite, JSON, in-memory only, none?
- Does Cozy have a concept of "memory" today — accumulated context, prior interactions, learned preferences? If yes, where does it live in the code?
- Does Cozy have a concept of "session" or "user" or "tenant"? Identity model: explicit, implicit, absent?
- Where would a `Moneta(config)` handle plug in — what existing object or scope owns "state for this run"?

**Output:** `State & Memory` — concrete file references, identity-model assessment, and a one-paragraph note on the candidate Moneta-handle ownership site.

---

### [4/12] Retrieval surface and embedder posture

The replacement question for the retrieval path. This step sizes the EmbeddingGemma spike directly.

- Is there a retrieval mechanism today — vector search, keyword, hybrid, none?
- If vectors: what embedder is in use, how is it called, where does it live (cloud API, local model, hardcoded, configurable)?
- If keyword: what does the indexer look like — full-text? regex? tag-based?
- If none: what's the substitute today — re-running everything from scratch each call? Storing raw context blobs?
- Where does retrieval get *invoked* — agent loop, request handler, somewhere else? This is the call site that, post-integration, would route through Moneta.

**Output:** `Retrieval Surface` — current mechanism, embedder location (or absence), and the specific call sites where retrieval happens today.

---

### [5/12] Agent loop architecture

The deployment question for the agent: where does the loop live, what SDK drives it, who owns the conversation?

- Is there an agent loop in Cozy today? Where? What does it import — `anthropic`, `claude_code_sdk`, `claude_agent_sdk`, `langchain`, `openai`, custom?
- Loop shape: streaming, turn-based, single-shot, none?
- Tool exposure: does Cozy expose tools to the model? How are they registered?
- Conversation context: where does message history live? Is it serialized? Reconstructed each call? Held in memory?
- Gates: is there any concept of human-in-the-loop, approval, review, or interrupt today?

**Output:** `Agent Loop` — concrete description of the current loop, SDK in use (or absence), and a one-paragraph note on where Moneta-backed memory would feed the loop.

---

### [6/12] The "it remembered" demo path

The minimum demo from the tier list: same query, better answer after context accumulates. Sixty to ninety seconds of footage, Loom-raw. The scout's job is to find what's in the way.

- Is there a query→answer path that runs today? Trace it. Where would "context accumulates" hook in?
- What would the same-query/different-answer test look like end-to-end against the current code? Identify the minimum surface that needs to exist.
- Specifically: what's missing today that the demo needs — persistence, retrieval, an embedder, a UI, anything?
- Is there a way to record this demo today against current Cozy + a hypothetical Moneta handle, or are there structural pieces to build first?

**Output:** `Demo Path` — current query→answer path, gap list against the "it remembered" demo, and a sized estimate (in days) for the minimum demo surface assuming Moneta integration is done.

---

### [7/12] Integration call-site inventory

The surface-area question, made concrete.

- Identify every place in Cozy that today does what Moneta does — state read, state write, retrieval, memory access, agent context handoff. Count them. List them.
- For each: what's the current implementation? What would change to route through `substrate.<op>(...)` instead?
- Are call sites concentrated in one module (good — small integration surface) or scattered across the codebase (larger surface, more cutover work)?

**Output:** `Call-Site Inventory` — table of file × line × current op × Moneta-equivalent op × invasiveness (small / medium / large change).

---

### [8/12] Configuration and lifecycle

How does Cozy construct things, and where does a `Moneta(config)` instantiation fit?

- Where does Cozy load config today? Env vars, config files, CLI args, hardcoded?
- What's the existing object lifecycle — does Cozy have a "session" or "context" object that owns state, or is everything held in module/global scope?
- If Cozy has its own context/session/handle concept, that's the natural Moneta-handle ownership site. If not, that's a flag — the integration may force introducing one.
- Async surface: is Cozy sync or async? Moneta is sync today. Mismatch is a flag, not a blocker, but it scopes the integration.

**Output:** `Configuration & Lifecycle` — where config lives, what owns state today, and one paragraph on the Moneta-handle lifecycle integration shape (constructed once at startup, per-request, per-session, etc.).

---

### [9/12] Tests and stability signal

- Test count, framework, pass status. Run existing test scripts only — do not author new tests, do not modify test config.
- Identify which subsystems are well-tested vs. thin.
- Specifically flag: tests that exercise state persistence, retrieval, or agent loop behavior. Those tests will need updating during integration. Their density and quality scopes the cutover effort.

**Output:** `Test Coverage` — table of subsystem × test count × stability signal (solid / thin / untested) × integration-impact flag (will / may / won't change during Moneta cutover).

---

### [10/12] Workload characterization for benchmarking

The scout step that sizes the benchmark + token-telemetry work against real Cozy workloads.

- What does a "task" look like in Cozy? Single function call, multi-turn conversation, batch run, something else?
- What's the dominant workload — define one or two representative tasks that could be instrumented for dollars-per-task measurement.
- Where are the natural instrumentation points — request entry, agent-loop turn, model call, retrieval call, response emit?
- Is there existing logging, metrics, or tracing? What does it capture? Token counts at the SDK boundary?

**Output:** `Workload Profile` — definition of representative tasks, list of instrumentation points, and current observability posture.

---

### [11/12] Cloud-readiness, scoped to Cozy

The thin-deployment question, asked of Cozy's existing code rather than future plans.

- Is Cozy local-only today, or does it have any deployment shape (Dockerfile, Procfile, server entrypoint, hosted-service code)?
- If a try-without-installing link existed for the Cozy + Moneta combination, what's missing on the Cozy side — packaging, web UI, API surface, auth, anything?
- What product-shaped assumptions in Cozy would have to break for thin deployment? (Single-user assumptions, hardcoded paths, local-filesystem-only retrieval, etc.)

**Output:** `Cloud Readiness` — Cozy's current deployment shape, gap list for thin-deployment, and explicit warning list for any code that would push thin-deployment toward full SaaS scope.

---

### [12/12] Integration synthesis and open questions

Synthesize across the previous eleven steps. Two outputs:

**A. Integration scope estimate** — a sized breakdown of the Cozy-side work for Moneta integration, organized into the three bands from the planning pass:

| Band | Cozy-side work | Days |
|---|---|---|
| Minimum demo | What's needed for the "it remembered" footage | ? |
| Mike-credible | + benchmark instrumentation + token economics | ? |
| Substrate-proven | + thin cloud deployment for Cozy + Moneta | ? |

Fill in the days column with concrete numbers grounded in the call-site inventory and demo-path findings. Note assumptions explicitly. Cite the steps that justify each estimate.

**B. Open questions for the integration design pass** — bulleted questions only. No proposed resolutions. Cover at minimum:

- Lifecycle integration shape (handle owned by what, lifetime aligned with what?)
- Async/sync mismatch resolution if Cozy is async
- Retrieval ownership — does Cozy keep its current retrieval, replace with Moneta, or hybrid?
- Embedder location — Cozy hosts EmbeddingGemma, or Cozy stays embedder-agnostic and the consumer of Cozy provides vectors?
- Identity passthrough — if Cozy has a session/user concept, how does it map to Moneta's storage_uri?
- Test cutover scope — which existing tests change, which new tests are needed?
- Agent-loop ownership — does Moneta inform the loop, or does the loop drive Moneta?

**Output:** `Integration Scope Estimate` and `Integration Open Questions`.

---

## Closing

End `SCOUT_COZY_v0_1.md` with a one-paragraph **Bottom line**:

In plain language, what does Cozy currently look like as a Moneta consumer? Is the integration surface small or sprawling? Are the seams where you'd expect, or are they scattered? What's the single most important thing to get right in the integration design pass that follows this scout?

---

## What This Map Unlocks

When `SCOUT_COZY_v0_1.md` comes back:

- **Cozy × Moneta minimum demo** gets a real day estimate from step [6] grounded in step [7]'s call-site inventory
- **EmbeddingGemma spike scope** gets sized against step [4]'s embedder posture
- **Benchmark + token-telemetry instrumentation** gets concrete instrumentation points from step [10]
- **Thin cloud deployment scope** for the Cozy half gets sourced from step [11]
- **Integration design pass** (the next phase, Architect-role) gets sourced from step [12]
- **Total project estimate** — Moneta days plus Cozy days — becomes a real number, not a range

No building until this map is in hand.
