# PRD: Phase 8 — 9x9 (All Categories to 9/10)

> **Status:** Draft
> **Author:** Joe Ibrahim + Claude Opus 4.6
> **Date:** 2026-04-12
> **Baseline:** Phase 7 complete, 3608 tests, all passing

---

## Executive Summary

Phase 8 closes every stub, gap, and missing subsystem identified in the 4-axis audit (Frontier AI, Production-Ready, Gen AI, Automation). The goal is 9/10 across all four categories. Each workstream targets a specific gap with measurable exit criteria.

**Current scores:** Frontier AI 8, Production-Ready 7, Gen AI 8, Automation 7
**Target scores:** All 9

---

## Gap Analysis

| # | Gap | Category | Current State | File:Lines |
|---|-----|----------|---------------|------------|
| G1 | Vision evaluator is rule-based 0.7/0.1 | Frontier, Automation | Stub | `cognitive/pipeline/autonomous.py:441-451` |
| G2 | Auto-retry loop never fires | Automation | Threshold read, never checked | `cognitive/pipeline/autonomous.py:345-367` |
| G3 | CWM accuracy not fed back to recalibrate | Frontier | One-way recording | `agent/stage/cwm.py:190-222` |
| G4 | Counterfactual validation is heuristic-only | Frontier | Quality delta = distance * 0.2 | `cognitive/prediction/counterfactual.py:144-147` |
| G5 | Metrics/telemetry absent | Production | No file exists | — |
| G6 | Zero LLM provider tests | Production, Gen AI | 3 providers, 0 tests | `agent/llm/_openai.py`, `_gemini.py`, `_ollama.py` |
| G7 | Knowledge retrieval is keyword-only | Gen AI | No embeddings | `agent/system_prompt.py:104-137` |
| G8 | Integration test harness minimal | Production | 1 class, 2 tests | `tests/test_e2e_pipeline.py` |
| G9 | No external webhook/event trigger | Automation | WebSocket parse only | `cognitive/transport/events.py` |
| G10 | Health endpoint lacks metrics | Production | Basic check_health() | `agent/health.py` |

---

## Workstreams

### WS-A: Vision Evaluator + Auto-Retry Loop
**Closes:** G1, G2, G3, G4
**Categories:** Frontier AI (8→9), Automation (7→9)

#### Requirements

**A1. Vision-based QualityScore evaluator**
- New function `vision_evaluator(execution_result) -> QualityScore` in `cognitive/pipeline/autonomous.py`
- Calls `brain/vision.py:analyze_image()` with the output image path from `execution_result`
- Maps vision response to multi-axis QualityScore: `overall`, `technical`, `aesthetic`, `prompt_adherence`
- Falls back to rule-based evaluator if vision call fails (circuit breaker pattern)
- Wire as `PipelineConfig.evaluator` default when brain is enabled

**A2. Auto-retry loop**
- After Stage 6 (EVALUATE), check `result.quality.overall < config.quality_threshold`
- If below threshold: log reason, increment `result.retry_count`, loop back to Stage 3 (COMPOSE)
- Max retries: `config.max_retries` (default 2, so up to 3 total attempts)
- Each retry modifies composition parameters (increase steps, adjust CFG, try different sampler)
- New `PipelineStage.RETRY` enum value
- Increment `ExecutionResult.retry_count` in `cognitive/tools/execute.py`

**A3. CWM recalibration feedback**
- After recording accuracy in `cwm.record_accuracy()`, adjust confidence thresholds
- If prediction accuracy > 0.8 over last 10 predictions: increase confidence_high by `CALIBRATION_STEP`
- If prediction accuracy < 0.4 over last 10: decrease confidence_high by `CALIBRATION_STEP`
- Bounded: confidence_high in [0.5, 0.95], confidence_low in [0.1, 0.5]
- Store calibration state in experience accumulator for cross-session persistence

**A4. Counterfactual validation tie-in**
- After pipeline execution, auto-generate counterfactuals for the run
- When the same workflow runs again with different parameters, validate prior counterfactuals against observed outcomes
- Feed validated counterfactuals back to CWM as experience chunks with `source="counterfactual"`

#### Exit Criteria
- [ ] `python -m pytest tests/test_vision_evaluator.py -v` — all pass
- [ ] `python -m pytest tests/test_pipeline_retry.py -v` — all pass
- [ ] Pipeline with intentionally bad parameters retries and produces higher quality on retry
- [ ] CWM confidence thresholds shift after 10+ predictions (test with synthetic data)
- [ ] Counterfactual from run N validated against run N+1 outcome
- [ ] Net test count: +40 minimum

