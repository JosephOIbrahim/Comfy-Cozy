# Phase 6A — Wire the Pipe: Design Document

**Author:** Architect agent (Claude Sonnet 4.6)
**Date:** 2026-04-08
**Baseline:** 2683 passing tests (locked invariant after Phase 3A)
**Status:** READ-ONLY design. No source files modified.
**Builds on:** `PHASE_6_PIPELINE_ANALYSIS.md` (scout, 2026-04-08)

---

## 1. Goal and Constraints

This document is the blueprint for a forge agent that will implement six
targeted changes to `cognitive/pipeline/autonomous.py` and add a bootstrap
function to `cognitive/pipeline/__init__.py`. These changes wire the four
missing connections in the end-to-end autonomous pipeline cycle, add a
post-COMPOSE diagnostic call, and provide a factory function for constructing
a fully-equipped pipeline with sensible defaults.

Joe's decision: **Option A — long-lived cognitive component singletons, MCP
server owns lifetime.** The pipeline receives components injected at
construction time. The bootstrap function (Change 6) constructs those
components once; the MCP server will call it at startup in a future session.
The bootstrap function is NOT wired into the MCP server this session.

This pass delivers design only. Six changes are in scope:

1. **Default Executor Wire** — EXECUTE stage calls `execute_workflow` when
   `config.executor` is None, instead of silently skipping.
2. **Template Loading** — COMPOSE stage passes a non-empty `available_templates`
   list so `workflow_data` is non-empty on cold start.
3. **Default Evaluator** — EVALUATE stage applies a rule-based `QualityScore`
   when `config.evaluator` is None.
4. **ExperienceChunk Parameter Shape Fix** — LEARN stage builds
   `parameters=params` (flat) instead of `parameters={"composed": params}`
   (nested).
5. **§17 Diagnostic (analyze_workflow post-COMPOSE)** — Call `analyze_workflow`
   after COMPOSE success; log a warning if the workflow has zero nodes.
6. **Bootstrap Function** — `create_default_pipeline()` factory in
   `cognitive/pipeline/__init__.py`.

---

## 2. Current State (Evidence)

### autonomous.py (282 lines, fully read)

All seven active stages are present. The pipeline can run a full cycle today in
mock mode (no ComfyUI required). The four gaps are exactly as the scout
described.

**Scout claim verification — each claim checked against actual file content:**

**CLAIM: `parameters={"composed": params}` at line 216 — CORRECT.**
Line 216 reads:
```python
parameters={"composed": params},
```
`params` is `composition.plan.parameters` (a flat `{"cfg": float, "steps": int}`
dict). The outer `{"composed": ...}` wrap is the mismatch.

**CLAIM: EXECUTE stage checks `config.executor`, skips when None (lines 184-194) — CORRECT.**
Lines 183-194:
```python
result.stage = PipelineStage.EXECUTE
if config.executor is not None:
    try:
        exec_result = config.executor(result.workflow_data)
        result.execution_result = exec_result
        result.log("Execution complete")
    except Exception as e:
        result.error = f"Execution failed: {e}"
        result.stage = PipelineStage.FAILED
        return result
else:
    result.log("No executor provided — execution skipped (mock mode)")
```
No import of `execute_workflow` exists anywhere in the file.

**CLAIM: Lines 131-135 — COMPOSE passes `available_templates=None` — CORRECT.**
Lines 131-135:
```python
composition = compose_workflow(
    config.intent,
    model_family=config.model_family,
    experience_patterns=experience_patterns,
)
```
`available_templates` is omitted entirely, which means it receives its default
value of `None` inside `compose_workflow`.

**CLAIM: EVALUATE stage checks `config.evaluator`, skips when None (lines 198-209) — CORRECT.**
Lines 197-209:
```python
result.stage = PipelineStage.EVALUATE
if config.evaluator is not None:
    try:
        quality = config.evaluator(result.execution_result)
        if isinstance(quality, QualityScore):
            result.quality = quality
        elif isinstance(quality, (int, float)):
            result.quality = QualityScore(overall=float(quality))
        result.log(f"Quality: {result.quality.overall:.1%}")
    except Exception as e:
        result.log(f"Evaluation failed: {e}")
else:
    result.log("No evaluator — skipping quality assessment")
```

**CLAIM: `analyze_workflow` is imported but never called — CORRECT.**
Line 29: `from ..tools.analyze import analyze_workflow`
`analyze_workflow` appears nowhere else in the 282-line file.

All five scout claims are verified correct. No design adjustments needed.

### execute.py (408 lines, fully read)

`execute_workflow(workflow_data, timeout_seconds=300, on_progress=None, on_complete=None, base_url=None) -> ExecutionResult`

First parameter is `workflow_data: dict[str, Any]`. All others have defaults.
Calling `execute_workflow(result.workflow_data)` is a valid call — no signature
mismatch. `ExecutionResult.output_filenames` is a `@property` (line 62) that
returns `list[str]`. The LEARN stage's `getattr(result.execution_result, "output_filenames", [])` works on properties. No type mismatch. The wire is clean.

### compose.py (119 lines, fully read)

`compose_workflow(intent, available_templates=None, experience_patterns=None, model_family=None) -> CompositionResult`

`available_templates` is consumed at lines 111-116:
```python
if available_templates:
    for tmpl in available_templates:
        if tmpl.get("family", "").lower() == plan.model_family.lower():
            plan.base_template = tmpl.get("name", "")
            result.workflow_data = tmpl.get("data", {})
            break
```
Expected shape per consumer: `list[dict]` where each dict has keys `"family"`
(str) and `"data"` (dict — the full workflow JSON). The `"name"` key is also
read for `plan.base_template`. When `available_templates` is `None` or an empty
list, `result.workflow_data` remains `{}` (its `field(default_factory=dict)`
default). An empty workflow dict causes `execute_workflow` to return FAILED
with "No nodes found in workflow" — confirmed at execute.py lines 376-382.

### chunk.py (167 lines, fully read)

`ExperienceChunk.parameters: dict[str, Any]` has the inline comment on line 62:
```python
# parameters: {node_id: {param: value}} — flat representation of the workflow state
```
The docstring says flat `{node_id: {param: value}}`. The current code writes
`{"composed": params}` — a single nested key, not a node-id-keyed flat dict.
This is a data-shape mismatch, not a runtime crash.

However, `ExperienceChunk.matches_context()` (lines 95-123) also uses
`self.parameters` — it iterates `set(self.parameters.keys())` for key overlap.
With the `{"composed": ...}` shape, the only key is `"composed"`, which will
never match another chunk's `"composed"` key unless both have the same inner
dict (unlikely). The mismatch silently degrades retrieval quality.

### signature.py (143 lines, fully read)

