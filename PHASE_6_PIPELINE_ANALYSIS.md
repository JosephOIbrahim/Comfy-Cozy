# Phase 6 Pipeline Analysis — `cognitive/pipeline/autonomous.py`

## Document Status

- **Author:** SCOUT agent (Claude Sonnet 4.6)
- **Date:** 2026-04-08
- **Baseline:** 2683 passing tests (locked invariant after Phase 3A)
- **Purpose:** Full read-through of `autonomous.py` (281 LOC) to classify every
  pipeline stage, map data flow, verify Phase 3A integration, and identify the
  shortest path to one complete working cycle.
- **Scope:** Read-only. No source modifications, no pytest, no git operations.

---

## Executive Summary

`autonomous.py` is more complete than the previous scout's PARTIAL/MEDIUM verdict
suggested. All seven active stages (INTENT, COMPOSE, PREDICT, GATE, EXECUTE,
EVALUATE, LEARN) are implemented in `run()`, and the three terminal states
(COMPLETE, FAILED, INTERRUPTED) are reachable from the correct code paths. The
pipeline is **structurally wired and can run a full cycle today in mock mode**
(no ComfyUI required). The weakest links are the EXECUTE and EVALUATE stages,
which both rely entirely on caller-supplied delegate callbacks — the pipeline
itself never calls `cognitive/tools/execute.py:execute_workflow`. Phase 3A's
real `execute_workflow` exists and is architecturally compatible, but the two
are not wired together: no import, no call site. Additionally, the auto-retry
logic in LEARN is explicitly incomplete (logs intent to retry, does not actually
re-run). The headline recommendation: wire `execute_workflow` as the default
executor and add a stub evaluator as the default evaluator — those two changes
promote the pipeline from "mock-capable" to "art-director-ready."

---

## Stage-by-Stage Analysis

### INTENT (Stage 1)

**What it does:** Validates that `config.intent` is non-empty. Logs the intent
string. No NLP, no classification — pure guard clause.

**Classification: WIRED**

**Call sites:**
- Lines 121-126: `config.intent.strip()` empty check → sets `FAILED` and returns.
- `result.log(f"Intent: {config.intent}")` on success.

**Returns / consumed by:** Sets `result.intent` (via `PipelineResult` init) and
passes `config` unchanged to COMPOSE.

**Issues:** No intent parsing or normalization. The intent string flows raw into
`compose_workflow()`. Fine for v0; would break on adversarial input (very long
strings, non-ASCII) in production.

**Changes needed to be WIRED:** None — intent validation is appropriately minimal
for the current scope.

---

### COMPOSE (Stage 2)

**What it does:** Calls `compose_workflow()` from `cognitive/tools/compose.py`
with the raw intent string, an optional `model_family` override, and a list of
experience patterns retrieved from the accumulator. If composition fails, sets
`FAILED`. On success, extracts `workflow_data`, `model_family`, and `params`
from the `CompositionResult`.

**Classification: PARTIAL**

**Call sites:**
- Line 130: `self._get_experience_patterns(config)` — retrieves top-5 patterns
  from accumulator (returns `[]` on cold start).
- Lines 131-135: `compose_workflow(config.intent, model_family=..., experience_patterns=...)`.
  Note: `available_templates` is **not passed** — always `None`.
- Lines 141-144: Extracts `composition.workflow_data`, `composition.plan.model_family`,
  `composition.plan.parameters`.

**Returns / consumed by:** `result.workflow_data` — passed to EXECUTE stage as
the workflow dict. `model_family` and `params` — passed to PREDICT stage.

**Issues:**

1. `available_templates=None` is always passed. `compose.py` skips template
   selection when `available_templates` is falsy, so `result.workflow_data` will
   always be an **empty dict `{}`** on cold start. An empty workflow dict will
   cause Phase 3A's `execute_workflow()` to return `FAILED` with "No nodes found
   in workflow" — the pipeline cannot actually execute anything without templates.

