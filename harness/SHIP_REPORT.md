# SHIP REPORT — Write-Back v1 (Tier 1+2)

Brief **Bet 3-out / Write-Back v1 · v2** · interaction track · 2026-05-28
Branch `feat/writeback-v1-tier1-2`, **10 commits**, unpushed.

Closes the live shipping gap where `pushAgentToCanvas` silently discards
every link the agent emits (`panel/web/js/superduperPanel.js:89–92, :106`).

---

## SPEC Compliance (predicate by predicate)

| ID | Predicate | Status | Evidence |
|---|---|---|---|
| **P1** | Link-state parity (applied ops) | ✅ MET | L-8 `_applyTouchedLink` calls LiteGraph `connect`/`disconnectInput` with the server's `[from_node, from_output]` shape; L-10 integration oracle + PASS-5 proxy assert connect args match server fixture |
| **P2** | Delta-merge / no-clobber | ✅ MET | L-1 server `touched-set` (diff vs last-pushed snapshot) + L-2 frontend iterates touched only. F-1 scenarios verified at every layer: L-1 pytest, L-2 vitest, L-10 integration, PASS-5 proxy, PASS-6 100-entry stress |
| **P3** | No silent drop (enumerated surface) | ✅ MET | All 6 surface types (`tier3_add`, `tier3_delete`, `stale_node_ref`, `missing_slot`, `malformed`, `link_rejected`) fire in one PASS-5-proxy test; L-7 accumulator + `graphMode.js` status-bar renders rolled-up "N delta(s) not applied" + modal |
| **P4** | No echo | ✅ MET | L-6 `withObserverPause` with try/finally + module-level refcount (PASS-6 amendment); observer canonical after success, sync throw, async reject, and overlapping pause |
| **P5** | ID-shape correctness | ✅ MET | L-3 `_parseNodeId` strict `/^-?\d+$/` regex on widget + link to-node + link from-node; non-numeric / null / empty all surface as `malformed` |
| **P6** | Disconnect correctness | ✅ MET (subsumed) | LiteGraph's `disconnectInput(input_name)` is self-sufficient — no source-id lookup needed; covered by L-8 + integration |
| **P7** | Panel-only honored | ✅ MET | L-11 PASS-7 check: `git diff master -- agent/mcp_server.py` returns empty |

**7 of 7 predicates met. SPEC fully compliant.**

---

## Mitigations Status (CAPSULE F-1 … F-8)

See `harness/CAPSULE.md` "PASS 4–6 verification status" table for the
finding-by-finding breakdown. Summary:

| Finding | Severity | Status |
|---|---|---|
| F-1 stale-cache clobber | DESIGN-CONSTRAINT | ✅ closed (L-1+L-2+L-8) |
| F-2 NaN node IDs | DESIGN-CONSTRAINT | ✅ closed (L-3) |
| F-3 Tier-3 leak | DESIGN-CONSTRAINT | ✅ closed (L-4) |
| F-4 observer-pause leak | HARDEN | ✅ closed (L-6 try/finally) |
| F-5 concurrent push race | HARDEN | ✅ closed (L-6 debounce + PASS-6 refcount amendment) |
| F-6 malformed shape | HARDEN | ✅ closed (L-3+L-5+L-8) |
| F-7 cross-mode visibility | BOUNDED | deferred — surface in PASS-5 manual if UX-critical |
| F-8 backend unreachable on push | BOUNDED | orchestrator swallows + logs; nice-to-have surface (status row) deferred |

---

## Verifier Coverage

| Layer | Coverage |
|---|---|
| L0 static / collect | ✅ `ruff check` clean on panel/server/{touched,routes,chat}.py + tests; `ruff format` applied; `npm test` exit 0. No JS lint stack (per A2 amendment — Vitest is the substitute). |
| L1 unit / component | ✅ 87 vitest cases across 7 files (sample, deltaFailures, pushApplyTouched, pushControl, pushOrchestrator, integration, stress); 24 pytest cases in tests/test_touched.py |
| L2 property | ✅ pushControl: observer restored on throw + async reject; pushOrchestrator: observer canonical post-push; stress: overlapping pause |
| L3 semantic / SPEC-fit | ✅ integration.test.js asserts P1/P2/P3/P4 directly on composed pipeline; pushOrchestrator.test.js exercises full push composition with vi.fn() stubs |
| L4 stress | ✅ stress.test.js: 100-entry push, 50-event burst, 50-node Tier-3 both directions, overlapping pauses, 80ms ackPush, mixed malformed, rapid 5-push sequence |
| Real-canvas L3 (live ComfyUI) | ⏸ DEFERRED — PASS-5 manual; operator-run before merge |