`GenerationContextSignature.from_workflow(workflow_data: dict[str, Any])` expects
the **actual ComfyUI API format** — the full `{node_id: {class_type, inputs}}`
dict, NOT `ExperienceChunk.parameters`. It walks `workflow_data.items()` looking
for nodes with `"class_type"` keys. `from_workflow` is called in the pipeline's
`_get_experience_patterns` method only to build a query signature (line 264):
```python
sig = GenerationContextSignature()
if config.model_family:
    sig.model_family = config.model_family
```
It does NOT call `from_workflow` on the chunk's `parameters` field.
`accumulator.retrieve(sig, ...)` uses `GenerationContextSignature.similarity()`
between two signatures — neither of which is built from `ExperienceChunk.parameters`.

**Key finding:** `ExperienceChunk.parameters` is NOT consumed by
`GenerationContextSignature.from_workflow()`. The field comment's description of
the shape (`{node_id: {param: value}}`) describes the intended shape for
external consumers and `matches_context()`, but `from_workflow` does not depend
on it. The simplest fix is `parameters=params` (flat `{"cfg": 7.0, "steps": 20}`),
which is at least consistent with what `matches_context()` will iterate.

### cwm.py (first 100 lines read, __init__ confirmed)

`CognitiveWorldModel.__init__(self)` — no parameters.

### arbiter.py (first 60 lines read, __init__ confirmed)

`SimulationArbiter.__init__(self, explicit_threshold=0.7, soft_threshold=0.4, interrupt_quality_floor=0.2)` — three optional float parameters.

### counterfactual.py (first 70 lines read, __init__ confirmed)

`CounterfactualGenerator.__init__(self)` — no parameters.
Location: `cognitive/prediction/counterfactual.py` (not `cognitive/generation/`).

### accumulator.py (first 55 lines read, __init__ confirmed)

`ExperienceAccumulator.__init__(self, max_chunks=10000)` — one optional int parameter.

### Templates investigation

- `G:\Comfy-Cozy\templates\` — does NOT exist.
- `G:\Comfy-Cozy\agent\templates\` — EXISTS with four files:
  `img2img.json`, `txt2img_lora.json`, `txt2img_sd15.json`, `txt2img_sdxl.json`

`txt2img_sd15.json` is confirmed ComfyUI API format with 7 nodes:
`CheckpointLoaderSimple` (ckpt_name: `"v1-5-pruned-emaonly.safetensors"`),
`CLIPTextEncode` (positive + negative), `EmptyLatentImage` (512x512),
`KSampler`, `VAEDecode`, `SaveImage`.

`agent/tools/workflow_templates.py` is a pure agent-layer module — it imports
from `agent.config` and should NOT be imported from `cognitive/`. This is a
reference only, not a dependency.

**Template decision implication:** The `cognitive/` layer must not import from
`agent/templates/` at module load time (Option A compliance). The fallback
strategy must be either: copy a template dict inline, or load `agent/templates/`
files via a path computed at call time with no agent imports.

### test_cognitive_pipeline.py (268 lines, fully read)

**Current test count:** 23 tests across 7 classes:
- `TestPipeline` (7 tests)
- `TestDelegates` (4 tests)
- `TestArbiterInterrupt` (1 test)
- `TestLearning` (3 tests)
- `TestRetry` (3 tests)
- `TestFullPipeline` (5 tests)

Key behavior for EXECUTE change:
- `TestDelegates::test_with_executor` — passes mock executor via `config.executor`.
  Will keep passing because the new code preserves the `config.executor is not None`
  branch.
- `TestDelegates::test_executor_failure` — passes a raising executor via
  `config.executor`. Same: preserved path.
- `TestFullPipeline::test_zero_intervention_mock_mode` — runs with `intent=...`
  and NO executor/evaluator. Currently asserts `result.success is True`. After
  Change 1, it will attempt real `execute_workflow` — which will fail (ComfyUI
  not running in test) and set `stage=FAILED`. **This test will BREAK.**
- `TestFullPipeline::test_pipeline_improves_with_experience` — 35 runs with
  evaluator only, no executor. Same breakage risk.

Key behavior for EVALUATE change:
- `TestRetry::test_retry_logged_below_threshold` — passes an evaluator that
  returns `QualityScore(overall=0.3)`. Will still pass.
- `TestRetry::test_no_retry_above_threshold` — same: evaluator provided.
- `TestRetry::test_no_retry_when_disabled` — same: evaluator provided.
- No test currently asserts the "No evaluator — skipping quality assessment" log
  message directly.

### analyze.py (first 50 lines read)

`analyze_workflow(workflow_data, schema_cache=None) -> WorkflowAnalysis`
`WorkflowAnalysis.node_count: int` — set by counting nodes with `class_type`.
When `workflow_data = {}`, `node_count = 0`. Safe to call with empty dict.

### PHASE_6_PIPELINE_ANALYSIS.md (fully read)

Scout identifies the same four gaps with HIGH confidence. All findings
corroborated by direct file reads above. Open questions §12-§17 in the scout
are the foundation for this document's design decisions.

---

## 3. Change 1 — Default Executor Wire

### 3.1 Problem

(Scout finding, §EXECUTE): `autonomous.py` does not import
`cognitive/tools/execute.py` anywhere. When `PipelineConfig` is constructed
without an `executor=` argument, `config.executor` is `None` and EXECUTE
silently skips, logging "No executor provided — execution skipped (mock mode)."
Phase 3A's production-grade `execute_workflow` exists but is unconnected.
The pipeline cannot generate a real image without an executor.

Lines 184-194 of autonomous.py confirm the mock-mode skip.

### 3.2 Proposed Implementation

**Top-of-file import addition** (after line 29, the existing analyze import):

Before:
```python
from ..tools.analyze import analyze_workflow
```

After:
```python
from ..tools.analyze import analyze_workflow
from ..tools.execute import execute_workflow as _execute_workflow_default
```

The `_execute_workflow_default` alias signals it is the internal default, not
a re-exported public name. This avoids collision with any caller-visible
`execute_workflow` in the module namespace.

**EXECUTE stage replacement** (lines 183-194):

Before:
```python
        # Stage 5: EXECUTE
        result.stage = PipelineStage.EXECUTE
        if config.executor is not None:
            try:
                exec_result = config.executor(result.workflow_data)
                result.execution_result = exec_result
                result.log("Execution complete")
            except Exception as e:
                result.error = f"Execution failed: {e}"
                result.stage = PipelineStage.FAILED
                return result
        else:
            result.log("No executor provided — execution skipped (mock mode)")
```

After:
```python
        # Stage 5: EXECUTE
        result.stage = PipelineStage.EXECUTE
        _executor = config.executor if config.executor is not None else _execute_workflow_default
        try:
            exec_result = _executor(result.workflow_data)
            result.execution_result = exec_result
            result.log("Execution complete")
        except Exception as e:
            result.error = f"Execution failed: {e}"
            result.stage = PipelineStage.FAILED
            return result