2. `compose.py`'s keyword matching is v0 NLP — family detection works for
   explicit mentions ("flux", "sdxl") but defaults to SD1.5 for everything else.
   Not a blocking issue for MVP; a known limitation.

**Changes needed to be WIRED:**
- Pass `available_templates` from a real source (filesystem templates directory,
  or the existing `templates/` folder). This is the single most important change
  to make COMPOSE produce a non-empty workflow.

---

### PREDICT (Stage 3)

**What it does:** Reads `experience_weight` from the accumulator and
`counterfactual_adjustment` from the CF generator, then calls
`self._cwm.predict()` with model family, parameters, average experience quality,
experience weight, and CF adjustment.

**Classification: WIRED**

**Call sites:**
- Line 148: `self._accumulator.experience_weight` — property on `ExperienceAccumulator`;
  returns `0.0` on cold start (PRIOR phase). Signature verified.
- Line 149: `self._cf_gen.get_adjustment()` — returns `0.0` when fewer than 5
  validated counterfactuals exist. Signature verified at `counterfactual.py:151`.
- Lines 151-157: `self._cwm.predict(model_family, parameters, experience_quality, experience_weight, counterfactual_adjustment)`.
  Signature verified at `cwm.py:87-94`. All arguments match.

**Returns / consumed by:** `result.prediction` (a `Prediction` dataclass).
`prediction.quality_estimate` and `prediction.confidence` pass to GATE.

**Issues:** On cold start (no experience), `experience_quality=None` and
`experience_weight=0.0` — CWM falls back to prior-rules-only prediction.
This is correct by design per the three-phase learning model.

**Changes needed to be WIRED:** None — PREDICT is correctly wired to production
cognitive components.

---

### GATE (Stage 4)

**What it does:** Calls `self._arbiter.decide()` with quality estimate,
confidence, and risk factors. If `decision.should_interrupt` is True, logs a
message, sets `result.error`, and returns `INTERRUPTED`. Otherwise logs the
delivery mode message (if not SILENT) and proceeds to EXECUTE.

**Classification: WIRED**

**Call sites:**
- Lines 166-170: `self._arbiter.decide(prediction.quality_estimate, prediction.confidence, prediction.risk_factors)`.
  Signature verified at `arbiter.py:55-60`. All arguments match.

**Returns / consumed by:** `result.arbiter_decision` (an `ArbiterDecision`
dataclass). `decision.should_interrupt` controls whether the pipeline halts or
continues.

**Issues:** None identified. The interrupt path and the continue path are both
correctly implemented. On cold start, the CWM will produce a moderate
`quality_estimate` (prior-rules baseline ~0.7 for default SD1.5 parameters),
which the arbiter will almost certainly pass as SILENT — the pipeline will
proceed to EXECUTE.

**Changes needed to be WIRED:** None.

---

### EXECUTE (Stage 5)

**What it does:** Checks `config.executor` (a `Callable | None`). If not None,
calls `config.executor(result.workflow_data)` and stores the result. If None,
logs "No executor provided — execution skipped (mock mode)" and continues.

**Classification: PARTIAL**

**Call sites:**
- Lines 184-194: Executor delegate check and call.

**Returns / consumed by:** `result.execution_result` — passed to EVALUATE (for
quality scoring) and to LEARN (for `output_filenames` extraction).

**Issues — THE CRITICAL GAP:**

Phase 3A shipped `cognitive/tools/execute.py:execute_workflow()` as a real,
production-grade implementation (WebSocket-based, POST /prompt, output fetching).
However:

1. `autonomous.py` does **NOT import** `cognitive/tools/execute.py` anywhere.
   There is no `from ..tools.execute import execute_workflow` in the imports.
2. `autonomous.py` does **NOT set a default executor**. When `PipelineConfig`
   is constructed without an `executor=` argument, `config.executor` is `None`
   and execution is silently skipped.
