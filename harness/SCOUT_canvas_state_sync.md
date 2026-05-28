# SCOUT — Canvas State Sync

**Question:** Does the agent loop reconcile against live ComfyUI state BEFORE
it mutates a workflow, or does it patch from a cached/assumed graph?

**Method:** Read-only file:line evidence. No fixes proposed.

---

### Paths

- Patch module: `agent/tools/workflow_patch.py` (965 lines)
- API client:  `agent/tools/comfy_api.py` (452 lines)
- Sidebar transport (push-from-frontend, not in agent loop):
  `ui/server/routes.py`, `panel/server/routes.py`, `panel/server/chat.py`
- MCP transport (no reconcile path at all): `agent/mcp_server.py`

The capsule's "agent/workflow_patch.py / comfy_api.py" referent resolves to the
above. Both live under `agent/tools/`.

---

### Decisive Trace

Entry point → mutation target → variable origin:

1. `apply_workflow_patch` schema declared at `agent/tools/workflow_patch.py:149`.
2. Dispatch: `handle()` at `agent/tools/workflow_patch.py:889`, branch at
   `:897-898` → calls `_handle_apply_patch`.
3. Handler body: `_handle_apply_patch` at `agent/tools/workflow_patch.py:405`.
4. Mutation target — two write-paths, both touch the cache:
   - Engine path: `_sync_state_from_engine()` at `:457`, which assigns
     `_get_state()["current_workflow"] = engine.to_api_json()` at `:85`.
   - jsonpatch fallback: `_get_state()["current_workflow"] = jp.apply(...)`
     at `:466`.
5. `_get_state()` is `get_session(current_conn_session())` at `:54-56` —
   per-connection `WorkflowSession`, ContextVar-scoped.
6. The cached `current_workflow` is set in exactly three external sources:
   - **File on disk** via `_load_workflow()` at `:134`:
     `_get_state()["current_workflow"] = copy.deepcopy(api_nodes)` where
     `api_nodes` comes from `path.read_text(encoding="utf-8")` at `:104`.
   - **Frontend push** via `load_workflow_from_data(data, source)` at
     `:921`, with assignment at `:944`. Caller is the sidebar/panel
     WebSocket handler (see Drift Detection below). The agent never calls
     this itself.
   - **Undo / reset** internal transitions (`:538`, `:634`).
7. No code in the `_handle_apply_patch` → mutation chain calls any
   ComfyUI-fetch function. There is no GET against the live editor state
   on the path between "patches received" and "cache mutated."

Conclusion of trace: the variable being mutated has a single origin per
session — the most recent of {file load, frontend push, prior internal
mutation}. It is not reconciled at mutation time.

---

### Sub-Questions

1. **Getter exists?** NO. | `agent/tools/comfy_api.py:41-157` declares the
   full `TOOLS` list — `is_comfyui_running`, `get_all_nodes`, `get_node_info`,
   `get_system_stats`, `get_queue_status`, `get_history`. Underlying REST
   surfaces touched: `/system_stats` (`:198`), `/object_info` (`:232`, `:286`,
   `:291`), `/queue` (`:363`), `/history` (`:386`, `:388`). None of these
   return the live editor canvas. ComfyUI's server does not expose canvas
   state via REST — the canvas lives in the browser editor and only crosses
   the wire when the frontend POSTs `/prompt` (execution) or, in this repo,
   when sidebar/panel WebSockets push the workflow as a chat-message payload.
   The only canvas-shaped intake is `load_workflow_from_data` at
   `agent/tools/workflow_patch.py:921`, which is a passive sink, not a fetcher.
   | Confidence: HIGH.

2. **Getter called in patch path?** NO. | `_handle_apply_patch` at
   `agent/tools/workflow_patch.py:405-493` contains zero ComfyUI HTTP calls.
   It reads `_get_state()["current_workflow"]` at `:440`, snapshots for undo
   at `:443`, optionally routes through `engine.mutate_workflow` at `:452`,
   and otherwise applies `jsonpatch.JsonPatch(patches).apply(...)` at `:465-466`.
   No `_get(...)`, no `httpx.Client().get(...)`, no `load_workflow_from_data`
   invocation. | Confidence: HIGH.

