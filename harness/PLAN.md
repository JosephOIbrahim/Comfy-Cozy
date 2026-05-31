# PLAN — Write-Back v1 (Tier 1+2) to the live ComfyUI canvas

PASS 3 (DECOMPOSE). Built from PASS 2 CAPSULE + SPEC predicates + A2 verifier
binding.

Substrate scope reminder:
- `panel/web/js/**` **MODIFY**
- `panel/server/**` **MODIFY** (new `touched.py`, additions to `routes.py`)
- New JS verifier root (`package.json`, `vitest.config.js`, `tests/panel/**`) **CREATE**
- `agent/tools/workflow_patch.py` **CALL-ONLY** — *zero changes* (touched-set
  tracking lives in `panel/server/touched.py`, not in workflow_patch)
- `agent/mcp_server.py` **NO-TOUCH** (P7)
- Upstream LiteGraph / ComfyUI **CALL-ONLY** (never patch)

---

## Plan Tree

```
ROOT: write-back v1 — agent deltas reach the canvas as a touched-only delta-merge

L-0  Vitest stack stand-up                       [pre-leaf per A2; blocks all L1-L10]
│
├─ L-7  Surface-report accumulator               [unblocks L-3, L-4, L-5]
│
├─ L-1  Touched-set tracking (panel/server)      [F-1, P2]
│  └─ L-2  Frontend touched-set consumer         [dep: L-1]
│
├─ L-6  Observer-pause + try/finally + debounce  [F-4, F-5, P4 — independent]
│
├─ L-3  ID-shape shim + parse surfacing          [F-2, P5; dep: L-7]
├─ L-5  Malformed-shape guard                    [F-6; dep: L-7]
├─ L-4  Tier-3 detection                          [F-3, P3-a; dep: L-2, L-7]
│
├─ L-8  Link-delta diff + apply (LiteGraph)      [P1, P6; dep: L-2,3,4,5]
│  └─ L-9  Disconnect-source resolution          [SUBSUMED into L-8]
│
├─ L-10  Integration parity check                 [P1 L3; dep: L-0..L-8]
└─ L-11  Panel-only honored                       [P7; L0 git-diff; independent]
```

---

## Predicate / finding coverage matrix

| ID | Predicate / finding | Leaf | Verifier |
|---|---|---|---|
| P1 (parity, applied ops) | L-8 + L-10 | L1, L3 |
| P2 (delta-merge / no-clobber) | L-1 + L-2 | L1 |
| P3-a (Tier-3 surface) | L-4 + L-7 | L1, L3 |
| P3-b (stale node ref surface) | L-3 + L-7 | L1, L3 |
| P3-c (missing slot surface) | L-5 + L-7 | L1, L3 |
| P4 (no echo) | L-6 | L2 |
| P5 (ID-shape) | L-3 | L1 |
| P6 (disconnect correctness) | L-8 (LiteGraph self-sufficient) | L1 |
| P7 (panel-only) | L-11 | L0 |
| F-1 clobber race | L-1 + L-2 | L1 |
| F-2 NaN IDs | L-3 | L1 |
| F-3 Tier-3 leak | L-4 | L1 |
| F-4 observer-pause leak | L-6 | L2 |
| F-5 concurrent push race | L-6 (debounce + module-level save) | L4 |
| F-6 malformed shape | L-5 | L1 |
| F-7 cross-mode visibility | OUT-OF-SCOPE (PASS 5 may surface) | — |
| F-8 backend unreachable | OUT-OF-SCOPE (nice-to-have) | — |

---

## Leaves (execution order: risk-reduction → dependency-unblock → cost)

### L-0 — Vitest stack stand-up · (A2 pre-leaf)

**Files (CREATE):**
- `package.json` — minimal: `{name, version, type: "module", scripts: {test: "vitest run"}, devDependencies: {vitest: "^1.x"}}`
- `vitest.config.js` — points test dir at `tests/panel/`, optional alias `@panel → panel/web/js/`
- `tests/panel/_stubs/litegraph.js` — exports `makeFakeGraph()` returning a stub `app.graph` with `getNodeById`, `removeLink`, and node-level `connect(slot, target_node, target_slot)`, `disconnectInput(slot)`, `disconnectOutput(slot, target?)`, `widgets[]`, `inputs[]`
- `tests/panel/_stubs/app.js` — exports stub `app` so `import { app } from "..."` resolves under test
- `tests/panel/sample.test.js` — trivial assertion to prove the stack runs

**Contract.** `npm install` succeeds offline-friendly; `npm test` runs Vitest;
sample test passes. Stubs match the LiteGraph API shape the production code
will call.

