# Claude Code Install Pack — Phase 5 Minimum + Comfy-Cozy v3

## For: Joe Ibrahim (Creative Director / Architect)
## To: Claude Code (operating under MOE roles + 8 Commandments)
## Date: April 7, 2026
## Status: Execution-ready
## Project root: `G:\Comfy-Cozy\`
## Specs being built: `PHASE_5_MINIMUM_BUILD_SPEC_V3.md` + `COMFY_COZY_V3_BUILD_SPEC.md`

---

# ⚠️ VERIFY BEFORE FIRST PASTE — Python Package Name

The project was renamed from `comfyui-agent` to **Comfy-Cozy**. Directory paths are updated throughout this pack (`G:\Comfy-Cozy`). **But the Python package name inside the code is a separate question.**

Before pasting Mile 1, check which of these is true:

```powershell
cd G:\Comfy-Cozy
dir comfy_agent 2>$null; dir comfy_cozy 2>$null
```

- If you see `comfy_agent\` → the Python package was NOT renamed. The prompts use `comfy_agent/brain/memory/...` which is correct. Proceed as-is.
- If you see `comfy_cozy\` → the Python package WAS renamed. Before pasting any prompt, do a find-and-replace in this doc: `comfy_agent/` → `comfy_cozy/` and `from comfy_agent` → `from comfy_cozy`.

**Why this matters:** Python imports are brittle. One wrong `from comfy_agent.core import ...` and Mile 1 fails before it starts. 30 seconds of verification now saves 30 minutes of debugging later.

---

# 0. HOW TO USE THIS PACK

This document is a **copy-paste install guide**. You don't read it linearly — you find your current mile marker and execute the prompt block at that step.

**Each step has:**

- A **mile marker** (Mile X of Y)
- A **role declaration** in `[DOMAIN × ROLE]` format
- A **copy-paste prompt** for Claude Code (drop into the terminal as-is)
- A **"you should see"** verification line
- A **stop point** (where to halt for review)

**The 8 Commandments are embedded in §1.** Every Claude Code prompt in this pack references them. They are the constitution every agent operates under. Read them once before starting.

**Single session, single repo.** Comfy-Cozy lives at `G:\Comfy-Cozy\` with both backend (`comfy_agent/`) and panel (`panel/`) under one root. Launch Claude Code once from that directory and work the whole pack from a single session. No more two-terminal juggling.

**Two tracks within the single session:**

- **Track A — Phase 5 Minimum** (Cerebellum receiving side, ~1–2 days, all backend)
- **Track B — Comfy-Cozy v3 Features 1, 2, 3** (Panel + backend, ~3–5 days)

These two tracks are **independent** in terms of code dependencies until Mile 10. You can run them sequentially (Track A first, then Track B) or interleave them within the same session if you're confident. Sequential is the recommended first run.

**Mile 10 (Auto-Heal)** is the convergence point. It requires both tracks complete.

---

# 1. THE 8 AGENT COMMANDMENTS (CONSTITUTION)

Every agent operating under this pack follows these rules. They are quoted in every prompt. Violating them is grounds for an immediate stop.

### Commandment 1 — SCOUT BEFORE YOU ACT

Reconnaissance is the first action of any phase. Search for relevant files, don't ingest the codebase. Read 2–3 existing examples before creating anything new. Match conventions, don't invent them. Identify frozen boundaries before touching the work area.

### Commandment 2 — VERIFY AFTER EVERY MUTATION

The distance between a change and its verification is exactly one step. Run tests after every file create/modify. Existing passing tests are invariants. You leave more verification than you found.

### Commandment 3 — BOUNDED FAILURE → ESCALATE

3 retries on the same fix, then stop. Stopping is not failure — it's correct behavior. Surface what you tried, what failed, what you think the issue is. Never silently weaken a test or skip a requirement.

### Commandment 4 — COMPLETE OUTPUT OR EXPLICIT BLOCKER

No stubs. No `TODO: implement later`. No truncation. No `// ... existing code ...` ellipsis. Either the file is fully realized, or you explicitly flag what's missing and what it would take. There is no middle ground.

### Commandment 5 — ROLE ISOLATION

You operate inside your declared `[DOMAIN × ROLE]` boundary. Architects design and do not implement. Forges implement what was specified and do not freelance. Disagreements are surfaced as notes, not silent improvements. Competence is not authority.

### Commandment 6 — EXPLICIT HANDOFFS

The interface between agents is a named artifact, not ambient context. Each phase produces a specific deliverable the next phase reads. State is committed at every phase boundary so rollback is always possible.

### Commandment 7 — ADVERSARIAL VERIFICATION

The Crucible role exists to break what was built, not confirm success. Edge cases are mandatory, not bonus. Vague assertions are bugs. Fix the implementation when a test fails — never weaken the test to make it pass.

### Commandment 8 — HUMAN GATES AT IRREVERSIBLE TRANSITIONS

Decisions expensive to reverse require human confirmation. Gates go after design (before implementation commits a direction), not after implementation (when sunk cost is spent). Use as few gates as possible. Every gate is a momentum break.

---

# 2. PRE-FLIGHT CHECKLIST (DO THIS FIRST)

**Mile marker: Pre-flight (~30 minutes)**

Before any agent touches code, run this checklist by hand. It enforces the "Verify, Don't Rebuild" rule from both spec docs. If any item fails, file a 1-hour fix ticket BEFORE proceeding.

### Pre-flight Step 1 — Confirm Phase 1 (typed graph engine)

Open a terminal in `G:\Comfy-Cozy` and run:

```powershell
.venv312\Scripts\activate
pytest tests/core/ -v
```

**You should see:** All Phase 1 tests passing. `CognitiveGraphEngine`, `DeltaLayer`, `mutate_workflow`, `verify_stack_integrity` all green.

**If they fail:** Stop. Phase 1 needs to be fixed before any new work. File this as the only blocker.

### Pre-flight Step 2 — Confirm `to_topological_dict()` exists

```powershell
python -c "from comfy_agent.core.engine import CognitiveGraphEngine; e = CognitiveGraphEngine(); print(hasattr(e, 'to_topological_dict'))"
```

**You should see:** `True`

**If you see `False`:** This is the semantic compression primitive Comfy-Cozy depends on. File a 1-hour ticket to add it before Track B starts.

### Pre-flight Step 3 — Confirm Anthropic prompt caching is wired

Open `comfy_agent/api/server.py` (or wherever `claude_bridge` lives) and search for:

```
"type": "ephemeral"
```

**You should see:** At least one `ephemeral` cache marker on the system prompt and tool definitions.

**If missing:** 1-hour fix. Add `cache_control={"type": "ephemeral"}` to the system prompt block and the tools block in the Anthropic API call. This is the 90% latency win — don't skip it.

### Pre-flight Step 4 — Confirm PILOT layer exists

```powershell
python -c "from comfy_agent.intelligence.pilot import PILOT_TOOLS; print(len(PILOT_TOOLS))"
```

**You should see:** `13` (or close to it)

**If missing or wrong path:** Find where the 13 PILOT tools live and update Mile 8 prompts with the correct import path before launching Track B.

### Pre-flight Step 5 — Confirm Brain/Vision tools exist

```powershell
python -c "from comfy_agent.brain.vision import VISION_TOOLS; print(len(VISION_TOOLS))"
```

**You should see:** `4`

**If missing or wrong path:** Same as above — find the correct path and update the prompts.

### Pre-flight Step 6 — Confirm panel symlink is live

```powershell
Get-Item "G:\COMFY\ComfyUI\custom_nodes\Comfy-Cozy-Panel" | Select-Object LinkType, Target
```

**You should see:** `LinkType: SymbolicLink` (or `Junction`), `Target: G:\Comfy-Cozy\panel`

**If missing:** See §2 of `CLAUDE_CODE_SETUP_GUIDE.md` for the symlink command. Without this, ComfyUI won't load any panel changes you make in Track B.

### Pre-flight Step 7 — Tag the current state in git

```powershell
cd G:\Comfy-Cozy
git tag pre-phase5-minimum
git push --tags
```

**You should see:** Tag created. This is your rollback point. If Track A goes sideways, `git reset --hard pre-phase5-minimum` returns you here cleanly.

---

# 3. TRACK A — PHASE 5 MINIMUM (CEREBELLUM RECEIVING SIDE)

**Total mile markers in this track: 4**
**Estimated duration: 1–2 days**
**Spec source:** `docs/PHASE_5_MINIMUM_BUILD_SPEC_V3.md`
**Hard LOC budget:** ~600 lines of Python total
**Files touched:** All under `comfy_agent/brain/memory/`, `comfy_agent/api/`, `tests/brain/memory/`

---

## Mile 1 of 4 — Schemas (`experience.py`)

**Role:** `[EXPERIENCE × FORGE]`
**Estimated time:** ~30 minutes

### Copy-paste prompt for Claude Code:

```
ROLE: [EXPERIENCE × FORGE]

You are operating under the 8 Agent Commandments. The most relevant for this task:
- Commandment 1: SCOUT before you act. Read 2-3 existing Pydantic models in the codebase before writing new ones to match the convention.
- Commandment 2: VERIFY after every mutation. Run the test after creating the file, before declaring done.
- Commandment 4: COMPLETE OUTPUT. No stubs. No TODOs. No truncation.
- Commandment 5: ROLE ISOLATION. You implement what is specified. You do not redesign.

SPEC: docs/PHASE_5_MINIMUM_BUILD_SPEC_V3.md, Section 3 Module 1, and Section 4 Pydantic Models.

TASK: Create the file `comfy_agent/brain/memory/experience.py` containing exactly two Pydantic models: `FailureExperience` and `ProposalEvent`. Use the exact field definitions from Section 4 of the spec. Use `default_factory` for `id` (uuid4) and `created_at` (datetime.utcnow).

CONSTRAINTS:
- Zero new dependencies beyond Pydantic and stdlib.
- LOC budget for this file: ~60 lines.
- Match existing Pydantic conventions in the codebase (scout first).
- Python package name is `comfy_agent` (not `comfy_cozy`). Do not rename imports.

TEST GATE: After creating the file, write and run a quick smoke test:
1. Instantiate `FailureExperience` with mock data.
2. Verify `id` and `created_at` are auto-populated.
3. Verify the `Literal` constraints on `resolution_status` reject invalid values.

If any of these fail, do not proceed. Surface the failure with what you tried.

DO NOT create `signature.py`, `failure_store.py`, or modify `server.py` in this step. Those are separate mile markers.

When done, commit with message: "Phase 5 Minimum: experience.py schemas (Mile 1/4)"

STOP after commit. Do not proceed to Mile 2 without my confirmation.
```

### You should see:

- `comfy_agent/brain/memory/experience.py` created, ~60 lines
- Both models instantiate cleanly
- Literal constraints reject `"foo"` for `resolution_status`
- Git commit landed
- Claude Code stops and reports

### Stop point:

**Human gate.** Quick scan the file. Confirm both models match the spec. Then proceed to Mile 2.

---

## Mile 2 of 4 — Signature (`signature.py`)

**Role:** `[EXPERIENCE × FORGE]`
**Estimated time:** ~1 hour

### Copy-paste prompt for Claude Code:

```
ROLE: [EXPERIENCE × FORGE]

You are operating under the 8 Agent Commandments. Most relevant:
- Commandment 4: COMPLETE OUTPUT. The signature canonicalization rules are precise. Implement every rule.
- Commandment 7: ADVERSARIAL VERIFICATION. The signature primitive is the load-bearing piece of the retry guard. Test it adversarially.

SPEC: docs/PHASE_5_MINIMUM_BUILD_SPEC_V3.md, Section 3 Module 2.

TASK: Create the file `comfy_agent/brain/memory/signature.py` containing exactly one public function:

    def compute_workflow_signature(workflow_state: dict) -> str

The function MUST implement all six logic steps from the spec:
1. Format detector for UI vs API prompt format
2. Deep-copy the API-format dict
3. Value stripping: strip primitive tunables, but PRESERVE:
   (a) Edge references of the form [node_id, output_index]
   (b) Strings ending in .safetensors, .ckpt, .pt, .gguf, .bin, .sft
   (c) Values whose input key matches *_name or *_model
4. Sort dict keys recursively, sort top-level node IDs.
   CRITICAL: Edge reference lists [node_id, output_index] must NEVER be sorted or modified.
5. Serialize with separators=(',', ':'), sort_keys=True
6. Return hashlib.sha256(canonical_bytes).hexdigest()

CONSTRAINTS:
- Zero new dependencies. hashlib + json + copy from stdlib only.
- LOC budget: ~90 lines.
- The format detector is ~10 lines at the top of the function.
- This is the only public function. Helpers can be private (_underscored).

TEST GATE: After creating the file, write a smoke test in a scratch file (not the real test file yet) that proves:
1. Two API workflows differing only in seed values produce the same hash.
2. Two API workflows with different model names produce different hashes.
3. An edge reference list [node_id, index] is unchanged after canonicalization.

If any fail, do not proceed.

DO NOT create the formal test file (`test_phase5_minimum.py`). That is Mile 4.

When done, commit with message: "Phase 5 Minimum: signature.py canonicalization (Mile 2/4)"

STOP after commit.
```

