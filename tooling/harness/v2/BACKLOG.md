# BACKLOG — v2 build

Epoch chain lives in STATE.json. This file holds the always-ready **hygiene lanes**
(blast-radius-disjoint work the harness runs whenever the serial chain is gated —
raises unattended duty cycle from ~30% to ~60-70%) and parked leads.

## Hygiene lanes (mechanical; standing auto-merge applies)

- [ ] H-COV: raise coverage on the lowest-covered kept modules (census bucket `keep` only; never touch agent/stage/**)
- [ ] H-FLAKE: characterize the known Windows flake (`test_kill_after_flush_resumes_cleanly`) toward de-flaking; never widen the allowance
- [ ] H-DOCSWEEP: fix stale counts/claims in docs against generated truth (post-E0b)
- [ ] H-LOGHYG: add `*.log`, `.env.bak` to tracked .gitignore (innocuous patterns only; lands with any E0b+ PR)
- [ ] H-DEADBRANCH: inventory stale local branches -> report for Joe's deletion batch (agents never delete)

## Read-only pre-work (allowed while a gate blocks the next serial epoch)

- Scout+Architect of the next `blocked` epoch against the PR-ready tree; no forge until merge.

## Utility Track (harness-architect design, 2026-07-02 — recursive utility/latency improvement)

- [ ] U0 (S, rides E0c): recursion contract §10 ✅ · 5 seed scenarios AUTHORED (utility_eval.py, first run 2026-07-02: score 0.2 — provision-gate PASSes through real dispatch; 4 fails are harness-integration: (a) dispatch requires an active session a bare runner doesn't establish — bootstrap it the way mcp_server/tests do; (b) check_model_compatibility param names; (c) error-humanity re-assert post-session). The session finding = E3a's dual-store issue observed from outside. utility_score.json format ✅ · ratchet check #8 wiring pending U0 completion
- [ ] U1 (M, ∥ E1/E2): suite → ~15 scenarios across 6 classes (intent translation, repair funnel, compat refusal, recipes, failure-message quality, undo round-trip) · per-scenario dispatch latency (public-safe latency axis; flagged local bench stays local) · utility baseline pinned
- [ ] U2 (M, after E4a alias metrics or earlier on JSONL+DEADENDS): explore_signals miner → auto-ranked BACKLOG candidates with evidence · first MINED epoch end-to-end = the recursion existence proof
- [ ] U3 (ongoing): mined cycle becomes default /loop behavior · Tier-B self-tuning begins

## Parked leads

- L-IMPORT-DELTA: cold-import 553.5ms pre-union → 334.0ms post-union (H2 perf wave restored); residual vs the 188-199ms recorded champion methodology — reconcile via the local latency lead's instruments (local-only; see exclude-list triage record) if it ever matters
- L-PROMPTS: MCP prompts spike (E4d) — could a ~50-tool core + prompts beat 75 on selection accuracy?
- L-ECOSYSTEM-PROBE: monthly — official local MCP? subgraph tooling? (pivot trigger per plan §3)