3. The `ExecutionResult` type returned by Phase 3A's `execute_workflow` has an
   `output_filenames` property — LEARN correctly uses `getattr(result.execution_result, "output_filenames", [])`.
   This means the LEARN stage is already written to accept a real `ExecutionResult`.
   The types are compatible; only the wire is missing.

**Changes needed to be WIRED:**
- Import `execute_workflow` from `..tools.execute`.
- Set `config.executor = execute_workflow` as the default when none is provided
  (or wire it inside the constructor as `self._default_executor`).
- The call signature mismatch to check: `config.executor(result.workflow_data)`
  would call `execute_workflow(workflow_data)` — this matches `execute_workflow`'s
  first positional argument. All other arguments (`timeout_seconds`, `on_progress`,
  etc.) have defaults. **No signature mismatch.** The wire is trivially simple.

---

### EVALUATE (Stage 6)

**What it does:** Checks `config.evaluator` (a `Callable | None`). If not None,
calls `config.evaluator(result.execution_result)` and accepts either a
`QualityScore` or a `float`. If None, logs "No evaluator — skipping quality
assessment" and continues with an unscored `QualityScore`.

**Classification: STUBBED**

**Call sites:**
- Lines 198-209: Evaluator delegate check, call, and type-dispatch.

**Returns / consumed by:** `result.quality` (a `QualityScore`). LEARN uses
`result.quality.is_scored` to decide whether to record prediction accuracy and
trigger auto-retry logic.

**Issues:**

1. No default evaluator is provided. Without an evaluator, `result.quality`
   remains at its zero-initialized state (`overall=0.0`, `is_scored=False`).
2. When unscored, LEARN skips `cwm.record_accuracy()` — the CWM never calibrates.
3. When unscored, auto-retry never triggers (the `is_scored` guard blocks it).
4. The pipeline effectively degrades to a fire-and-forget system with no
   feedback loop when `config.evaluator` is None.

For MVP, a rule-based evaluator (returns 0.7 if `execution_result.success` else
0.2) would be sufficient to close the feedback loop. Vision scoring
(`analyze_image` tool) is the production target but not required for MVP.

**Changes needed to move from STUBBED to PARTIAL:**
- Provide a default evaluator that returns a score based on `ExecutionResult.success`.

---

### LEARN (Stage 7)

**What it does:** Constructs an `ExperienceChunk` from the session data
(model_family, prompt, parameters, quality score, output filenames). Records it
to the accumulator. If quality is scored and a prediction exists, calls
`cwm.record_accuracy()`. Generates a counterfactual via `cf_gen.generate()`.
Checks auto-retry conditions and logs intent to retry (but does NOT re-run).
Sets stage to COMPLETE.

**Classification: PARTIAL**

**Call sites:**
- Lines 213-227: `ExperienceChunk` construction and `self._accumulator.record(chunk)`.
- Lines 230-234: `self._cwm.record_accuracy(predicted, actual)` — conditional on
  `result.quality.is_scored`. Method exists on `CognitiveWorldModel` (verified in
  cwm.py read).
- Lines 237-239: `self._cf_gen.generate(params, prediction.quality_estimate)`.
  Signature verified at `counterfactual.py:78-82`. Arguments match.
- Lines 242-251: Auto-retry block — logs intent but comment explicitly says
  "In a real implementation, we'd adjust params and re-run. For now, just log."

**Returns / consumed by:** `result.experience_chunk` stored. LEARN always
advances to COMPLETE unless a preceding stage returned early.

**Issues:**

1. Auto-retry is explicitly stubbed. The comment on line 250 says "just log
   the intent to retry." No actual retry occurs — `result.retries` increments
   but `run()` is not called again with adjusted parameters.
2. `ExperienceChunk` is constructed with `parameters={"composed": params}` —
   a single nested key wrapping the composed params dict, not a flat
   `{node_id: {param: value}}` structure that `GenerationContextSignature.from_workflow()`
   expects. Retrieval similarity scoring may not function as intended because
   the chunk proxy won't have the expected node structure. This is a latent
   data-shape mismatch, not a runtime crash.