```

**Rationale:** The two-branch if/else collapses to a single ternary assignment.
The try/except block is shared — both real and custom executors get the same
error handling. `config.executor` override path is preserved exactly; tests
that pass a mock executor continue to work.

### 3.3 Test Impact

| Test | Class | Impact | Reason |
|---|---|---|---|
| `test_with_executor` | TestDelegates | PASS UNCHANGED | `config.executor` is set; ternary picks it. |
| `test_executor_failure` | TestDelegates | PASS UNCHANGED | `config.executor` is the raising function; same error path. |
| `test_zero_intervention_mock_mode` | TestFullPipeline | **REWRITE** | No executor → now calls `_execute_workflow_default(result.workflow_data)`. In test environment, ComfyUI is not running. `execute_workflow({})` will fast-fail with "No nodes found" (empty workflow from Change 2 must be fixed first). After Change 2 also applies, it will fail with "ComfyUI not reachable." Either way, `result.stage = FAILED`, breaking the `assert result.success is True`. Must be rewritten to pass a mock executor in test context, OR add an integration test skip marker. |
| `test_pipeline_improves_with_experience` | TestFullPipeline | **REWRITE** | 35 runs without executor → 35 calls to `_execute_workflow_default`. Same failure mode. Must mock the executor or mark as integration test. |
| `test_full_pipeline_with_delegates` | TestFullPipeline | PASS UNCHANGED | Passes `executor=lambda wf: ...` explicitly. |
| All `TestRetry` tests | TestRetry | PASS UNCHANGED | All pass explicit `evaluator=`; no executor → will call default, but workflow is empty (fails early in execute_workflow). However, the tests only assert on `result.retries` and `result.stage_log`, and if EXECUTE fails, `result.stage = FAILED` — breaking some of these. **REWRITE needed** for any test that expects `COMPLETE` without passing an executor. |

Detailed re-check of `TestRetry`:
- `test_retry_logged_below_threshold`: No executor. After Change 1, EXECUTE fails
  (empty workflow). Stage goes to FAILED before EVALUATE. Retry logic never runs.
  **REWRITE** — must provide mock executor.
- `test_no_retry_above_threshold`: Same — **REWRITE**.
- `test_no_retry_when_disabled`: Same — **REWRITE**.

Note: all `TestRetry` rewrites need only add `executor=lambda wf: type("R", (), {"output_filenames": [], "success": True})()` to each `PipelineConfig`. One-liner fix each.

---

## 4. Change 2 — Template Loading

### 4.1 Problem

(Scout finding, §COMPOSE): `compose_workflow` is called without `available_templates`,
which defaults to `None`. When `available_templates` is `None`, `compose.py`
skips the template-selection block (lines 111-116) and `result.workflow_data`
stays `{}`. An empty workflow dict causes `execute_workflow` to return `FAILED`
with "No nodes found in workflow" (execute.py lines 376-382). The pipeline
cannot generate a real image without a non-empty workflow.

Lines 131-135 of autonomous.py confirm the missing `available_templates` argument.

### 4.2 Template Decision

**Decision: Option (c) — Load from `agent/templates/` at runtime by path, fall
back to hardcoded inline dict if the path does not exist.**

Reasoning:
- `G:\Comfy-Cozy\templates\` does NOT exist. There is no `templates/` at repo root.
- `G:\Comfy-Cozy\agent\templates\` EXISTS with four properly formatted files.
- `agent/tools/workflow_templates.py` imports from `agent.config` — it cannot be
  imported from `cognitive/` without breaking Option A isolation.
- Accessing files by path (`Path(__file__).parent.parent.parent / "agent" / "templates"`)
  does NOT import from `agent/` — it is a filesystem read. Option A prohibits
  `from agent import ...`, not `open("agent/templates/foo.json")`.
- The hardcoded fallback ensures the pipeline is self-sufficient even if the
  templates directory is missing or relocated.

**Template-loading shape** (what `compose_workflow` expects):
```python
available_templates = [
    {
        "name": "txt2img_sd15",
        "family": "SD1.5",
        "data": {...}  # full ComfyUI API-format workflow dict
    },
    ...
]
```

### 4.3 The Hardcoded Fallback Workflow

The inline fallback is a 7-node SD 1.5 txt2img workflow matching the structure
of `agent/templates/txt2img_sd15.json` exactly, with one important difference:
the checkpoint name defaults to `"v1-5-pruned-emaonly.safetensors"`.

```python
_FALLBACK_WORKFLOW_SD15: dict = {
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"},
    },
    "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "a beautiful image", "clip": ["1", 1]},
    },
    "3": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "ugly, blurry, low quality", "clip": ["1", 1]},
    },
    "4": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 512, "height": 512, "batch_size": 1},
    },
    "5": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 42,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler_ancestral",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["1", 0],
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
        },
    },
    "6": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
    },
    "7": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "ComfyUI", "images": ["6", 0]},
    },
}
```

**MVP limitation:** This workflow works if the user has
`v1-5-pruned-emaonly.safetensors` in their ComfyUI models directory. If they
don't, ComfyUI returns a 400 with a node error like "CheckpointLoaderSimple:
checkpoint not found." This is a clear, user-readable message — not a crash.
The forge doc should note this as a known Day 1 limitation.

### 4.4 Proposed Implementation

**New module-level constant and helper** (add near top of autonomous.py, after
imports):

```python
import copy
import json
from pathlib import Path

_FALLBACK_WORKFLOW_SD15: dict = {
    # ... (full dict as shown in §4.3 above)
}

_AGENT_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "agent" / "templates"

_FAMILY_TO_TEMPLATE = {
    "SD1.5": "txt2img_sd15",
    "SDXL": "txt2img_sdxl",
    "SD3": "txt2img_sd15",   # No SD3 template — fall back to SD1.5
    "Flux": "txt2img_sd15",  # No Flux template — fall back to SD1.5
}


def _load_available_templates() -> list[dict]:
    """Load workflow templates from agent/templates/ dir.

    Returns a list of template metadata dicts in the shape expected by
    compose_workflow: [{"name": str, "family": str, "data": dict}].

    Falls back to the hardcoded SD1.5 template if the directory is missing
    or all files fail to parse.
    """
    templates = []
    family_map = {
        "txt2img_sd15": "SD1.5",
        "txt2img_sdxl": "SDXL",
        "img2img": "SDXL",
        "txt2img_lora": "SDXL",
    }
    if _AGENT_TEMPLATES_DIR.exists():
        for json_path in sorted(_AGENT_TEMPLATES_DIR.glob("*.json")):
            name = json_path.stem
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                templates.append({
                    "name": name,
                    "family": family_map.get(name, "SD1.5"),
                    "data": data,
                })
            except (json.JSONDecodeError, OSError):
                continue

    if not templates:
        # Hardcoded fallback — ensures pipeline is self-sufficient
        templates = [
            {
                "name": "txt2img_sd15_fallback",
                "family": "SD1.5",
                "data": copy.deepcopy(_FALLBACK_WORKFLOW_SD15),
            }
        ]
    return templates
