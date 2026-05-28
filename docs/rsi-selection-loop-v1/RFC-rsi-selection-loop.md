# RSI SELECTION LOOP v1 — RFC

**Status.** `RATIFIED — v1 architecture; §0 facts pending PASS-1 SCOUT; awaiting Gemini R-series before FINAL.` Ratified 2026-05-28 by Joe (Creative Director). Authored under `EXECUTION_MODE = DESIGN_ONLY` by `[AUTONOMY × ARCHITECT]`.

**Scope.** A recursive self-improvement (RSI) loop running *over* the consolidated Moneta memory produced by Substrate Egress v1.1. This is the layer **on top of** that foundation: Substrate Egress governs how experience gets *into* Moneta; this RFC governs how the system gets *better* by reusing what won.

**Foundation.** Builds on `../substrate-egress-v1.1/MISSION_SUBSTRATE_EGRESS_V1.1_DELTA.md` (the 7 `[RFC]` axioms). Referenced, **not restated** — every place this RFC says "consolidation," "Intra-Session Blindness," "WAL," or "materialized view," it means exactly what that document defines.

**Path D.** Markdown only. No code execution, no runtime wiring, no `agent/stage/` mutation until **Jun 16**. The `[EXEC SPEC]` companion (`EXECUTION_QUEUE.md`, mirroring the substrate-egress split) is deferred to post-gate and is intentionally absent here.

**Fixed law (not relitigated in this document).** Moneta is frozen to four ops. The LIVRPS **S=6 inverted Safety arc** is the immovable bounding mechanism for self-mutation. Reward anchors in **human selection only** — no model-as-judge.

---

## Spine quick-reference *(the loop's invariants)*

| # | Principle | Frame | Patent surface |
|---|-----------|-------|----------------|
| 1 | Closed selection loop: compile → present → **human selects** → reward → consolidate → promote → reuse | Control theory | P1 |
| 2 | Reward **is** human selection. Never a model-judged score. | Choice-anchored RL | P2 |
| 3 | The learned unit is the **resolved-LIVRPS-stack** (compiled blueprint), not the final workflow JSON | Compositional search | P4 |
| 4 | Promotion = the **existing N-shot gate** (3+ traces → recipe). No parallel path. | Falsifiability gate | P2 |
| 5 | Moneta consumed through **four frozen ops** only; cadence = `run_sleep_pass()` as Moneta defines it | Sovereign memory | P5 |
| 6 | All self-mutation is **subordinate to S=6**. The loop may never weaken, reorder, or bounded-queue Safety. | Deterministic state evolution | P1 |
| 7 | Autonomous **execution** is gated on the vision evaluator (out of scope here; named, not designed) | — | — |

---

## §0 — VERIFY FIRST

Load-bearing facts the build phase must confirm against the live repo before any forge work. The RFC's correctness rests on these; do not assume them. **PASS-1 SCOUT folds its findings here.**

- **§0a — Reward write path.** Confirm where `record_outcome()` writes and whether the Substrate Egress "Action 1" in-process `deposit` has landed. The loop's reward signal (§2) rides this path; if `deposit` is still file-watch rather than in-process, §2's reward-deposit step inherits that transport. `[VERIFY]`
- **§0b — Blueprint materialization *(CRUX)*.** Confirm whether resolved LIVRPS stacks are materialized/addressable **at generation time**, or whether only the final workflow JSON is persisted. §3 requires the *compiled blueprint* as the learned unit. If only final JSON exists today, capturing the resolved stack is a **prerequisite on the Substrate Egress side** (an Action-1 deposit concern), **not** a Moneta change. `[VERIFY — gates §3]`
- **§0c — Doc/harness convention.** Resolved: RFCs live under `docs/<name>-vN/` (this file mirrors `docs/substrate-egress-v1.1/`); the causal-DAG trace convention is `harness/PLAN.md` + `harness/TRACE.md` (no dot, no `BUILD_HARNESS.md`). `[CONFIRMED]`
- **§0d — Safety arc intact.** Confirm the LIVRPS opinion order `P < R < V < I < L < S` holds with **S pinned strongest** in the live composition engine before the loop is permitted to write any promoted recipe. `[VERIFY — gates §6 · provisionally substantiated by ratification CRUCIBLE against cognitive/core/delta.py:20-27 (LIVRPS_PRIORITY, S=6 "INVERTED: always wins") + cognitive/core/graph.py:113-116 (S sorts last, wins); SCOUT to formally confirm]`
- **§0e — Consolidation cadence trigger.** Confirm **session-end** is the actual `run_sleep_pass()` trigger in the live single-workstation runtime — the trigger adopted at ratification for §6-Q2, inheriting Substrate Egress Axiom 1's session-boundary consolidation. `[VERIFY — gates §6-Q2; RESOLVED-PENDING-SCOUT]`
- **§0f — Passive decay reliance.** Confirm Moneta applies **lazy decay** to unreinforced consolidated recipe nodes on the agent-facing path (without an agent op). §9/E1's passive-demotion resolution depends on this. `[VERIFY — supports §9/E1]`

