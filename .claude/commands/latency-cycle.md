---
description: Run one latency-optimization MoE chain (scout → profiler → architect → forge → crucible → profiler → vision → scribe).
argument-hint: "[operation name | hot-path description]"
---

# /latency-cycle — One latency-optimization MoE pass

Governed by `.claude/LATENCY_CONSTITUTION.md` (which inherits the Cozy
Constitution). Targets a specific operation and ratchets it through one
measure-propose-apply-re-measure-judge-persist loop.

## Target operation

$ARGUMENTS

## Chain protocol

The chain is **scout → profiler → architect → forge → crucible → profiler
→ vision → scribe** — note the double profiler invocation (one for
baseline, one for verification).

1. **Scout** — locate the operation in code. Identify call sites, callers,
   shared state. Output: `recon_report` with file:line citations.

2. **Profiler (baseline)** — capture p50/p95/p99 + mem_peak + a worst-case
   sample. Output: `measurement_report` named "baseline".

3. **Architect** — design ONE optimization that the constitution permits.
   Tag with (impact, confidence, effort). Adversarial vision: identify
   the worst-case input for the proposed change. Output: `design_spec`.

4. **Forge** — apply the optimization as a minimal, type-safe patch. No
   feature drift. Output: `build_artifact` with the diff.

5. **Crucible** — run the full test suite (`pytest -m "not integration"`)
   plus the targeted baseline workflow. Output: `execution_result` —
   PASS only if all 4194+ tests still pass.

6. **Profiler (verification)** — re-measure the same operation with the
   same N. Output: `measurement_report` named "after".

7. **Vision** — judge the proposal against the constitution:
     - improvement ≥ 10%? (Article II)
     - no metric regressed > 2%? (Article II)
     - mem_peak ≤ 1.5× baseline? (Article II)
     - same outputs? (Article III)
     - concurrent-call benchmark passed? (Article IV)
   Output: `quality_report` with verdict: `accept` / `refine` / `reject`.

8. **Scribe** — IF accepted: commit with the `[HARDEN:WS-N]` convention,
   include before/after metrics in commit body, save session, record
   experience. Output: `persistence_receipt`.

## Halt conditions

  - Profiler returns TERMINAL (target operation crashes) → halt
  - Crucible returns FAIL (test regression) → halt
  - Vision returns `reject` with same proposal class twice in a row → halt
  - Self-healing ladder counter > 3 for same signature → halt

## Output

Single chain-summary block at the end:

```
Operation:    <target>
Baseline:     p50=Xms p95=Yms p99=Zms mem=AMB
After:        p50=X'ms p95=Y'ms p99=Z'ms mem=A'MB
Improvement:  N% (target: ≥ 10%)
Verdict:      ACCEPT | REFINE | REJECT
Commit:       <sha> | (none)
```

Do NOT push to remote. Do NOT bypass the constitution.
