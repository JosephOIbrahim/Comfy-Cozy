# TRACE — Write-Back v1 (Tier 1+2) to the live ComfyUI canvas

Append-only causal log. `parent_id` is the causal predecessor, not wall-clock predecessor.

---

```
span_id:       s0
parent_id:     null
pass:          0
step_type:     plan
input_state:   operator brief "Bet 3-out · Write-Back v1 · v2" (panel-only Tier 1+2);
               two scouts already produced (SCOUT_rewiring_scope, SCOUT_canvas_state_sync)
action:        Read scouts; draft SPEC.md (PROPOSED) at harness/SPEC.md with
               predicates P1-P7, falsifiers F1-F5, assumptions A1-A3 (A4 closed as
               RATIFIED DECISION on target surface).
output_state:  SPEC drafted. Brief B artifacts still in harness/ root from prior run.
verifier:      none (pre-ratification)
outcome:       success
external_calls: [Read x3, ls x2]
```

```
span_id:       s1
parent_id:     s0
pass:          0
step_type:     verify
leaf_id:       F5-check (target surface verification)
input_state:   panel/web/js/superduperPanel.js cited file:line in SCOUT_rewiring_scope.md
action:        Read superduperPanel.js; check pushAgentToCanvas body, parseInt shim,
               link-drop filter, _lastGraphHash, onAfterChange observer against scout cites.
output_state:  pushAgentToCanvas at :94-118 (docstring :89-93); parseInt at :101; link-drop
               filter at :106; _lastGraphHash at :19,33-35; onAfterChange at :66-71.
               Every scout citation matches.
verifier:      L0 (file existence + line-anchored grep) — F5 does NOT fire
outcome:       success
external_calls: [Read]
```

```
span_id:       s2
parent_id:     s1
pass:          0
step_type:     correction
input_state:   operator path correction: (1) scouts belong at harness/, not harness/ledger/;
               (2) ledger/ holds recipe candidates only, NOT artifact archives;
               (3) confirm the real rotation convention before moving Brief B artifacts.
action:        Investigate ledger/candidates/ (3 candidate_*.md from Brief B SLEEP)
               + git log for harness/ledger/ (single commit 377c788, same as Brief B
               artifacts). No archive-dir convention exists on this repo. Revert:
               git mv Brief B SPEC/PLAN/TRACE/CAPSULE/SHIP_REPORT back to harness/;
               mv scouts back to harness/; rmdir harness/ledger/brief-b/ (invented dir).
output_state:  Brief B record preserved at commit 377c788; this run's artifacts overwrite
               Brief B's in place at harness/{SPEC,PLAN,TRACE,CAPSULE,SHIP_REPORT}.md.
               Net rotation: zero. Scouts at harness/ root.
verifier:      L0 (git status: only untracked scouts; tracked files at committed state) — PASS
outcome:       success — superseded the initial PASS-0 rotation conclusion in s0
external_calls: [ls, find, git log x2, mv x2, git mv x5, rmdir]
```

```
span_id:       s3
parent_id:     s2
pass:          0
step_type:     amend
leaf_id:       A1 (amendment)
input_state:   AskUserQuestion ratification gate; operator selected "Amend Predicates (Q3)"
               and dictated revised P1: "Link-state parity (applied ops). After a push,
               every link op that successfully applied achieves parity... Ops that cannot
               apply (stale node reference, missing slot) are surfaced per P3, never
               silently dropped, and are excluded from the parity assertion. Write-back v1
               is best-effort-with-reporting, not all-or-nothing."
action:        Propagate amendment: replace P1 verbatim; expand P3 to enumerate surface
               conditions (a) Tier-3 shape, (b) stale node ref, (c) missing slot; update
               Outcome paragraph with contract-shape clause; add A5 (user-visible surface
               report). No new F-conditions; F1-F5 still cover SPEC-aborts only.
output_state:  SPEC.md updated; PASS 0 status PROPOSED-A1 awaiting re-ratification.
               Amendments section logs A1 with origin = operator PASS-0 amendment.
verifier:      none yet (re-ratification gate pending)
outcome:       success
external_calls: [Write x2 (SPEC, TRACE), Read]
```

```
span_id:       s4
parent_id:     s3
pass:          0
step_type:     verify
input_state:   SPEC at harness/SPEC.md after A1 propagation (P1 narrowed, P3 enumerated,
               Outcome amended with best-effort-with-reporting clause, A5 added,
               F-table unchanged with explicit "stale-ref/missing-slot are runtime not
               SPEC-abort" note)
action:        AskUserQuestion re-ratification gate; operator selected
               "Ratify with A1 — freeze for PASS 1"
output_state:  SPEC frozen for PASS 1. PASS 0 closed.
verifier:      operator acceptance — PASS
outcome:       success
external_calls: [AskUserQuestion]
```