**Test totals: 111 (87 vitest + 24 pytest), 100% passing.**

---

## Known Limitations

| Limitation | Severity | Disposition |
|---|---|---|
| Real-canvas L3 against live ComfyUI not run automatically | Medium | PASS-5 manual; operator runs the panel as a ComfyUI extension and validates P1/P2/P3/P4 on the real canvas before merge. The PASS-5 proxy is a high-fidelity automated stand-in but not a replacement. |
| Cross-mode P3 visibility (status-bar only renders in GRAPH mode) | Low | F-7 BOUNDED. If PASS-5 manual surfaces this as a UX gap, add chat-mode mirror (`comfy-cozy:delta-failed` event posted as system chat message) — separate brief |
| Session routing between HTTP / WebSocket contexts | Architectural / pre-existing | Existing concern: `current_conn_session()` returns "default" for browser HTTP, `conv.id` for in-agent WebSocket. L-1 is session-id-parameterized so it adapts; if HTTP/WS sessions don't intersect in production, F-1 mitigation degrades. PASS-5 manual will surface if real. Out of write-back v1 scope. |
| Tier 3 (node add/delete + auto-layout) | OUT-OF-SCOPE | Deferred per SPEC. Detected + surfaced as P3 entries; never applied. |
| MCP write-back | OUT-OF-SCOPE | Deferred per SPEC; no reconcile path exists there. P7 verified. |
| Wholesale graph replace | OUT-OF-SCOPE | Forbidden per SPEC Hard Guardrails. |
| Backend-unreachable surface row | Low | F-8 BOUNDED; orchestrator logs to `console.debug`. Status-row surface deferred — separate brief. |
| `_resetObserverPauseState` exported | Low | Test-only API exported from production module; documented in source. Tolerable; could be `import.meta.env`-gated later. |

---

## Deployment Artifact

Branch `feat/writeback-v1-tier1-2` @ `ee2f4e4` (HEAD).
29 files changed, +6,535 / -453, **10 commits**, **unpushed, not merged.**

**Server side (Python):**
- `panel/server/touched.py` (new, ~165 LOC) — per-session touched-set
- `panel/server/routes.py` (+125 LOC) — `/get-workflow-api-with-touched`, `/ack-push`, load + reset hooks
- `panel/server/chat.py` (+ ~10 LOC) — `clear_session` on WS disconnect

**Frontend (JS):**
- `panel/web/js/_deltaFailures.js` (new) — L-7 surface accumulator
- `panel/web/js/_pushApplyTouched.js` (new) — L-2/L-3/L-4/L-5/L-8 apply pipeline
- `panel/web/js/_pushControl.js` (new) — L-6 debounce + withObserverPause (refcount)
- `panel/web/js/_pushOrchestrator.js` (new) — PASS-5-proxy: composed push
- `panel/web/js/superduperPanel.js` — `pushAgentToCanvas` now delegates to orchestrator
- `panel/web/js/agentClient.js` (+ 28 LOC) — `getWorkflowApiWithTouched`, `ackPush`
- `panel/web/js/graphMode.js` (+ 78 LOC) — status-bar + delta-failure modal

**Verifier stack (per A2):**
- `package.json`, `vitest.config.js`, `tests/panel/_stubs/litegraph.js` + 7 test files

**Harness ledger:**
- `harness/{SPEC, PLAN, CAPSULE, TRACE, SHIP_REPORT}.md` — this run's record
- `harness/SCOUT_{rewiring_scope, canvas_state_sync}.md` — PASS-1 evidence
- Brief B's prior record preserved at commit `377c788`

**No deletion of MCP write path** (P7 verified by L-11 git-diff).

---

## Deploy sequence (when authorized)