**Verifier.** `npm test` exits 0; sample test reports 1 pass.

**Dependencies.** none.

**Risk.** Low. Vitest is mature; ~30 min infra.

---

### L-7 — Surface-report accumulator · (A5 plumbing, P3 dependency)

**Files (MODIFY):**
- `panel/web/js/superduperPanel.js` — new module-level `_deltaFailures: []`;
  helpers `_addDeltaFailure(entry)`, `getDeltaFailures()`, `_clearDeltaFailures()`
- `panel/web/js/graphMode.js:319-426` — extend `_refreshStatusBar` to append
  a warning row when `getDeltaFailures().length > 0`; "Details" button opens
  a modal listing entries with type / node_id / input / reason

**Contract.** Any caller can push a `{type, node_id?, input_name?, raw_value?,
reason?}` entry. Status bar surfaces a single rolled-up warning
(`"N delta(s) not applied"` with action button). Modal renders the full list.
Entries cleared on successful next-push or on user dismissal.

**Verifier (L1).** Unit tests: push 3 entries → `getDeltaFailures().length === 3`;
clear → empty. (Status-bar render covered by L-3 / L-4 / L-5 / L-10 integration.)

**Dependencies.** L-0.

**Risk.** Low. Pattern matches existing `_refreshStatusBar` warning shape.

---

### L-1 — Touched-set tracking (panel/server) · (F-1, P2)

**Files (CREATE):**
- `panel/server/touched.py` — per-session module:
  - `record_last_pushed(session_id, workflow)` snapshots the workflow at the
    moment of a successful push (called via new `/comfy-cozy/ack-push`)
  - `compute_touched(session_id, current_workflow)` returns
    `list[{node_id, input_name, kind: "widget"|"link", old_value, new_value}]`
    as the diff between current_workflow and the last-pushed snapshot
  - `clear_session(session_id)` — drop snapshot (on conn close / reset / load)
  - Storage: in-memory `dict[session_id → workflow_snapshot]`, threading.Lock

**Files (MODIFY):**
- `panel/server/routes.py` — add `/comfy-cozy/get-workflow-api-with-touched` GET
  endpoint returning `{workflow, touched}` (calls
  `get_current_workflow()` + `compute_touched(session_id, workflow)`); add
  `/comfy-cozy/ack-push` POST endpoint that calls `record_last_pushed`.
- Hook `clear_session` from existing `/comfy-cozy/load-workflow-data` (after
  load), `/comfy-cozy/reset` (after reset), and chat WebSocket disconnect
  (`panel/server/chat.py:459-462` finally block).

**Contract.** `compute_touched` reports exactly the slots that differ between
current_workflow and the last-pushed snapshot. First call after a load returns
empty touched (snapshot = base). `record_last_pushed` updates snapshot
atomically. `clear_session` drops snapshot — next compute_touched returns
all slots (full sync).

**Verifier (L1).** Python unit tests at `tests/test_touched.py`:
- mutate current_workflow widget → touched has 1 widget entry with
  old/new values
- mutate link → touched has 1 link entry
- ack-push → next compute_touched is empty
- clear_session → next compute_touched returns all populated slots

**Dependencies.** None on the JS side; works with Python pytest stack already
present.

**Risk.** Medium. The "first push after load" edge case (snapshot = base ≠
canvas state if canvas-sync POST happened in between) is the subtle part.
Mitigation: hook `clear_session` to load events too.

**SPEC alignment note.** Zero changes to `agent/tools/workflow_patch.py`.
Touched-set computation is pure-additive in `panel/server/`. The "CALL-ONLY"
status of the server-side workflow ops is preserved.

---

### L-2 — Frontend touched-set consumer · (F-1, P2)

**Files (MODIFY):**
- `panel/web/js/agentClient.js` — add `getWorkflowApiWithTouched()`,
  `ackPush()`
- `panel/web/js/superduperPanel.js` — replace `client.getWorkflowApi()` call
  in `pushAgentToCanvas` at `:96`; iterate `touched` not `Object.entries(workflow)`;
  call `ackPush()` after successful push (in the finally that also restores
  the observer)

**Contract.** Push iterates touched entries only. Untouched canvas slots are
**never** read or written — the SPEC's no-clobber predicate (P2) is enforced
at the iteration level, not at the diff-check level. Existing widget-diff
check at `:107` is kept as defense-in-depth.

**Verifier (L1).** Stub `client.getWorkflowApiWithTouched` returning a
fixture; assert canvas mutation count == touched length; assert no
mutation on slots absent from touched. Cover the F-1 race fixture:
director edited slot X at T=0; agent delta touches slot Y; touched =
[{Y}]; assert X.value preserved.