```
span_id:       s5
parent_id:     s4
pass:          1
step_type:     verify
leaf_id:       A1
input_state:   panel/server/chat.py, panel/server/routes.py
action:        Trace cache-freshness path. ConversationState._workflow_hash at chat.py:86;
               _inject_current_workflow at :124-141 (reads agent cache, hashes, dedup at
               :133); _inject_workflow_data at :144-162 (force-inject canvas push, hashes
               at :147, dedup at :148). WebSocket handler calls injection per chat msg
               at :378-394 and per explicit workflow msg at :431-454. Frontend canvas-sync
               POSTs /comfy-cozy/load-workflow-data (routes.py:155-202), which calls
               load_workflow_from_data at routes.py:172.
output_state:  Two-channel hash-diff cache freshness confirmed. For write-back direction
               specifically (push agent→canvas), cache is fresh because the trigger IS an
               agent mutation that updated the cache directly via
               _handle_apply_patch / _handle_connect_nodes. F3 does NOT fire.
verifier:      L0 (file:line evidence) — A1 HOLDS
outcome:       success
external_calls: [Read x2]
```

```
span_id:       s6
parent_id:     s4
pass:          1
step_type:     verify
leaf_id:       A2
input_state:   superduperPanel.js:12 import "../../../scripts/app.js"; system-wide find
               for ComfyUI/LiteGraph source
action:        Confirm LiteGraph link API reachable. ComfyUI installed at
               /Applications/ComfyUI.app/Contents/Resources/ComfyUI/.../scripts/app.js.
               Panel loads as a ComfyUI custom_node extension; the import resolves at
               runtime to host's /scripts/app.js. app.graph is the LGraph instance;
               LGraphNode primitives node.connect(slot, target_node, target_slot),
               node.disconnectInput(slot), node.disconnectOutput(slot, target_node?),
               and graph.removeLink(link_id) are standard LiteGraph API. Delta contract
               maps cleanly:
                 connect:    from_node.connect(from_output, to_node, to_input)
                 disconnect: to_node.disconnectInput(to_input)
output_state:  Link API reachable. F1 does NOT fire. Slot semantics: to_input accepts
               name OR index — server uses string names, matches LiteGraph contract.
verifier:      L0 (extension host exists; API surface standard) — A2 HOLDS
outcome:       success
external_calls: [find x2, ls x3]
```

```
span_id:       s7
parent_id:     s4
pass:          1
step_type:     verify
leaf_id:       A3
input_state:   superduperPanel.js (already read at s1)
action:        Re-confirm echo suppression surface. _lastGraphHash at :19, :33-35 is
               length-based (JSON.stringify(graphData).length — weak, but adequate).
               onAfterChange observer at :66-71 debounces 500ms. CRITICAL: post-push the
               new graph hash DIFFERS from old, so the existing _lastGraphHash auto-update
               at :35 will NOT suppress the echo by itself — it would just record the new
               state as the latest. Suppression requires explicit wire: either
               (a) pushAgentToCanvas pre-stamps _lastGraphHash with the post-mutation hash
                   before the observer's debounce fires; OR
               (b) temporarily replaces app.graph.onAfterChange with a no-op during the
                   push (observer-pause).
output_state:  Mechanism present, but neither auto-suppresses. PASS 3 must select (a) or
               (b) as a leaf-level design choice. Recommend (b) observer-pause: direct,
               immune to hash-collision, restores on finally. F3 does NOT fire.
verifier:      L0 (mechanism exists; explicit PASS 4 wiring required) — A3 HOLDS with caveat
outcome:       success
external_calls: []
```

```
span_id:       s8
parent_id:     s4
pass:          1
step_type:     verify
leaf_id:       A5
input_state:   panel/web/js/graphMode.js
action:        Confirm user-visible surface for delta-failure reports. _createStatusBar
               at :312-317; _refreshStatusBar at :319-426. Warning shape at :334, :365:
               {text, action?, handler?}. Existing warnings: missing nodes ("Repair"
               button at :337-351), deprecated nodes ("Migrate" button at :368-387),
               wiring issues at :353-357. Each warning is dismissable (dismissBtn at
               :418-422). Status bar mounts at top of GRAPH mode (container.appendChild
               at :4-5).
output_state:  Surface exists and is extensible within Tier-1+2 scope. Delta-failure
               report adds a new warnings.push() entry of shape
               {text:"N delta(s) not applied", action:"Details", handler: showModal}.
               No Tier-3 work required. F2/F5 do NOT fire on A5.
verifier:      L0 (existing extensible pattern) — A5 HOLDS
outcome:       success
external_calls: [Read]
```