1. **PASS-5 manual L3 against live ComfyUI:**
   - Install panel as a ComfyUI custom extension.
   - Load a workflow into the canvas.
   - Trigger agent mutations (widget edit, link change) via the chat panel.
   - Confirm: canvas reflects agent changes; manual director edits on untouched
     nodes survive a push; no echo back into the agent; P3 status bar surfaces
     simulated failures (stale-ref, missing-slot, Tier-3) when forced.
2. If PASS-5 surfaces UX issue with `F-7 cross-mode visibility`, file a
   follow-up brief; don't block merge.
3. **Operator approves merge.** Push (per-call git push approval).
4. PASS-7 SLEEP: scan `harness/ledger/candidates/` for promotable recipes
   (none from this run; pure feature build).

---

## Recommended Next

1. **PASS-5 manual L3** — close the one remaining verification gap; expected
   smoke test, no production risk anticipated.
2. **F-7 cross-mode P3 visibility** — only if PASS-5 surfaces it as
   UX-critical. Cheap to add (chat-mode mirror of status-bar warnings).
3. **F-8 backend-unreachable status row** — nice-to-have; surface a
   persistent "agent backend offline" indicator. Cheap.
4. **Tier 3 follow-up brief** — node create/delete + auto-layout placement.
   The hardest open question (per CAPSULE) is: how does the agent's emitted
   node-add render on a canvas the agent didn't visually compose?
5. **Architectural: session routing** — investigate whether browser-HTTP
   "default" session and in-agent-loop `conv.id` session need to be reconciled
   for write-back v1 mitigations to hold under real WebSocket flows.
6. **Cleanup follow-up:** `_resetObserverPauseState` is test-only; consider
   gating with build-time flag (vite-define, etc.) before production hardening.

---

## Operator decision

**Decision: SHIP** (with PASS-5 manual L3 as a pre-merge gate).
Operator-confirmed at PASS 7 SHIP question.

Per CLAUDE.md Git Authority Map: **push requires explicit operator
approval**; the materials below are prepared for the operator to execute.
The branch is **not pushed** by this run.

---

## Merge preparation (operator commands)

### Step 1 — Push the feature branch

```bash
git push -u origin feat/writeback-v1-tier1-2
```

### Step 2 — Open the PR

```bash
gh pr create --base master --head feat/writeback-v1-tier1-2 \
  --title "feat(panel): write-back v1 (Tier 1+2) — close link-drop gap with delta-merge + observer-pause + Tier-3 surface" \
  --body-file harness/PR_BODY.md
```

(PR body is also drafted inline below — operator can paste directly into
`gh pr create --body "..."` instead of using the file form.)

### Step 3 — PASS-5 manual L3 against live ComfyUI (before merge)