**Dependencies.** L-0, L-1.

**Risk.** Low. Pure consumer change.

---

### L-6 — Observer-pause + try/finally + debounce · (F-4, F-5, P4)

**Files (MODIFY):**
- `panel/web/js/superduperPanel.js`:
  - Module-level `_originalOnAfterChange = null` set on first `setupCanvasSync`
    call (and only then — re-init is a no-op)
  - `_pauseObserver()` / `_restoreObserver()` helpers using
    `_originalOnAfterChange` as canonical source
  - `pushAgentToCanvas` wraps mutations in `try { _pauseObserver(); ... }
    finally { _restoreObserver(); }`
  - Debounce wrapper on the `comfy-cozy:workflow-changed` event handler
    at `:138`: coalesce events within a 100 ms window into one push

**Contract.** After any push outcome (success, throw, partial), the canvas
observer is the original handler. Rapid event bursts produce at most one
push per 100 ms window.

**Verifier (L2).** Property: for any sequence of (push-success ∪ push-throw),
the post-sequence observer equals the original. **L4 stress:** fire 100
events in 50 ms; assert ≤ 1 actual push executed; assert observer canonical
after settle.

**Dependencies.** L-0.

**Risk.** Low–medium. JS event/timer edge cases (especially around throw
inside debounced callback) need care. Tests cover.

---

### L-3 — ID-shape shim + parse surfacing · (F-2, P5)

**Files (MODIFY):**
- `panel/web/js/superduperPanel.js`:
  - new helper `parseNodeId(raw) → {ok: bool, id?: number, raw}`; on
    `Number.isNaN(parseInt(raw,10))` returns `{ok:false, raw}`
  - Replace `parseInt(nodeId, 10)` at `:101` and `:125` with `parseNodeId`
  - On `!ok`, call `_addDeltaFailure({type:"malformed", node_id: raw,
    reason:"non-numeric id"})` and skip

**Contract.** Numeric-string IDs parse and apply as today. Non-numeric IDs
surface as malformed P3 entries — never silently dropped.

**Verifier (L1).** Unit: feed `"5"` → ok=true id=5; feed `"my-node"` →
ok=false, raw="my-node"; feed `""` → ok=false. Stub call: assert
`_addDeltaFailure` called once per non-numeric ID.

**Dependencies.** L-0, L-7.

**Risk.** Low.

---

### L-5 — Malformed-shape guard · (F-6, P3-c)

**Files (MODIFY):**
- `panel/web/js/superduperPanel.js`:
  - new helper `classifyInputValue(v) → "scalar" | "link" | "malformed"`:
    - scalar: not `Array.isArray(v)`
    - link: `Array.isArray(v) && v.length===2 && typeof v[0]==="string"
      && typeof v[1]==="number"`
    - malformed: everything else
  - per-touched iteration uses `classifyInputValue` to route to widget-write,
    link-write, or `_addDeltaFailure({type:"malformed", node_id, input_name,
    raw_value: v})`

**Contract.** Only well-shaped values are written. Malformed shapes are
surfaced, not silently filtered.

**Verifier (L1).** Unit: feed `7` → scalar; feed `["7", 0]` → link; feed
`["7"]` → malformed; feed `[7, 0]` → malformed (first elem not string);
feed `null` → malformed.

**Dependencies.** L-0, L-7.

**Risk.** Low.

---

### L-4 — Tier-3 detection · (F-3, P3-a)

**Files (MODIFY):**
- `panel/web/js/superduperPanel.js`:
  - new helper `detectTier3(serverWorkflow, canvasGraph) → {add: [], delete: []}`
    - `add`: server has node_id not on canvas
    - `delete`: canvas has node_id not in server
  - `pushAgentToCanvas` calls `detectTier3` first; for each entry calls
    `_addDeltaFailure({type:"tier3_add"|"tier3_delete", node_id, class_type?})`
  - Per-touched iteration only processes ids in the intersection

**Contract.** Tier-3-shaped deltas detected and surfaced. The per-node
mutation loop never sees Tier-3 entries.

**Verifier (L1).** Unit: fixture server={1,2,3}, canvas={1,2,4} →
add=[3], delete=[4]; assert `_addDeltaFailure` called twice with correct
types.

**Dependencies.** L-0, L-2, L-7.

**Risk.** Low.

---

### L-8 — Link-delta diff + apply via LiteGraph · (P1, P6)

