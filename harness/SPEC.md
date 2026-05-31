# SPEC — Write-Back v1 (Tier 1+2) to the live ComfyUI canvas

Source brief: **Bet 3-out** (interaction track), **v2**.
PASS 0 status: **RATIFIED** (A1 propagated).
PASS 1 status: **CLOSED** — A1/A2/A3/A5 HOLD; F4 amended to A2 (Vitest pre-leaf).
Scope: **panel-only**, Tier 1 (widget/value edits) **+** Tier 2 (rewiring links
between *existing* nodes). Tier 3 (node create/delete, auto-layout) and MCP
write-back are **deferred**.

Ratified before this SPEC was drafted (do not re-open):
- **Target surface:** existing `panel/web/js/superduperPanel.js` `pushAgentToCanvas`.
  The `ComfyUI-SuperDuper-Panel` rebuild is **not** the target; the link-delta
  contract is host-agnostic and ports later. PASS 0 verifies the file, it does
  not re-decide the surface.
- **Scope:** panel-only. Tier 3 and MCP write-back deferred.

PASS 0 verification (this run):
- Target surface `panel/web/js/superduperPanel.js` exists; `pushAgentToCanvas`
  body at `:94–118`, docstring `:89–93`; `parseInt(nodeId, 10)` at `:101`;
  link-drop filter `if (apiValue !== undefined && !Array.isArray(apiValue))`
  at `:106`; `_lastGraphHash` at `:19, :33–35`; `onAfterChange` observer at
  `:66–71`. All scout citations match. **F5 does not fire.**