### You should see:

- `signature.py` created, ~90 lines
- The smoke test passes all three assertions
- Git commit landed

### Stop point:

**Human gate (light).** Read the canonicalization function. Confirm edge reference preservation logic is explicit. Proceed to Mile 3.

---

## Mile 3 of 4 — Failure Store (`failure_store.py`)

**Role:** `[EXPERIENCE × FORGE]`
**Estimated time:** ~2 hours

### Copy-paste prompt for Claude Code:

```
ROLE: [EXPERIENCE × FORGE]

You are operating under the 8 Agent Commandments. Most relevant:
- Commandment 1: SCOUT. If any other module in this codebase uses sqlite3, read it first to match conventions.
- Commandment 4: COMPLETE OUTPUT. Two classes, full implementations, no stubs.
- Commandment 5: ROLE ISOLATION. Do not redesign the schema. Use exactly the SQL from Section 4.

SPEC: docs/PHASE_5_MINIMUM_BUILD_SPEC_V3.md, Section 3 Module 3, and Section 4 SQLite Schema.

TASK: Create the file `comfy_agent/brain/memory/failure_store.py` containing exactly two classes: `FailureStore` and `ProposalEventStore`.

`FailureStore` exposes:
- __init__(self, db_path: Path) — creates dir if missing, runs CREATE TABLE/INDEX
- record_failure(self, failure: FailureExperience) -> FailureExperience
  UPSERT logic: compute signature -> SELECT existing by signature.
  If exists: increment retry_count, update created_at, set recalcitrant = (retry_count >= 3), return updated record.
  Else: INSERT new row with retry_count=1, return new record.
- get_by_signature(self, signature: str) -> Optional[FailureExperience]
- mark_resolved(self, failure_id: str, status: str, proposal_id: Optional[str]) -> None

`ProposalEventStore` exposes:
- __init__(self, db_path: Path) — same DB, different table
- record_event(self, event: ProposalEvent) -> ProposalEvent
- get_recent(self, session_id: str, limit: int = 100) -> List[ProposalEvent]

CONSTRAINTS:
- sqlite3 from stdlib only. No SQLAlchemy. No ORM.
- Both stores share the same SQLite file via separate connections.
- Sync only. No async.
- LOC budget: ~150 lines total for the file.
- Storage path defaults to G:/Comfy-Cozy/data/experience.db (use forward slashes in shell commands), configurable via env var COMFY_AGENT_EXPERIENCE_DB_PATH.
- Use the EXACT SQL schema from Section 4. Do not add columns. Do not reshape.

CRITICAL: This module imports `compute_workflow_signature` from `signature.py` and the schemas from `experience.py`. Verify those imports work before writing the rest.

TEST GATE: Smoke test in a scratch file:
1. Initialize FailureStore with an in-memory SQLite (`:memory:`).
2. record_failure on a mock FailureExperience. Confirm retry_count=1 returned.
3. record_failure with the SAME workflow_state. Confirm retry_count=2.
4. record_failure with the SAME workflow_state again. Confirm retry_count=3 AND recalcitrant=True.
5. mark_resolved on the failure ID. Confirm resolution_status updates.

DO NOT modify server.py yet. That is Mile 4.

When done, commit with message: "Phase 5 Minimum: failure_store.py SQLite stores (Mile 3/4)"

STOP after commit.
```

### You should see:

- `failure_store.py` created, ~150 lines
- All five smoke test assertions pass
- An SQLite file appears at the default location (or `:memory:` works)
- Git commit landed

### Stop point:

**Human gate.** This is the most logic-dense file. Spend 5 minutes reading the UPSERT logic — confirm the retry_count increment and recalcitrant flag are correct. Proceed to Mile 4.

---

## Mile 4 of 4 — API endpoints + full test suite

**Role:** `[EXPERIENCE × FORGE]` then `[EXPERIENCE × CRUCIBLE]`
**Estimated time:** ~3 hours

### Copy-paste prompt for Claude Code (FORGE half):

```
ROLE: [EXPERIENCE × FORGE]

You are operating under the 8 Agent Commandments. Most relevant:
- Commandment 1: SCOUT. Read existing endpoints in server.py to match the routing convention (FastAPI? Flask? something custom?).
- Commandment 4: COMPLETE OUTPUT. All five endpoints, full request/response schemas.
- Commandment 5: ROLE ISOLATION. Do not change existing endpoints. Only add new ones.

SPEC: docs/PHASE_5_MINIMUM_BUILD_SPEC_V3.md, Section 3 Module 4, and Section 5 API Surface.

TASK: Modify `comfy_agent/api/server.py` to add exactly five new endpoints:

1. POST /failures        — accepts failure payload, returns updated FailureExperience
2. GET /failures/signature/{signature_hex}  — returns FailureExperience or 404
3. PATCH /failures/{id}/resolve  — marks resolved, returns success
4. POST /proposal_events — inserts ProposalEvent, returns 201 with full record
5. GET /proposal_events?session_id=X&limit=N — returns list of ProposalEvents

Inject FailureStore and ProposalEventStore into the application state at startup. Both stores point to the same SQLite file.

CONSTRAINTS:
- Match the existing endpoint convention in server.py.
- Do not modify ANY existing endpoint.
- LOC budget for the additions: ~100 lines.
- Request/response schemas EXACTLY as Section 5 of the spec.

When done, commit with message: "Phase 5 Minimum: API endpoints wired (Mile 4a/4)"

STOP after commit. Do not write the formal test suite yet — that is the CRUCIBLE half.
```

### Then, copy-paste prompt for Claude Code (CRUCIBLE half):