3. `output_filenames=[]` is the default; populated from `getattr(result.execution_result, "output_filenames", [])` only when execution_result is not None. Correct.

**Changes needed to be WIRED:**
- Implement real retry: save adjusted `PipelineConfig` with CF-suggested
  parameter changes and recursively call `self.run()` (with a depth guard).
- Fix the `parameters` dict shape in `ExperienceChunk` construction to match
  the flat `{node_id: {param: value}}` format expected by signature matching.

---

### COMPLETE / FAILED / INTERRUPTED (Terminal States)

**Classification: WIRED**

All three terminal states are reachable via correct code paths:
- `COMPLETE`: Set on line 253 after LEARN exits normally.
- `FAILED`: Set on lines 124, 138, 191 (empty intent, compose failure, executor exception).
- `INTERRUPTED`: Set on line 177 (arbiter halts) and on line 301 in execute.py
  (timeout — though autonomous.py does not surface this directly since execution
  is delegated).

`PipelineResult.success` is correctly defined as `stage == COMPLETE and not error`.

---

## Data Flow Map

```
User provides: PipelineConfig(intent="moody neon portrait", model_family=None)

  INTENT (lines 120-126)
    → validates intent string is non-empty
    → result.intent = "moody neon portrait"

  COMPOSE (lines 129-144)
    → _get_experience_patterns() → accumulator.retrieve() → [] on cold start
    → compose_workflow("moody neon portrait", available_templates=None,
                       experience_patterns=[], model_family=None)
         keyword-matches: no "flux"/"xl"/"sd3" → plan.model_family = "SD1.5"
         keyword-matches: no style hints → cfg=7.0, steps=20
         template selection: SKIPPED (available_templates is None)
    → result.workflow_data = {}   ← EMPTY on cold start (no templates)
    → model_family = "SD1.5"
    → params = {"cfg": 7.0, "steps": 20}

  PREDICT (lines 147-162)
    → accumulator.experience_weight → 0.0 (PRIOR phase, 0 chunks)
    → cf_gen.get_adjustment() → 0.0 (< 5 validated CFs)
    → cwm.predict("SD1.5", {"cfg":7.0,"steps":20}, experience_quality=None,
                  experience_weight=0.0, counterfactual_adjustment=0.0)
         prior rules for SD1.5 + cfg=7.0 → score ~0.7, risks=[]
    → result.prediction = Prediction(quality_estimate≈0.7, confidence≈0.4, ...)

  GATE (lines 164-180)
    → arbiter.decide(0.7, 0.4, [])
         urgency = 0.4 * (1.0 - 0.7 + 0.0) = 0.12  → SILENT mode
         should_interrupt = False
    → result.arbiter_decision = ArbiterDecision(SILENT, ...)
    → pipeline continues

  EXECUTE (lines 183-194)
    → config.executor is None (no default set)
    → logs "execution skipped (mock mode)"
    → result.execution_result = None

  EVALUATE (lines 197-209)
    → config.evaluator is None (no default set)
    → logs "No evaluator — skipping quality assessment"
    → result.quality = QualityScore(overall=0.0, is_scored=False)

  LEARN (lines 212-253)
    → ExperienceChunk(model_family="SD1.5", prompt="moody neon portrait",
                      parameters={"composed": {"cfg":7.0,"steps":20}},
                      quality=QualityScore(0.0), output_filenames=[])
    → accumulator.record(chunk)  → generation_count = 1
    → quality.is_scored=False → cwm.record_accuracy SKIPPED
    → cf_gen.generate({"cfg":7.0,"steps":20}, 0.7) → Counterfactual or None
    → auto-retry: quality.is_scored=False → SKIPPED
    → result.stage = COMPLETE

PipelineResult(stage=COMPLETE, intent="moody neon portrait",
               workflow_data={}, execution_result=None,
               quality=QualityScore(0.0, is_scored=False),
               experience_chunk=<recorded>, success=True)
```