```
span_id:       s9
parent_id:     s4
pass:          1
step_type:     verify
leaf_id:       JS-verifier-stack
input_state:   repo root + recursive find for JS tooling
action:        Search for package.json, eslint config, vitest/jest/playwright config,
               .test.js / .spec.js test files, pyproject JS section. ALL ABSENT. Only
               Python tooling present (pytest, pytest-asyncio, pytest-cov).
output_state:  No JS verifier stack exists. 6 of 7 predicates (P1-P6) require JS
               automation to verify via L1-L4. P7 (panel-only honored) checkable by L0
               git-diff filter alone, independent of stack.
               F4 TRIGGER: "No stack" is satisfied; "can't be stood up" is NOT satisfied
               (Vitest is cheap to add). Per F4 response clause: halt and surface to
               operator. Amendment options:
                 (A) Stand up Vitest as PASS 3 pre-leaf 0. ~30 min infra. L0-L4 automated.
                 (B) Accept manual verification. Replace L1-L4 with manual smoke-test
                     script on live canvas. Faster start, no regression coverage.
                 (C) Hybrid: Vitest L1 for pure-function leaves (ID-shape shim,
                     disconnect-source resolution). Manual for app.graph-touching leaves
                     (P1, P2, P3, P4).
verifier:      L0 (filesystem scan, exhaustive) — JS stack ABSENT, F4 amendable
outcome:       escalation
external_calls: [find x3, grep, ls]
```

```
span_id:       s10
parent_id:     s9
pass:          1
step_type:     amend
leaf_id:       A2 (amendment)
input_state:   F4 escalation; AskUserQuestion offered (A) Vitest full automation,
               (B) manual verification, (C) hybrid, (D) narrow scope to P7-only.
action:        Operator selected (A): Vitest as PASS 3 pre-leaf 0. Propagate amendment
               into SPEC.md: add A2 to Amendments, extend Substrate Scope with CREATE row
               for JS verifier stack (package.json, vitest.config, tests/panel/**,
               minimal litegraph stub), rebind Verifier Layers L0-L4 to Vitest (no jsdom
               — link-delta logic is pure-ish, DOM not required for L1/L2).
output_state:  SPEC.md amended; PASS 1 ratification log entry added. PASS 1 CLOSES.
verifier:      operator acceptance — PASS
outcome:       success
external_calls: [AskUserQuestion, Write (SPEC)]
```

```
span_id:       s11
parent_id:     s10
pass:          2
step_type:     execute
input_state:   PASS 1 evidence (s5-s10) + SPEC P1-P7 + F1-F5
action:        Red-team adversarial scenarios across the delta-merge surface: stale-cache
               clobber, NaN node IDs, Tier-3 leak, observer-pause leak, concurrent push
               race, malformed delta shape, A5 visibility limit, backend-unreachable.
               Categorize by severity (SHOWSTOPPER / DESIGN-CONSTRAINT / HARDEN /
               BOUNDED). Map each finding to predicate at risk and mitigation surface.
               Write CAPSULE.md.
output_state:  CAPSULE.md committed with 8 findings (F-1..F-8 internal IDs to disambiguate
               from SPEC F1-F5). Severity breakdown: 0 SHOWSTOPPER, 3 DESIGN-CONSTRAINT
               (F-1 clobber race, F-2 NaN IDs, F-3 Tier-3 leak), 3 HARDEN (F-4 observer
               leak, F-5 concurrent race, F-6 malformed shape), 2 BOUNDED (F-7 visibility,
               F-8 unreachable). NO F1-F5 trip. PASS 2 closes clean. PASS 3 inherits 10
               anticipated leaves (L-0..L-10) as preview.
verifier:      L0 (no SPEC F-trip on any finding) — PASS 2 GATE PASS
outcome:       success
external_calls: [Write (CAPSULE)]
```