```
ROLE: [EXPERIENCE × CRUCIBLE]

You are operating under the 8 Agent Commandments. Most relevant:
- Commandment 7: ADVERSARIAL VERIFICATION. You are the breaker, not the builder. Try to find failures.
- Commandment 5: ROLE ISOLATION. You write tests. You do NOT modify the implementation. If a test fails, surface the bug — do not fix it yourself.

SPEC: docs/PHASE_5_MINIMUM_BUILD_SPEC_V3.md, Section 6 Test Plan.

TASK: Create the file `tests/brain/memory/test_phase5_minimum.py` containing all 11 tests from Section 6 of the spec:

Signature tests (4):
1. Format Agnostic — UI format and API format produce identical hashes
2. Value Independence — different seeds/prompts/CFG -> same hash
3. Model Dependence — different model names -> different hashes
4. Structural Dependence — different edge references -> different hashes; AND assert edge ref lists are un-mutated

Failure store tests (4):
5. Initial Record — retry_count=1
6. Collision Increment — second failure same signature -> retry_count=2
7. Recalcitrant Flag — third failure same signature -> recalcitrant=True
8. Resolution Update — mark_resolved mutates correctly

Proposal event tests (2):
9. Write/Read — insert and query by session_id
10. Null Handling — time_to_decision_seconds=None survives roundtrip

Integration test (1):
11. Auto-Heal Guard Flow — POST /failures three times -> third response has recalcitrant=true

CONSTRAINTS:
- All tests use in-memory SQLite (":memory:") for isolation.
- LOC budget: ~150 lines total.
- Tests must be specific. assert x is a bug — assert x == expected_value or assert x.field == expected.
- If any test reveals a bug in the implementation, STOP and surface it. Do not weaken the test. Do not fix the implementation yourself (you are CRUCIBLE, not FORGE).

After writing the tests, run them:
    pytest tests/brain/memory/test_phase5_minimum.py -v

All 11 must pass. If any fail, stop and report which one + what the implementation did wrong.

When all 11 pass, commit with message: "Phase 5 Minimum: test suite (Mile 4b/4) — all 11 tests green"

Then run the FULL existing test suite:
    pytest

Confirm zero regressions in pre-existing tests. If any pre-existing test broke, STOP and surface it.

STOP after the final commit.
```

### You should see:

- `test_phase5_minimum.py` created, ~150 lines
- All 11 new tests passing
- Zero regressions in the pre-existing test suite
- Two git commits landed (Mile 4a, Mile 4b)

### Stop point:

**Human gate (the big one).** Phase 5 Minimum is done. Tag this state:

```powershell
git tag phase5-minimum-complete
git push --tags
```

This is your second rollback point. Track A is finished. Now start Track B.

---

# 4. TRACK B — COMFY-COZY V3 FEATURES 1, 2, 3

**Total mile markers in this track: 5**
**Estimated duration: 3–5 days**
**Spec source:** `docs/COMFY_COZY_V3_BUILD_SPEC.md`
**Hard constraints (panel files only):** Vanilla JS only, no React, no external runtime deps, Pentagram design language

**Features in this track (sequential):**

- Mile 5 — Backend proposal lifecycle endpoints
- Mile 6 — Ghost Workflows (Feature 1) — panel side
- Mile 7 — Bi-Directional Spatial Binding (Feature 2)
- Mile 8 — VRAM Guardrails (Feature 3)
- Mile 9 — Crucible pass on all three features

**Important:** Ghost Workflows (Feature 1) **depends on Phase 5 Minimum** for the proposal event logging. Track A must be complete before starting Mile 6.

---

## Mile 5 of 9 — Backend proposal lifecycle endpoints

**Role:** `[GRAPH × FORGE]`
**Estimated time:** ~2 hours

### Copy-paste prompt for Claude Code:

```
ROLE: [GRAPH × FORGE]

You are operating under the 8 Agent Commandments. Most relevant:
- Commandment 1: SCOUT. Read the existing typed graph engine and DeltaLayer code before adding endpoints.
- Commandment 5: ROLE ISOLATION. You do NOT modify CognitiveGraphEngine internals. You add new endpoints that USE the engine.

SPEC: docs/COMFY_COZY_V3_BUILD_SPEC.md, Section 3 Feature 1 (Backend Changes only — not panel changes yet).

TASK: Add three new endpoints + one heartbeat endpoint to comfy_agent/api/server.py:

1. POST /propose_delta
   Body: { delta: DeltaLayer payload, session_id: str }
   Behavior: Generate a UUID proposal_id. Store the delta in an in-memory dict keyed by proposal_id, with: { delta, session_id, created_at, last_heartbeat, predicted_quality: None }.
   Response: { proposal_id: str, predicted_quality: None }

2. POST /commit_proposal/{proposal_id}
   Behavior: Look up the proposal. If found, push its delta to the engine via mutate_workflow(). Log a ProposalAccepted event to the experience layer (use ProposalEventStore from Phase 5 Minimum). Remove from pending dict. Return committed delta hash.
   If not found: 404.

3. POST /reject_proposal/{proposal_id}
   Behavior: Look up the proposal. If found, log a ProposalRejected event. Remove from pending dict.
   If not found: 404.

4. POST /proposals/{proposal_id}/heartbeat
   Behavior: Update last_heartbeat to now. Return 200.

ALSO add a background garbage collector that runs every 5 minutes:
- Iterates pending proposals
- Any proposal whose last_heartbeat is older than 30 minutes is removed
- For each removed proposal, log a ProposalAbandoned event

CONSTRAINTS:
- Proposals live in-memory only. No persistence. Agent restart drops all pending proposals.
- 30-minute TTL hardcoded but read from env var COMFY_AGENT_PROPOSAL_TTL_SECONDS for testability (default 1800).
- The garbage collector runs in a background thread or asyncio task — match the existing server.py concurrency model.
- LOC budget: ~120 lines added to server.py.

TEST GATE: Smoke test in a scratch file:
1. POST /propose_delta with a mock delta → returns proposal_id
2. POST /commit_proposal/{id} → returns committed hash, ProposalAccepted logged
3. POST /propose_delta again → POST /reject_proposal/{id} → ProposalRejected logged
4. POST /propose_delta → wait for TTL (set TTL env var to 2 seconds for the test) → confirm garbage collector removes it AND logs ProposalAbandoned

When done, commit: "Comfy-Cozy v3: backend proposal lifecycle endpoints (Mile 5/9)"

STOP after commit.
```

### You should see:

- `server.py` modified, ~120 new lines
- Four endpoints respond correctly
- Garbage collector sweeps stale proposals
- ProposalAccepted/Rejected/Abandoned events landing in the experience DB
- Git commit landed

### Stop point:

**Human gate (light).** Confirm the env var works for testing — you'll need short TTLs for fast iteration. Proceed to Mile 6.

---

## Mile 6 of 9 — Ghost Workflows (Feature 1, panel side)