---

## §1 — The Loop

The closed cycle, defined once:

1. **Intent.** A user intent arrives. The agent composes a **resolved-LIVRPS-stack** (a compiled blueprint) for it — optionally *seeded* by a prior recipe retrieved from Moneta (step 7).
2. **Candidates.** The blueprint produces one or more candidate outputs presented to the human.
3. **Selection.** The human picks which candidate(s) they kept. **This selection is the only reward signal** (§2).
4. **Reward deposit.** The selection event — `(intent-class, blueprint identity, kept | shown-and-passed)` — is written to Moneta via `deposit`, and its salience marked via `signal_attention` (§5).
5. **Consolidation.** At `run_sleep_pass()` cadence, Moneta consolidates deposited traces into the materialized view. Per **Intra-Session Blindness** (Substrate Egress Axiom 1), the loop **cannot** read its own current-session deposits; consolidation is session-boundary work.
6. **Promotion.** When the **existing N-shot gate** observes 3+ consolidated traces of a winning blueprint for an intent-class, that blueprint is promoted to a **recipe** (§4).
7. **Reuse *(the recursion)*.** Future intents of the same intent-class query Moneta for the promoted recipe and seed composition from it. The system improves because it reuses **human-validated** winning blueprints — no model retraining, no model judge.

**Why this is recursive self-improvement.** Step 7 alters step 1's starting point: future behavior is shaped by past human selections, deterministically, through the LIVRPS composition layer. The improvement is in *which priors compose first*, never in the Safety tier (§6).

**Execution boundary.** In v1 the loop **learns and proposes** autonomously, but **execution stays human-in-the-loop**: the agent does not autonomously run promoted recipes to mint new candidates without a human selecting. Closing that gap is gated on the vision evaluator (§8 OUT).

**Cross-session latency *(inherited).*** Because of Intra-Session Blindness, improvement manifests **across** sessions, not within one. The loop is intentionally slow-closed; that is a feature of the foundation, not a defect to engineer away.

---

## §2 — Reward: Human Selection

- **Definition.** Reward = the human's selection among presented candidates. Not a quality score, not a model judgment, not a heuristic. This is the load-bearing anchor (no-LLM-as-judge is fixed law).
- **Signal shape (v1).** Binary per candidate: `kept` vs `shown-and-passed`. Ordinal ranking is **[PROPOSED — v2; out of scope for v1]**.
- **Negative vs absent.** A candidate that was **shown and passed over** is weak negative evidence; a candidate **never shown** is *no* evidence. The reward-deposit (§1.4) must distinguish the two or the N-shot traces (§4) carry false negatives. Build-time design note, flagged.
- **Reward channel into Moneta.** Human selection enters as `signal_attention` — the retroactive-salience weighting that Substrate Egress Axiom 7 already reserves for "mapping retroactive confidence onto deduplicated nodes" (its Phase-2.5 hook). **Human selection *is* that retroactive confidence.** This RFC reuses that hook rather than inventing a reward channel — see §5.

---

## §3 — The Selected Unit: Resolved-LIVRPS-Stack / Compiled Blueprint

- **The unit the loop learns over is the resolved-LIVRPS-stack** — the fully composed opinion stack (which deltas at which tiers) that produced the candidate — **not** the final workflow JSON alone.
- **Why the blueprint, not the JSON.** The blueprint carries the *compositional* structure that makes a win **transferable** across similar intents (P4 combinatorial search). The final JSON is a leaf instance; the blueprint is the generative recipe. Learning over leaves would not generalize.
- **Persistence prerequisite.** This requires the resolved stack to be addressable at generation time — see **§0b**. If unmet, the unit is not persistable without a Substrate-Egress-side capture; that is a prerequisite, flagged, not designed here.
- **Storage form** is **§6-Q3** *(open)*. **Identity for trace-matching** depends on the intent-class clustering key, **§6-Q4** *(open)*.

---

## §4 — Promotion: the existing N-shot gate

