# Phase 3A — `cognitive/tools/execute.py` Design

**Agent:** `[GRAPH × ARCHITECT]`
**Date:** 2026-04-08
**Status:** Architect-only. No code written. Awaiting human gate before FORGE pass.
**Resolves:** Open Question §7 from `PHASE_STATUS_REPORT.md` for `execute.py` specifically (one of three Phase 3 stubs).

---

## 1. Goal and Constraint

Joe's resolution to §7 was Option A, verbatim: **"cognitive layer is self-contained, talks to ComfyUI directly, does not delegate to agent/tools/ at runtime."** This pass produces a design doc for replacing `cognitive/tools/execute.py`'s stub body with a real implementation that posts a workflow to ComfyUI's `/prompt` endpoint, monitors the WebSocket stream for execution events, fetches output filenames from `/history/{prompt_id}`, and returns a populated `ExecutionResult` — without importing anything from `agent.tools.*`. This pass writes only this design doc; the FORGE pass that executes it is a separate session after Joe's review.

---

## 2. Current State (Evidence)

### `cognitive/tools/execute.py` (92 LOC, stub)

The file already has the stable contract that must NOT change: `ExecutionStatus` enum (PENDING, RUNNING, COMPLETED, FAILED, INTERRUPTED, TIMEOUT), `ExecutionResult` dataclass with `status`, `prompt_id`, `outputs`, `elapsed_ms`, `node_timings`, `error`, `retry_count` fields plus `success` and `output_filenames` properties, and `execute_workflow(workflow_data, timeout_seconds, on_progress, on_complete)` function signature. Lines 86-90 hold the stub body that calls `on_complete(result)` with `status = PENDING`. The early-failure branches at lines 69-82 (empty workflow → FAILED with "Empty workflow data"; zero-node workflow → FAILED with "No nodes found in workflow") are already real and should be preserved unchanged.

### `cognitive/transport/events.py` (126 LOC)

Has the parser `execute.py` needs: `ExecutionEvent.from_ws_message(msg, started_at)` classmethod at lines 81-126 takes a raw `{"type": ..., "data": {...}}` dict and returns a typed `ExecutionEvent`. Critical behavior at lines 102-104: when an `executing` event arrives with `node=None`, the parser synthesizes `EventType.EXECUTION_COMPLETE` — this is ComfyUI's native completion signal. Lines 67-74 expose `is_terminal` (True for COMPLETE, ERROR, INTERRUPTED) and lines 76-79 expose `is_error`. Lines 113-115 set `started_at = now` automatically when an `EXECUTION_START` event is parsed. **The execute.py loop should call `ExecutionEvent.from_ws_message(json.loads(raw), started_at=started_at)` once per text frame and exit on `event.is_terminal`** — the parser handles all the type classification.

### `cognitive/transport/interrupt.py` (51 LOC)

Conventions to match: synchronous functions, `httpx` for HTTP (not `httpx.AsyncClient`), explicit `httpx.ConnectError` and `httpx.TimeoutException` catches with friendly error strings, generic `Exception` catch as the last resort. The `interrupt_execution(base_url, timeout)` function returns `(success: bool, message: str)` — execute.py's timeout path will call this exactly: `success, msg = interrupt_execution(base_url=..., timeout=5.0)`. No new HTTP library is needed; the cognitive transport already uses `httpx` synchronously.

### `agent/tools/comfy_execute.py` (REFERENCE — 863 LOC)

Read in detail to extract the ComfyUI HTTP/WS protocol. **Not imported, not copied — clean-room reference only.** Findings:

- **POST URL:** `f"{COMFYUI_URL}/prompt"` with body `{"prompt": workflow_data, "client_id": <uuid>}` and `timeout=30.0` (line 197-201 of comfy_execute.py).
- **POST response (success):** JSON `{"prompt_id": "...", "number": N, "node_errors": {...}}`. The `prompt_id` is the load-bearing identifier; if it's missing or empty, the request was accepted-but-broken and should be treated as FAILED.
- **POST response (4xx with validation errors):** Body contains `node_errors` dict shaped `{"node_id": {"class_type": "...", "errors": [{"message": "..."}]}}`. Lines 217-225 show how the agent reference flattens this into a multi-line error string. The cognitive version should do the same.
- **WebSocket URL:** `f"{ws_scheme}://{COMFYUI_HOST}:{COMFYUI_PORT}/ws?clientId={client_id}"` where `ws_scheme` is `wss` if the HTTP URL is HTTPS, else `ws`. Same `client_id` UUID is used for the POST body and the WS URL — this is how ComfyUI routes events to the right listener.
- **WebSocket library:** `websockets.sync.client.connect(ws_url, close_timeout=5, open_timeout=10)` (line 371). Confirmed installed in `.venv312` as `websockets-16.0`. Sync API. No new dep needed.
- **WebSocket recv:** `ws.recv_bufsize = 16 * 1024 * 1024` (16MB buffer for ComfyUI's preview-image binary frames), `ws.recv(timeout=2.0)` blocks with a 2-second deadline and raises `TimeoutError` on no data. Binary frames are skipped (`if isinstance(raw, bytes): continue`). JSON decode errors are skipped (`try/except json.JSONDecodeError`).
- **Termination signal:** Either an `executing` message with `data.node == None` (success) or an `execution_error` message (failure). The reference also breaks on a synthetic "queue_remaining == 0" status check, which is defensive — the cognitive version doesn't need this because `events.py:102-104` already converts node=None into the synthetic EXECUTION_COMPLETE event.
- **Output collection:** After the terminal event, GET `/history/{prompt_id}` (line 514). Response shape: `{prompt_id: {outputs: {node_id: {images: [{filename, subfolder, ...}], gifs: [{filename, subfolder, ...}]}}}}`. The cognitive version should extract `filename` from each `images[]` and `gifs[]` entry and append to `result.outputs` (where `result.output_filenames` reads them via the existing property).
- **Circuit breaker:** The agent reference uses a module-level `COMFYUI_BREAKER` for fault isolation. The cognitive version explicitly does NOT import this (it's an `agent.*` symbol). Cognitive layer is simpler and accepts that a transient ComfyUI failure produces FAILED status without circuit-breaker memory.

### `cognitive/tools/__init__.py` (26 LOC)

`from .execute import execute_workflow, ExecutionStatus` is the public re-export. **No change needed.** The new implementation keeps the same public surface.

### `tests/test_cognitive_tools.py::TestExecuteWorkflow` (lines 202-222, 4 tests)

```python
class TestExecuteWorkflow:

    def test_empty_workflow(self):
        result = execute_workflow({})
        assert result.status == ExecutionStatus.FAILED
        assert "Empty" in result.error

    def test_no_nodes_workflow(self):
        result = execute_workflow({"metadata": "not a node"})
        assert result.status == ExecutionStatus.FAILED
        assert "No nodes" in result.error

    def test_valid_workflow_returns_pending(self, sample_workflow):
        result = execute_workflow(sample_workflow)
        assert result.status == ExecutionStatus.PENDING
        assert result.prompt_id != ""

    def test_callback_called(self, sample_workflow):
        called = []
        execute_workflow(sample_workflow, on_complete=lambda r: called.append(r))
        assert len(called) == 1
```

Two tests stay (`test_empty_workflow`, `test_no_nodes_workflow`) — the early-failure branches are unchanged. **Two tests need rewriting:** `test_valid_workflow_returns_pending` becomes `test_valid_workflow_executes` (asserts COMPLETED with mocked POST + WS, not PENDING), and `test_callback_called` needs a mocked POST + WS so it doesn't try to hit a real ComfyUI server. The `sample_workflow` fixture is presumed to exist in `conftest.py`; the FORGE pass should reuse it.

---

## 3. Target Behavior

From the caller's perspective, after the FORGE pass:

**Input:**
- `workflow_data: dict[str, Any]` — ComfyUI API format workflow (`{node_id: {class_type, inputs}}`).
- `timeout_seconds: int = 120` — hard ceiling on wall-clock time. Includes POST + WS + history fetch.
- `on_progress: Callable[[ExecutionEvent], None] | None = None` — invoked for every parsed `PROGRESS` event in real time. **Not invoked for non-PROGRESS events** — the design intentionally narrows the callback to progress only, keeping the contract clean. Other event types (EXECUTING, EXECUTED) update internal state but do not surface to the callback.
- `on_complete: Callable[[ExecutionResult], None] | None = None` — invoked **exactly once** with the final result, regardless of success/failure/interrupt path. Guaranteed by a `try/finally` wrapper.

**Side effects:**
1. Generate a fresh UUID4 `client_id`.
2. Open the WebSocket connection to `ws://host:port/ws?clientId={client_id}` BEFORE posting the prompt (so no events are missed in the race window — see §4.2 for justification).
3. POST the workflow to `http://host:port/prompt` with `{"prompt": workflow_data, "client_id": client_id}`.
4. Drain WS messages, parsing each text frame via `ExecutionEvent.from_ws_message(...)`. For each parsed event:
   - PROGRESS → invoke `on_progress(event)` if provided.
   - EXECUTING (with node) → record `current_node` for timing.
   - EXECUTED → record node completion in `node_timings`.
   - EXECUTION_START → mark `started_at` (auto-handled by parser).
   - terminal events (COMPLETE, ERROR, INTERRUPTED) → break the loop.
5. After loop exit, GET `/history/{prompt_id}` and extract output filenames (images + gifs).
6. Construct `ExecutionResult` with real `status`, `prompt_id`, `outputs`, `elapsed_ms`, `node_timings`, and `error`.
7. Invoke `on_complete(result)` exactly once.
8. Return `result`.

**Output:**
- `ExecutionResult` with `status` set to one of COMPLETED, FAILED, INTERRUPTED, TIMEOUT (NOT PENDING — PENDING is removed from the return surface).
- `prompt_id` is the real UUID returned by ComfyUI's POST response (NOT the fake `id(workflow_data):x` form from the stub).
- `outputs` is a list of dicts `{type: "image" | "video", filename: str, subfolder: str}` — matching the agent reference's output shape.
- `output_filenames` (existing property) returns the list of `filename` strings from `outputs`, in insertion order.
- `elapsed_ms` is wall-clock time from POST submission to terminal event.
- `error` is empty string on success, populated with a human-readable message on any failure path.

**Callback ordering guarantee:**
- `on_progress` may be called 0..N times before `on_complete`.
- `on_complete` is always the last callback invocation, called exactly once, with the final `ExecutionResult` instance that is also returned to the caller.
- If both callbacks are `None`, the function still works and returns the result correctly.

---

## 4. Implementation Plan

### 4.1 HTTP POST flow

```python
import os
import json
import time
import uuid

import httpx

# Config — read from env at function-call time, not at module load
def _comfyui_base_url() -> str:
    host = os.environ.get("COMFYUI_HOST", "127.0.0.1")
    port = os.environ.get("COMFYUI_PORT", "8188")
    return f"http://{host}:{port}"

def _comfyui_ws_url(client_id: str) -> str:
    base = _comfyui_base_url()
    ws_scheme = "wss" if base.startswith("https") else "ws"
    rest = base.split("://", 1)[1]
    return f"{ws_scheme}://{rest}/ws?clientId={client_id}"
```

**Why env-at-call-time, not module-level constants:** matches `cognitive/transport/interrupt.py`'s approach (default arg `base_url="http://127.0.0.1:8188"`), and avoids coupling the cognitive layer to `agent.config` (Option A). The FORGE pass may choose to thread `base_url` through the function signature for testability — see §4.5.

**client_id generation:** `client_id = uuid.uuid4().hex` (32 hex chars, unique per call). **Not module-level**, not derived from workflow data — a fresh ID per execution prevents WS event cross-contamination if multiple execute_workflow calls run in the same process.

**POST request:**
```python
post_payload = {
    "prompt": workflow_data,
    "client_id": client_id,
}
with httpx.Client() as client:
    resp = client.post(
        f"{_comfyui_base_url()}/prompt",
        json=post_payload,
        timeout=30.0,
    )
```

**Response handling:**
- `resp.status_code == 200` → parse `resp.json()`, extract `prompt_id`. If `prompt_id` is empty/missing → FAILED with "ComfyUI accepted the workflow but didn't return a job ID."
- `resp.status_code in (400, 422)` → parse `resp.json()`, extract `node_errors`. Format as multi-line error string per the agent reference's pattern (lines 217-225). Status: FAILED.
- Other 4xx/5xx → FAILED with `f"HTTP {resp.status_code}: {resp.text[:300]}"`.
- `httpx.ConnectError` → FAILED with `f"ComfyUI not reachable at {base_url}. Is it running?"`.
- `httpx.TimeoutException` → FAILED with `f"ComfyUI did not respond within 30s"`.
- Generic `Exception` → FAILED with `str(e)`.

### 4.2 WebSocket monitoring loop

**Critical ordering decision:** Open the WebSocket FIRST, then POST. This diverges from the agent reference (which POSTs first, then opens WS). Justification: opening the WS first guarantees we are subscribed BEFORE the prompt is queued, eliminating the race window where EXECUTION_START could fire between the POST and the WS connect. The cost is one extra TCP connection that needs cleanup if the POST fails — handled by a `with websockets.sync.client.connect(...)` context manager so the WS is always closed cleanly.

```python
import websockets.sync.client

client_id = uuid.uuid4().hex
ws_url = _comfyui_ws_url(client_id)
base_url = _comfyui_base_url()

started_at = 0.0
prompt_id = ""
deadline = time.monotonic() + timeout_seconds

with websockets.sync.client.connect(
    ws_url,
    close_timeout=5,
    open_timeout=10,
) as ws:
    ws.recv_bufsize = 16 * 1024 * 1024  # 16MB for preview frames

    # Now post the prompt — WS is already listening
    post_result = _post_prompt(workflow_data, client_id, base_url)
    if post_result.error:
        result.status = ExecutionStatus.FAILED
        result.error = post_result.error
        return _finalize(result, on_complete)
    prompt_id = post_result.prompt_id
    result.prompt_id = prompt_id

    # Drain WS events until terminal
    while time.monotonic() < deadline:
        try:
            raw = ws.recv(timeout=2.0)
        except TimeoutError:
            continue
        if isinstance(raw, bytes):
            continue  # Skip binary preview frames
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue

        event = ExecutionEvent.from_ws_message(msg, started_at=started_at)
        if event.event_type == EventType.EXECUTION_START:
            started_at = event.started_at  # Auto-set by parser

        # Filter to our prompt only — multiple clients may share the WS
        if event.prompt_id and event.prompt_id != prompt_id:
            continue

        if event.event_type == EventType.PROGRESS and on_progress is not None:
            on_progress(event)

        if event.is_terminal:
            if event.event_type == EventType.EXECUTION_COMPLETE:
                result.status = ExecutionStatus.COMPLETED
            elif event.event_type == EventType.EXECUTION_ERROR:
                result.status = ExecutionStatus.FAILED
                result.error = event.data.get("exception_message", "Execution failed (no details)")
            elif event.event_type == EventType.EXECUTION_INTERRUPTED:
                result.status = ExecutionStatus.INTERRUPTED
            break
    else:
        # Loop exited via deadline, not via break → timeout
        from ..transport.interrupt import interrupt_execution
        interrupt_execution(base_url=base_url, timeout=5.0)
        result.status = ExecutionStatus.INTERRUPTED
        result.error = f"Execution did not complete within {timeout_seconds}s — interrupted"
```

The `for/else` Python idiom handles the timeout-without-terminal-event case cleanly: the `else` clause runs only when the `while` loop exits without `break`. The deadline check inside `while` ensures we don't busy-loop on an unresponsive ComfyUI.

### 4.3 Output file collection

After the WS loop exits with COMPLETED status, fetch outputs from `/history/{prompt_id}`:

```python
if result.status == ExecutionStatus.COMPLETED:
    try:
        with httpx.Client() as client:
            hist_resp = client.get(
                f"{base_url}/history/{prompt_id}",
                timeout=10.0,
            )
            hist_resp.raise_for_status()
            history = hist_resp.json()
        if prompt_id in history:
            entry = history[prompt_id]
            for _node_id, node_out in sorted(entry.get("outputs", {}).items()):
                for img in node_out.get("images", []):
                    result.outputs.append({
                        "type": "image",
                        "filename": img.get("filename", ""),
                        "subfolder": img.get("subfolder", ""),
                    })
                for vid in node_out.get("gifs", []):
                    result.outputs.append({
                        "type": "video",
                        "filename": vid.get("filename", ""),
                        "subfolder": vid.get("subfolder", ""),
                    })
    except Exception as e:
        # Output fetch failed but execution succeeded — log via the result, don't fail
        result.outputs = []
        # Status stays COMPLETED — the prompt ran, we just couldn't enumerate outputs
```

**Edge cases handled:**
- Workflow has no SaveImage / SaveAnimatedWEBP nodes → `outputs = []`. Status stays COMPLETED. Not a failure. The `output_filenames` property returns `[]`.
- `/history/{prompt_id}` returns 404 (rare race where history is being written) → outputs stays empty, status stays COMPLETED.
- `/history/{prompt_id}` returns 500 → outputs stays empty, status stays COMPLETED. The execution succeeded; the bookkeeping failed.

`elapsed_ms` is set from `(time.monotonic() - start_monotonic) * 1000.0` where `start_monotonic` is captured immediately before `with websockets.sync.client.connect(...)`.

### 4.4 Error handling matrix

Every error path constructs a `ExecutionResult` and routes through a single `_finalize(result, on_complete)` helper that ensures `on_complete` is called exactly once before returning. Implementation as a `try/finally`:

```python
def execute_workflow(
    workflow_data: dict[str, Any],
    timeout_seconds: int = 120,
    on_progress: Callable | None = None,
    on_complete: Callable | None = None,
) -> ExecutionResult:
    result = ExecutionResult()

    # Early validation (existing logic, unchanged)
    if not workflow_data:
        result.status = ExecutionStatus.FAILED
        result.error = "Empty workflow data"
        return _finalize(result, on_complete)

    node_count = sum(
        1 for v in workflow_data.values()
        if isinstance(v, dict) and "class_type" in v
    )
    if node_count == 0:
        result.status = ExecutionStatus.FAILED
        result.error = "No nodes found in workflow"
        return _finalize(result, on_complete)

    # Real execution (new logic)
    start_monotonic = time.monotonic()
    try:
        _run_execution(
            workflow_data=workflow_data,
            result=result,
            timeout_seconds=timeout_seconds,
            on_progress=on_progress,
            start_monotonic=start_monotonic,
        )
    except Exception as e:
        if result.status not in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.INTERRUPTED,
            ExecutionStatus.TIMEOUT,
        ):
            result.status = ExecutionStatus.FAILED
            result.error = f"Execution failed: {e}"
    finally:
        result.elapsed_ms = (time.monotonic() - start_monotonic) * 1000.0
        _finalize(result, on_complete)

    return result


def _finalize(result: ExecutionResult, on_complete: Callable | None) -> ExecutionResult:
    if on_complete is not None:
        try:
            on_complete(result)
        except Exception:
            pass  # Callback errors must not affect the return value
    return result
```

The `_finalize` helper guarantees `on_complete` fires exactly once. Catching exceptions inside `_finalize` prevents a buggy callback from corrupting the return path. The `try/finally` in `execute_workflow` ensures `_finalize` is called even if `_run_execution` raises an unexpected exception (defense-in-depth — the inner function should catch its own errors but we don't trust it).

**Error matrix (every path produces a typed `ExecutionResult` and calls `_finalize` once):**

| Trigger | Status | Error string |
|---|---|---|
| Empty workflow_data | FAILED | "Empty workflow data" |
| Zero nodes in workflow | FAILED | "No nodes found in workflow" |
| `httpx.ConnectError` on POST | FAILED | f"ComfyUI not reachable at {base_url}. Is it running?" |
| `httpx.TimeoutException` on POST | FAILED | "ComfyUI did not respond within 30s" |
| POST returns 400/422 with node_errors | FAILED | "Validation errors:\n" + multi-line node errors |
| POST returns other 4xx/5xx | FAILED | f"HTTP {code}: {body[:300]}" |
| POST returns 200 but prompt_id is empty | FAILED | "ComfyUI accepted the workflow but didn't return a job ID" |
| WebSocket connection refused | FAILED | f"WebSocket unreachable at {ws_url}" |
| WebSocket `ConnectionClosedError` mid-stream | FAILED | f"WebSocket disconnected: {e}" |
| EXECUTION_ERROR event from WS | FAILED | event.data["exception_message"] |
| EXECUTION_INTERRUPTED event from WS | INTERRUPTED | "" (no error string — interrupt is not an error) |
| EXECUTION_COMPLETE event from WS | COMPLETED | "" |
| Wall-clock timeout exceeded | INTERRUPTED | f"Execution did not complete within {timeout_seconds}s — interrupted" + side effect: `interrupt_execution(base_url, 5.0)` is called |
| Generic exception in `_run_execution` | FAILED | f"Execution failed: {e}" |

### 4.5 Module-level imports

```python
"""execute_workflow — Submit + monitor + evaluate + retry.

Posts a workflow to ComfyUI's /prompt endpoint, monitors the WebSocket
event stream until execution completes (or errors, or times out, or is
interrupted), and returns a structured ExecutionResult with output
filenames, elapsed time, and per-node timing.

The cognitive layer talks to ComfyUI directly — this module does not
import from agent.tools.* or any other agent.* package. ComfyUI host
and port are read from the COMFYUI_HOST and COMFYUI_PORT environment
variables at function-call time (defaults: 127.0.0.1:8188).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

import httpx
import websockets.sync.client
from websockets.exceptions import ConnectionClosedError, WebSocketException

from ..transport.events import EventType, ExecutionEvent
from ..transport.interrupt import interrupt_execution
```

**Imports that stay:** `dataclasses`, `enum`, `typing.Any`, `typing.Callable` (already in the stub).

**New imports added:**
- `json` (parse WS frames)
- `os` (env config)
- `time` (monotonic deadline + elapsed_ms)
- `uuid` (client_id generation)
- `httpx` (POST + history fetch — already a project dep)
- `websockets.sync.client` (sync WS connect — already a project dep, websockets-16.0)
- `websockets.exceptions.ConnectionClosedError`, `WebSocketException` (specific catches)
- `..transport.events.EventType`, `..transport.events.ExecutionEvent` (parser + types)
- `..transport.interrupt.interrupt_execution` (timeout side effect)

**Imports explicitly forbidden by Option A:**
- `from agent.tools.comfy_execute import ...` — never.
- `from agent.config import COMFYUI_HOST, COMFYUI_PORT, COMFYUI_URL` — never. Use `os.environ` directly.
- `from agent.circuit_breaker import COMFYUI_BREAKER` — never. Cognitive layer accepts simpler failure semantics.

### 4.6 Sync vs async — DECISION: stay synchronous

**Decision: keep `execute_workflow` synchronous.** The current public signature is `def execute_workflow(...) -> ExecutionResult` (no `async`). Changing it to `async def` would force every caller — including `cognitive/pipeline/autonomous.py:run()` and any future MCP tool wrapper — to be async-aware, cascading async into the entire cognitive layer. None of the other cognitive modules are async (interrupt.py is sync, mutate.py is sync, the engine is sync), and the autonomous pipeline's `run()` is sync. **Breaking the sync convention to wire one function would propagate async through the whole layer.**

**How sync works for WebSocket:** `websockets.sync.client.connect(...)` returns a sync context manager. `ws.recv(timeout=2.0)` blocks the calling thread for up to 2 seconds, raising `TimeoutError` if no data. The 2-second poll interval is short enough that the wall-clock timeout (default 120s) is checked frequently, and `on_progress` callbacks fire promptly when PROGRESS events arrive. No threading needed. No queue needed. No event loop needed. The whole execution is one synchronous function call from the caller's perspective.

**Trade-off accepted:** the calling thread is blocked for the full execution duration. For the cognitive pipeline this is fine — the pipeline expects to wait for execution before proceeding to the EVALUATE stage anyway. For the MCP tool surface, the caller (Claude) is also blocking on the tool call result, so the sync interface is correct. The only context where async would matter is a hypothetical UI that wants to fire-and-forget execution while staying responsive — and in that case the UI can wrap `execute_workflow` in `asyncio.to_thread` itself without polluting the cognitive layer.

**Reference confirmation:** `agent/tools/comfy_execute.py` is also synchronous and uses the same `websockets.sync.client.connect(...)` pattern (line 371). The cognitive version follows the proven sync pattern; no innovation needed.

---

## 5. Test Plan

The new tests live in `tests/test_cognitive_tools.py::TestExecuteWorkflow`. The class currently has 4 tests; after the FORGE pass it will have ~11 tests (2 preserved + 2 rewritten + 7 new). All tests use mocks via `unittest.mock.patch` — no real ComfyUI server is contacted at any point. **Pattern:** patch `httpx.Client` for the POST and the history fetch, patch `websockets.sync.client.connect` for the WS stream. The mocked WS yields a list of pre-built JSON strings via a custom mock object whose `recv()` method pops from a queue.

| # | Test name | Setup | Assertion |
|---|---|---|---|
| 1 | `test_empty_workflow` | (preserved from current) | status FAILED, "Empty" in error |
| 2 | `test_no_nodes_workflow` | (preserved from current) | status FAILED, "No nodes" in error |
| 3 | `test_execute_happy_path` | mock POST 200 → `prompt_id="abc"`; mock WS yields START → EXECUTING(node="1") → PROGRESS(value=5,max=10) → EXECUTED(node="1") → EXECUTING(node=None); mock history with 1 image | status COMPLETED, prompt_id="abc", output_filenames=["test.png"], on_complete called once |
| 4 | `test_execute_with_progress_callback` | same as #3 + `on_progress` collector | progress_callback called once with the PROGRESS event, event.progress_pct == 50.0 |
| 5 | `test_execute_comfyui_unreachable` | mock POST raises `httpx.ConnectError` | status FAILED, error contains "not reachable", on_complete called once |
| 6 | `test_execute_validation_errors` | mock POST returns 400 with `{"node_errors": {"3": {"class_type": "KSampler", "errors": [{"message": "cfg out of range"}]}}}` | status FAILED, error contains "Validation errors" and "cfg out of range" |
| 7 | `test_execute_timeout` | mock POST 200; mock WS yields nothing (TimeoutError on every recv); `timeout_seconds=1` | status INTERRUPTED, error contains "did not complete within 1s", `interrupt_execution` was called once |
| 8 | `test_execute_error_event` | mock POST 200; mock WS yields START → EXECUTION_ERROR with `data={"exception_message": "OOM"}` | status FAILED, error contains "OOM" |
| 9 | `test_execute_interrupt_event` | mock POST 200; mock WS yields START → EXECUTION_INTERRUPTED | status INTERRUPTED |
| 10 | `test_execute_no_callbacks` | both `on_progress` and `on_complete` are None; mock POST 200 + WS terminal | status COMPLETED, function returns normally, no AttributeError |
| 11 | `test_execute_output_filenames_empty` | mock POST 200; mock WS terminal; mock history with empty `outputs` dict | status COMPLETED, output_filenames == [] |
| 12 | `test_execute_post_returns_no_prompt_id` | mock POST 200 with `{"prompt_id": ""}` | status FAILED, error contains "didn't return a job ID" |
| 13 | `test_execute_websocket_unreachable` | mock POST 200; `websockets.sync.client.connect` raises `OSError` | status FAILED, error contains "WebSocket unreachable" |

**Total: 13 tests** (2 preserved + 11 new). Existing tests `test_valid_workflow_returns_pending` and `test_callback_called` are **deleted** — they assert the stub's behavior and are no longer correct.

The mocking helper for WS streams should be a small `_MockWS` class in `conftest.py` (or inline in the test file) with a `recv(timeout=2.0)` method that pops the next pre-built JSON string from a `collections.deque`, raising `TimeoutError` when the deque is empty. This avoids depending on any specific websockets library mock helper and works for every test that needs to inject a WS sequence.

---

## 6. Backwards Compatibility

**Public surface changes:** None.
- `ExecutionStatus` enum: unchanged.
- `ExecutionResult` dataclass: unchanged (all fields preserved, including `retry_count` which is reserved for future use).
- `execute_workflow` signature: unchanged.
- `cognitive.tools.__init__.py` re-exports: unchanged.

**Behavior changes:** Two.
1. The returned `result.status` is no longer `PENDING` for valid input. It is one of COMPLETED, FAILED, INTERRUPTED, TIMEOUT.
2. The returned `result.prompt_id` is the real ComfyUI-issued prompt UUID, not `f"cognitive_{id(workflow_data):x}"`.

**Tests broken by these changes:** Two — `test_valid_workflow_returns_pending` and `test_callback_called` (the latter only because it relies on the stub being able to "complete" without a real backend; the new mocked version replaces it).

**Cross-module dependencies on the old PENDING return:** `grep "ExecutionStatus.PENDING" cognitive/` should be checked by the FORGE pass — if any module branches on `result.status == PENDING`, that branch is now dead code and needs review. From the architect-pass investigation, I do not believe any such branch exists in `cognitive/pipeline/autonomous.py` (the pipeline checks `result.success`, which only returns True for COMPLETED). The FORGE pass should `grep -rn "ExecutionStatus.PENDING\|status.*PENDING" cognitive/` as a safety check before declaring done.

**No `pyproject.toml` changes.** All required deps (`httpx`, `websockets`) are already in `[project] dependencies` post-Phase-0.5.

---

## 7. Forge Acceptance Criteria

The FORGE pass on Phase 3A is complete when **all** of the following are true:

1. `cognitive/tools/execute.py` is rewritten per §4. Stub comment ("This stub returns PENDING — the caller wires it to comfy_execute") is removed.
2. The fake `prompt_id = f"cognitive_{id(workflow_data):x}"` line is removed.
3. The new module imports list matches §4.5 exactly. Specifically:
   - `from ..transport.events import EventType, ExecutionEvent` is present.
   - `from ..transport.interrupt import interrupt_execution` is present.
   - `import websockets.sync.client` is present.
   - **No** `from agent` or `import agent` line anywhere in the file.
4. `tests/test_cognitive_tools.py::TestExecuteWorkflow` has 13 tests per §5. The two old tests that depend on PENDING are removed; the two preserved tests are unchanged; 11 new tests are added.
5. `python -m pytest tests/test_cognitive_tools.py::TestExecuteWorkflow -v` reports 13 passed in <5 seconds.
6. `python -m pytest tests/ --tb=no -q` reports a passing count of **2673 + (13 - 4) = 2682** (or higher if other Phase 3 tests improve as a side effect, but no regressions).
7. `grep -n "TODO\|FIXME\|HACK\|stub\|placeholder\|NotImplementedError" cognitive/tools/execute.py` returns zero matches (case-insensitive sweep — completeness check per C4).
8. `grep -n "from agent\|import agent" cognitive/tools/execute.py` returns zero matches (Option A constraint).
9. `grep -rn "ExecutionStatus.PENDING" cognitive/` returns zero matches (PENDING is removed from the cognitive layer's vocabulary — the enum value still exists as a placeholder for future use, but no code paths reach it).
10. The runtime smoke test from a fresh shell: `python -c "from cognitive.tools.execute import execute_workflow, ExecutionStatus; r = execute_workflow({}); assert r.status == ExecutionStatus.FAILED; print('OK')"` prints `OK`.

If any of these fail, the FORGE pass STOPS per C3 (3 retries max) and files BLOCKER.md.

---

## 8. Risks and Unknowns

### Risk A — `websockets.sync.client.recv(timeout=...)` semantics

The `websockets` library's sync API surface is sparsely documented. The agent reference uses `ws.recv(timeout=2.0)` and catches `TimeoutError` (line 376-379), implying the timeout argument is supported and raises a builtin `TimeoutError` (not a websockets-specific exception). I verified the agent reference uses this pattern, but I did NOT independently confirm the websockets-16.0 sync API supports `recv(timeout=...)` — it's possible the library version matters and 16.0 has a different signature than the agent reference was written against.

**Resolution path for FORGE:** First test run will catch this. If `recv` doesn't accept `timeout`, fall back to a per-iteration `select()` or use `ws.recv()` without timeout but inside a thread that's signaled by a deadline timer. **My best guess is the timeout arg works** — agent/tools/comfy_execute.py is currently in the 2673-passing baseline, so the pattern is verified at least under the test mocks.

### Risk B — Mocking `websockets.sync.client.connect` is non-trivial

The websockets sync client is a context manager that returns a connection object with `recv()`, `send()`, `close()`, and a `recv_bufsize` attribute. Mocking it requires either (a) a custom `_MockWS` class that implements all the methods used by execute.py, or (b) `unittest.mock.patch` of `websockets.sync.client.connect` returning a `MagicMock` whose `__enter__` returns a configurable mock connection. **Approach (a) is more explicit and easier to read** — the FORGE pass should write a small `_MockWS` helper class, even if it's only ~30 lines. The agent test suite (tests/test_comfy_execute.py) likely already does this; the FORGE pass can crib from that pattern without importing it.

**My best guess:** straightforward, but the FORGE pass should expect to spend ~30% of its time on mock plumbing rather than the execute.py rewrite itself.

### Risk C — The `for/else` deadline pattern requires careful test mocking

The §4.2 design uses Python's `while/else` idiom: the `else` clause runs only when the loop exits via the `while` condition becoming false (deadline expired) rather than via `break` (terminal event). This is correct Python but easy to get wrong, and tests need to exercise both paths. **`test_execute_timeout` (test #7 in §5) is the canary** — if it passes, the deadline path works. If `test_execute_happy_path` passes but `test_execute_timeout` fails, the `for/else` is wrong.

**Resolution:** The FORGE pass should write `test_execute_timeout` early and verify the deadline path before completing the rest of the implementation. This is a self-checking design — the test catches the error before any other code is touched.

### Risk D — `interrupt_execution` may itself fail during the timeout cleanup

If `interrupt_execution(base_url, 5.0)` fails (because ComfyUI is also unreachable, which is the condition that triggered the timeout in the first place), the cognitive `execute.py` doesn't care — `interrupt_execution` already catches its own exceptions and returns `(False, error_str)`. The cognitive code calls it and ignores the return value (we already know we're returning INTERRUPTED). **This is fine.** Worth flagging only because a future code reviewer might wonder why we don't check the interrupt return value.

### Risk E — ComfyUI WebSocket may emit events for ALL clients on the same connection

ComfyUI's WS broadcasts events tagged with `client_id`. The §4.2 design filters events to `event.prompt_id == prompt_id` (skipping events from other prompts that share the same WS connection). This is defensive — in single-user development, only one prompt is in flight at a time and the filter is a no-op. In production with multiple concurrent calls (rare for the cognitive layer, more common for the panel), the filter ensures no cross-talk.

**Resolution:** Filter is included in the design. The FORGE pass should preserve it. The test for it is implicit — `test_execute_happy_path` passes a single prompt_id and the mock WS only emits events with that prompt_id, so the filter is exercised in the affirmative case.

### Risk F — The `recv_bufsize` attribute may be a property, not an assignable field

`ws.recv_bufsize = 16 * 1024 * 1024` works in the agent reference, so it's at least supported in the version of websockets agent uses. If websockets-16.0 changed it to a read-only property, this assignment will raise `AttributeError`. **My best guess is it still works** (the agent reference is in the passing baseline). If not, the FORGE pass can either drop the assignment (it's an optimization, not load-bearing — the default bufsize is 1MB and ComfyUI preview frames can be larger but they're skipped anyway via `if isinstance(raw, bytes): continue`) or pass `max_size=16*1024*1024` to `connect()` instead.

### Risk G — The 2-second `recv` timeout interacts with the wall-clock deadline

If `timeout_seconds=10` and `recv(timeout=2.0)` is called every 2 seconds, the deadline check fires every 2 seconds and the loop can exit cleanly within ~2 seconds of the deadline. For `timeout_seconds=120`, the resolution is fine. For `timeout_seconds=1` (used in `test_execute_timeout`), the loop fires `recv(timeout=2.0)` once, which itself takes 2 seconds, then checks the deadline and exits. **The test will see ~2-second elapsed time even though `timeout_seconds=1`.** This is acceptable behavior but the test needs to assert on `INTERRUPTED` status, not on elapsed time precision.

**Resolution:** test #7 in §5 asserts on status only, not elapsed time. The FORGE pass should NOT add an elapsed-time assertion to the timeout test.

---

## 9. Out of Scope

This pass and the FORGE pass that executes it do NOT address:

- `cognitive/tools/dependencies.py` — separate Phase 3B session.
- `cognitive/tools/research.py` — separate Phase 3C session.
- `cognitive/pipeline/autonomous.py` — Phase 6 verification is a separate pass.
- Any change to `cognitive/transport/events.py` — the parser is sufficient as-is. Even if WS event coverage is incomplete (e.g., the synthetic EXECUTION_COMPLETE may need refinement), the FORGE pass on execute.py does NOT extend events.py. If a missing event surfaces during testing, flag it as a follow-up; don't fix it inline.
- Any change to `cognitive/tools/__init__.py` — the public API is stable.
- Any change to `pyproject.toml` — `httpx` and `websockets` are already declared.
- Any change to `agent/tools/comfy_execute.py` — read-only reference, never edited.
- Any retry logic. `ExecutionResult.retry_count` exists in the dataclass but the Phase 3A implementation never increments it. Retry is a future enhancement that lives at the pipeline layer (`cognitive/pipeline/autonomous.py`'s `config.max_retries`), not at the execute layer.
- Any caching of POST/history responses.
- Any node_timing population beyond what the WS event stream provides naturally. The current `ExecutionResult.node_timings` field can stay empty for the Phase 3A implementation; populating it is a polish step that can land later.
- HTTPS/TLS testing. The design supports `wss://` if the COMFYUI_HOST resolves to an HTTPS URL, but the tests use `ws://` mocks only.

---

## 10. Open Questions for Joe

These are decisions that should be answered before the FORGE pass begins. None of them block the design — the FORGE pass can proceed with my proposed defaults — but Joe's input would tighten the implementation.

### Q1 — Should the cognitive `execute_workflow` honor a different env var than `COMFYUI_HOST`/`COMFYUI_PORT`?

The agent layer reads `COMFYUI_HOST` and `COMFYUI_PORT` from `agent.config`, which loads from `.env`. The cognitive layer has no equivalent config module (and shouldn't, per Option A's "no agent.* imports"). My §4.1 proposal reads `os.environ.get("COMFYUI_HOST", "127.0.0.1")` directly, which means the same `.env` file populates it (since `python-dotenv` is already loaded by the agent's startup). **This works in practice, but couples cognitive to the agent's `.env` loading order.** Alternative: define `COGNITIVE_COMFYUI_HOST` / `COGNITIVE_COMFYUI_PORT` as cognitive-specific env vars to fully decouple. **My recommendation: stay with `COMFYUI_HOST`/`COMFYUI_PORT`** — single source of truth, no duplication. But it's worth confirming you don't want cognitive-specific overrides.

### Q2 — Should `execute_workflow` accept a `base_url` parameter for testability?

Reading env vars from inside the function makes mocking awkward (tests have to `monkeypatch.setenv`). An alternative signature is:

```python
def execute_workflow(
    workflow_data: dict[str, Any],
    timeout_seconds: int = 120,
    on_progress: Callable | None = None,
    on_complete: Callable | None = None,
    base_url: str | None = None,  # NEW — defaults to env-derived value
) -> ExecutionResult:
```

When `base_url` is None, the function reads from env. When provided, it uses the explicit value. **This is a public API change** (added optional parameter), which arguably violates §6's "no public surface changes." But the parameter is fully optional and backward-compatible. **My recommendation: add the parameter**, because the test plan in §5 needs to inject mock URLs and the cleanest way is via an explicit parameter. Confirm or override.

### Q3 — Default `timeout_seconds` value

The current stub uses `timeout_seconds: int = 120`. The agent reference uses `timeout: float = 300` for `_execute_with_websocket` (5 minutes). 120 seconds is too short for SDXL+upscale workflows; 300 is more realistic. **My recommendation: bump the default to 300** to match the agent reference, since the cognitive layer is talking to the same ComfyUI instance and the same workloads. This is a behavior change but a safe one (more time, not less). Confirm or override.

### Q4 — How should `node_timings` be populated?

The `ExecutionResult.node_timings: dict[str, float]` field is in the dataclass but the Phase 3A implementation doesn't populate it. The agent reference tracks per-node timings via the EXECUTING events (start time on transition to a new node, end time on transition to the next). **My recommendation: leave node_timings empty in Phase 3A** to keep the implementation focused, then add it as a Phase 3A.1 polish step. The data is preserved in the WS event stream and can be reconstructed later. Confirm or override (i.e., "no, populate it now").

### Q5 — `_MockWS` location

The test plan uses a `_MockWS` helper class. Should it live in:
- (a) `tests/test_cognitive_tools.py` directly (private to the test file)
- (b) `tests/conftest.py` as a shared fixture (reusable by future cognitive tests)
- (c) `tests/_helpers/mock_ws.py` (a new helpers module)

**My recommendation: (a)** — keep it private to the test file for now, and promote it to (b) or (c) only if a second test file needs the same helper. YAGNI applies here. Confirm or override.

### Q6 — Should the `for/else` deadline pattern be replaced with an explicit flag?

Some Python style guides discourage `while/else` because it's easy to misread. An alternative:

```python
exited_via_terminal = False
while time.monotonic() < deadline:
    # ... loop body ...
    if event.is_terminal:
        # ... set status ...
        exited_via_terminal = True
        break

if not exited_via_terminal:
    # timeout path
    interrupt_execution(...)
    result.status = ExecutionStatus.INTERRUPTED
```

This is more verbose but more obvious. **My recommendation: use `while/else`** — it's a 30-year-old Python idiom and reads correctly to anyone familiar with the language. The flag-based version is fine if you prefer it, but it adds 4 lines for no behavioral difference. Confirm or override.

---

## Architect Sign-Off

Design complete. No code written. No tests run. No git operations performed. Awaiting Joe's review and answers to §10 (Q1-Q6) before the FORGE pass begins.

The design is concrete enough that the FORGE pass can execute it without making new architectural decisions, modulo the six open questions above. My defaults for Q1-Q6 are documented inline; if Joe accepts them silently the FORGE pass proceeds with those defaults.
