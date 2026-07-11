# LATENCY PASS — CONSTITUTION

Governs every session of the latency-and-refinement harness (`tooling/harness/latency/`
+ `tooling/bench/`). Blueprint lineage: WP-4.0 (trace scout) and WP-4.1 (benchmark
harness) of `LOCAL_TWIN_BLUEPRINT.md`, pulled into one measure→refine→verify ratchet.

## Article I — Measure before move

No refinement lands without a baseline number it demonstrably improves. Hypotheses
come from the adversarially-verified census; numbers come from `tooling/bench/` runs
on this machine. A hotspot nobody measured is a hypothesis, not a work item.

## Article II — Median-of-N or it didn't happen

Micro-benchmarks: median of ≥ 20 runs. Boot/cold benchmarks: median of ≥ 5 runs.
Cold vs warm always labeled. Hardware, Python version, and git SHA recorded with
every run. Single-run numbers are anecdotes and never enter the map.

## Article III — The ratchet

After each refinement: full test suite green (baseline 4,748) **and** re-measure the
full tracked scenario set. A refinement that regresses any tracked scenario > 2 %
median reverts — no exceptions, no "but it should be faster." `benchmark_log.jsonl`
is append-only (champion-tracking convention); every entry carries `{sha, scenario,
median_ms, n, mode}`.

## Article IV — Surgical, layered, lane-respecting

One hotspot per commit. `agent/stage/**` is frozen (C1) — cite it, never touch it.
L5 (ComfyUI execution) is upstream's lane: attribute it in the map, never optimize
it here. No new observability frameworks — L3/L4 spans ride the existing
logging + correlation-ID rails or they don't exist.

## Article V — Scope honesty

Offline scenarios run tonight. `needs-live-comfyui` and `needs-real-llm` scenarios
ship as runnable-but-deferred with exact run instructions — never as fabricated
numbers. C6 stands: measured numbers live in `benchmark_log.jsonl` and
`docs/LATENCY_MAP.md`; nothing reaches README/public surfaces until WP-4.1's
publication gate.

## Article VI — Inherited law

C1–C8 of the blueprint apply verbatim. Session git law: atomic commits under an
active grant; push/tag/remote ops are Joe's per-call decision, always. The
brightline pre-commit hook is never bypassed or token-renamed around.

## Article VII — Bounded failure

Three attempts per refinement (fix → re-measure → suite), then the hotspot parks in
the LATENCY_MAP DEADENDS table with what was tried and why it lost. A parked item
is a result, not a failure.

## Roles

| Role | Authority |
|------|-----------|
| Census agents | read-only; file:line evidence; no numbers |
| Verifiers | read-only; refute miscited/off-path claims |
| Bench (scripts) | the only source of numbers |
| Forge agents | one owned file-set per refinement; no git |
| Conductor | adjudicates, runs bench + suite, commits; sole mutation authority outside forge mandates |