- Promotion uses the **existing N-shot consolidation gate**: 3+ consolidated traces of the same `(intent-class, winning-blueprint)` → promote to recipe. **No parallel consolidation path is introduced** (per scope spine).
- **Falsifiability framing (P2).** A blueprint is an unproven assertion until ≥3 independent human selections corroborate it; only then does it graduate to a recipe (a validated prior). Promotion is a falsifiability gate, not a popularity counter.
- **Operates on consolidated traces only.** Promotion runs post-`run_sleep_pass()`, honoring Intra-Session Blindness — a blueprint cannot promote from inside the session that produced its trace.
- **Threshold is inherited.** The `N=3` gate is Moneta's existing definition; this RFC does not re-tune it. If the loop appears to need a different `N` or a different gate, that is a **change to the existing gate → ratification flag**, not a silent re-tune.
- **Subordination.** A promoted recipe is always below S in the tier order (§6); it can seed composition but can never override a Safety opinion.

---

## §5 — Moneta Consumption Contract

The loop consumes Moneta **only** through the four frozen ops:

| Op | Loop use |
|----|----------|
| `deposit` | Write the selection trace (the reward event, §1.4). |
| `query` | Retrieve candidate recipes/blueprints for an intent-class at composition time (reuse, §1.7). |
| `signal_attention` | Attach human-selection salience (retroactive reward weight) to consolidated nodes (§2). |
| `get_consolidation_manifest` | Read what has been consolidated/promoted — the recipe catalog the loop reuses (§1.7). |

- **Cadence.** Consolidation runs at `run_sleep_pass()` **as Moneta defines it** — invoked by Moneta's own scheduler, **never by the loop/agent**. The loop honors this and **proposes no alternative** (scope-pinned). Trigger = **session-end** (see §6-Q2, RESOLVED-PENDING-SCOUT).
- **Handle lifecycle** (long-lived vs per-deposit) is **§6-Q1** *(open)*.
- **Hard constraint.** If any loop function appears to need a **fifth op** or a Moneta-internals change → **§9 escalation**. Surfaced, never engineered around. One such tension was found during drafting (active recipe demotion) — see **§9 / E1**.

---

## §6 — OPEN QUESTIONS

Carried **verbatim** from the orchestrator prompt's §6 enumeration. None silently resolved.