- Install the panel as a ComfyUI custom_node extension (point ComfyUI at
  this repo's `panel/` directory or symlink it under `ComfyUI/custom_nodes/`).
- Load a workflow into the canvas.
- Trigger agent mutations via the chat panel (widget edits + connect_nodes).
- Confirm:
  - canvas reflects agent changes (P1)
  - manual director edits on untouched nodes survive a push (P2, F-1)
  - no echo back into the agent (P4)
  - simulated Tier-3 / stale-ref / missing-slot deltas surface in the
    status bar as "N delta(s) not applied" with the Details modal (P3)
  - rapid `workflow-changed` events coalesce to one push (F-5)

### Step 4 — Merge after PASS-5 passes

```bash
gh pr merge --merge   # or --squash if the project prefers; this branch
                      # is 11 distinct commits, --merge preserves the
                      # leaf-by-leaf TRACE-able history
```

---

## PR title

```
feat(panel): write-back v1 (Tier 1+2) — close link-drop gap with delta-merge + observer-pause + Tier-3 surface
```

## PR body (paste into gh pr create --body)

```markdown
## Summary

Closes the live shipping gap where `pushAgentToCanvas` silently
discards every link the agent emits (`panel/web/js/superduperPanel.js:89–92, :106`).
Tier 1 (widget edits) **+** Tier 2 (rewiring links between *existing*
nodes) write-back to the live ComfyUI canvas via a touched-only
delta-merge.

Tier 3 (node create/delete + auto-layout) and MCP write-back are
deferred per SPEC — Tier-3-shaped deltas are detected and surfaced,
never applied; MCP path is untouched (P7 verified).

## What changes

**Server (`panel/server/`):**
- `touched.py` (new) — per-session "last pushed" snapshot + diff
- `routes.py` — `/get-workflow-api-with-touched`, `/ack-push` endpoints;
  `record_last_pushed` hooked into load + reset
- `chat.py` — `clear_session` on WebSocket disconnect

**Frontend (`panel/web/js/`):**
- `_pushApplyTouched.js` (new) — touched-only iteration with full
  L-3/L-4/L-5/L-8 surface enumeration (tier3_add, tier3_delete,
  stale_node_ref, missing_slot, malformed, link_rejected)
- `_pushControl.js` (new) — `debounce` + `withObserverPause`
  (module-level refcount; safe under concurrent overlap)
- `_pushOrchestrator.js` (new) — composed push: clear → fetch →
  pause → apply → setDirty → ack
- `_deltaFailures.js` (new) — surface-report accumulator
- `superduperPanel.js` — `pushAgentToCanvas` rewritten as one-line
  delegation
- `agentClient.js` — `getWorkflowApiWithTouched`, `ackPush`
- `graphMode.js` — status-bar warning + modal for "N delta(s) not
  applied"

**JS verifier stack (new — per SPEC amendment A2):**
- `package.json`, `vitest.config.js`
- `tests/panel/` (7 test files): sample, deltaFailures,
  pushApplyTouched, pushControl, pushOrchestrator, integration, stress
- Stubs: `tests/panel/_stubs/litegraph.js`

**No changes to `agent/mcp_server.py`** (P7 panel-only honored; verified
by L-11 `git diff master -- agent/mcp_server.py` → empty).

## Test results

| Suite | Count |
|---|---|
| Python (`tests/test_touched.py`) | 24/24 |
| JS Vitest (7 files) | 87/87 |
| **Total** | **111/111** |

`ruff check` clean. `ruff format` applied across changed Python.

## SPEC compliance

7 of 7 predicates met:

- **P1** link parity (applied ops) — L-8 + L-10 + PASS-5 proxy
- **P2** delta-merge / no-clobber — L-1 + L-2 + F-1 stress
- **P3** enumerated surface — all 6 types in one push test
- **P4** no echo — L-6 + module-level refcount
- **P5** ID-shape — L-3 strict `/^-?\d+$/`
- **P6** disconnect correctness — LiteGraph self-sufficient
- **P7** panel-only — git-diff filter empty

See `harness/SHIP_REPORT.md` for predicate-by-predicate evidence,
`harness/CAPSULE.md` for the F-1..F-8 verification table,
`harness/TRACE.md` for the append-only causal log (s0..s25).

## Known limitations

- **Real-canvas L3 against live ComfyUI** is the one open verification
  gap (PASS-5 manual). PASS-5 automated proxy + PASS-6 stress are the
  regression net; this PR should be reviewed AND validated against a
  real canvas before merge.
- Cross-mode P3 visibility (status-bar only in GRAPH mode) — BOUNDED,
  deferred per SPEC.
- Session routing between browser-HTTP and in-agent-WebSocket contexts
  — architectural pre-existing concern; out of write-back v1 scope.
- `_resetObserverPauseState` is a test-only export from production
  code; tolerable, could be build-flag-gated later.

## Test plan

- [ ] Pull branch; install panel as ComfyUI custom extension
- [ ] Load a workflow into the canvas
- [ ] Trigger an agent widget edit via chat → confirm canvas reflects it
- [ ] Hand-edit a node widget; trigger an agent edit on a DIFFERENT node
      → confirm hand edit survives (F-1 / P2)
- [ ] Trigger an agent link change → confirm canvas link state matches
      server `current_workflow.inputs[*]`
- [ ] Force a stale-ref / Tier-3 / missing-slot condition → confirm
      status-bar surfaces "N delta(s) not applied" + modal lists entries
- [ ] Rapidly fire `workflow-changed` events → confirm only one push
      fires (F-5 debounce)
- [ ] Throw mid-apply (forced) → confirm observer restored, push catches

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```