**Data dropped:** The empty `workflow_data` is recorded as the chunk's
`parameters` but is not flagged as an error — the pipeline successfully
"completes" with no actual image generated.

**Data faked:** None. Unlike the old execute.py stub which returned PENDING with
a fake prompt_id, autonomous.py correctly skips rather than fakes when
components are absent.

---

## The Shortest Path to One Working Cycle

A "working cycle" means: user submits intent → pipeline executes against real
ComfyUI → a real image is generated → quality is scored → experience is recorded
with useful data.

### Prerequisite: ComfyUI must be running

Phase 3A's `execute_workflow` requires a live ComfyUI at the configured host/port.
This is an external prerequisite, not a code change.

### Required code changes (in priority order):

**Change 1 — Wire the executor (EXECUTE stage)**
File: `cognitive/pipeline/autonomous.py`
- Add import: `from ..tools.execute import execute_workflow`
- In `run()` EXECUTE stage, replace the `if config.executor is not None` block
  with a two-branch version that uses `execute_workflow` as the default when
  `config.executor is None`.
- Effort: ~5 lines.

**Change 2 — Load a template so workflow_data is non-empty (COMPOSE stage)**
File: `cognitive/pipeline/autonomous.py` or caller code.
- Load a starter workflow template (e.g., from `templates/` directory) and pass
  it as `available_templates` to `compose_workflow()`, OR set a default template
  directly when `compose_workflow` returns an empty `workflow_data`.
- Without this, `execute_workflow` will reject the empty dict with "No nodes found".
- Effort: ~10 lines (load JSON from `templates/` dir, pass to compose).

**Change 3 — Provide a default evaluator (EVALUATE stage)**
File: `cognitive/pipeline/autonomous.py`
- Add a simple default evaluator: if `execution_result` is not None and
  `execution_result.success` is True, return `QualityScore(overall=0.7)`, else
  return `QualityScore(overall=0.1)`.
- Without this, the feedback loop (CWM calibration, auto-retry) is permanently
  disabled.
- Effort: ~8 lines (define `_default_evaluator` method, assign in EXECUTE).

**Change 4 — Fix ExperienceChunk parameter shape (LEARN stage)**
File: `cognitive/pipeline/autonomous.py`, line 216.
- Change `parameters={"composed": params}` to `parameters=params` or to the
  flat `{node_id: {param: value}}` format expected by
  `GenerationContextSignature.from_workflow()`.
- This is not a runtime crash — just a data-shape mismatch that makes retrieved
  experience patterns useless for signature matching.
- Effort: 1 line.

**Not required for one working cycle:**
- The auto-retry real implementation (LEARN stage stub). Skip for MVP.
- Vision evaluator (`analyze_image`). Rule-based evaluator (Change 3) is sufficient.
- Experience accumulator pre-population. Cold-start works.
- `research.py` ratchet body. Not called by the pipeline.
- `dependencies.py` implementation. Not called by the pipeline.
- CWM prior rules registration. CWM defaults to `~0.7` without registered rules.

---

## The Art Director MVP Path

**Goal:** User types an intent, the pipeline generates a real image with no
further intervention.

### Session N+1 (next session — "Wire the Pipe")
Implement Changes 1-4 above in `autonomous.py`. Add a thin CLI or MCP tool
entrypoint that:
1. Constructs a `PipelineConfig(intent=<user_input>)` with a real template.
2. Calls `AutonomousPipeline().run(config)`.
3. Returns `result.execution_result.output_filenames` to the user.

This gives: intent → real ComfyUI execution → filenames returned. Quality scoring
is rule-based (success/fail). Experience accumulates but retrieval is
low-fidelity until parameter shapes are fixed.

### Session N+2 (one session later — "Close the Loop")
- Replace rule-based evaluator with vision-based scoring using `analyze_image`
  from the existing tool suite.
- Implement real auto-retry: when quality below threshold, apply CF-suggested
  parameter change and re-run (with max_retries depth guard).
