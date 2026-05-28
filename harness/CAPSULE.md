# CAPSULE — Write-Back v1 (Tier 1+2) Red-Team

PASS 2 status: **COMPLETE — no F1–F5 trips.**

Severity classes:
- **SHOWSTOPPER** — trips F1–F5; return PASS 0 and amend.
- **DESIGN-CONSTRAINT** — PASS 3 leaf must address; SPEC predicate at risk.
- **HARDEN** — PASS 4 must guard with explicit code path; verifier asserts.
- **BOUNDED** — acceptable / SPEC out-of-scope / nice-to-have.

---

## Findings

### F-1: Stale-cache clobber race — [DESIGN-CONSTRAINT, P2-bearing]

**Scenario.** Director hand-edits canvas node 5 `cfg` from 7.0 → 8.0 at T=0.
Canvas-sync POST debounces 500 ms (`superduperPanel.js:69`). At T=200 ms the
agent emits a `connect_nodes` delta on node 9. `comfy-cozy:workflow-changed`
fires → `pushAgentToCanvas`. The push reads `client.getWorkflowApi()`. The
server cache is still pre-edit at this point — `cfg=7.0` for node 5. Diff at
`:107` sees `widget.value=8.0` vs `apiValue=7.0` → writes 7.0, **clobbering
the director's edit.**

**Where the SPEC said this couldn't happen.** P2 ("manual edit on an untouched
node/slot survives a push").

**Where the live race emerges.** The cache-freshness asymmetry: agent-mutated
nodes are fresh because the mutation went through `_handle_apply_patch` /
`_handle_connect_nodes`; director-mutated nodes lag behind the canvas by the
500 ms debounce.

**Mitigation surface (PASS 3 leaf):** the push must write **only agent-touched
widgets/links**, not "every diff between cache and canvas."

- **(a) Agent-touched set.** Server tags each mutation with a
  `touched=[{node, input}]` set; `pushAgentToCanvas` writes only those slots.
  Server changes: extend `_handle_*` to record the touched set in
  per-conversation state. Frontend change: `getWorkflowApi` returns
  `{workflow, touched}`; push iterates `touched` not all nodes.
- **(b) Pre-push canvas re-sync.** Before `pushAgentToCanvas` runs, force a
  canvas-sync POST and wait. Adds a round-trip; uses existing transport;
  pure-frontend change. Risk: re-sync overwrites the agent's just-made
  mutation if the canvas hasn't received it yet (re-introduces the inverse
  race).

**Recommendation.** (a) — surgical, eliminates the race symmetrically.

**Verifier (L1).** Pre-edit fixture → push unrelated delta → assert untouched
slot retains its pre-push value. Cover the 500 ms window explicitly by
controlling fake clock.

---

### F-2: NaN / non-numeric node IDs silently skipped — [DESIGN-CONSTRAINT, P3-bearing]