```
span_id:       s12
parent_id:     s11
pass:          3
step_type:     plan
input_state:   SPEC P1-P7 + CAPSULE 8 findings (F-1..F-8) + A2 Vitest binding
action:        Decompose into 12 leaves L-0..L-11 (L-9 subsumed by L-8).
               Per-leaf CONTRACT + VERIFIER + DEPS + FILES. Cover every SPEC predicate
               and every CAPSULE finding. Key design call: F-1 mitigation chose option
               (a) server-touched-set via NEW panel/server/touched.py — purely additive,
               zero changes to agent/tools/workflow_patch.py, preserves CALL-ONLY status.
               Execution order: risk-reduction × dependency × parallelism, leading with
               L-0 (stack) → L-7 (surface) → L-1+L-2 (touched-set) → L-6 (observer) →
               L-3+L-5 (parsing/shape) → L-4 (Tier-3) → L-8 (link apply) → L-10
               (integration) → L-11 (git-diff at PASS 7).
output_state:  PLAN.md written. Predicate / finding coverage matrix included.
               3 open design calls surfaced for operator: (1) F-1 mitigation (a) vs
               fallback (c), (2) debounce window 100ms, (3) surface-bar UX (rolled-up
               vs per-entry).
verifier:      L0 (every SPEC predicate owned by a leaf; every CAPSULE finding mapped) — PASS
outcome:       success
external_calls: [Write (PLAN), Read (Brief B PLAN for format)]
```

```
span_id:       s13
parent_id:     s12
pass:          4
step_type:     execute
leaf_id:       L-0
input_state:   feat/writeback-v1-tier1-2 branch; PLAN.md L-0 contract (Vitest stack)
action:        Create package.json (vitest ^1.6 devDep), vitest.config.js (include
               tests/panel/**, node env), tests/panel/_stubs/litegraph.js
               (makeFakeNode/makeFakeGraph/makeFakeApp recording stubs), and
               tests/panel/sample.test.js (4 smoke assertions). Run npm install
               --include=dev (npm config get omit returned "dev" → had to force include);
               run npm test. Extend .gitignore with node_modules/ and npm-debug.log*.
output_state:  Vitest 1.6.1 installed (124 packages). tests/panel/sample.test.js: 4/4
               passing in 210ms. node_modules/ ignored. L-0 contract satisfied.
verifier:      L0 (test runner exits 0; 4/4 passing) — L-0 GREEN
outcome:       success
external_calls: [Bash (git checkout -b, mkdir, npm install, npm test), Write x4, Edit x2]
```

```
span_id:       s14
parent_id:     s13
pass:          4
step_type:     execute
leaf_id:       L-7
input_state:   L-0 stack ready; PLAN L-7 contract (surface accumulator + status-bar wire)
action:        Implementation refinement vs PLAN: extracted helpers into new
               panel/web/js/_deltaFailures.js module (pure ES module, no dependency
               on the host app import, trivially unit-testable). Wired
               graphMode.js:_refreshStatusBar to surface deltaFailureCount() > 0 as
               a "Details" warning row; modal renders entries with type/node/input/
               class/reason/raw. Hooked clearDeltaFailures() at the top of
               superduperPanel.js:pushAgentToCanvas to reset accumulator each push.
               Added 5 Vitest tests covering insert/get/clear/copy-safety/order.
output_state:  panel/web/js/_deltaFailures.js (new). graphMode.js: +import, +warning
               push in _refreshStatusBar, +_showDeltaFailureModal helper.
               superduperPanel.js: +import, +clear-on-push hook.
               9/9 Vitest tests passing (4 sample + 5 deltaFailures).
verifier:      L1 (Vitest deltaFailures.test.js: 5/5) — L-7 GREEN
outcome:       success
external_calls: [Write x2, Edit x5, Bash (npm test x2)]
```

```
span_id:       s15
parent_id:     s14
pass:          4
step_type:     execute
leaf_id:       L-1
input_state:   L-7 ready; PLAN L-1 contract (per-session touched-set + routes hooks)
action:        Write panel/server/touched.py (record_last_pushed / compute_touched /
               clear_session; thread-safe via RLock; deep-copy snapshot semantics;
               link/widget classification). Add 2 new routes:
               GET  /comfy-cozy/get-workflow-api-with-touched  -> {workflow, touched}
               POST /comfy-cozy/ack-push                       -> snapshot current.
               Hook record_last_pushed into existing /comfy-cozy/load-workflow-data
               (post-load) and /comfy-cozy/reset (post-reset). Hook clear_session
               into chat.py WebSocket disconnect finally block. Write tests/
               test_touched.py (24 pytest cases: snapshot semantics, diff,
               classification, F-1 clobber scenario, session isolation, ack-push
               flow, malformed shapes). Bug surfaced + fixed: classification used
               `or` short-circuit which failed when new_value was None (link
               removed); "unknown" is truthy → old_value fallback never ran.
               Replaced with explicit conditional.
output_state:  panel/server/touched.py (new, 132 LOC). panel/server/routes.py:
               +2 endpoints (~58 LOC), +load-hook, +reset-hook. panel/server/
               chat.py: +clear_session on disconnect. tests/test_touched.py
               (new, 245 LOC, 24 tests). py_compile clean.
               Architectural note (out of scope, surfaced for PASS 5): production
               session routing between HTTP and WebSocket contexts
               (current_conn_session() returns "default" for browser HTTP,
               conv.id for in-agent loop) was NOT addressed; L-1's mechanism is
               session-id-parameterized so it adapts to whichever session is in
               play, but if HTTP/WS sessions don't intersect, F-1 mitigation
               degrades. Surface at PASS 5 integration.
verifier:      L1 (24/24 pytest passing in tests/test_touched.py) +
               L0 (9/9 vitest sanity, no JS changes) — L-1 GREEN
outcome:       success
external_calls: [Write x2, Edit x4, Bash (pytest x2, npm test, py_compile)]
```