- Fix ExperienceChunk parameter shape so retrieval actually improves over time.

After Session N+2: the pipeline meets the stated product goal — intent → execute
→ evaluate → iterate → surface finished image with minimal human intervention.

### Session N+3 (optional polish)
- Surface arbiter warnings to the user (currently SILENT for most cold-start
  predictions).
- Add persistence: `accumulator.save()` between pipeline runs so experience
  carries across sessions.
- Upgrade COMPOSE to use `agent/stage/cwm.py` when USD is available
  (per Phase 5 open question §8).

---

## Integration Check — Phase 3A execute.py

**Summary: Compatible but unwired.**

Phase 3A's `cognitive/tools/execute.py` defines:

```python
def execute_workflow(
    workflow_data: dict[str, Any],
    timeout_seconds: int = 300,
    on_progress: Callable | None = None,
    on_complete: Callable | None = None,
    base_url: str | None = None,
) -> ExecutionResult:
```

`autonomous.py`'s EXECUTE stage calls:

```python
exec_result = config.executor(result.workflow_data)
```

If `execute_workflow` were wired as the default executor, the call would be:

```python
execute_workflow(result.workflow_data)
```

**Signature check:** `workflow_data` is the first positional parameter of
`execute_workflow`. All other parameters have defaults. **No signature mismatch.**
The wire is clean.

**Type check:** `execute_workflow` returns `ExecutionResult` with an
`output_filenames` property (`list[str]`). LEARN stage accesses:

```python
chunk.output_filenames = getattr(result.execution_result, "output_filenames", [])
```

`ExecutionResult.output_filenames` is a `@property` on the dataclass
(line 62 of execute.py). `getattr` works on properties. **No type mismatch.**

**Import check:** `autonomous.py` does NOT currently import from
`cognitive/tools/execute.py`. The import `from ..tools.analyze import analyze_workflow`
is present but `analyze_workflow` is never called — it's a dead import. The
needed import (`from ..tools.execute import execute_workflow`) is missing entirely.

**Verdict:** Phase 3A is architecturally correct and compatible with the pipeline.
The integration is one import and ~5 lines of code away.

---

## Open Questions for Joe

Continuing from §11 of `PHASE_STATUS_REPORT.md`.

### §12 — What is the default executor path? (HIGH — blocks real execution)

`autonomous.py` needs a default executor. Three options:
1. Wire `cognitive/tools/execute.py:execute_workflow` directly as the default
   (simplest — everything lives in cognitive/).
2. Accept `None` but fail loudly with a clear error (forces caller to always
   provide an executor — more explicit).
3. Auto-detect `COMFYUI_HOST` env var and default to execute only when ComfyUI
   appears reachable.

**Recommended default:** Option 1. Wire execute_workflow as default. It already
handles the "ComfyUI not reachable" case gracefully (returns FAILED with a
human-readable message).

### §13 — What is the default evaluator? (HIGH — blocks feedback loop)

Without an evaluator, the CWM never calibrates and auto-retry never triggers.
Options:
1. Rule-based default: `QualityScore(overall=0.7)` if execution succeeded,
   `QualityScore(overall=0.1)` if failed. Zero code dependencies.
2. Hash-based: use `hash_compare_images` if a reference image is provided,
   stub otherwise.
3. Vision-based: call `analyze_image` for every output. Requires ComfyUI output
   to be accessible on disk.
4. Human callback only: ship with no default, require the caller to wire it.

**Recommended default:** Option 1 for MVP. Option 3 for Session N+2.

### §14 — Does the COMPOSE stage need real template loading? (HIGH — blocks real execution)

Currently `available_templates=None` is always passed to `compose_workflow()`,
producing an empty `workflow_data` dict. `execute_workflow` rejects empty
workflows with "No nodes found." For the pipeline to generate anything:
- Should `autonomous.py` load templates from `G:/Comfy-Cozy/templates/` by default?
- Or should template loading be the caller's responsibility (passed in via config)?
- Or should `compose_workflow` have a hardcoded minimal fallback workflow for each
  model family?