- Artifact rotation: confirmed not required. Brief B's
  `SPEC/PLAN/TRACE/CAPSULE/SHIP_REPORT` are committed at `377c788`; `harness/
  ledger/` is for recipe candidates only (see `ledger/candidates/`), not an
  artifact archive. Git history is the prior-run archive. This run's artifacts
  overwrite Brief B's in place at `harness/{SPEC,PLAN,TRACE,CAPSULE,
  SHIP_REPORT}.md`.
- Scout paths: this run's evidence lives in `harness/SCOUT_rewiring_scope.md`
  and `harness/SCOUT_canvas_state_sync.md`, **directly under `harness/`**.

Amendments:
- **A1 (2026-05-28)** — P1 narrowed from "every existing-node input slot" to
  "every link op that successfully applied." Outcome paragraph propagated;
  P3 expanded to enumerate the surface conditions (Tier-3 shape, stale node
  reference, missing slot). Contract shape stated explicitly: write-back v1
  is **best-effort-with-reporting, not all-or-nothing**. **A5** added to
  load-bearing assumptions to cover the user-visible surface-report path.
  *Origin: PASS 0 ratification gate, operator amendment.*
- **A2 (2026-05-28)** — F4 escalation resolved. Verifier stack: Vitest +
  minimal LiteGraph stubs (no jsdom — link-delta logic is pure-ish; DOM not
  required for L1/L2). Stack stand-up becomes **PASS 3 pre-leaf 0**:
  `package.json` + `vitest.config.{js,ts}` + `tests/panel/` + stub module for
  `app.graph`. Verifier layers L0–L4 bind to Vitest; P7 remains testable via
  L0 git-diff alone. Substrate Scope row for the panel frontend extends to
  cover the JS test dir. *Origin: PASS 1 escalation, operator selected
  option (A) — full automation.*

---

## Outcome

When the agent computes workflow changes, the panel applies them to the live
ComfyUI (LiteGraph) canvas as a **targeted delta-merge**: differing widget
values **and** differing links between existing nodes are written; untouched
nodes, values, and the director's manual edits are preserved; nothing the
agent emits is silently dropped. Write-back v1 is **best-effort-with-reporting,
not all-or-nothing** — ops that cannot apply (stale node reference, missing
slot, Tier-3-shape) are surfaced to the director, never silently dropped.
After a push, the canvas link state matches the agent's server-side
`current_workflow` for every existing-node pair **where the link op applied**;
non-applied ops appear in the surface report.

This closes a live, shipping gap: the agent is directed to use `connect_nodes`
as a first-class tool (`agent/system_prompt.py:34`), it emits links today,
and `pushAgentToCanvas` silently discards every one
(`panel/web/js/superduperPanel.js:89–92, :106`).

---

## Substrate Scope

| Surface | Permission | Files |
|---|---|---|
| Comfy-Cozy panel frontend (JS) | **MODIFY** | `panel/web/js/superduperPanel.js` (`pushAgentToCanvas` + new link-delta step); `panel/web/js/graphMode.js` if A5 surfacing required — operator-ratified target; rebuild rejected |
| Comfy-Cozy JS verifier stack *(added by A2)* | **CREATE** | `package.json` (vitest dep + scripts); `vitest.config.{js,ts}`; `tests/panel/**` (unit + property + semantic tests); minimal `tests/panel/_stubs/litegraph.js` |
| Comfy-Cozy server ops | **CALL-ONLY (built)** | `agent/tools/workflow_patch.py` — `connect_nodes`/`_handle_connect_nodes` + undo snapshot already exist; **do not change their semantics** |
| ComfyUI / LiteGraph core | **CALL-ONLY (never patch)** | upstream `node.connect` / `disconnectInput` / `disconnectOutput` / `removeLink` |
| MCP path | **NO-TOUCH** | `agent/mcp_server.py` |
| Moneta | **NO-TOUCH (frozen)** | none |

Any PASS 3 leaf that proposes touching MCP-write, modifying `connect_nodes`
server semantics, or patching upstream LiteGraph halts and escalates.

---

## Acceptance Predicates

| ID | Predicate | Verifier |
|---|---|---|
| **P1** | **Link-state parity (applied ops).** After a push, every link op that successfully applied achieves parity: the canvas link matches server-side `current_workflow` `inputs[*]` for that existing-node pair. Ops that cannot apply (stale node reference, missing slot) are surfaced per P3, never silently dropped, and are excluded from the parity assertion. Write-back v1 is best-effort-with-reporting, not all-or-nothing. | L1 + L3 |
| **P2** | **Delta-merge / no-clobber.** Push applies ONLY differing widgets + differing links. A manual edit on an untouched node/slot survives a push. (Pre-edit → push unrelated delta → assert survival.) | L1 |
| **P3** | **No silent drop (enumerated surface).** Every emitted delta is applied or surfaced. The surface report enumerates: (a) Tier-3-shaped deltas (add/delete node) — detected and reported, never applied; (b) stale node reference — server cites a node id absent from the canvas; (c) missing slot — server cites an input name absent on the live node. None of (a)–(c) is applied; none is silently dropped. | L1 + L3 |
| **P4** | **No echo.** Applying a push does not re-trigger `onAfterChange` back into the agent (suppress via `_lastGraphHash` at `:19, :33–35` or observer-pause at `:66–71`). Assert no re-sync fires post-push. | L2 |
| **P5** | **ID-shape correctness.** Server `[from_node_id_str, from_output_int]` maps correctly to LiteGraph numeric `node.id` + slot index (`parseInt` shim, cf. `:101`). | L1 |
| **P6** | **Disconnect correctness.** A `disconnect` op deduces `from_*` from the prior cached/undo value (`workflow_patch.py:753, :783` `old_value`) — no orphaned or wrong-source links. | L1 |
| **P7** | **Panel-only honored.** MCP write path unaffected; zero changes to `agent/mcp_server.py`. | L0 |

---

## Out of Scope

- Tier 3: node create/delete, auto-layout/placement (deferred — detected + reported only per P3).
- MCP write-back (deferred — no reconcile path exists there).
- Wholesale graph replace.
- Modifying `connect_nodes` server semantics (already built and correct per scout).
- The `ComfyUI-SuperDuper-Panel` rebuild (not the target — see ratified decisions above).

---

## Falsification Conditions

*Falsification → return to PASS 0 and amend, then continue. Not abort.*

| ID | Condition | Response |
|---|---|---|
| **F1** | LiteGraph link API not reachable/stable from the extension JS context. | Return PASS 0. Re-spec the frontend approach. |
| **F2** | Delta-merge still clobbers despite design (P2 fails). | Return PASS 0. Re-spec source-of-truth. |
| **F3** | PASS-1 assumption **A1** fails — the panel push does NOT keep the agent cache fresh before write-back. | Return PASS 0. v1 gains an explicit live-canvas read before write; amend + re-ratify. |
| **F4** | No viable JS verifier stack exists and can't be stood up. | Halt → operator decides: stand up a JS test harness as a pre-leaf, or accept manual verification. *Resolved by A2.* |
| **F5** | **Target-surface verification fails** — `pushAgentToCanvas` / scout `file:line` don't match the live repo. | Halt → surface to operator. (Verification failure on a ratified target — *not* a re-decision of existing-vs-rebuild.) |

*Stale node ref / missing slot are EXPECTED runtime failure modes handled by
P3, not falsifications. F1–F5 cover SPEC-aborts only.*

---

## Load-Bearing Assumptions (PASS-1 scout targets)

- **A1** — The panel's existing hash-diff push keeps the agent cache fresh
  before write-back. Scout: `panel/server/{routes,chat}.py` per-conversation
  lifecycle. *(PASS 1: HOLDS — `chat.py:86,:124-141,:144-162`.)*
- **A2** — LiteGraph link primitives (`node.connect`, `disconnectInput/Output`,
  `removeLink`) are reachable from the extension JS context with stable
  slot-index semantics. Scout: upstream LiteGraph/ComfyUI source.
  *(PASS 1: HOLDS — ComfyUI desktop app present; standard LiteGraph API.)*
- **A3** — `onAfterChange` suppression via `_lastGraphHash` (or
  observer-pause) prevents the echo. Scout: `superduperPanel.js:19, :33–35,
  :66–71`. *(PASS 1: HOLDS with caveat — neither auto-suppresses; PASS 3 must
  pick observer-pause or pre-stamp hash. Recommend observer-pause.)*

*(A4 — target surface — promoted to RATIFIED DECISION above, not an open
assumption. PASS 0 verified the file. Not re-opened.)*

- **A5** *(added by amendment A1)* — A user-visible surface in the panel for
  delta-failure reports (toast, modal, status bar, or equivalent) exists, or
  can be added within Tier-1+2 scope without dragging in Tier-3 work. Scout:
  `panel/web/js/graphMode.js:330–388` (existing repair/migrate notification
  patterns). *(PASS 1: HOLDS — `graphMode.js:312-317,:319-426` extensible
  status-bar pattern.)*

PASS-1 evidence already in hand: `harness/SCOUT_rewiring_scope.md` and
`harness/SCOUT_canvas_state_sync.md`. PASS 1 built on these and added the
per-predicate confidence scores recorded in `TRACE.md` spans s5–s9.

---

## Verifier Layers (bound to Vitest stack per A2)

- **L0** — `git diff --stat` filter (P7 panel-only check); JS lint (eslint or
  vitest's own type check) for the new test/extension code.
- **L1** — Vitest unit tests. Pure-function leaves (ID-shape shim,
  disconnect-source resolution) test directly. Stub `app.graph` minimally
  (getNodeById → fake node with `widgets[]`, `inputs[]`, `connect`,
  `disconnectInput`) for delta-merge logic.
- **L2** — Vitest property tests. No-echo: assert `onAfterChange` not
  re-entered post-push. No-wholesale-replace: assert the diff step writes ≤ N
  ops where N is the count of differing slots.
- **L3** — Semantic / SPEC-fit. Vitest integration with the stub graph,
  asserting parity against server-side `current_workflow` (the parity check
  is the L3 oracle).
- **L4** — Stress / property at scale. Burst N pushes, assert observer never
  leaks paused; serialize via mutex or debounce.

Real-canvas integration (no stubs) is deferred to PASS 5 manual smoke against
a live ComfyUI host. PASS 5 confirms the stubs were faithful.

---

## Hard Guardrails (non-negotiable)

- **Extension surface ONLY.** Frontend JS in `panel/web/js/` + the already-built
  server ops in `agent/tools/workflow_patch.py`. **Never patch ComfyUI core
  or LiteGraph upstream** — *call* LiteGraph's link API, do not fork or
  modify it.
- **Panel-only.** Do not touch `agent/mcp_server.py`.
- **Delta-merge only.** Wholesale graph replace is forbidden.
- **No silent drops.** Every emitted delta is applied or surfaced per the P3
  enumeration. Tier-3-shaped deltas, stale node refs, and missing slots are
  detected and reported, never applied, never silently dropped.
- **Git:** per-call approval for `push`. Never force-push or rewrite history.
  Stage specific files (no `git add -A`).
- **Frozen substrate:** Moneta is CALL-ONLY / NO-TOUCH (not in scope here regardless).

---

## Operating Principles (active for this run)

- The SPEC freezes **for a pass, not for the run.** Falsification returns to
  PASS 0 and amends — it does not abort, and does not silently work around.
- Amendments are logged. Every SPEC change, correction, or retracted
  conclusion is a `TRACE.md` span, so a downstream pass never inherits a
  stale conclusion.
- The harness manages its own lifecycle. Artifact rotation, re-ratification,
  and scope amendment evolve through the journey.

---

## Ratification log

- **PASS 0** — Ratified (with A1 propagated): Outcome ✓ · Target surface ✓ (closed Q2) · Predicates P1–P7 ✓ (P1, P3 amended) · Falsification F1–F5 ✓.
- **PASS 1** — Closed (with A2 amended): JS verifier stack chosen = Vitest (full automation).