```
span_id:       s16
parent_id:     s15
pass:          4
step_type:     execute
leaf_id:       L-2
input_state:   L-1 ready (server touched-set + endpoints + hooks); L-7 ready
               (surface accumulator); PLAN L-2 contract (frontend consumer)
action:        PLAN deviation: extracted apply logic into new pure module
               panel/web/js/_pushApplyTouched.js (takes app+workflow+touched as
               args; testable without import-of-host-app concerns). Added
               agentClient.getWorkflowApiWithTouched() and agentClient.ackPush().
               Replaced superduperPanel.pushAgentToCanvas body: fetch via new
               with-touched endpoint, call applyTouchedSet (iterates touched
               only), call ackPush in nested try (failure logged but not thrown
               — re-applied widget writes on next push are idempotent no-ops).
               Link kind handled by no-op stub _applyTouchedLink — DEFERRED to
               L-8. Widget kind writes widget.value if not already equal.
               Unknown kind silently dropped (L-5 will surface upstream).
               Missing node / missing widget silently dropped (L-3/L-4/L-5
               will surface upstream).
output_state:  panel/web/js/_pushApplyTouched.js (new, ~55 LOC).
               panel/web/js/agentClient.js: +getWorkflowApiWithTouched, +ackPush
               (~28 LOC). panel/web/js/superduperPanel.js: pushAgentToCanvas
               rewritten; +applyTouchedSet import. tests/panel/
               pushApplyTouched.test.js (new, 14 cases).
               F-1 mitigation now closed end-to-end for widget edits; link
               write-back still pending L-8.
verifier:      L1 (Vitest pushApplyTouched.test.js: 14/14; total 23/23 vitest
               + 24/24 pytest = 47/47 across L-0..L-2 + L-7) — L-2 GREEN
outcome:       success
external_calls: [Read (agentClient), Write x2, Edit x3, Bash (npm test)]
```

```
span_id:       s17
parent_id:     s16
pass:          4
step_type:     execute
leaf_id:       L-6
input_state:   L-2 ready (touched-set consumer wired); PLAN L-6 contract
               (observer-pause + try/finally + debounce; F-4, F-5, P4)
action:        Extracted control primitives into new panel/web/js/_pushControl.js:
                 debounce(fn, ms) — coalesces rapid calls; .cancel() drops
                                    pending fire; swallows fn errors safely
                 withObserverPause(graph, fn) — saves graph.onAfterChange,
                                    replaces with no-op, restores in finally
                                    (works for sync throws, async rejects,
                                    null graph)
               superduperPanel.js: wrapped applyTouchedSet + setDirty in
               withObserverPause(app.graph, ...) inside pushAgentToCanvas;
               debounce(pushAgentToCanvas, 100) replaces the bare event
               handler call on comfy-cozy:workflow-changed.
output_state:  panel/web/js/_pushControl.js (new, ~55 LOC).
               panel/web/js/superduperPanel.js: +import {debounce,
               withObserverPause}; +withObserverPause wrap around mutations;
               +_debouncedPushAgentToCanvas at module scope replacing inline
               pushAgentToCanvas() event call. tests/panel/pushControl.test.js
               (new, 11 cases). P4 (no echo): pause is module-internal; the
               saved handler is always restored even on exception, so no echo
               and no observer leak. F-5 (concurrent race): debounce makes
               the queue head-of-line — at most one push in flight per 100 ms
               window.
verifier:      L2 (Vitest pushControl: 11/11 covering throw-restore, async-
               reject-restore, coalesce N rapid → 1 fn, cancel kills pending,
               null-graph safe, paused observer doesn't fire original) + L0
               sanity (all prior vitest + pytest green; new total 58/58) —
               L-6 GREEN
outcome:       success
external_calls: [Write x2, Edit x3, Bash (npm test)]
```