```

**COMPOSE stage change** (lines 131-135):

Before:
```python
        composition = compose_workflow(
            config.intent,
            model_family=config.model_family,
            experience_patterns=experience_patterns,
        )
```

After:
```python
        available_templates = _load_available_templates()
        composition = compose_workflow(
            config.intent,
            model_family=config.model_family,
            experience_patterns=experience_patterns,
            available_templates=available_templates,
        )
```

**Additional import at top of file** (add `import copy`, `import json`,
`from pathlib import Path` — these are stdlib, no new dependencies):

```python
import copy
import json
from pathlib import Path
```

**Post-COMPOSE fallback guard** (after line 141, `result.workflow_data = composition.workflow_data`):

Add:
```python
        # Last-resort fallback if compose still returned empty workflow_data
        # (e.g., no template matched the detected model family)
        if not result.workflow_data:
            result.log(
                f"No template matched family={model_family} — using SD1.5 fallback"
            )
            result.workflow_data = copy.deepcopy(_FALLBACK_WORKFLOW_SD15)
```

This handles the case where `_load_available_templates()` returns templates but
none match the detected family (e.g., compose detects "Flux" but only SD1.5
template exists). Note: the `_FAMILY_TO_TEMPLATE` dict in the helper maps Flux
and SD3 to `txt2img_sd15`, so compose will find a match — but the fallback guard
is a correctness belt-and-suspenders.

### 4.5 Test Impact

| Test | Class | Impact | Reason |
|---|---|---|---|
| `test_basic_intent_completes` | TestPipeline | PASS UNCHANGED | Now gets real workflow_data (non-empty). Still completes. |
| `test_with_model_family` (Flux) | TestPipeline | PASS UNCHANGED | Flux → no Flux template → fallback guard → SD1.5 workflow. COMPLETE. |
| `test_zero_intervention_mock_mode` | TestFullPipeline | **REWRITE** | Now has non-empty workflow; will attempt real execute. See Change 1 §3.3. |
| `test_pipeline_improves_with_experience` | TestFullPipeline | **REWRITE** | Same. |
| All other tests | All | PASS UNCHANGED | Non-empty workflow is strictly better. |

Note: `_load_available_templates()` reads from the filesystem during tests. In
the test environment, `G:\Comfy-Cozy\agent\templates\` exists and contains real
JSON files. Template loading will succeed in tests. This is acceptable — the
templates are checked-in static files, not live data.

---

## 5. Change 3 — Default Evaluator

### 5.1 Problem

(Scout finding, §EVALUATE): No default evaluator is provided. When
`config.evaluator` is `None`, `result.quality` remains at `QualityScore(overall=0.0,
is_scored=False)`. An unscored quality score means the CWM never calibrates
(`cwm.record_accuracy()` is gated on `quality.is_scored`), auto-retry never
triggers (gated on `is_scored`), and the feedback loop is permanently disabled.
Lines 197-209 of autonomous.py confirm the skip-when-None behavior.

### 5.2 Proposed Implementation

**New method on `AutonomousPipeline`:**

```python
    def _default_evaluator(self, execution_result: Any) -> QualityScore:
        """Rule-based quality evaluation for when no evaluator is provided.

        Returns 0.7 if execution succeeded, 0.1 if not.
        Zero code dependencies — no vision, no hashing.
        """
        if execution_result is not None and getattr(execution_result, "success", False):
            return QualityScore(overall=0.7, source="rule")
        return QualityScore(overall=0.1, source="rule")
```

**EVALUATE stage change** (lines 197-209):

Before:
```python
        # Stage 6: EVALUATE
        result.stage = PipelineStage.EVALUATE
        if config.evaluator is not None:
            try:
                quality = config.evaluator(result.execution_result)
                if isinstance(quality, QualityScore):
                    result.quality = quality
                elif isinstance(quality, (int, float)):
                    result.quality = QualityScore(overall=float(quality))
                result.log(f"Quality: {result.quality.overall:.1%}")
            except Exception as e:
                result.log(f"Evaluation failed: {e}")
        else:
            result.log("No evaluator — skipping quality assessment")
```

After:
```python
        # Stage 6: EVALUATE
        result.stage = PipelineStage.EVALUATE
        _evaluator = config.evaluator if config.evaluator is not None else self._default_evaluator
        try:
            quality = _evaluator(result.execution_result)
            if isinstance(quality, QualityScore):
                result.quality = quality
            elif isinstance(quality, (int, float)):
                result.quality = QualityScore(overall=float(quality))
            result.log(f"Quality: {result.quality.overall:.1%}")
        except Exception as e:
            result.log(f"Evaluation failed: {e}")