**Role:** `[SCAFFOLD × FORGE]`
**Estimated time:** ~6–8 hours

### Copy-paste prompt for Claude Code:

```
ROLE: [SCAFFOLD × FORGE]

You are operating under the 8 Agent Commandments. The Pentagram constraint lock applies to EVERY file you create or modify under panel/. Read it twice.

PENTAGRAM CONSTRAINTS (NON-NEGOTIABLE for files under panel/):
- Vanilla JavaScript only. No React. No Vue. No Svelte. No build steps.
- Zero external runtime dependencies. No Dagre. No ELK. No D3. No Lodash.
- Background #0D0D0D. Single accent #0066FF. Inter typography. 1px solid borders. Max 4px corner radius.
- No gradients. No drop shadows.
- Animations: opacity and transform only, 200ms ease-out, no bouncy easing.

If you find yourself reaching for `npm install`, STOP. You are violating a hard constraint.

SPEC: docs/COMFY_COZY_V3_BUILD_SPEC.md, Section 3 Feature 1 (Panel Changes).

TASK: Create three new files under panel/web/:

1. panel/web/js/ghost_renderer.js (~300 LOC)
   - Hook app.canvas.onDrawForeground
   - Fetch pending proposals from the agent backend (GET /proposals/active)
   - Render ghost geometry for each proposal:
     * New nodes: 40% opacity, 1px dashed #0066FF border
     * Modified nodes: solid existing render + #0066FF outline pulse via CSS
     * New edges: 1px dashed #0066FF spline
     * Removed elements: 20% opacity with diagonal hatch
   - PERFORMANCE: Cache draw commands per proposal_id. Invalidate cache only when:
     (a) A proposal is added/removed
     (b) The camera moves or zooms (app.canvas.ds changes)
     (c) The underlying graph mutates
   - On every onDrawForeground tick where nothing has changed, REPLAY cached commands instead of recomputing.

2. panel/web/js/proposal_lifecycle.js (~120 LOC)
   - Generates a session_id on panel load (store in window.COMFY_COZY_SESSION_ID)
   - Sends a heartbeat every 60 seconds to POST /proposals/{id}/heartbeat for every active proposal
   - Manages the in-panel state of pending proposals (a Map keyed by proposal_id)
   - Exposes addProposal(proposal), removeProposal(id), getActiveProposals() for other modules

3. panel/web/js/components.js (~180 LOC for the Proposal Card; other cards land in later miles)
   - ProposalCard(proposal) returns a DOM element styled to Pentagram spec
   - Contains: human-readable summary, [Accept] button, [Reject] button
   - Reserved DOM slot for "Predicted quality: X" (hidden when null) — Phase 7C wiring
   - Click [Accept] → POST /commit_proposal/{id} → on success, removeProposal(id) and unmount card
   - Click [Reject] → POST /reject_proposal/{id} → on success, removeProposal(id) and unmount card
   - Card mounts into the right sidebar of the panel
   - NO [Modify] button. Deferred to Phase 7B.

ALSO update panel/web/css/pentagram.css with:
- The pulse animation keyframes (#0066FF outline, 200ms ease-out, opacity-only)
- Card styling matching Pentagram spec
- Diagonal hatch pattern via CSS (no images)

CONSTRAINTS:
- Total new LOC across the three JS files: ~600.
- Touch nothing else in the panel directory.
- LiteGraph 2D canvas API is your ONLY rendering surface for ghosts. No new canvas elements.
- The panel loads in ComfyUI via the symlink at G:/COMFY/ComfyUI/custom_nodes/Comfy-Cozy-Panel — your edits to panel/ are live in ComfyUI on next restart.

TEST GATE: Manual test (no automated test infrastructure exists for the panel yet):
1. Restart ComfyUI to pick up the panel changes.
2. Manually POST a mock proposal to the backend via curl.
3. Verify a ghost node appears on the canvas with correct opacity and color.
4. Verify the Proposal Card appears in the sidebar.
5. Click Accept. Verify the ghost solidifies into a real node and the card disappears.
6. Repeat with Reject. Verify the ghost vanishes.
7. Open three proposals at once. Verify all three render and don't thrash the canvas (smooth pan/zoom).

If any step fails, STOP and surface what broke.

When all manual steps pass, commit: "Comfy-Cozy v3: Ghost Workflows panel side (Mile 6/9)"

STOP after commit. This is the highest-risk mile in Track B. I want to review before we go to Mile 7.
```

### You should see:

- Three new JS files under `panel/web/js/`
- `panel/web/css/pentagram.css` updated
- Manual test passes all 7 steps
- Git commit landed

### Stop point:

**Human gate (critical).** This is the make-or-break visual integration. Spend 10 minutes hands-on:

- Drop a ghost on the canvas
- Pan and zoom — does it stay smooth on a 100-node graph?
- Accept and reject several proposals
- Confirm Pentagram aesthetic — no React contamination, no rounded corners > 4px, no gradients

If any of those fail, roll back to `phase5-minimum-complete` and re-spec. **Do not proceed to Mile 7 until Mile 6 is solid.**

If it works, tag it:

```powershell
cd G:\Comfy-Cozy
git tag comfy-cozy-feature1-complete
git push --tags
```

---

## Mile 7 of 9 — Bi-Directional Spatial Binding (Feature 2)

**Role:** `[GRAPH × FORGE]`
**Estimated time:** ~4 hours

### Copy-paste prompt for Claude Code:

```
ROLE: [GRAPH × FORGE]

You are operating under the 8 Agent Commandments and the Pentagram constraint lock (for files under panel/).

SPEC: docs/COMFY_COZY_V3_BUILD_SPEC.md, Section 3 Feature 2.

TASK (split: backend then panel):

BACKEND (under comfy_agent/):

1. Update the Claude system prompt (in claude_bridge.py or wherever it lives) to include this instruction:
   "When you reference a specific node by name in your response, wrap the name in <node ref='ID'>Name</node> tags where ID is the node's string ID."

2. Add to comfy_agent/core/engine.py:
   def scoped_context(self, node_ids: List[str], mode: str = "1hop") -> dict:
       '''Returns a pruned topological subgraph of the workflow.
       
       Modes:
       - "1hop": selected nodes + immediate upstream + immediate downstream + edges among them
       - "strict", "upstream", "closure": raise NotImplementedError
       '''
   Implement only the "1hop" mode. The 1-hop subgraph includes:
   - All selected nodes
   - All nodes that feed directly into a selected node (upstream neighbors)
   - All nodes that consume the output of a selected node (downstream neighbors)
   - All edges among the resulting set

PANEL (under panel/web/):

3. Create panel/web/js/spatial_binding.js (~200 LOC):
   
   Chat → Canvas:
   - Parse chat response text for <node ref="(\d+)">(.*?)</node> tokens
   - Replace each token with an interactive DOM <span class="node-pill" data-node-id="X">Name</span>
   - On mouseenter: 
     * Calculate the target node's canvas coordinates via app.graph._nodes_by_id[id]
     * Compute the target offset to center the node in the viewport
     * Animate app.canvas.ds.offset using requestAnimationFrame, 200ms ease-out
     * Inject an 800ms #0066FF pulse animation on the node via CSS class
   - No instant snaps regardless of distance.
   
   Canvas → Chat:
   - Bind to app.canvas.onSelectionChange (or the equivalent LiteGraph event)
   - Maintain a module-scoped selectedNodeIds Set
   - When non-empty: render a "Scoped to N nodes" badge above the chat input
   - When the user submits a chat message and selectedNodeIds is non-empty: 
     * Call backend GET /scoped_context?node_ids=X,Y,Z
     * Attach the resulting subgraph dict to the message payload as `scoped_context`

CONSTRAINTS:
- Pentagram pulse: opacity transitions only, 200ms ease-out
- Camera pan: requestAnimationFrame loop, ease-out cubic, exactly 200ms
- The node-pill DOM span uses #0066FF underline on hover, no other decoration

TEST GATE: Manual test:
1. Restart ComfyUI to pick up panel changes.
2. Type a message that gets a response referencing a node by name
3. Confirm the node name renders as a clickable pill
4. Hover the pill — confirm camera pans smoothly (not snap) and the node pulses
5. Box-select 3 nodes on the canvas — confirm "Scoped to 3 nodes" badge appears
6. Type "what does this cluster do" — confirm the request payload contains scoped_context with only those 3 nodes plus their 1-hop neighbors

When all 6 pass, commit: "Comfy-Cozy v3: Spatial Binding (Mile 7/9)"

STOP after commit.
```

### You should see:

- `comfy_agent/core/engine.py` has new `scoped_context()` method
- `panel/web/js/spatial_binding.js` created
- All 6 manual tests pass
- Git commit landed

### Stop point:

**Human gate (light).** Confirm the camera pan feels right — 200ms is the sweet spot, anything slower feels sluggish, anything faster feels jarring. Proceed to Mile 8.

---

## Mile 8 of 9 — VRAM Guardrails (Feature 3)

**Role:** `[GRAPH × FORGE]`
**Estimated time:** ~3 hours

### Copy-paste prompt for Claude Code:

```
ROLE: [GRAPH × FORGE]

You are operating under the 8 Agent Commandments and the Pentagram constraint lock (for files under panel/).

SPEC: docs/COMFY_COZY_V3_BUILD_SPEC.md, Section 3 Feature 3.

TASK (split: backend then panel):

BACKEND:

1. Create comfy_agent/utils/hardware_profiler.py (~80 LOC):
   - On import, capture torch.cuda.get_device_properties(0)
   - Cache as a module-level HardwareProfile dataclass with: vram_gb, gpu_name, system_ram_gb
   - Expose get_hardware_profile() returning the cached dataclass
   - Expose format_for_system_prompt() returning: '<hardware vram_gb="24" gpu="RTX 4090" />'

2. Create comfy_agent/utils/model_vram_registry.json:
   Hand-curated registry. Start with these entries minimum:
   - flux1-dev.safetensors: { vram_full_gb: 24, vram_gguf_q4_gb: 8, vram_gguf_q8_gb: 12 }
   - flux1-schnell.safetensors: { vram_full_gb: 24, vram_gguf_q4_gb: 8, vram_gguf_q8_gb: 12 }
   - sd_xl_base_1.0.safetensors: { vram_full_gb: 7, vram_gguf_q4_gb: 4, vram_gguf_q8_gb: 5 }
   - sd_xl_refiner_1.0.safetensors: { vram_full_gb: 7, vram_gguf_q4_gb: 4, vram_gguf_q8_gb: 5 }
   - sd3_medium.safetensors: { vram_full_gb: 12, vram_gguf_q4_gb: 5, vram_gguf_q8_gb: 7 }
   Add 5–10 more from common ComfyUI workflows. This file is intentionally hand-maintained.

3. Wrap the existing PILOT model load tools (find them in comfy_agent/intelligence/pilot/):
   - Before executing a load: query the registry for the requested model
   - If model is in the registry AND requested VRAM > available headroom:
     return { "refused": True, "reason": "OOM_RISK", "suggested_alternative": "<the GGUF Q4 variant>", "available_vram_gb": X, "requested_vram_gb": Y }
   - If model is NOT in the registry:
     ALLOW the load to proceed.
     Log a MissingModelEntry event to the experience layer (add a missing_model_entries table to the SQLite schema for this — minimal schema, just (id, created_at, model_name, observed_vram_gb)).

4. Inject the hardware profile into the Claude system prompt at startup (claude_bridge.py).

PANEL:

5. Add to panel/web/js/components.js: a RefusalCard(refusal) function:
   - Renders a Pentagram-styled card with the refusal reason (the accent stays #0066FF — no real red, the design system has one accent only)
   - Shows: "Model X requires Yg VRAM. You have Zg available."
   - Single button: [Apply alternative: <gguf name>]
   - On click: re-trigger the original PILOT call with the suggested_alternative substituted

6. Add a tiny missing-model badge in the panel header:
   - GET /missing_model_entries/count on panel load
   - If count > 0: render a "[N missing]" badge next to the hardware indicator
   - Click opens a list view (just a simple modal listing model names) for weekly review

CONSTRAINTS:
- The registry is intentionally small. Do not auto-populate from the internet.
- The wrapper around PILOT load tools must NOT modify the PILOT tools themselves. Use a wrapper pattern.

TEST GATE:
1. Mock an 8GB hardware profile. Request a flux1-dev.safetensors load. Confirm refusal returned with flux1-dev-Q4_K_M.gguf or similar as the alternative.
2. Request an unknown model (e.g. fake_model_xyz.safetensors). Confirm load proceeds, MissingModelEntry logged.
3. Confirm panel renders the missing-model badge after the unknown load.
4. Confirm RefusalCard renders correctly and the Apply Alternative button re-triggers the load.

When all 4 pass, commit: "Comfy-Cozy v3: VRAM Guardrails (Mile 8/9)"

STOP after commit.
```