**Files (MODIFY):**
- `panel/web/js/superduperPanel.js`:
  - `_pushLinkConnect(fromNode, fromOutput, toNode, toInputName)` calls
    `fromNode.connect(fromOutput, toNode, toInputName)`; on falsy return
    `_addDeltaFailure({type:"link_rejected", ...})`
  - `_pushLinkDisconnect(toNode, toInputName)` calls
    `toNode.disconnectInput(toInputName)` — LiteGraph self-sufficient for
    source resolution (P6)
  - Per-touched link entry: determine connect vs disconnect from
    `{old_value, new_value}` (old non-null + new null → disconnect; old
    null + new non-null → connect; both non-null but different → disconnect
    then connect)

**Contract.** Touched link entries map to LiteGraph calls; rejections surface;
disconnect uses the API's self-sufficient form.

**Verifier (L1).** Stub graph with `connect` / `disconnectInput` jest-like
spies. Fixture touched=[connect Y from X.0 to W.samples]; assert spy called
with (0, W, "samples"). Same for disconnect.

**Verifier (L3, deferred to L-10).** Post-push canvas link state matches
server `inputs[*]` for every touched pair.

**Dependencies.** L-0, L-2, L-3, L-4, L-5.

**Risk.** Medium. LiteGraph's connect/disconnect return values and
slot-name vs slot-index semantics need care. Tests cover both.

---

### L-9 — Disconnect-source resolution · SUBSUMED

LiteGraph's `node.disconnectInput(slot)` is self-sufficient: it doesn't need
the source ID. The undo-history `old_value` machinery cited in P6 is the
server's own concern; the canvas side never needs it. **L-9 is satisfied by
L-8** — no separate leaf code.

---

### L-10 — Integration parity check · (P1 L3 oracle)

**Files (CREATE):**
- `tests/panel/integration.test.js` — wires the full push path end-to-end
  against the stub graph. Scenarios:
  1. Touched widget + touched link + untouched widget → assert mutation
     count == 2, untouched preserved.
  2. Touched link with stale node ref → assert P3 entry, no mutation.
  3. Touched delta + Tier-3 add concurrent → assert Tier-3 entry, touched
     applied.
  4. Push throws mid-execution → assert observer restored.

**Contract.** End-to-end SPEC-fit oracle. Each scenario asserts
post-push canvas state matches expected per the SPEC predicate it covers.

**Verifier.** L3 — this leaf IS the oracle.

**Dependencies.** L-0 through L-8.

**Risk.** Medium. Cross-leaf wiring bugs surface here.

---

### L-11 — Panel-only honored · (P7)

**Files (CREATE):**
- `tests/panel/no-mcp-touch.test.js` (or shell snippet in PASS 7
  SHIP_REPORT verifier section): runs
  `git diff --stat origin/master -- agent/mcp_server.py`; asserts empty.

**Contract.** Branch diff touches zero lines of `agent/mcp_server.py`.

**Verifier.** L0 (git command exit code / empty output).

**Dependencies.** none.

**Risk.** None.

---

## Execution order for PASS 4

Risk-reduction × dependency × parallelism:

1. **L-0** — stack first (blocks everything).
2. **L-7** — surface accumulator (unblocks L-3, L-4, L-5).
3. **L-1** — touched-set server (highest-risk design call; F-1 mitigation).
4. **L-2** — touched-set consumer (validates L-1 end-to-end on the JS side).
5. **L-6** — observer-pause + debounce (independent; high impact).
6. **L-3 + L-5** — ID-shape + shape guard (parallel; both leaf-on-L-7).
7. **L-4** — Tier-3 detect (after L-2 so it knows the touched filter).
8. **L-8** — link diff + apply (the core).
9. **L-10** — integration / SPEC oracle.
10. **L-11** — git-diff check (defer to PASS 7).

Per-leaf flow: implement → run L1 verifier → mark TRACE span → commit (per
Git Authority Map autonomous-tier `git add` + `git commit` on the feature
branch). L-10 + manual L3 against live ComfyUI is PASS 5.

---

## Open design calls (operator may amend)

- **F-1 mitigation (a) vs (c).** PLAN picks (a) — server-touched-set in new
  `panel/server/touched.py`. Option (c) (frontend-only diff-of-diffs against
  module-cached baseline) is viable as a fallback if (a) proves brittle on
  the first-push-after-canvas-sync edge case. **Default: (a).**
- **L-6 debounce window.** PLAN picks 100 ms. Too short → echo risk; too
  long → laggy UX. Operator may tune at PASS 5.
- **L-7 surface-bar UX.** PLAN picks one rolled-up warning + modal. Alt:
  per-entry warning rows. Operator may pivot at PASS 5 if entries are rare.