```
span_id:       s18
parent_id:     s17
pass:          4
step_type:     execute
leaf_id:       L-3
input_state:   L-6 ready; PLAN L-3 contract (ID-shape shim + parse surfacing)
action:        Added _parseNodeId(raw) -> {ok, id} helper to
               _pushApplyTouched.js with strict /^-?\d+$/ shape check (handles
               null/undefined/non-numeric/empty string). Replaced parseInt
               calls in both _applyTouchedWidget and _applyTouchedLink with
               parseNodeId; on failure, emit addDeltaFailure({type:"malformed",
               reason:"non-numeric node id"}) and return.
output_state:  panel/web/js/_pushApplyTouched.js: +_parseNodeId, parseInt
               replaced in both apply functions, +malformed surface on failure.
verifier:      L1 (5 tests in L-3 group: non-numeric widget, non-numeric link,
               empty string, null, numeric-string passes) — L-3 GREEN
outcome:       success
external_calls: [Write, Edit, Bash (npm test)]
```

```
span_id:       s19
parent_id:     s18
pass:          4
step_type:     execute
leaf_id:       L-4
input_state:   L-3 ready; PLAN L-4 contract (Tier-3 detection at top of push)
action:        Added _detectTier3(graph, workflow) -> {add, delete} that diffs
               server node-set against canvas node-set (graph._nodes array,
               LiteGraph's exposure). Called at top of applyTouchedSet; emits
               tier3_add for server-only, tier3_delete for canvas-only. Built
               tier3Ids set so touched entries on Tier-3 nodes are SKIPPED in
               main loop (avoid double-surface as stale_node_ref). Updated
               tests/panel/_stubs/litegraph.js: added _nodes getter so the
               fake graph mirrors LiteGraph's array exposure. Per-touched
               stale_node_ref retained for narrower case (touched entry whose
               node-id is missing from BOTH workflow and canvas).
output_state:  panel/web/js/_pushApplyTouched.js: +_detectTier3, +Tier-3
               surface at top, +tier3Ids skip in main loop.
               tests/panel/_stubs/litegraph.js: +_nodes getter.
               Tests rewritten to pass wfBase() (a workflow matching the
               canvas) by default; Tier-3 tests deliberately override wfBase
               to exercise add/delete paths.
verifier:      L1 (4 Tier-3 detect tests + 1 per-touched stale test) — L-4 GREEN
outcome:       success
external_calls: [Edit (stub), Bash (npm test)]
```

```
span_id:       s20
parent_id:     s19
pass:          4
step_type:     execute
leaf_id:       L-5
input_state:   L-4 ready; PLAN L-5 contract (unknown-kind + missing-slot)
action:        Added missing_slot surface in _applyTouchedWidget for two
               cases: (a) node has no widgets array, (b) widget with given
               name not found. Added malformed surface in main loop when
               entry.kind is neither "widget" nor "link" ("unknown" or
               other). raw_value captured in the malformed entry for
               diagnostic value.
output_state:  panel/web/js/_pushApplyTouched.js: +missing_slot surface in
               widget path, +malformed surface for unknown kind. P3 surface
               enumeration complete for the widget path (links wait for L-8).
verifier:      L1 (3 L-5 tests: nonexistent input name, null widgets array,
               unknown kind) + L0 sanity (all prior green; new total 68/68
               = 44 vitest + 24 pytest) — L-5 GREEN
outcome:       success
external_calls: [Bash (npm test)]
```

```
span_id:       s21
parent_id:     s20
pass:          4
step_type:     execute
leaf_id:       L-8
input_state:   L-5 ready (surface enumeration complete for widget path); PLAN
               L-8 contract (link primitive apply via LiteGraph)
action:        Implemented _applyTouchedLink in _pushApplyTouched.js with
               three-state transition handling:
                 old null + new link → connect via
                   fromNode.connect(fromOutput, toNode, input_name)
                 old link + new null → toNode.disconnectInput(input_name)
                 old A    + new B    → disconnect, then connect
                 old == new          → no-op (defensive)
               Added _isLink(v) and _linkEq(a, b) helpers. Failure surfaces
               mirror the widget path: malformed (parse), stale_node_ref
               (missing to-node OR from-node), and a new "link_rejected"
               type for LiteGraph returning false on connect/disconnect.
               Extended tests/panel/_stubs/litegraph.js: makeFakeNode accepts
               opts.{connectReturns, disconnectInputReturns,
               disconnectOutputReturns} so tests simulate LiteGraph rejection.
               Bug surfaced + fixed: needsConnect only checked _isLink(new)
               — would re-issue connect when old == new. Added !linkEq guard.
output_state:  panel/web/js/_pushApplyTouched.js: _applyTouchedLink full
               implementation; +_isLink, +_linkEq.
               tests/panel/_stubs/litegraph.js: +returns options.
               tests/panel/pushApplyTouched.test.js: L-8 deferred test removed;
               L-8 describe block (10 tests) added.
               F-1 mitigation NOW CLOSED FOR LINKS — director-edited
               neighbours survive both widget AND link writes. P1 (link-state
               parity, applied ops) is verifiable: connect args match server's
               [from_node_id_str, from_output_int] shape via parseNodeId
               conversion.
verifier:      L1 (10 new L-8 tests + 24 prior in same file + 5 deltaFailures
               + 11 pushControl + 4 sample = 54 vitest; 24 pytest unchanged;
               new total 78/78) — L-8 GREEN
outcome:       success
external_calls: [Write, Edit x3, Bash (npm test x2)]
```