---

### WS-B: Observability & Metrics
**Closes:** G5, G10
**Categories:** Production-Ready (7→9)

#### Requirements

**B1. Metrics module (`agent/metrics.py`)**
- Lightweight, no external dependencies (no prometheus_client, no OpenTelemetry SDK)
- Thread-safe counters and histograms using `threading.Lock`
- Metrics:
  - `tool_call_total` (counter, labels: tool_name, status)
  - `tool_call_duration_seconds` (histogram, labels: tool_name)
  - `llm_call_total` (counter, labels: provider, status)
  - `llm_call_duration_seconds` (histogram, labels: provider)
  - `circuit_breaker_state_changes` (counter, labels: from_state, to_state)
  - `session_active_count` (gauge)
  - `pipeline_runs_total` (counter, labels: stage_reached, retry_count)
- Export as JSON dict via `get_metrics() -> dict`
- Optional Prometheus text format export via `get_metrics_prometheus() -> str`

**B2. Instrument tool dispatch**
- In `agent/tools/__init__.py:handle()`: wrap each tool call with timing and counter increment
- On success: increment `tool_call_total{status="ok"}`
- On error: increment `tool_call_total{status="error"}`
- Record duration in histogram

**B3. Instrument LLM calls**
- In `agent/llm/_base.py` or each provider: wrap `stream()`/`create()` with timing
- Record token counts where available (Anthropic usage headers)

**B4. Health endpoint with metrics**
- Extend `agent/health.py:check_health()` to include `get_metrics()` summary
- Add `metrics` key to health response: tool call rates, error rates, p50/p99 latencies
- Add `/health` resource to MCP server (if MCP supports resources; otherwise expose via tool)

#### Exit Criteria
- [ ] `python -m pytest tests/test_metrics.py -v` — all pass
- [ ] Metrics increment correctly after tool calls (unit test with mocked tools)
- [ ] Histogram percentiles computed correctly (p50, p95, p99)
- [ ] Health endpoint includes metrics summary
- [ ] Thread-safe under concurrent access (test with 8 threads)
- [ ] Net test count: +30 minimum

---

### WS-C: LLM Provider Test Coverage
**Closes:** G6
**Categories:** Production-Ready (7→9), Gen AI (8→9)

#### Requirements

**C1. Provider unit tests**
- `tests/test_llm_openai.py` — test OpenAI provider message conversion, tool conversion, streaming mock, error handling
- `tests/test_llm_gemini.py` — test Gemini provider message conversion, tool conversion, streaming mock, error handling
- `tests/test_llm_ollama.py` — test Ollama provider message conversion, tool conversion, streaming mock, error handling
- Each test file mocks the underlying HTTP client (httpx for Ollama/Gemini, openai SDK for OpenAI)
- Test cases per provider:
  - Message conversion: text, tool_use, tool_result, image (vision), system prompt
  - Tool schema conversion: Anthropic format → provider format → back
  - Streaming: mock stream events, verify on_text/on_thinking callbacks fire
  - Error mapping: provider-specific errors → LLMAuthError, LLMRateLimitError, LLMError
  - Edge cases: empty messages, missing fields, malformed responses

**C2. Provider interface conformance test**
- `tests/test_llm_conformance.py` — parameterized test that runs the same scenarios against all 4 providers
- Verifies all providers implement the `LLMProvider` protocol correctly
- Tests that tool schemas round-trip through conversion without data loss

#### Exit Criteria
- [ ] `python -m pytest tests/test_llm_*.py -v` — all pass
- [ ] Each provider has 15+ test cases covering message/tool/stream/error paths
- [ ] Conformance test passes for all 4 providers
- [ ] No provider-specific code is tested only via the Anthropic path
- [ ] Net test count: +60 minimum

---

### WS-D: Semantic Knowledge Retrieval
**Closes:** G7
**Categories:** Gen AI (8→9)

#### Requirements