### You should see:

- `hardware_profiler.py`, `model_vram_registry.json` created under `comfy_agent/utils/`
- PILOT load wrapper in place
- RefusalCard component working in `panel/web/js/components.js`
- Missing-model badge appears for unknown models
- Git commit landed

### Stop point:

**Human gate (light).** Spot-check the registry entries — these need to be reasonably accurate. You may want to tune the GGUF VRAM numbers based on your actual hardware. Proceed to Mile 9.

---

## Mile 9 of 9 — Crucible pass on Track B

**Role:** `[GRAPH × CRUCIBLE]`
**Estimated time:** ~2 hours

### Copy-paste prompt for Claude Code:

```
ROLE: [GRAPH × CRUCIBLE]

You are operating under the 8 Agent Commandments. Most relevant:
- Commandment 7: ADVERSARIAL VERIFICATION. Your job is to break what was built. Find failures.
- Commandment 5: ROLE ISOLATION. You write tests and report bugs. You do NOT fix the implementation. Surface failures and stop.

SPEC: docs/COMFY_COZY_V3_BUILD_SPEC.md, all four features (Ghost Workflows, Spatial Binding, VRAM Guardrails, Auto-Heal NOT YET — only Features 1, 2, 3 in this mile).

TASK: Hammer the three features built in Miles 5–8. Find their breaking points.

EDGE CASES TO TEST (write a script that exercises each):

Ghost Workflows:
1. Propose 50 proposals at once. Does the renderer slow down? Does the cache invalidate too aggressively?
2. Propose, reject, propose the same delta again — does the same proposal_id return or a new one?
3. Propose, then trigger an agent restart — does the panel correctly clear stale ghosts?
4. Propose with malformed delta (missing fields) — does the backend reject cleanly with a 4xx, or crash?
5. Wait 31 minutes without heartbeat (or use the env var to set TTL=2s) — confirm garbage collection logs ProposalAbandoned.

Spatial Binding:
6. Hover a node-pill referencing a node ID that no longer exists (deleted) — does it crash or fail gracefully?
7. Box-select 0 nodes — does the badge disappear?
8. Box-select 100 nodes and submit a chat — does scoped_context return reasonable size?
9. scoped_context with mode="strict" — does it raise NotImplementedError as specified?

VRAM Guardrails:
10. Request a model whose VRAM is exactly equal to available headroom — does it allow or refuse? (Edge case: should allow with a 0.5GB safety margin.)
11. Request the same unknown model 5 times — confirm 5 MissingModelEntry rows logged, not deduplicated.
12. Apply an alternative that ALSO doesn't fit — does it cascade to another refusal?

For each failure found:
- Document the exact reproduction
- Document the expected behavior
- Document the observed behavior
- DO NOT FIX. Surface to me.

If all 12 edge cases pass, commit: "Comfy-Cozy v3: Crucible pass (Mile 9/9) — all green"

If any fail, commit a separate file `tests/crucible_findings_mile9.md` listing the failures and STOP.
```

### You should see:

- Either: `tests/crucible_findings_mile9.md` listing bugs, OR
- A clean commit confirming all 12 edge cases pass

### Stop point:

**Human gate (critical).** If Crucible found bugs, route them back to the appropriate `[X × FORGE]` role for fixes (one bug at a time, each with its own retry budget per Commandment 3). If clean, tag:

```powershell
cd G:\Comfy-Cozy
git tag comfy-cozy-features123-complete
git push --tags
```

Track B is done. Mile 10 (convergence) is next.

---

# 5. MILE 10 — CONVERGENCE: COMFY-COZY FEATURE 4 (AUTO-HEAL)

**Role:** `[EXPERIENCE × FORGE]` then `[EXPERIENCE × CRUCIBLE]`
**Estimated time:** ~4 hours
**Prerequisites:** Track A complete (Phase 5 Minimum) AND Track B complete (Comfy-Cozy F1/F2/F3)

This is the convergence point. Auto-Heal depends on:

- The cerebellum receiving side (`/failures` endpoint, `FailureExperience` schema, retry guard) — from Track A
- The Ghost Workflows rendering pipeline — from Track B
- The proposal lifecycle endpoints — from Track B

If either track is incomplete, **stop and finish that track first**.

### Copy-paste prompt for Claude Code:

```
ROLE: [EXPERIENCE × FORGE]

You are operating under the 8 Agent Commandments and the Pentagram constraint lock (for files under panel/).

SPEC: docs/COMFY_COZY_V3_BUILD_SPEC.md, Section 3 Feature 4 (Auto-Heal Error Interceptor).

TASK: Wire the closed loop. Failures captured from ComfyUI become FailureExperience records, propose fix DeltaLayers via Claude, render as Ghost Workflows, accept and re-queue.

BACKEND (under comfy_agent/):

1. Implement the three-tier capture strategy in priority order:
   
   PRIMARY: Subscribe to ComfyUI's WebSocket execution_error events from the agent backend.
   - Open a persistent WebSocket connection to ws://localhost:8188/ws on agent startup
   - Listen for messages with type=="execution_error"
   - Extract: prompt_id, exception_message, exception_type, traceback, node_id, node_type, executed
   - Forward to the internal _handle_failure() method
   
   SECONDARY: Poll GET /history every 2 seconds as a fallback if the WebSocket disconnects.
   - Detect failed prompts by status.status_str=="error"
   - Forward to _handle_failure()
   
   TERTIARY: Document a monkey-patch fallback in a comment in panel/__init__.py, but do NOT implement it unless WebSocket and polling both fail in real testing.

2. _handle_failure(failure_data):
   - Construct a FailureExperience record (use the schema from Phase 5 Minimum)
   - Call FailureStore.record_failure() (this returns the upserted record with retry_count and recalcitrant flag)
   - If recalcitrant=True: emit a "recalcitrant_failure" event to the panel via WebSocket. Do NOT propose a fix.
   - If retry_count <= 3: prompt Claude with the trace + workflow_state asking for a fix DeltaLayer. Use the existing PILOT/INTELLIGENCE pipeline.
   - When Claude returns a proposed fix delta, call POST /propose_delta internally. Get back a proposal_id.
   - Emit a "failure_with_fix" event to the panel via WebSocket with: { failure_id, proposal_id, summary }

3. Add a callback hook to commit_proposal: when a proposal that originated from a failure is committed, call mark_resolved on the FailureStore for that failure_id.

PANEL (under panel/web/):

4. Add to panel/web/js/components.js: FailureCard(failure_event) function:
   - Renders a Pentagram-styled card sliding in from the right
   - Shows: "Generation failed: <one-line summary>"
   - Shows: "Proposed fix: <delta summary>"
   - [Accept] button: commits the proposal_id and re-queues the original prompt via ComfyUI API
   - [Dismiss] button: rejects the proposal_id and does NOT re-queue

5. For recalcitrant_failure events: render a different card variant
   - Shows: "This pattern has failed 3 times in a row. Manual intervention needed."
   - Single [OK] button to dismiss
   - No fix proposal offered

6. Wire the panel WebSocket listener to receive failure_with_fix and recalcitrant_failure events and route them to the correct card type.

CONSTRAINTS:
- WebSocket subscription is the primary path. Polling is fallback only.
- Monkey-patching is documented but not implemented. If you find yourself reaching for it, surface to me first.
- LOC budget: ~250 lines backend, ~150 lines panel.

TEST GATE:
1. Force a ComfyUI generation error (deliberately broken workflow). Confirm the WebSocket capture path catches it.
2. Confirm a FailureExperience row is logged in the SQLite DB.
3. Confirm a Ghost Workflow proposal appears on the canvas.
4. Confirm the FailureCard renders in the panel sidebar.
5. Click Accept. Confirm the delta commits, the prompt re-queues, and (if it succeeds this time) the FailureExperience is marked resolved.
6. Force the SAME failure 3 times in a row. Confirm the third attempt produces a recalcitrant card with no fix proposal.
7. Disconnect the WebSocket mid-test. Confirm polling kicks in and still captures failures.

When all 7 pass, commit: "Comfy-Cozy v3: Auto-Heal closed loop (Mile 10/10)"

STOP after commit. This is the moment Comfy-Cozy becomes a learning organ.
```