**Scenario.** Workflow has node IDs like `"my-node"` (some legacy templates,
or workflows authored outside ComfyUI's numeric-ID convention).
`parseInt("my-node", 10)` → `NaN`. `app.graph.getNodeById(NaN)` → `null`.
Current code at `:102` `if (!node || !node.widgets) continue;` — skips. The
agent's emitted delta is **silently dropped.**

**Where the SPEC said this couldn't happen.** P3 ("every emitted delta is
applied or surfaced").

**Where it leaks.** The silent `continue` at `:102` predates the surface
contract. Same code path catches both legitimate-skip (node truly absent) and
type-error (NaN from non-numeric ID).

**Mitigation surface.** PASS 4's link-delta diff step must distinguish
"node ID could not be parsed" from "node not present on canvas" and feed
both into the P3 surface report as separate entries:

- Unparseable ID → `{type: "malformed", node_id: "my-node", reason: "non-numeric id"}`
- Parsed but absent → `{type: "stale_node_ref", node_id: 42}`

**Verifier (L1).** Stub `app.graph.getNodeById` returns null for selected IDs;
assert surface report receives the entries; assert no widget/link mutation
attempted.

---

### F-3: Tier-3 delta silently absorbed — [DESIGN-CONSTRAINT, P3-bearing]

**Scenario.** Agent emits a node-add (Tier-3-shape) — e.g., adds a
`LatentUpscale` node id `12` to the server workflow. Push iterates server
workflow; for `nodeId=12`, `getNodeById(12)` on the canvas returns null
(canvas doesn't have it). Code at `:102` skips silently — **same path as
F-2.**

**Where the SPEC said this couldn't happen.** P3 (a) — "Tier-3-shaped deltas
(add/delete node) — detected and reported, never applied."

**Mitigation surface.** Tier-3 detection needs to happen **before** the
per-node iteration: diff the server's node-set vs the canvas's node-set
once at the top of `pushAgentToCanvas`. Asymmetric difference becomes P3
entries:

- Server has, canvas doesn't → `{type: "tier3_add", node_id, class_type}`
- Canvas has, server doesn't → `{type: "tier3_delete", node_id}` *(out of
  scope for write-back v1; agent doesn't emit deletes yet — but symmetric
  detection is cheap.)*

Then the per-node iteration only runs over the intersection of node-sets.

**Verifier (L1).** Same harness as F-2; different fixture (server has node N
that canvas doesn't). Assert Tier-3 entry, not stale-ref entry.

---

### F-4: Observer-pause leak — [HARDEN, P4-bearing]

**Scenario.** `pushAgentToCanvas` pauses `app.graph.onAfterChange` to suppress
echo (per A3 recommendation). An exception mid-push (e.g., a single bad
widget value type-coerce throw) leaves the observer paused. Canvas-sync from
the director's subsequent edits never reaches the agent — **agent state
diverges silently from canvas state forever after.**

**Mitigation surface (PASS 4 leaf).** Observer-pause inside `try`, restore
inside `finally`. Idempotent restore (set to the saved handler, not the
original-original — survives nested pauses).

**Verifier (L2).** Property test: for any push outcome (success, throw,
partial), assert the saved observer handler equals the post-push handler.

---

### F-5: Concurrent push race — [HARDEN, P4-bearing]

**Scenario.** Two `comfy-cozy:workflow-changed` events fire faster than push
can serialize. Push 1 starts (paused observer). Push 2 starts before push 1
finishes (observer already paused — saved handler is now the null/no-op).
Push 1 finishes (restores observer to the saved handler — restores **null**,
not the original). Observer permanently dead.

**Mitigation surface.** Single in-flight push at a time. Options:

- **(a) Mutex.** Push acquires a lock; subsequent pushes wait or coalesce.
- **(b) Debounce.** Coalesce rapid events into a single push.
- **(c) Save handler at module level once, not per-push.** Eliminates the
  nested-save bug, even if pushes overlap.

**Recommendation.** (b) + (c) — debounce for performance, module-level save
for correctness.

**Verifier (L4 stress).** Fire N events in rapid succession; assert observer
restored to the canonical handler after all settle.

---

### F-6: Malformed delta shape — [HARDEN, P3-bearing]

**Scenario.** Server emits `inputs: { samples: ["7"] }` — array but wrong
length (link shape is exactly `[string, number]`). Current frontend at `:106`
checks `Array.isArray(apiValue)` only — flips true → write skipped silently.
After amendment: not a link, not a value — must surface per P3 as malformed.

**Mitigation surface.** Shape guard: `Array.isArray(v) && v.length===2 &&
typeof v[0]==='string' && typeof v[1]==='number'`. Non-conforming arrays →
P3 entry `{type: "malformed", node_id, input_name, raw_value}`.

**Verifier (L1).** Fixture with malformed inputs; assert P3 surface entry;
assert no canvas mutation.

---

### F-7: A5 status-bar visibility limit — [BOUNDED]

**Scenario.** User is in CHAT mode of the panel, not GRAPH mode. `graphMode.js`
status bar only renders inside `createGraphMode`. P3 surface report fires but
is invisible.

**Bounded by SPEC scope.** A5 confirms a surface exists; cross-mode visibility
was not specified. Two paths if PASS 5 testing surfaces this as a real UX
gap:

- (a) Add a chat-mode mirror (post P3 entries as system chat messages).
- (b) Make the status bar global (mount above mode switcher, persistent).

Both are PASS 4 leaf additions, not SPEC amendments. PASS 5 will surface
whether this matters in practice.

---

### F-8: Agent-backend unreachable on push — [BOUNDED]

**Scenario.** `client.getWorkflowApi()` fails — agent backend unreachable.
Current code at `:115` `console.debug` — silent in UI.

**Bounded.** This isn't a delta-failure; the entire push is impossible. Surface
as an "agent unreachable" status row, not a P3 entry. PASS 4 nice-to-have, not
required by current SPEC.

---

## F1–F5 trip check

| F | Status | Reasoning |
|---|---|---|
| F1 | **NOT TRIPPED** | A2 holds; LiteGraph API standard. |
| F2 | **NOT TRIPPED — close watch** | F-1 (clobber race) is real but addressable in PASS 3 leaf design (touched-set, option (a)). If PASS 3 cannot select a mitigation that survives PASS 4 implementation, return PASS 0. |
| F3 | **NOT TRIPPED** | A1 holds. F-1 is a write-back race, not a cache-freshness fail. |
| F4 | **RESOLVED VIA A2** | Vitest pre-leaf chosen at PASS 1 escalation. |
| F5 | **NOT TRIPPED** | Target surface verified at s1. |

PASS 2 closes clean. PASS 3 (DECOMPOSE) inherits **3 design-constraint findings
(F-1, F-2, F-3) + 3 harden findings (F-4, F-5, F-6) + 2 bounded findings
(F-7, F-8)** to convert into leaf contracts.

---

## PASS 4–6 verification status (post-implementation)

| Finding | Severity | PASS 4 Closure | PASS 5 Proxy | PASS 6 Stress |
|---|---|---|---|---|
| F-1 stale-cache clobber | DESIGN-CONSTRAINT | ✅ L-1 server touched-set + L-2 frontend consumer (widgets) + L-8 link apply | ✅ orchestrator F-1 end-to-end | ✅ 100-entry batch + rapid 5-push sequence |
| F-2 NaN node IDs | DESIGN-CONSTRAINT | ✅ L-3 strict `parseNodeId` (`/^-?\d+$/`) | ✅ via orchestrator P3 propagate | ✅ malformed-mix stress |
| F-3 Tier-3 leak | DESIGN-CONSTRAINT | ✅ L-4 top-level detect (server vs canvas) | ✅ all 6 surface types in one push | ✅ 50-node Tier-3 in both directions |
| F-4 observer-pause leak | HARDEN | ✅ L-6 try/finally | ✅ orchestrator throw-restore | ✅ — |
| F-5 concurrent push race | HARDEN | ⚠️ L-6 shipped option (b) debounce only — see PASS 6 amendment below | ✅ — | ✅ overlapping-pauses now safe via refcount (option c) |
| F-6 malformed shape | HARDEN | ✅ L-3 + L-5 + L-8 from-node parse | ✅ orchestrator surface propagate | ✅ mixed malformed don't throw |
| F-7 cross-mode visibility | BOUNDED | unchanged | unchanged | unchanged — deferred per SPEC; PASS 5 manual L3 will surface if UX-critical |
| F-8 agent-backend unreachable | BOUNDED | unchanged | ✅ getWorkflowApiWithTouched-throws path swallows + logs | unchanged — nice-to-have, not specified by SPEC |

### PASS 6 amendment summary

**F-5 nested-save bug surfaced.** L-6 originally shipped CAPSULE option (b)
— debounce only — assuming `comfy-cozy:workflow-changed` events would never
overlap. Concurrent direct invocations (bypassing debounce: tests, direct
calls) still nested-saved the noop handler, leaking the observer.

Fixed in TRACE span s24 by adding **CAPSULE option (c) on top**:
module-level refcount + saved-handler in `panel/web/js/_pushControl.js`.
The handler is captured ONCE when depth transitions 0 → 1 and restored
ONCE when depth returns to 0. Nested / concurrent pauses see depth > 0
and only increment / decrement.

### PASS 6 gate

**NO SHOWSTOPPER. Bounded items (F-7, F-8) documented as deferred per
SPEC. PASS 6 PASSES.**

---

## Leaf-shape preview for PASS 3

Anticipated leaves from these findings (full PLAN at PASS 3):

- **L-0** *(pre-leaf, per A2)* — Stand up Vitest + stubs.
- **L-1** Server-side touched-set tagging (server change for F-1, option a).
- **L-2** Frontend touched-set consumer + per-touched iteration (F-1).
- **L-3** ID-shape shim + parse-failure surfacing (F-2, P5).
- **L-4** Tier-3 detection step (F-3).
- **L-5** Malformed-shape guard (F-6).
- **L-6** Observer-pause + try/finally + module-level save (F-4, F-5, P4).
- **L-7** Surface-report panel wire (graphMode.js status-bar entry).
- **L-8** Link-delta diff step itself (per-touched node, connect/disconnect ops via LiteGraph).
- **L-9** Disconnect-source resolution from canvas state (P6 — LiteGraph's `disconnectInput` is self-sufficient; leaf may be trivial).
- **L-10** Integration / parity check against stub graph (P1 L3).