**Recommended default:** Add `template_dir: str | None = None` to `PipelineConfig`.
When set, `autonomous.py` loads templates from disk. When None, `compose_workflow`
uses a hardcoded minimal 3-node workflow (KSampler + CheckpointLoader + EmptyLatentImage)
as the fallback.

### §15 — Should auto-retry actually re-run the pipeline? (MEDIUM)

The auto-retry block (lines 242-251) explicitly says "In a real implementation,
we'd adjust params and re-run." The comment is honest — it doesn't retry. Options:
1. Implement recursive `self.run()` with a depth guard (clean, but adds recursion).
2. Move `run()` into a `while retries < max_retries` loop (avoids recursion).
3. Leave auto-retry as a log-only stub for MVP; add it in Session N+2.

**Recommended default:** Option 3 for MVP. Auto-retry adds complexity that
obscures the basic "does one cycle work" question. Add it in Session N+2 once
the basic cycle is validated.

### §16 — Should `experience_weight` influence COMPOSE, not just PREDICT? (LOW)

Currently, experience patterns are retrieved and passed to `compose_workflow()`
(which applies them when confidence > 0.7), but `experience_weight` from the
accumulator is not used to gate this application. On cold start, `experience_weight
= 0.0` but the compose function will still apply high-confidence patterns if any
exist. This is a minor inconsistency — experience patterns and experience weight
are from the same accumulator but gated differently.

**Recommended default:** Leave as-is for MVP. The discrepancy only matters once
the accumulator has >30 chunks (Phase 2 of learning), which won't happen in the
first few sessions.

### §17 — Should `analyze_workflow` be called somewhere in the pipeline? (LOW)

`autonomous.py` imports `analyze_workflow` from `cognitive/tools/analyze.py` but
never calls it. The import is dead code. Options:
1. Call it after COMPOSE to validate that `workflow_data` has the expected
   structure before passing it to EXECUTE.
2. Remove the import (dead import cleanup).
3. Leave it — it documents intent without runtime cost.

**Recommended default:** Option 1 — add a COMPOSE post-check that calls
`analyze_workflow(result.workflow_data)` and warns (but does not halt) if the
workflow has zero nodes. This would have caught the empty-workflow issue sooner
in the data flow.

---

## Confidence Assessment

| Stage | Confidence | Reasoning |
|---|---|---|
| INTENT | HIGH | 6 lines, fully read, no external calls. |
| COMPOSE | HIGH | Fully read + compose.py fully read. Empty-template issue confirmed by tracing. |
| PREDICT | HIGH | All call signatures verified against cwm.py, accumulator.py, counterfactual.py. |
| GATE | HIGH | Arbiter.decide() signature verified. Logic is clear. |
| EXECUTE | HIGH | Fully read. Gap confirmed: no import of execute.py, no default executor. |
| EVALUATE | HIGH | Fully read. Stub confirmed: no default evaluator. |
| LEARN | HIGH | Fully read. Auto-retry stub confirmed by code comment. Param shape mismatch identified. |
| COMPLETE/FAILED/INTERRUPTED | HIGH | All three reachable via verified code paths. |
| **Phase 3A integration** | HIGH | Signature and type match confirmed. Missing import confirmed. |

**Overall pipeline confidence: HIGH.** The previous scout's MEDIUM was due to
the run() body being unread. With all 282 lines read and all major dependencies
traced, every stage classification is HIGH confidence.

---

## Out of Scope (Explicit)

- Running any tests
- Modifying any source files
- Git operations of any kind
- Implementing any of the MVP path changes described above
- Re-reading Phase 2-5 internals beyond what was needed to verify specific call sites
  at autonomous.py's call sites (accumulator.py lines 60-157, cwm.py lines 60-159,
  arbiter.py lines 1-60, counterfactual.py lines 55-170 — all read only to verify
  method signatures)