```

**Rationale:** Same structural pattern as Change 1. Collapses to ternary
assignment; single try/except handles both paths. `config.evaluator` override
preserved.

`_default_evaluator` accepts `Any` because `execution_result` is typed as `Any`
in `PipelineResult` and may be `None` (if EXECUTE was skipped before Change 1,
or if execution fails before returning). `getattr(execution_result, "success",
False)` handles None gracefully.

### 5.3 Test Impact

| Test | Class | Impact | Reason |
|---|---|---|---|
| `test_with_evaluator` | TestDelegates | PASS UNCHANGED | `config.evaluator` set; ternary picks it. |
| `test_evaluator_numeric` | TestDelegates | PASS UNCHANGED | Same. |
| `test_quality_recorded_with_evaluator` | TestLearning | PASS UNCHANGED | Evaluator provided. |
| `test_prediction_accuracy_tracked` | TestLearning | PASS UNCHANGED | Evaluator provided → is_scored → record_accuracy fires. |
| `test_retry_logged_below_threshold` | TestRetry | See Change 1 | Evaluator provided. After Change 1 rewrite, still passes. |
| `test_zero_intervention_mock_mode` | TestFullPipeline | **REWRITE** (see Change 1) | No evaluator → default fires. But quality scoring is now active. |
| `test_basic_intent_completes` | TestPipeline | PASS UNCHANGED | Result.quality now has `overall=0.1` (execution not provided). |
| `test_prediction_populated` | TestPipeline | PASS UNCHANGED | Evaluator not checked in this test. |

One behavior change to document: tests that run without a custom executor AND
assert `result.quality.is_scored` should now expect `True` (default evaluator
fires) instead of `False`. Currently no test asserts directly on
`result.quality.is_scored` in the no-evaluator path — the mock-mode tests
(`test_zero_intervention_mock_mode`) only assert on `result.success` and stage.

---

## 6. Change 4 — ExperienceChunk Parameter Shape Fix

### 6.1 Problem

(Scout finding, §LEARN): Line 216 constructs:
```python
parameters={"composed": params},
```
where `params = composition.plan.parameters` — a flat dict like
`{"cfg": 7.0, "steps": 20}`. The outer `{"composed": ...}` wrap creates a
single-key dict whose only key is `"composed"`. The inline comment on
`ExperienceChunk.parameters` (chunk.py line 62) states the expected shape is
`{node_id: {param: value}}`. The current shape is neither flat nor node-keyed.

`ExperienceChunk.matches_context()` (lines 95-123) iterates `self.parameters.keys()`
— with the `{"composed": ...}` shape, the only key is `"composed"`, which will
never match between two chunks unless both happen to have the same inner dict.
Retrieval similarity via `matches_context` is effectively broken.

### 6.2 Proposed Implementation

**Decision: Option (a) — `parameters=params` (flat dict).**

Justification:
- `GenerationContextSignature.from_workflow()` takes a full workflow dict with
  `class_type` nodes — it does NOT consume `ExperienceChunk.parameters`.
  The field comment's `{node_id: {param: value}}` description is aspirational,
  not enforced by any current consumer.
- `ExperienceChunk.matches_context()` iterates keys. With `parameters=params`
  (`{"cfg": 7.0, "steps": 20}`), two chunks from similar intents will have
  overlapping keys (`"cfg"`, `"steps"`) and can compute meaningful similarity
  scores.
- Converting to true `{node_id: {param: value}}` format would require knowing
  which node ID holds the KSampler (it varies by template). This is brittle and
  overengineered for MVP.
- Flat `{"cfg": float, "steps": int}` is the simplest correct shape for
  parameter-level similarity matching. The field comment can be updated in a
  later cleanup pass.

**LEARN stage change** (line 216):

Before:
```python
        chunk = ExperienceChunk(
            model_family=model_family,
            prompt=config.intent,
            parameters={"composed": params},
            quality=result.quality,
            output_filenames=[],
        )
```

After:
```python
        chunk = ExperienceChunk(
            model_family=model_family,
            prompt=config.intent,
            parameters=params,
            quality=result.quality,
            output_filenames=[],
        )
```

This is a one-line change. No new imports needed.

### 6.3 Test Impact

| Test | Class | Impact | Reason |
|---|---|---|---|
| `test_experience_recorded` | TestPipeline | PASS UNCHANGED | Asserts `experience_chunk is not None` and `generation_count == 1`. Not shape-sensitive. |
| `test_multiple_runs_accumulate` | TestLearning | PASS UNCHANGED | Asserts `generation_count == 5`. Not shape-sensitive. |
| `test_style_locked_series` | TestFullPipeline | PASS UNCHANGED | Asserts `all(r.success for r in results)` and `generation_count == 3`. Not shape-sensitive. |
| `test_pipeline_improves_with_experience` | TestFullPipeline | **REWRITE** (see Change 1) | Not due to this change; due to Change 1 executor wiring. |

No currently-passing test asserts on the literal shape of `experience_chunk.parameters`.
This change should cause zero test regressions by itself.

---

## 7. Change 5 — §17 Diagnostic (analyze_workflow post-COMPOSE)

### 7.1 Problem

`autonomous.py` imports `analyze_workflow` from `cognitive/tools/analyze.py` (line 29)
but never calls it. The import is dead code. The scout's §17 recommendation
(PHASE_6_PIPELINE_ANALYSIS.md): call `analyze_workflow` after COMPOSE to detect
an empty workflow before it reaches EXECUTE, where the error message is less
informative.

### 7.2 Proposed Implementation

Add the call immediately after line 141 (`result.workflow_data = composition.workflow_data`),
before the last-resort fallback guard from Change 2.

**Exact insertion point** (after Change 2's fallback guard, after `result.workflow_data` is set):

```python
        result.workflow_data = composition.workflow_data

        # Post-COMPOSE diagnostic (§17): warn if workflow is empty or malformed.
        # Warn-only — does not halt the pipeline. The fallback guard below
        # ensures we proceed with a valid workflow even if the warning fires.
        _analysis = analyze_workflow(result.workflow_data)
        if _analysis.node_count == 0:
            result.log(
                "COMPOSE warning: workflow has 0 nodes — "
                "falling back to SD1.5 template"
            )

        # Last-resort fallback if compose still returned empty workflow_data
        if not result.workflow_data:
            result.log(
                f"No template matched family={model_family} — using SD1.5 fallback"
            )
            result.workflow_data = copy.deepcopy(_FALLBACK_WORKFLOW_SD15)
```

**Ordering note:** `analyze_workflow` is called on the original `composition.workflow_data`
(which may be `{}`). The warning fires. Then the fallback guard replaces
`result.workflow_data` with a real workflow. The diagnostic fires before the
repair, giving the log a clear "here is what happened" message. After Change 2,
the `agent/templates/` load should make `composition.workflow_data` non-empty
in the normal path, so the warning will only fire in edge cases.

`analyze_workflow` signature: `(workflow_data, schema_cache=None) -> WorkflowAnalysis`.
Calling with just `result.workflow_data` is valid — `schema_cache` defaults to
`None`. Returns `WorkflowAnalysis` with `node_count = 0` on empty dict. This
is safe to call with any dict, even `{}`.

The import for `analyze_workflow` already exists at line 29. No import change
needed for this change.

---

## 8. Change 6 — Bootstrap Function (Option A)

### 8.1 Problem

`AutonomousPipeline.__init__` already accepts all four cognitive components with
default construction:
```python
self._accumulator = accumulator or ExperienceAccumulator()
self._cwm = cwm or CognitiveWorldModel()
self._arbiter = arbiter or SimulationArbiter()
self._cf_gen = counterfactual_gen or CounterfactualGenerator()
```
So `AutonomousPipeline()` already works with no arguments. However, future callers
(MCP server) need a single, blessed entry point that:
1. Constructs a pipeline with sensible singleton components.
2. Is importable from a stable, predictable location.
3. Does NOT instantiate a second set of singletons if called twice (caller owns
   singleton lifetime per Option A — the function returns a new pipeline each call,
   but the cognitive singletons are fresh instances, not module-level globals).

### 8.2 Location Decision

**Decision: `cognitive/pipeline/__init__.py` — add `create_default_pipeline` to the
existing public API.**

Rationale:
- `cognitive/pipeline/__init__.py` already exists (15 lines) and exports
  `AutonomousPipeline`, `PipelineConfig`, `PipelineResult`, `PipelineStage`.
- The MCP server would naturally import from `cognitive.pipeline` — the module
  that owns the pipeline concept.
- A `create_default_pipeline()` in `__init__.py` is a natural "module constructor"
  pattern, consistent with how `ExperienceAccumulator`, `CognitiveWorldModel`, etc.
  are already built with no-arg `__init__` constructors.
- A standalone `cognitive/bootstrap.py` (option b) is a new module for ~10 lines
  of code — unnecessary overhead.
- A classmethod `AutonomousPipeline.create_default()` (option c) conflates factory
  and class — the class already has a clean `__init__`. Adding a classmethod just
  because it's an alternative constructor with defaults adds noise.

The import path the MCP server will use:
```python
from cognitive.pipeline import create_default_pipeline
```

### 8.3 Signature and Implementation

Add to `cognitive/pipeline/__init__.py`:

```python
from ..experience.accumulator import ExperienceAccumulator
from ..prediction.cwm import CognitiveWorldModel
from ..prediction.arbiter import SimulationArbiter
from ..prediction.counterfactual import CounterfactualGenerator