### You should see:

- WebSocket subscription active
- Failures captured, logged, fixed via Ghost Workflow
- Recalcitrant failures gracefully degrade to manual mode
- All 7 manual tests pass
- Git commit landed

### Stop point:

**Human gate (the celebration one).** This is the moment the cerebellum gets its first heartbeat. Tag it:

```powershell
cd G:\Comfy-Cozy
git tag comfy-cozy-v3-complete
git push --tags
```

Manually trigger a few real failures. Watch the loop close. The first time you accept an Auto-Heal Ghost Workflow and the next generation succeeds is the milestone.

---

# 6. HUMAN GATES SUMMARY

**Total gates in this pack: 8**

| Mile        | Gate Type    | What you're checking                                       |
| ----------- | ------------ | ---------------------------------------------------------- |
| Pre-flight  | Verification | All "Verify, Don't Rebuild" items + symlink confirmed      |
| Mile 1      | Light review | Schemas match spec                                         |
| Mile 3      | Review       | UPSERT logic + retry guard correctness                     |
| Mile 4      | Critical     | Phase 5 Minimum complete, all 11 tests green, no regressions |
| Mile 6      | Critical     | Ghost Workflows render correctly, smooth performance       |
| Mile 7      | Light review | Camera pan feels right                                     |
| Mile 9      | Critical     | Crucible findings reviewed, bugs routed for fix            |
| Mile 10     | Celebration  | Full closed loop tested, real failure → Auto-Heal → success |

**Rule:** Do not skip a critical gate. Light reviews can be combined or fast-tracked if you're in flow. Critical gates exist because the cost of getting it wrong cascades.

---

# 7. ROLLBACK POINTS

Every git tag in this pack is a rollback point. If something goes wrong, `git reset --hard <tag>` returns you to a known good state.

| Tag                                | What's safe                                                      |
| ---------------------------------- | ---------------------------------------------------------------- |
| `pre-phase5-minimum`               | Everything before this pack started                              |
| `phase5-minimum-complete`          | Track A complete, cerebellum receiving side live                 |
| `comfy-cozy-feature1-complete`     | Ghost Workflows working                                          |
| `comfy-cozy-features123-complete`  | All three independent Comfy-Cozy features working                |
| `comfy-cozy-v3-complete`           | Full Auto-Heal closed loop, learning organ live                  |

**Rule:** Tag at every "complete" milestone. Push tags to remote so they survive a local disk failure.

---

# 8. ESCALATION PROTOCOL (COMMANDMENT 3 IN PRACTICE)

When Claude Code hits 3 retries on the same fix without progress, it stops and surfaces a blocker. The blocker report contains:

- **What was attempted** — the three approaches tried
- **What failed** — the exact error or test failure each time
- **What the agent thinks the issue is** — the agent's hypothesis
- **What it would take to resolve** — the agent's recommendation

When you see a blocker report:

1. Read it. Don't just retry.
2. Decide: is this a real bug in the spec, a real bug in the implementation, or a real bug in the agent's understanding?
3. Route accordingly:
   - Spec bug → update the spec doc, hand back to the same role
   - Implementation bug → assign to the appropriate FORGE role with a fix-specific prompt
   - Understanding bug → re-prompt with clearer instructions and the relevant context inline

**Never tell an agent to "just try again."** That violates Commandment 3 — the retry budget exists for a reason.

---

# 9. CAPSULE FORMAT (FOR PROJECT SWITCHING)

If you need to step away mid-pack, generate a capsule before closing the session:

```
+== COMFY-COZY CAPSULE ============================+
| WHERE WE ARE:        Mile X of 10                |
| LAST COMPLETED:      Mile X-1                    |
| LAST COMMIT:         <git hash>                  |
| LAST TAG:            <tag name>                  |
| NEXT ACTION:         Run Mile X prompt           |
| BLOCKERS:            <if any>                    |
| ENERGY REQUIRED:     <type + level>              |
| OPEN BUGS FROM CRUCIBLE: <list or none>          |
+==================================================+
```

Paste this into the next session to resume cleanly.

---

# 10. ONE-LINE FRAME

**You are not building a chat panel for ComfyUI. You are growing a learning organ that happens to live inside ComfyUI.**

Every mile in this pack feeds the cerebellum. The Ghost Workflows are the visible surface of the delta layer engine. The Auto-Heal loop turns failures into permanent training signal. The proposal lifecycle events become a record of your aesthetic preferences over time.

When Mile 10 lands, the loop closes. Comfy-Cozy starts learning.

Build it boring. Build it small. Build it correctly. The marathon is 10 miles long.

— End of install pack —