```
span_id:       s22
parent_id:     s21
pass:          4
step_type:     execute
leaf_id:       L-10
input_state:   L-8 ready (link apply complete); PLAN L-10 contract
               (integration / SPEC-fit oracle composing all leaves)
action:        Created tests/panel/integration.test.js. Composes the push
               pipeline as superduperPanel.pushAgentToCanvas does:
                 clearDeltaFailures
                 → withObserverPause(graph, () => applyTouchedSet(app, wf, t))
               12 scenarios directly assert SPEC predicates:
                 P1 link parity (connect args match server shape; widget value
                    matches server new_value)
                 P2 manual-edit survival (director widget survives link write;
                    director sibling widget survives agent widget edit)
                 P3 surface enumeration (single push hits tier3_add,
                    tier3_delete, stale_node_ref, missing_slot, malformed,
                    link_rejected — all six documented types); every failure
                    has type + node_id
                 P4 no echo (observer restored after success; observer
                    restored after applyTouchedSet throws; paused observer
                    doesn't re-trigger original during apply)
                 F-1 end-to-end (multi-touched + multi-director-edit; all
                    survive)
                 mixed widget+link in one push
                 empty touched no-op (observer canonical)
output_state:  tests/panel/integration.test.js (new, 12 scenarios).
               PASS 4 EXECUTE substantively complete: all SPEC-bearing
               leaves L-0..L-8 + L-10 green. L-11 (P7 git-diff filter)
               deferred to PASS 7 SHIP.
verifier:      L1 + L3 (the 12-scenario suite IS the SPEC-fit oracle for
               stub integration; real-canvas L3 is PASS 5 manual). All
               prior tests still green; new total 90/90 (66 vitest + 24
               pytest) — L-10 GREEN
outcome:       success
external_calls: [Write, Bash (npm test)]
```

```
span_id:       s23
parent_id:     s22
pass:          5
step_type:     execute
input_state:   PASS 4 closed (8 leaves green, 90/90 tests); operator
               PASS-5 gate chose option (D) — proxy via vi.fn() stubs.
action:        Extracted push orchestration into new
               panel/web/js/_pushOrchestrator.js exporting
               runPushAgentToCanvas(app, client). Composes the full
               pipeline: clearDeltaFailures → client.getWorkflowApi-
               WithTouched → withObserverPause(applyTouchedSet +
               setDirty) → client.ackPush. Error swallowing at top-level
               (event handler must not throw); ackPush failure caught
               separately and logged.
               superduperPanel.js: replaced inline pushAgentToCanvas
               body with `return runPushAgentToCanvas(app, client)`.
               Removed now-unused imports (addDeltaFailure,
               clearDeltaFailures, applyTouchedSet, withObserverPause)
               — only `app`, `AgentClient`, `debounce`, and the new
               orchestrator remain as direct dependencies.
               Wrote tests/panel/pushOrchestrator.test.js (13 scenarios):
                 - happy widget / happy link / empty touched (all
                   trigger ackPush)
                 - early returns: client null, workflow null, app.graph
                   absent — none call ackPush
                 - ackPush throws → swallowed; widget still applied;
                   observer restored
                 - getWorkflowApiWithTouched throws → swallowed; no
                   ackPush; observer restored
                 - P3 surfaces propagate through orchestrator
                 - L-7 lifecycle: stale failures from prior push cleared
                 - F-1 end-to-end through orchestrator
                 - call-order: getWorkflowApiWithTouched precedes
                   ackPush
                 - observer paused during apply (snapshot taken in
                   setDirty hook), restored before push completes
output_state:  panel/web/js/_pushOrchestrator.js (new, ~55 LOC).
               panel/web/js/superduperPanel.js: imports trimmed;
               pushAgentToCanvas reduced to one-line delegation.
               tests/panel/pushOrchestrator.test.js (new, 13 cases).
               Total: 79 vitest + 24 pytest = 103 tests.
               PASS 5 proxy GREEN. Real-canvas manual L3 against live
               ComfyUI remains operator's final-mile validation; this
               proxy is the automated regression net that covers the
               same seams.
verifier:      L1 + L3 (orchestrator proxy = SPEC-fit on the composed
               pipeline; 13 scenarios cover every leaf + ackPush flow +
               error paths) + ruff sanity (no JS lint stack per F4
               amendment; Python ruff clean on touched modules)
outcome:       success
external_calls: [Write x2, Edit x2, Bash (npm test, ruff)]
```