def create_default_pipeline(
    config: PipelineConfig | None = None,
) -> AutonomousPipeline:
    """Construct an AutonomousPipeline with default singleton components.

    Instantiates all four cognitive components fresh. The caller owns
    their lifetime — for MCP server use, call once at startup and keep
    the returned pipeline alive for the server's lifetime (Option A).

    Two calls return two independent pipelines with independent
    accumulator state. There is no implicit module-level singleton.

    Args:
        config: Not used at construction time. Included for forward
            compatibility — future versions may use it to pre-configure
            the CWM with domain-specific prior rules.

    Returns:
        AutonomousPipeline ready to call .run(PipelineConfig(...)).
    """
    accumulator = ExperienceAccumulator()
    cwm = CognitiveWorldModel()
    arbiter = SimulationArbiter()
    cf_gen = CounterfactualGenerator()
    return AutonomousPipeline(
        accumulator=accumulator,
        cwm=cwm,
        arbiter=arbiter,
        counterfactual_gen=cf_gen,
    )


__all__ = [
    "AutonomousPipeline",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStage",
    "create_default_pipeline",
]
```

**Import note:** `PipelineConfig` is already imported in `__init__.py` via the
`from .autonomous import ...` line. The four new cognitive imports are the only
additions needed.

### 8.4 Test Impact

**[NEW] tests to add in `tests/test_cognitive_pipeline.py`:**

```python
class TestCreateDefaultPipeline:

    def test_returns_autonomous_pipeline(self):
        from cognitive.pipeline import create_default_pipeline
        p = create_default_pipeline()
        assert isinstance(p, AutonomousPipeline)

    def test_components_are_correct_types(self):
        from cognitive.pipeline import create_default_pipeline
        from cognitive.experience.accumulator import ExperienceAccumulator
        from cognitive.prediction.cwm import CognitiveWorldModel
        from cognitive.prediction.arbiter import SimulationArbiter
        from cognitive.prediction.counterfactual import CounterfactualGenerator
        p = create_default_pipeline()
        assert isinstance(p._accumulator, ExperienceAccumulator)
        assert isinstance(p._cwm, CognitiveWorldModel)
        assert isinstance(p._arbiter, SimulationArbiter)
        assert isinstance(p._cf_gen, CounterfactualGenerator)

    def test_two_calls_return_independent_pipelines(self):
        from cognitive.pipeline import create_default_pipeline
        p1 = create_default_pipeline()
        p2 = create_default_pipeline()
        assert p1 is not p2
        assert p1._accumulator is not p2._accumulator

    def test_pipeline_can_run_after_create(self, monkeypatch):
        """create_default_pipeline() returns a pipeline that can run()."""
        from cognitive.pipeline import create_default_pipeline
        # Mock execute to avoid real ComfyUI call
        import cognitive.pipeline.autonomous as auto_mod
        monkeypatch.setattr(
            auto_mod, "_execute_workflow_default",
            lambda wf: type("R", (), {"success": True, "output_filenames": []})(),
        )
        p = create_default_pipeline()
        result = p.run(PipelineConfig(intent="test intent"))
        assert result.stage == PipelineStage.COMPLETE
```

---

## 9. Full Test Plan

### Summary Table

| Test | File | Status | Change |
|---|---|---|---|
| `TestPipeline::test_empty_intent_fails` | test_cognitive_pipeline.py | UNCHANGED | — |
| `TestPipeline::test_basic_intent_completes` | test_cognitive_pipeline.py | UNCHANGED | — |
| `TestPipeline::test_prediction_populated` | test_cognitive_pipeline.py | UNCHANGED | — |
| `TestPipeline::test_experience_recorded` | test_cognitive_pipeline.py | UNCHANGED | — |
| `TestPipeline::test_stage_log_populated` | test_cognitive_pipeline.py | UNCHANGED | — |
| `TestPipeline::test_with_model_family` | test_cognitive_pipeline.py | UNCHANGED | — |
| `TestPipeline::test_arbiter_decision_attached` | test_cognitive_pipeline.py | UNCHANGED | — |
| `TestDelegates::test_with_executor` | test_cognitive_pipeline.py | UNCHANGED | Change 1 preserves override path |
| `TestDelegates::test_with_evaluator` | test_cognitive_pipeline.py | UNCHANGED | Change 3 preserves override path |
| `TestDelegates::test_evaluator_numeric` | test_cognitive_pipeline.py | UNCHANGED | Change 3 preserves override path |
| `TestDelegates::test_executor_failure` | test_cognitive_pipeline.py | UNCHANGED | Change 1 preserves error path |
| `TestArbiterInterrupt::test_interrupt_on_degenerate_params` | test_cognitive_pipeline.py | UNCHANGED | — |
| `TestLearning::test_multiple_runs_accumulate` | test_cognitive_pipeline.py | REWRITE | Change 1: add mock executor |
| `TestLearning::test_quality_recorded_with_evaluator` | test_cognitive_pipeline.py | UNCHANGED | Evaluator provided |
| `TestLearning::test_prediction_accuracy_tracked` | test_cognitive_pipeline.py | UNCHANGED | Evaluator provided |
| `TestRetry::test_retry_logged_below_threshold` | test_cognitive_pipeline.py | REWRITE | Change 1: add mock executor |
| `TestRetry::test_no_retry_above_threshold` | test_cognitive_pipeline.py | REWRITE | Change 1: add mock executor |
| `TestRetry::test_no_retry_when_disabled` | test_cognitive_pipeline.py | REWRITE | Change 1: add mock executor |
| `TestFullPipeline::test_zero_intervention_mock_mode` | test_cognitive_pipeline.py | REWRITE | Change 1: add mock executor |
| `TestFullPipeline::test_full_pipeline_with_delegates` | test_cognitive_pipeline.py | UNCHANGED | Executor provided |
| `TestFullPipeline::test_pipeline_improves_with_experience` | test_cognitive_pipeline.py | REWRITE | Change 1: add mock executor |
| `TestFullPipeline::test_counterfactual_generated` | test_cognitive_pipeline.py | REWRITE | Change 1: add mock executor |
| `TestFullPipeline::test_style_locked_series` | test_cognitive_pipeline.py | REWRITE | Change 1: add mock executor |
| `TestCreateDefaultPipeline::test_returns_autonomous_pipeline` | test_cognitive_pipeline.py | **[NEW]** | Change 6 |
| `TestCreateDefaultPipeline::test_components_are_correct_types` | test_cognitive_pipeline.py | **[NEW]** | Change 6 |
| `TestCreateDefaultPipeline::test_two_calls_return_independent_pipelines` | test_cognitive_pipeline.py | **[NEW]** | Change 6 |
| `TestCreateDefaultPipeline::test_pipeline_can_run_after_create` | test_cognitive_pipeline.py | **[NEW]** | Change 6 |

### Rewrite Pattern for Change 1 (applies to 8 tests)

Every test that currently runs without an executor must add a mock executor.
The pattern is identical for all:

```python
# Before (any test using pipeline fixture without executor):
result = pipeline.run(PipelineConfig(intent="test"))

