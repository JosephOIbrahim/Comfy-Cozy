# LATENCY CONSTITUTION v1
# Governs the latency-optimization MoE chain. Inherits the COZY_CONSTITUTION
# (.claude/COZY_CONSTITUTION.md) — every commandment there still binds.
# This document layers latency-specific axioms on top.

## Article I — Measurement precedes mutation

No optimization lands without a published baseline. The baseline is a p50,
p95, p99 measurement of the targeted operation against a fixed workflow on
the target hardware (Threadripper PRO 7965WX / RTX 4090 / 128GB). Baselines
live in `agent/perf/baselines/` as JSONL with one entry per invocation.

A proposal that cannot point at a baseline is rejected without review.

## Article II — Regression budget

A latency optimization is **accepted** when:

  - It improves the targeted metric by ≥ 10% (absolute, not relative).
  - AND no other tracked metric regresses by > 2% (relative).
  - AND memory peak does not exceed 1.5× the baseline.
  - AND every existing test still passes.

A proposal that hits 9.5% improvement is **rejected** unless three or more
proposals can be batched to clear the 10% bar collectively.

## Article III — Same outputs invariant

Optimizations may not alter results. Same inputs → same outputs, bit-for-bit
where the underlying operation is deterministic (e.g., tool returns), and
within a documented tolerance where it isn't (e.g., float aggregations).

A proposal that changes outputs is not a latency fix — it's a feature
change and goes through normal review.

## Article IV — Concurrency-safety bar

Any optimization touching shared mutable state must:

  - Include a concurrent-call contention benchmark (N=4 threads × 1000 calls).
  - Show that p95 under contention degrades by no more than 50% vs. solo.
  - Pass the existing thread-safety test suite.

## Article V — Profile-or-it-didn't-happen

"I think this is faster" is not evidence. Acceptance requires either:

  - A py-spy or cProfile trace showing the hot path was actually hot.
  - A reproducible benchmark in `tests/perf/` showing the improvement.

Microbenchmarks without context (e.g., a 100ns hot loop in a path that runs
once per minute) are explicitly rejected.

## Article VI — Adversarial worst-case

Every proposal must answer: **what input is the worst case for this
optimization?** If the worst case regresses by more than the budget allows,
the optimization is rejected even if the median improves.

Example: a cache that's fast for repeated keys but pathological for
high-cardinality inputs must include a high-cardinality benchmark.

## Article VII — Atomic commits, tagged

Every latency-related commit MUST use the `[HARDEN:WS-N]` convention
already established in the codebase (per `docs/AUTHORITY_MAP.md`). The
commit body must include:

  - Before metric (cite the baseline file:line)
  - After metric (cite the new measurement)
  - Improvement % (computed)
  - Memory delta
  - Worst-case input considered

## Article VIII — Hardware honesty

All measurements name the hardware they were taken on. Numbers from a
laptop are not numbers from the target Threadripper. Cross-hardware
comparisons require both columns.

## Self-healing ladder (inherited from COZY_CONSTITUTION Article III)

Latency proposals classify failure the same way as other Cozy work:

  - TRANSIENT (benchmark variance, CI flake) → re-measure with N+1 samples
  - RECOVERABLE (improvement < 10%, regression on adjacent metric) → re-propose
  - TERMINAL (output divergence, memory blow-up, test failure) → halt

## Forbidden

  - Optimizing code paths that do not appear in any profile trace
  - "Future-proofing" by adding caches/pools that aren't backed by current data
  - Replacing stdlib with third-party deps for sub-millisecond gains
  - Any optimization that increases the public API surface
