# SPEC — Real Semantic Embeddings for comfy-moneta-bridge

Source brief: **B** (semantic embeddings, first-run harness validation).
PASS 0 status: **RATIFIED.**
Amendments:
- **A1 (2026-05-26)** — P4 refined to install-time provisioning split; P6 marked
  PENDING + gated at PASS 6. Substrate scope and Outcome unchanged. Re-ratified.

---

## Outcome

The bridge produces real semantic embeddings of Comfy-Cozy outcomes such that cross-session retrieval returns relevant results across sessions. When session B is hydrated against a `storage_uri` that previously held session A, queries issued during session B can retrieve session-A memories on the basis of semantic relevance, not session-key collision.

This is the first build that turns Moneta from *"locked decisions waiting for a real consumer"* into the actual semantic backbone the Comfy-Cozy README promises.

---

## Substrate Scope

| Repo | Permission | Files touched |
|---|---|---|
| `comfy-moneta-bridge` | **MODIFY** (v0 surface) | `vector.py`, `ingest.py`, `cli.py` (config), `tests/` |
| `Moneta` | **CALL ONLY** (frozen) | none modified |
| `Comfy-Cozy` | **NO TOUCH** (mature) | none |
| `comfy-cozy-app` | **NO TOUCH** (skeleton) | none |

Any PASS 3 leaf that proposes modifying Moneta or Comfy-Cozy halts and escalates per Operating Principle 9 (FROZEN SUBSTRATE IS UNTOUCHABLE).

---

## Acceptance Predicates

| ID | Predicate | Verifier |
|---|---|---|
| **P1** | `vector.py` exports a real-embedder function backed by a chosen local model. Imports clean, deterministic output for fixed input. | L0 + L1 |
| **P2** | Bridge ingest calls the real embedder by default; a config flag falls back to the legacy synthetic embedder. Existing test suite passes under both modes. | L1 |
| **P3** | Vector dim is exactly 384 to match Moneta's existing vector index width assumption. | L0 |
| **P4** | No outbound network calls during ingest in default config. Model weights provisioned at install time via deterministic, verifiable cache. Verified by socket-patch property test during ingest. | L2 |
| **P5** | Existing synthetic-vector `storage_uri`s remain queryable after the change. Regression test against a pre-built synthetic-vector fixture passes. | L1 |
| **P6** | Default embedder ingest latency stays within v0 envelope: median ≤ 100ms, p95 ≤ 200ms per outcome on Threadripper, with ECS ≤ 1000. **PENDING** until Threadripper-reachable; gated at PASS 6 (STRESS), not PASS 5. An optional Mac SMOKE check screens catastrophic failures only and does **not** constitute the P6 record. | L4 (bench) |
| **P7** | Cross-session retrieval works end-to-end. Hydrate session B against a `storage_uri` containing sessions A+B; at least one returned memory originates from session A and is semantically related to a representative session-B query. | L3 (semantic-relevance check) |

---

## Out of Scope

- WAL ~1k performance ceiling (separate brief).
- Survivorship bias / failed-outcome capture (separate brief).
- Cursor-loss idempotency (separate brief).
- Bridge → in-process Moneta import (separate strategic decision per the capsule artifact).
- Remote-API embedding option (locked out by hard constraint — local only).
- Modifying Moneta in any way (frozen).
- Comfy-Cozy read-path changes (deferred — see Falsification F5 for the escalation path).

---

## Falsification Conditions

| ID | Condition | Response |
|---|---|---|
| **F1** | Moneta's vector index has a fixed-at-first-deposit dim, and mismatching breaks downstream queries. | Return to PASS 0 with revised dim-handling strategy. |
| **F2** | Existing synthetic-vector `storage_uri`s become unreadable after the change (P5 fails). | Halt. Re-spec the backward-compat path. |
| **F3** | Per-outcome encode latency exceeds 200ms p95 on Threadripper (P6 fails). | Brief expands into batched-deposit territory. Re-spec. |
| **F4** | Outcome payloads have insufficient natural-language content for embeddings to differentiate (A4 falsified). | Brief expands into "capture more text in the outcome." Re-spec. |
| **F5** | Comfy-Cozy doesn't consume cross-session memories in any read path (A5 falsified). The brief produces working infrastructure with no user-visible value. | **Halt and surface.** Operator decides: expand scope into Comfy-Cozy (which crosses the NO TOUCH boundary and requires constitutional review), or accept this as infrastructure-only work and adjust the Outcome statement. |

---

## Load-Bearing Assumptions (PASS 1 scout targets)

These get verified by PASS 1's reconnaissance step before any sketch becomes load-bearing.

- **A1** — Moneta's vector index is dim-agnostic at the API level. Scout: `src/moneta/vector_index.py`.
- **A2** — Cross-session retrieval is mechanically possible today against the same `storage_uri`. Scout: empirical run of `bridge hydrate` against a clean URI with two sessions.
- **A3** — A 384-dim local model loads and runs CPU-fast enough on Threadripper. Scout: bench load + encode latency.
- **A4** — Outcome payloads contain enough natural-language content to embed usefully. Scout: sample real `outcomes.jsonl` lines.
- **A5** — Comfy-Cozy's read path actually consumes cross-session memories. Scout: Comfy-Cozy session-load path and Brain layer.

If any of A1, A2, or A5 fail at PASS 1, the brief is in trouble and PASS 0 reopens. A3 and A4 failures expand scope but don't kill the brief.

---

## Ratification

Operator: confirm or revise. Specifically:

1. Is the Outcome statement what you want?
2. Is the Substrate Scope correct — especially the NO TOUCH boundaries on Comfy-Cozy and Moneta?
3. Are predicates P1–P7 the right set? Anything missing?
4. Are falsification conditions F1–F5 the right escalation surface? Especially F5 — is the *"halt and surface"* response correct, or do you want a different default?

Once ratified, this SPEC freezes for the duration of the build. Changes require returning to PASS 0.