1. **Long-lived vs per-deposit Moneta handle.** — `STATUS: OPEN — PASS-2 ARCHITECT` (resolve against the live repo).
2. **`run_sleep_pass()` cadence.** — `STATUS: RESOLVED-PENDING-SCOUT`. **Trigger adopted: session-end**, inheriting Substrate Egress Axiom 1's session-boundary consolidation. This is **not CLOSED** — it sits in the §0 verify-before-build bucket (**§0e**); PASS-1 SCOUT must confirm session-end is the real consolidation trigger in the live runtime before it resolves to FINAL. No alternative cadence is proposed (scope-pinned).
3. **Resolved-stack storage form: full serialized vs content-addressed reference.** — `STATUS: OPEN — PASS-2 ARCHITECT`. *(Non-binding observation: content-addressing would align with Substrate Egress Axiom 5's Environment-Pinning content-addressed identifiers — a consistency argument, not a resolution.)*
4. **Intent-class clustering key for N-shot consolidation.** — `STATUS: OPEN — PASS-2 ARCHITECT`. *(Coupling flag: this key is shared surface with Substrate Egress Axiom 3's diversity threshold, which must be "locked at shadow start." The loop inherits that lock; the choices should be made together.)*

---

## §7 — Inherited Dependencies

- **Substrate Egress Edit 5 — `causal_sequence_id` primary vs. fallback.** `STATUS: UNRESOLVED (inherited)`. Pending the R6 Q1 Causal-Invariant Code Trace against Moneta's LIVRPS source. **Do not assume a resolution.**
  - *Impact on this loop:* the ordering/identity of blueprint traces relies on `causal_sequence_id` semantics. If the **fallback** (loop-scoped monotonic snapshot) is selected, the 1:1 LIVRPS↔UI-state mapping is lost, and a winning blueprint reconstructed from its trace may not map frame-precisely to the UI state the human selected — weakening the precision of the `(blueprint → selection)` association the N-shot gate consolidates. Documented as an open inherited risk.
- **Intra-Session Blindness (Axiom 1).** The loop sees only **prior-session** consolidated recipes at reuse time; this fixes the cross-session improvement latency noted in §1. Inherited, not negotiable.

---

## §8 — Patent-Load-Bearing Invariants & Scope Fence

**Invariants (fixed; tension → §9 blocker, do not design around):**

- **S=6 inverted Safety arc (P1).** The bounding mechanism for self-mutation. Promoted recipes and learned blueprints are **always** subordinate to the S-tier. The loop may never weaken, reorder, or bounded-queue S. *Drafting check: no loop step requires touching S — see §9 / E2.*
- **Moneta four-op freeze (P5).** See §5. Fifth op or internals pressure → §9 escalation.

**Scope fence:**

- **IN:** single-workstation, product-runtime RSI over consolidated memory; human-selection reward; blueprint→recipe promotion via the existing N-shot gate.
- **OUT:** the **vision evaluator** — the loop's autonomous *execution* is gated on it; this RFC **names that gate and stops**, it does not design the evaluator. Also OUT: distributed / multi-agent operation; anything touching Moneta internals.

---

## §9 — Escalations & Blockers *(surfaced during drafting)*

- **E1 — `[RATIFIED — demotion split]` Recipe demotion / decay.** The loop rewards winning blueprints; over time some recipes go stale or stop winning. v1 resolves this as a **deliberate asymmetry in the reward physics**, not a gap — reinforcement is *active*, forgetting is *passive*:
  - **Passive demotion — COVERED.** Unreinforced recipes **fade on their own** via Moneta's existing **lazy decay**: a recipe that stops being re-selected receives no fresh `signal_attention`, so its salience decays through Moneta's own consolidation/decay machinery. This needs **no new op** — the loop consumes Moneta as a black box and lets decay happen; it does not invoke or control it. `[VERIFY — §0f: confirm lazy decay applies to unreinforced consolidated recipe nodes on the agent-facing path]`
  - **Active demotion — DEFERRED to §9 / counsel *(deliberate)*.** Explicit demotion or removal of a recipe has **no public op** in the frozen four, and adding one is a Moneta-API change. Because the four-op surface is **patent-load-bearing (P5)**, expanding it is **counsel territory, not an RFC decision**. v1 **withholds active negative control by design**: the loop can reinforce (human selection → `signal_attention`) but cannot explicitly punish. Substrate Egress R2 already rejected "freeze-decay" as a Moneta-frozen violation; v1 holds that line on purpose. This is the intended v1 reward physics, not an omission to be patched.
- **E2 — `[SAFETY ARC — checked, no tension found]`** No loop step requires weakening S=6. Promoted recipes slot **below** S in `P < R < V < I < L < S`, so they can never override Safety. Stated explicitly per fail-closed discipline: I looked for the tension and did not find it. *(Corroborated by ratification CRUCIBLE against the live composition engine.)*
- **E3 — `[INHERITED — not a new blocker]`** Edit 5 `causal_sequence_id` unresolved (see §7).
- **E4 — `[VERIFY BEFORE BUILD]`** §0b — if resolved LIVRPS stacks are not materialized at generation time, §3's unit is not persistable without a Substrate-Egress-side capture. Prerequisite, flagged.

---

## DECISIONS LOGGED *(ratified 2026-05-28 — not relitigated)*

- Reward = human selection only (no LLM-as-judge).
- Learned unit = resolved-LIVRPS-stack / compiled blueprint.
- Promotion = existing N-shot gate (3+ → recipe); no parallel path.
- **Demotion = passive only** in v1 (recipes fade via Moneta lazy decay when unreinforced); **active** demotion deferred to §9/counsel (no public op; expanding the four-op surface is patent-load-bearing). Deliberate asymmetry — see §9/E1.
- Cadence = `run_sleep_pass()` as Moneta defines it; no alternative proposed. **Trigger = session-end** (inherits Axiom 1) — `RESOLVED-PENDING-SCOUT` (§0e).
- §6 Q1 / Q3 / Q4 remain **OPEN — PASS-2 ARCHITECT** work against the live repo.
- Moneta four-op freeze; S=6 Safety arc fixed and strongest.
- Path D: markdown only, no code / no `agent/stage/` until Jun 16.
- Vision evaluator: execution-gating dependency; named, not designed.

---

## Traceability & next step

Every section maps to a scope-spine directive or an orchestrator §-reference (§0 verify-first, §6 open-questions, §9 escalation). The `[EXEC SPEC]` companion (`EXECUTION_QUEUE.md`) is **deferred to post-Jun-16** per Path D.

**Status: `RATIFIED — v1 architecture`** (Joe, 2026-05-28). §0 facts pending **PASS-1 SCOUT** (crux §0b); **awaiting Gemini R-series** before FINAL. No code, no wiring, no `agent/stage/` touch — Path D holds.