**D1. Embedding-based knowledge index**
- New module `agent/knowledge/embedder.py`
- On first load: chunk each knowledge markdown file into sections (by ## headers)
- Generate embeddings using a lightweight local model (sentence-transformers via optional dependency, or TF-IDF as zero-dependency fallback)
- Store index as JSON file in `agent/knowledge/_index.json` (rebuilt on knowledge file change via mtime check)
- Zero-dependency fallback: TF-IDF with cosine similarity (sklearn-free, pure Python)

**D2. Semantic trigger detection**
- Extend `system_prompt.py:_detect_relevant_knowledge()` to:
  1. First: run existing keyword triggers (fast path, no change)
  2. Then: if keyword triggers return < 2 files, run semantic search against the query/workflow context
  3. Semantic search returns top-3 chunks by cosine similarity above threshold (0.3)
  4. Map chunks back to knowledge file names
- Hybrid approach: keywords first (fast, precise), embeddings second (recall, fuzzy)

**D3. Knowledge freshness**
- `_index.json` includes `{file: mtime}` map
- On load, compare mtimes. If any file changed, rebuild that file's embeddings only (incremental)
- Thread-safe rebuild with `_index_lock`

#### Exit Criteria
- [ ] `python -m pytest tests/test_knowledge_embedder.py -v` — all pass
- [ ] Semantic search finds "ControlNet depth preprocessing" when query is "I need depth maps" (no exact keyword match)
- [ ] TF-IDF fallback works without any optional dependencies
- [ ] Index rebuilds incrementally when one knowledge file changes
- [ ] Hybrid detection returns superset of keyword-only detection
- [ ] Net test count: +20 minimum

---

### WS-E: Integration Test Harness + Event Triggers
**Closes:** G8, G9
**Categories:** Production-Ready (7→9), Automation (7→9)

#### Requirements

**E1. Integration test framework**
- `tests/integration/conftest.py` — fixtures for live ComfyUI connection
  - `@pytest.fixture` `comfyui_server` — skip if ComfyUI not running (checks `http://localhost:8188/system_stats`)
  - `@pytest.fixture` `api_key` — skip if `ANTHROPIC_API_KEY` not set
- All integration tests marked `@pytest.mark.integration`
- CI runs unit tests only by default; integration tests via `pytest -m integration`

**E2. Integration test cases**
- `tests/integration/test_comfyui_connection.py` — connect, get system stats, list models
- `tests/integration/test_workflow_roundtrip.py` — load → patch → validate → execute → get output
- `tests/integration/test_session_persistence.py` — save session → reload → verify state identical
- `tests/integration/test_provision_pipeline.py` — discover model → check if installed → provision if missing

**E3. Event trigger system**
- New module `cognitive/transport/triggers.py`
- `EventTrigger` dataclass: `event_type: EventType`, `callback: Callable`, `filter: dict | None`
- `TriggerRegistry`: register/unregister triggers, dispatch events to matching callbacks
- Wire into `comfy_execute.py`: after WebSocket event parsed, dispatch to trigger registry
- Built-in triggers:
  - `on_execution_complete` → auto-evaluate quality (connects to WS-A vision evaluator)
  - `on_execution_error` → auto-log to session notes
- External trigger injection: `register_webhook(url, event_types)` — POST to URL on matching events

**E4. Concurrent pipeline stress test**
- `tests/integration/test_concurrent_pipelines.py` — 4 concurrent pipeline runs with different sessions
- Verify session isolation (no cross-contamination of workflow state)
- Verify metrics increment correctly under load (connects to WS-B)

#### Exit Criteria
- [ ] `python -m pytest tests/integration/ -v -m integration` — all pass (when ComfyUI running)
- [ ] `python -m pytest tests/integration/ -v -m integration` — all skip cleanly (when ComfyUI not running)
- [ ] Event trigger fires callback on execution_complete
- [ ] Webhook POST sent to registered URL on matching event
- [ ] 4 concurrent pipelines complete without session cross-contamination
- [ ] Net test count: +25 minimum

---

## Dependency Graph

```
WS-A (Vision + Retry)  ──────────────────────┐
WS-B (Metrics)         ──────────────────────┤
WS-C (Provider Tests)  ─── independent ──────┤──→  Final Verification
WS-D (Semantic Knowledge) ─── independent ───┤
WS-E (Integration + Triggers) ── depends on A,B ─┘
```

WS-A, WS-B, WS-C, WS-D can run in parallel.
WS-E depends on WS-A (vision evaluator for trigger) and WS-B (metrics for stress test).

---

## Agent Team Assignment

### Roles (per MoE Commandments)

| Role | Agent | Authority | Cannot |
|------|-------|-----------|--------|
| **ARCHITECT** | Designs implementation for each WS | Write design docs, define interfaces | Write implementation code |
| **SCOUT** | Reconnaissance per WS | Read files, search patterns, map conventions | Mutate any file |
| **FORGE-A** | Implements WS-A (Vision + Retry) | Create/modify files in `cognitive/`, `agent/stage/` | Touch `agent/llm/`, `agent/knowledge/` |
| **FORGE-B** | Implements WS-B (Metrics) | Create/modify `agent/metrics.py`, instrument `agent/tools/__init__.py`, `agent/health.py` | Touch `cognitive/`, `agent/llm/` |
| **FORGE-C** | Implements WS-C (Provider Tests) | Create test files in `tests/test_llm_*.py` | Modify provider source code |
| **FORGE-D** | Implements WS-D (Semantic Knowledge) | Create/modify `agent/knowledge/`, `agent/system_prompt.py` | Touch `cognitive/`, `agent/llm/` |
| **FORGE-E** | Implements WS-E (Integration + Triggers) | Create `tests/integration/`, `cognitive/transport/triggers.py` | Touch `agent/tools/`, `agent/brain/` |
| **CRUCIBLE** | Adversarial verification of all WS | Run tests, write edge-case tests, break implementations | Fix bugs (escalates to FORGE) |

### Execution Sequence

```
Phase 1: SCOUT (all WS)      — Map conventions, frozen boundaries, existing patterns
Phase 2: ARCHITECT            — Design docs for all 5 WS (handoff artifacts)
Phase 3: HUMAN GATE           — Joe reviews designs before implementation
Phase 4: FORGE-A,B,C,D       — Parallel implementation (worktrees)
Phase 5: CRUCIBLE pass 1      — Adversarial testing of A,B,C,D
Phase 6: FORGE-E              — Integration (depends on A,B outputs)
Phase 7: CRUCIBLE pass 2      — Full regression + integration adversarial
Phase 8: HUMAN GATE           — Joe reviews before merge
```

### Commandment Compliance

| # | Commandment | How Enforced |
|---|-------------|-------------|
| C1 | Scout before you act | SCOUT agent runs first. Every FORGE reads 2-3 existing examples before writing. |
| C2 | Verify after every mutation | FORGE agents run `pytest` after every file create/modify. Regression = stop. |
| C3 | Bounded failure → escalate | 3 retries per step. After 3: write `BLOCKER.md` with what was tried, what failed, diagnosis. |
| C4 | Complete output or explicit blocker | No stubs, no TODOs, no truncation. If incomplete: BLOCKER.md with what's missing and what it would take. |
| C5 | Role isolation | Authority boundaries in table above. FORGE-C cannot modify provider source. ARCHITECT cannot write implementation. |
| C6 | Explicit handoffs | ARCHITECT produces design doc per WS. FORGE reads design doc, not conversation history. CRUCIBLE reads test plan, not implementation notes. |
| C7 | Adversarial verification | CRUCIBLE is structurally separate from all FORGE agents. Edge cases mandatory. Weak assertions are test bugs. Fix forward, never weaken tests. |
| C8 | Human gates at irreversible transitions | Gate after ARCHITECT (Phase 3). Gate before merge (Phase 8). Minimal gates, maximum information. |

---

## Success Metrics

| Category | Current | Target | Measurable Proof |
|----------|---------|--------|-----------------|
| Frontier AI | 8 | 9 | CWM predictions improve with experience count (test); vision evaluator produces multi-axis scores; counterfactuals validated against real outcomes |
| Production-Ready | 7 | 9 | Metrics module with p50/p99 latencies; 60+ provider tests; integration test harness; health endpoint with metrics |
| Gen AI | 8 | 9 | Semantic knowledge retrieval finds results keyword-only misses; all 4 providers tested; intent translation validated |
| Automation | 7 | 9 | Auto-retry loop fires and improves quality; event triggers dispatch on execution; cross-session learning demonstrated |

**Total new tests:** +175 minimum (40 + 30 + 60 + 20 + 25)
**Final test count target:** 3783+

---

## Non-Goals (Phase 8)

- No external vector database (Pinecone, Weaviate). TF-IDF is sufficient for 11 knowledge files.
- No OpenTelemetry SDK dependency. Lightweight custom metrics first.
- No fine-tuned models. Prompt engineering and tool use are the leverage points.
- No Kubernetes deployment. Single-machine MCP server is the deployment target.
- No real-time dashboard. JSON metrics export is the interface; dashboards are Phase 9.