```
span_id:       s24
parent_id:     s23
pass:          6
step_type:     execute
input_state:   PASS 5 proxy complete (103 tests); PLAN PASS 6 contract
               (stress attacks + bounded documentation)
action:        Wrote tests/panel/stress.test.js with 8 scenarios:
                 100-touched-entry apply + perf bound (<100ms)
                 burst events (50 calls → 1 debounced execution)
                 Tier-3 with 50 canvas-only nodes (50× tier3_delete)
                 Tier-3 with 50 server-only nodes (50× tier3_add)
                 overlapping observer-pauses (F-5 nested-save)
                 slow ackPush (80ms) — doesn't deadlock
                 mixed malformed deltas — no throw, correct surfaces
                 rapid 5-push sequence — last value sticks, observer canonical
               Stress test "overlapping observer-pauses" surfaced a REAL
               BUG: L-6 originally shipped CAPSULE option (b) debounce-
               only F-5 mitigation; concurrent direct invocations
               (bypass debounce) still leaked observer to noop because
               each call saved the CURRENT handler (noop after first
               pause). PASS 6 AMENDMENT to L-6: added CAPSULE option (c)
               on top — module-level refcount + saved-handler in
               _pushControl.js. Capture ONCE at 0→1; restore ONCE at
               1→0. Concurrent overlap nests safely. Added test-only
               _resetObserverPauseState export.
               Updated harness/CAPSULE.md with PASS 4-6 verification
               status table mapping every F-1..F-8 to current state;
               F-5 escalation summarized; gate marked PASS.
output_state:  panel/web/js/_pushControl.js: +module-level pause state
               (_pauseDepth, _savedOnAfterChange, _pausedGraph) +
               refcount logic + _resetObserverPauseState export.
               tests/panel/stress.test.js (new, 8 scenarios).
               harness/CAPSULE.md: PASS 4-6 status table appended;
               F-5 amendment summary; gate noted.
               Test totals: 111 (87 vitest + 24 pytest).
               PASS 6 gate: NO SHOWSTOPPER, BOUNDED ITEMS DOCUMENTED.
verifier:      L4 stress (8 scenarios incl. performance, concurrency,
               malformed mix, rapid sequence) + L0 sanity (no
               regression on prior 79 vitest + 24 pytest after F-5
               refcount amendment) — PASS 6 GREEN
outcome:       success
external_calls: [Write, Edit x3, Bash (npm test x2)]
```

```
span_id:       s25
parent_id:     s24
pass:          7
step_type:     execute
leaf_id:       L-11 + SHIP
input_state:   PASS 6 closed (111 tests, NO SHOWSTOPPER, F-5 amended);
               operator authorized PASS-5-proxy + drive-through path.
action:        L-11 P7 verification: ran `git diff master --
               agent/mcp_server.py` → empty (ZERO DIFF). P7 HOLDS.
               Read Brief B SHIP_REPORT for format reference. Wrote
               harness/SHIP_REPORT.md with SPEC compliance per-predicate
               table (7/7 met), CAPSULE mitigation status (F-1..F-6
               closed, F-7/F-8 bounded), verifier coverage (87 vitest
               + 24 pytest + ruff clean), known limitations (real-
               canvas L3 still PASS-5-manual deferred; session-routing
               architectural concern flagged for follow-up), deployment
               artifact summary (29 files, +6535/-453, 10 commits
               unpushed), deploy sequence (PASS-5 manual → operator
               merge), recommended next (PASS-5, F-7/F-8 follow-ups,
               Tier-3 brief, session routing investigation, refcount
               cleanup).
output_state:  harness/SHIP_REPORT.md complete and current. Branch ready
               for operator review + merge gate. Push NOT executed —
               per Git Authority Map, push requires explicit operator
               approval per call.
verifier:      L0 (git diff filter: P7 ZERO DIFF on agent/mcp_server.py)
               + content review (SPEC predicates mapped 1:1 to
               implementation evidence; F-findings mapped 1:1 to leaves;
               limitations enumerated)
outcome:       success — PASS 7 SHIP gate ready
external_calls: [Bash (git diff, git rev-list), Read (Brief B SHIP), Write]
```
