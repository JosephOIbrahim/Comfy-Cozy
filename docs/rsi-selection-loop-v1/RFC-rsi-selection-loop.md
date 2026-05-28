# RSI SELECTION LOOP v1 — RFC

**Status.** `RATIFIED — v1 architecture; PASS-1 SCOUT complete (§0 folded); 3 build prerequisites unmet (§0a egress, §0b blueprint capture, §0e cadence); awaiting Gemini R-series before FINAL.` Ratified 2026-05-28 by Joe (Creative Director); SCOUT 2026-05-28. Authored under `EXECUTION_MODE = DESIGN_ONLY` by `[AUTONOMY × ARCHITECT]`.

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

Load-bearing facts the build phase must confirm against the live repo before any forge work. **PASS-1 SCOUT (read-only, 2026-05-28) findings folded in below.** Net: §0c/§0d CONFIRMED; §0f CONFIRMED-WITH-CAVEATS; **§0a, §0b, §0e are UNMET build prerequisites.** The v1 architecture is sound; its build runway requires net-new Cozy-side work. These are pre-build gaps (Path D) — surfaced now by design, not blockers to the *design*.

- **§0a — Reward write path. `STATUS: NOT-CONFIRMED`.** `record_outcome()` (`agent/brain/memory.py:334` → `_append_outcome` `:314-317`) writes **only** append-only JSONL to `sessions/{session}_outcomes.jsonl`; it touches Moneta on **no** branch. The Substrate Egress "Action 1" in-process `deposit` has **not landed** here — the only Moneta path on this branch is the file-watch/outbox adapter `agent/integrations/moneta.py` (StageEvent-driven, not in-process). The genuine in-process `deposit` exists only on unmerged `feature/moneta-memory` (`agent/memory/moneta_store.py:147`) and deposits **conversation exchanges, not outcomes**. → **Prerequisite:** an in-process `record_outcome → Moneta deposit` (or a re-scoped exchange egress) must be authored, respecting the SCRIBE/Article-II boundary (Moneta sits outside the SCRIBE chain). See §9/E5.
- **§0b — Blueprint materialization *(CRUX)*. `STATUS: CONFIRMED — gap is real and larger than feared`.** Only the final workflow JSON is persisted; the resolved LIVRPS stack is **discarded**. Two compounding gaps: **(1)** the autonomous/RSI path **never builds a LIVRPS stack at all** — `cognitive/tools/compose.py:60-131` selects a template + flat params; `cognitive/pipeline/autonomous.py:26` imports `CognitiveGraphEngine` but never instantiates it. **(2)** The real LIVRPS machinery lives only in the interactive layer (`agent/tools/workflow_patch.py`), in-memory, FIFO-capped at 1000, **never serialized** (`DeltaLayer` has no `to_dict`/`from_dict`); `save_workflow` writes resolved JSON only. The experience sink `ExperienceChunk` stores `delta_count` (an **integer**), not the layers. → **§3's learned unit is neither produced nor persistable today.** Capturing it is net-new work across three layers (route compose through the engine; add `DeltaLayer` serialization; extend `ExperienceChunk`/sidecar at LEARN). `workflow_hash` addresses the *result* but is a one-way SHA-256 — it cannot reconstruct opinions/ordering. See §9/E4–E5.
- **§0c — Doc/harness convention. `STATUS: CONFIRMED`.** RFCs under `docs/<name>-vN/`; trace convention `harness/PLAN.md` + `harness/TRACE.md` (no dot, no `BUILD_HARNESS.md`).
- **§0d — Safety arc intact. `STATUS: CONFIRMED`.** Order `P(1) < R(2) < V(3) < I(4) < L(5) < S(6)` is enforced in `cognitive/core/delta.py:20-27` (`LIVRPS_PRIORITY`), surfaced via `DeltaLayer.priority` (`delta.py:83-86`); `graph.py:113-125` stable-sorts ascending and applies weakest-first, so **S writes last and wins on collision**. *Nuance: "INVERTED" is a comment (`delta.py:26`), not a separate code branch — S's dominance is realized purely by being the maximum priority (last-write-wins), not a dedicated inversion mechanism.* The loop's subordination-to-S guarantee (§4/§6/§8) is structurally sound.
- **§0e — Consolidation cadence trigger. `STATUS: NOT-CONFIRMED`.** **No session-end caller of `run_sleep_pass()` is wired anywhere** in the live runtime (Comfy-Cozy or Moneta production source) — only tests/load/doc examples call it. The "Consolidation Engineer's scheduler" named in `Moneta api.py:452` does not exist as code (aspirational). The MCP atexit/SIGTERM hook (`agent/mcp_server.py:490/492`) flushes the **USD stage**, not a Moneta consolidation pass. → **session-end is the ADOPTED-BUT-UNWIRED trigger; wiring it is a prerequisite, not a confirmation.** Scope pins cadence to "Moneta's own scheduler," which doesn't exist; and **§6-Q1** (no component holds a long-lived Moneta handle) blocks closure. §6-Q2 stays `RESOLVED-PENDING-SCOUT`. See §9/E6.
- **§0f — Passive decay reliance. `STATUS: CONFIRMED — WITH CAVEATS`.** Passive demotion holds: decay is a pure monotonic function (`Moneta decay.py:48-69`) applied to **all** live nodes unconditionally at three eval points — `query` (`api.py:400`), the attention reducer (`attention_log.py:131`), and the consolidation scan (`consolidation.py:161`); an unreinforced node still decays via `decay_all` and is pruned below `PRUNE_UTILITY_THRESHOLD=0.1`. **Caveats:** (a) decay **never self-fires** — dormant until an eval point is reached, so it depends on §0e's cadence wiring (a recipe never queried, with no sleep pass, does **not** fade); (b) recipe nodes must be deposited with `protected_floor=0.0` to be demotable (a positive floor makes them immune); (c) fade is **wall-clock half-life** (`DEFAULT_HALF_LIFE_SECONDS≈6h`, tunable), not per-pass. §9/E1's passive-demotion resolution is supported subject to (a)–(c).

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
- **E4 — `[VERIFY BEFORE BUILD — confirmed UNMET by SCOUT]`** §0b — resolved LIVRPS stacks are **not** materialized at generation time, and are not even produced on the autonomous path. §3's unit is not persistable today. See §0b / E5.
- **E5 — `[BUILD PREREQUISITE — SCOUT-surfaced]` Blueprint capture + outcome egress do not exist yet.** Two unbuilt prerequisites the loop assumes: **(i)** §0b — the resolved-LIVRPS-stack (§3's learned unit) is neither produced by the autonomous compose path nor serialized anywhere; capturing it is net-new work across three layers (route compose through `CognitiveGraphEngine`; add `DeltaLayer` serialization; extend `ExperienceChunk`/sidecar at LEARN). **(ii)** §0a — `record_outcome()` does not egress to Moneta; an in-process deposit hook (or re-scoped exchange egress, forward-ported from `feature/moneta-memory`) must be authored. **Neither is a Moneta-internals change nor a Safety-arc issue** — both are Cozy-side build work, gated post-Jun-16 (Path D). Not designed here.
- **E6 — `[BUILD PREREQUISITE — SCOUT-surfaced]` Consolidation cadence is unwired.** §0e — no session-end (or any) trigger for `run_sleep_pass()` exists in the live runtime; Moneta ships no scheduler. The loop "honors a cadence" that is not yet wired, and §0f's passive decay stays dormant without it. Resolution likely requires either Moneta shipping the Consolidation Engineer's scheduler **or** a Cozy-side session-boundary trigger — the latter touches the **SCRIBE/Article-II boundary** and must be revisited with that constraint before build. Coupled to §6-Q1 (long-lived handle). Not designed here.

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

**Status: `RATIFIED — v1 architecture`** (Joe, 2026-05-28). **PASS-1 SCOUT complete** (2026-05-28): §0c/§0d CONFIRMED, §0f CONFIRMED-with-caveats, **§0a/§0b/§0e are unmet build prerequisites** (see §0 + §9/E4–E6) — the design is sound; the build runway is not yet laid. **Awaiting Gemini R-series** before FINAL. No code, no wiring, no `agent/stage/` touch — Path D holds.