# After:
mock_exec = lambda wf: type("R", (), {"success": True, "output_filenames": []})()
result = pipeline.run(PipelineConfig(intent="test", executor=mock_exec))
```

For `test_multiple_runs_accumulate` and `test_pipeline_improves_with_experience`
(loop-based), add the executor to the `PipelineConfig` inside the loop.

**Alternative approach for `test_zero_intervention_mock_mode`:** This test is
specifically named "mock_mode." It might be appropriate to rename it to
`test_zero_intervention_with_mock_executor` and update the docstring to reflect
that real execution is the new default. The docstring "no human intervention"
is still accurate — `executor=mock_exec` is provided in code, not by a human.

### Delta

- **Existing tests:** 23
- **Rewrites:** 8 (all in test_cognitive_pipeline.py — logic preserved, only
  `executor=mock_exec` added to PipelineConfig)
- **New tests:** 4 (all in `TestCreateDefaultPipeline` class)
- **Expected count after forge:** 27 (23 - 0 deleted + 4 new)
- **Expected baseline delta:** 2683 → approximately 2687 (net +4 new tests,
  8 rewrites do not change count)

---

## 10. Forge Acceptance Criteria

The forge pass must meet all of the following, in order:

1. **All six changes implemented** per this design document — no partial implementation.

2. **Baseline holds at ≥ 2683.** Target after additions: ~2687.

3. **No regressions in tests/test_cognitive_pipeline.py.** All 23 existing test
   names must still exist and pass (8 with executor added to config).

4. **Dead-import eliminated:**
   ```bash
   grep "analyze_workflow" cognitive/pipeline/autonomous.py
   ```
   Must show at least one call site (the post-COMPOSE check), not just the import.

5. **Option A compliance — no agent imports in autonomous.py:**
   ```bash
   grep -n "from agent" cognitive/pipeline/autonomous.py
   grep -n "import agent" cognitive/pipeline/autonomous.py
   ```
   Both must return zero matches.

6. **Template loading uses path, not import:**
   ```bash
   grep -n "from agent" cognitive/pipeline/autonomous.py
   ```
   Must be zero. Template files are loaded via `Path`, not `import`.

7. **Fresh-shell import check:**
   ```bash
   python -c "from cognitive.pipeline import create_default_pipeline; p = create_default_pipeline(); print(type(p).__name__)"
   ```
   Must print `AutonomousPipeline`.

8. **No stubs remain without a TODO comment:**
   ```bash
   grep -n "TODO\|stub\|placeholder\|NotImplementedError\|mock mode" cognitive/pipeline/autonomous.py
   ```
   The only acceptable hits are: the auto-retry stub comment (line ~250, which
   is explicitly deferred to Session N+2) and no `"mock mode"` string (the
   "execution skipped (mock mode)" log message should be gone after Change 1).

9. **ExperienceChunk parameter shape:**
   ```bash
   grep -n '"composed"' cognitive/pipeline/autonomous.py
   ```
   Must return zero matches.

10. **4 new tests exist and pass:**
    ```bash
    pytest tests/test_cognitive_pipeline.py::TestCreateDefaultPipeline -v
    ```
    All 4 tests pass.

---

## 11. Risks and Unknowns

### Risk 1 — Template file format compatibility

`agent/templates/txt2img_sd15.json` was read and confirmed as valid ComfyUI API
format. The `_load_available_templates()` helper uses the same `json.loads()` +
`isinstance(data, dict)` check that `workflow_templates.py` uses. Risk is LOW:
the files are checked-in, stable, and already validated by the agent-layer tests.

If a future template file uses UI format (with a `"nodes"` array instead of
node-id keys), `_load_available_templates()` will skip it (the check requires
`class_type` keys). This is acceptable — those files cannot be passed to
`execute_workflow` anyway without UI→API conversion.

### Risk 2 — Hardcoded checkpoint name availability

`v1-5-pruned-emaonly.safetensors` is the most common SD 1.5 checkpoint name
but is not universal. If the user has renamed their checkpoint or uses a
different SD 1.5 model, ComfyUI will return a 400 error with a clear node-level
error message. `execute_workflow` surfaces this as `FAILED` with the ComfyUI
error text. This is a Day 1 limitation, not a crash. The forge doc should note
it and future work can add a checkpoint discovery call before execution.

Risk: LOW for most users (the checkpoint name is the default from the ComfyUI
installer). HIGH for users with custom model installations — they will see an
error on first run.

### Risk 3 — ExperienceChunk parameter shape complexity

The fix is `parameters=params` instead of `parameters={"composed": params}`.
`params` is a flat `{"cfg": float, "steps": int}` dict. This is simpler than
the ideal `{node_id: {param: value}}` format described in the comment, but is
strictly better than the current broken shape. Future work (Session N+2) can
upgrade the shape to true node-keyed format once template loading gives us
access to real node IDs at LEARN time.

Risk: LOW. The one-line change cannot cause a runtime error; `ExperienceChunk`
accepts any dict for `parameters`.

### Risk 4 — Test rewrites more invasive than expected

8 tests need `executor=mock_exec` added to their `PipelineConfig`. This is
a mechanical, one-liner change per test — but it touches 8 tests. If any test
has unusual fixture composition or setup that interacts with the executor path
in an unexpected way, the forge agent may need to investigate further.

Specific concern: `test_pipeline_improves_with_experience` runs 35 pipeline
iterations in a loop. Adding `executor=mock_exec` to each run is
straightforward, but the mock executor must return an object with `success=True`
AND `output_filenames=[]` (not just a bool-truthy return) to avoid breaking the
LEARN stage's `getattr(result.execution_result, "output_filenames", [])` call.
The mock pattern `type("R", (), {"success": True, "output_filenames": []})()` is
already used in `test_with_executor` and handles this correctly.

Risk: LOW — the pattern is established in the existing test file.

### Risk 5 — analyze_workflow call performance in tests

`analyze_workflow({})` is called once per pipeline run after Change 5. In tests
that run 35 iterations (`test_pipeline_improves_with_experience`), this adds 35
lightweight dict-iteration calls. With real templates, each call processes a 7-node
dict. At dict-iteration speed this is microseconds. Not a performance risk.

---

## 12. Out of Scope

The following are explicitly NOT in scope for this forge pass:

- **Auto-retry real implementation** — the LEARN stage stub comment ("In a real
  implementation, we'd adjust params and re-run") stays as-is. Session N+2 work.
- **Vision evaluator** — `analyze_image` scoring. Session N+2.
- **MCP server changes** — Change 6 (bootstrap) is a factory function only.
  Wiring it into `mcp_server.py` is a future session.
- **Phase 3B (dependencies.py)** — not called by the pipeline.
- **Phase 3C (research.py)** — not called by the pipeline.
- **CLI/user-facing interface** — no `agent run` changes.
- **test_health.py stale tests** — out of scope per standing project convention.
- **pyproject.toml changes** — no new dependencies; all new imports are stdlib
  (`copy`, `json`, `pathlib.Path`) or already-present cognitive-layer modules.
- **Session N+3 polish** — arbiter warning surfacing, accumulator persistence,
  SDXL/Flux template upgrade.
- **Checkpoint discovery** — detecting what checkpoints the user actually has.
  Day 1 limitation; tracked in §11 Risk 2.
- **`_FAMILY_TO_TEMPLATE` completeness** — Flux and SD3 fall back to SD1.5 template.
  This is a known limitation, not a bug. Full Flux support requires a Flux template
  file and Flux-specific node set.

---

## 13. Open Questions for Joe

Continuing from §17 of `PHASE_6_PIPELINE_ANALYSIS.md` (last used number was §17).

### §18 — Default executor: always wire, or gate on ComfyUI reachability? (HIGH)

**Context:** After Change 1, every pipeline run without a custom executor will
attempt a real ComfyUI connection. Tests that don't provide a mock executor will
fail (ComfyUI not running in test env). The forge pass resolves this by adding
mock executors to 8 tests. But in production, if someone runs
`pipeline.run(PipelineConfig(intent="..."))` and ComfyUI is not running,
`execute_workflow` returns `FAILED` with "ComfyUI not reachable at http://127.0.0.1:8188."
This is a correct, clear error.

**Question:** Is "attempt real execution, fail clearly if ComfyUI is down" the
right production behavior? Or should the pipeline check `is_comfyui_running()`
first and fall back to mock mode if not reachable?

**Recommended default:** Wire directly — fail clearly. The pipeline's job is to
execute. "ComfyUI not running" is a user-fixable condition, not a bug.
**Silent approval acceptable** (this recommendation matches the scout's §12 option 1).

### §19 — Default evaluator score values: 0.7 / 0.1 appropriate? (MEDIUM)

**Context:** The default evaluator returns `QualityScore(overall=0.7)` on
execution success and `QualityScore(overall=0.1)` on failure. These values
feed into CWM calibration and auto-retry (threshold defaults to 0.6). A score
of 0.7 on any successful execution means auto-retry never fires for
rule-evaluated generations. A score of 0.1 on failure always fires retry.

**Question:** Are 0.7 (success) and 0.1 (failure) the right placeholder values?
Should success score be lower (e.g. 0.5) to allow retry to fire occasionally,
driving the learning loop?

**Recommended default:** Keep 0.7 / 0.1. The rule-based evaluator is a stepping
stone to the vision evaluator. Until vision scoring is active, over-triggering
retry on "good" executions adds unnecessary ComfyUI load.
**Silent approval acceptable.**

### §20 — Template loading path: runtime or config? (LOW)

**Context:** `_load_available_templates()` hard-computes the templates path as
`Path(__file__).parent.parent.parent / "agent" / "templates"`. This is relative
to the `cognitive/pipeline/autonomous.py` file location — correct for the current
repo layout. If the project is installed as a package or the directory structure
changes, this path breaks silently (falls back to hardcoded).

**Question:** Should the templates path be configurable via an env var
(e.g., `COMFY_COZY_TEMPLATES_DIR`) or stay as a hard-coded relative path with
the hardcoded fallback as safety net?

**Recommended default:** Keep the hard-coded relative path + fallback. Env var
adds complexity for a feature that's only needed if the repo structure changes.
**Silent approval acceptable.**

### §21 — Should `create_default_pipeline` accept a `config` parameter? (LOW)

**Context:** The bootstrap function signature includes `config: PipelineConfig | None = None`
as a forward-compatibility stub. It is not used in the implementation. This is
documented in the docstring but adds a parameter that does nothing in v1.

**Question:** Remove the unused `config` parameter, or keep it for forward
compatibility?

**Recommended default:** Remove it. YAGNI — if future versions need it, add it
then. An unused parameter in a public API is a documentation burden.
**Silent approval acceptable.**

---

## Appendix A — File Change Summary

| File | Change Type | Lines Affected |
|---|---|---|
| `cognitive/pipeline/autonomous.py` | Modify | +~40 lines (imports, constant, helper fn, 5 stage edits) |
| `cognitive/pipeline/__init__.py` | Modify | +~30 lines (imports, factory function, updated __all__) |
| `tests/test_cognitive_pipeline.py` | Modify | +~30 lines (8 test rewrites + 4 new tests) |

No new files. No deletions. No changes outside `cognitive/pipeline/` and `tests/`.

---

## Appendix B — Import Additions to autonomous.py

Full import block after forge (additions marked `# NEW`):

```python
from __future__ import annotations

import copy                             # NEW
import json                             # NEW
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path                # NEW
from typing import Any, Callable

from ..core.graph import CognitiveGraphEngine
from ..experience.chunk import ExperienceChunk, QualityScore
from ..experience.accumulator import ExperienceAccumulator
from ..experience.signature import GenerationContextSignature
from ..prediction.cwm import CognitiveWorldModel, Prediction
from ..prediction.arbiter import SimulationArbiter, DeliveryMode
from ..prediction.counterfactual import CounterfactualGenerator
from ..tools.analyze import analyze_workflow
from ..tools.compose import compose_workflow
from ..tools.execute import execute_workflow as _execute_workflow_default  # NEW
```

Note: `CognitiveGraphEngine` is imported at line 21 of the current file but
never used in `run()`. It is retained as-is — out-of-scope cleanup.

---

*Design only. No source files modified. Forge agent: implement all six changes
per this document, run tests, verify all acceptance criteria in §10.*