3. **Diff vs. overwrite?** Patches are RFC6902 deltas against the CACHED
   graph, not against live state. | `agent/tools/workflow_patch.py:465-466`:
   `jp = jsonpatch.JsonPatch(patches); _get_state()["current_workflow"] =
   jp.apply(_get_state()["current_workflow"])`. The "total changes from
   base" report at `:491` diffs cache-vs-cache (`base_workflow` vs
   `current_workflow`), not cache-vs-live. When a fresh workflow arrives via
   `load_workflow_from_data`, it is a wholesale replace —
   `_get_state()["base_workflow"] = copy.deepcopy(nodes)` at `:943` and
   undo history reset to `deque(maxlen=_MAX_HISTORY)` at `:946`. |
   Confidence: HIGH.

4. **Drift detection?** PARTIAL — and not inside the agent. | The sidebar
   transport at `ui/server/routes.py:130-152` (`_inject_workflow`) hashes the
   pushed payload (`wf_hash = hash(_to_json(workflow_data))` at `:138`),
   compares against `conv._workflow_hash` at `:140`, and only re-loads when
   the hash differs (`:146-150`). This catches drift *only when the
   frontend re-pushes*. Same shape mirrored in `panel/server/chat.py:154`
   and `panel/server/routes.py:171`. The agent itself never polls for a
   hash or timestamp; `_ensure_loaded` at `agent/tools/workflow_patch.py:88-92`
   only checks presence. When the agent is invoked via MCP
   (`agent/mcp_server.py`), there is NO push surface and NO drift detection
   — grep on that file returned no matches for `load_workflow_from_data`,
   `reconcile`, `inject`, or any equivalent. | Confidence: HIGH.

5. **Cache location + invalidation?** | **Location:**
   `WorkflowSession._state["current_workflow"]`, accessed by
   `_get_state()` at `agent/tools/workflow_patch.py:54-56`; scoped per
   connection via the `_conn_session` ContextVar (`agent/_conn_ctx.py`
   referenced at import). Each MCP client, each sidebar conversation, and
   each CLI session gets its own slot.
   **Invalidation triggers (exhaustive):**
   - `_load_workflow()` from file — `:134`
   - `load_workflow_from_data()` from sidebar/panel push — `:944`, gated by
     hash mismatch at `ui/server/routes.py:140-146`
   - `_handle_undo()` pops history — `:538`
   - `_handle_reset()` reverts to `base_workflow` — `:634`
   - `_sync_state_from_engine()` after engine mutation — `:85`
   - Engine rebuild after fallback patch — `:473`
   There is no time-based, version-based, or server-poll-based
   invalidation. The cache is only refreshed by an external write into
   the session. | Confidence: HIGH.

---

### VERDICT

**mutate-from-cache** (with a partial, frontend-driven mitigation that lives
outside the agent loop).

The patch handler at `agent/tools/workflow_patch.py:405` mutates
`_get_state()["current_workflow"]` directly, with no fetch against ComfyUI
between the patch arriving and the cache changing — and ComfyUI itself
exposes no "current canvas" endpoint (`agent/tools/comfy_api.py:41-157`
enumerates the full GET surface: `/system_stats`, `/object_info`, `/queue`,
`/history`). The only reconcile mechanism is a per-message hash-diff push
from the sidebar at `ui/server/routes.py:130-152`, which is transport-layer,
not agent-layer, and is entirely absent when the agent runs via MCP
(`agent/mcp_server.py` has no equivalent injection path).

---

### OPEN ITEMS

- `panel/server/{routes.py,chat.py}` mirror the sidebar push pattern; verified
  the call site but did not trace the full per-conversation lifecycle there.
- `agent/engine/comfyui_adapter.py:11` carries the comment "not execution,
  and live outside the engine surface by design." Worth a future scout to
  understand what that engine boundary intends to model.
- `cognitive/core/graph.CognitiveGraphEngine` is imported and used as the
  primary mutation surface when available (`agent/tools/workflow_patch.py:29`,
  `:452`). It was not opened in this pass — it may track its own notion of
  state that's relevant to a future reconcile design.
- `ConversationState._workflow_hash` lifecycle across WebSocket reconnects
  was not traced. If the conversation persists but `_workflow_hash` is
  reset on reconnect, the first message after reconnect will force a
  re-inject; if not, stale-cache windows may exist. Out of scope here.
- `stage/model_registry.py:218 reconcile()` matched the grep but is about
  MODEL declared-vs-installed reconciliation, not workflow/canvas. Noted
  to disambiguate; not relevant to this question.
