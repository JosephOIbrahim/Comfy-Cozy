# PLAN.md — the four tracks (MODE: SIMULATED, round-robin attention)

Each: GOAL · CONTRACT · VERIFIER · queue · fork?

- **TRACK 1 — Tool Layer** (Home B) · GOAL: stop describing, start manipulating · CONTRACT:
  P1.1, P1.2 · VERIFIER: L1+L3 (disclosure), L1+L2 (surgery) · queue:
  `[#4 summary tier → #4 signature tier → #6 delete → #6 replace → #6 rewire]` ·
  **fork: none** (canonical builds).
- **TRACK 2 — Bridge → WS** (Home A + B) · GOAL: bidirectional canvas + free observability ·
  CONTRACT: P2.1–P2.4 · VERIFIER: L1+L2(+L4 push) · queue:
  `[Phase-0 bridge → #1 read-back → #5 profile → #8 watcher]` (Phase-0 first; rest share the
  WS subscription) · **fork: read-back transport (push vs pull) — resolve at its Leg 0.**
- **TRACK 3 — Comprehension** (Home B) · GOAL: read any shared workflow, resolve any local
  asset · CONTRACT: P3.1, P3.2 · VERIFIER: L1+L3 (parser), L1+L2+L4 (assets) · queue:
  `[#2 parser → #7 assets]` · **fork: parser mapping (schema-order vs heuristic vs hybrid).**
- **TRACK 4 — Gated / Dependent** (Home A + B) · GOAL: steering + cheap verification + real
  continuity · CONTRACT: P4.1–P4.3 · VERIFIER: L0-gate then L1/L2/L4 · queue:
  `[#3 (client-render gate FIRST) | #9 cache | #10 memory]` (#9, #10 may proceed
  independently of #3) · **fork: #10 relevance scorer.**

## ARC
`FRAME ✓ → SKETCH ✓ → DELIBERATE ⇄ EXECUTE (4 tracks) → INTEGRATE → STRESS → SHIP`
Loop-back on stagnation (N=3) or any falsification condition; re-derive mode at each reorganize.

## Stagnation tracker (N=3 → reopen DELIBERATE, announce)
- Track 1: 0 consecutive no-pass
- Track 2: 0
- Track 3: 0
- Track 4: 0
