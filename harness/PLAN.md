# PLAN — Real Semantic Embeddings for comfy-moneta-bridge

PASS 3 (DECOMPOSE). Built from PASS 2 CAPSULE + operator decisions:
**M1 wire** (build cross-session injection, keep Outcome) · **P5 mode-matched**
(M2 re-embed dropped) · **P4 install-time split** (Amendment A1) · **P6 deferred**
(PENDING, gated PASS 6).

All leaves: substrate = `comfy-moneta-bridge` **MODIFY** (+ its `tests/`).
`Moneta` CALL-ONLY, `Comfy-Cozy` NO-TOUCH (L5 consumes its loader, never edits it).

---

## Plan Tree

```
ROOT: bge embeddings real, default, offline-safe, cross-session-wired
│
├─ L1  Verify embedder            (P1, P3)   [foundation, cheapest]
├─ L2  Synthetic backward-compat  (P5)       [safety net, pre-flip]
├─ L3  Provision + offline guard  (P4/M3)    [highest design risk; gates L4]
├─ L4  Flip default → bge         (P2)       [dep: L1,L2,L3]
├─ L5  Cross-session wire + e2e   (P7/M1)    [dep: L1,L4 — the Outcome]
└─ L6  Mac SMOKE latency          (P6 partial)[dep: L4; non-gating, not the record]
```

---

## Leaves (execution order: risk-reduction → dependency-unblock → cost)

### L1 — Verify embedder · P1, P3
- **GOAL:** Confirm `encode_outcome` is a correct, clean-importing, 384-dim, deterministic-within-tolerance real embedder.
- **CONTRACT:** `from comfy_moneta_bridge.vector import encode_outcome` imports clean (extras present); `len(encode_outcome({"workflow_summary":"x"})) == 384`; two encodes of identical input equal within `1e-5` (tolerance, not exact `==` — per F-DETERMINISM).
- **VERIFIER:** L0 (`ruff` + `pytest --collect-only`) + L1 (`tests/test_vector_bge.py`; add tolerance-determinism case if absent).
- **DEPENDENCIES:** none.

### L2 — Synthetic mode-matched backward-compat · P5
- **GOAL:** A synthetic-v0 `storage_uri` stays queryable **when queried in synthetic mode**, after all changes (operator: mode-matched).
- **CONTRACT:** with `BRIDGE_EMBEDDER_MODE=synthetic`, ingest a fixture outcome → `recall()` in synthetic mode returns it; payload carries `_embedder="synthetic-v0"`; round-trip green. Default-flip (L4) provably does not touch synthetic-mode behavior.
- **VERIFIER:** L1 (regression test vs pre-built synthetic fixture; extend `tests/test_recall.py` / `test_ingest.py`).
- **DEPENDENCIES:** none. Establishes the guard before L4.

### L3 — Install-time provisioning + ingest offline guard + socket-patch test · P4 / M3
- **GOAL:** BGE weights provisioned at install via deterministic, verifiable cache; **zero outbound network during ingest** in default config (Amendment A1).
- **CONTRACT:** (a) provisioning path places weights at a known cache with a verifiable marker/hash (pyproject extra + `scripts/provision_bge` or equivalent, deterministic); (b) encode path runs `local_files_only`/`HF_HUB_OFFLINE=1` so it never reaches network; (c) **socket-patch property test**: patch `socket.socket.connect` to raise, run `ingest_outcome` in bge mode against pre-provisioned cache → completes, zero connect attempts.
- **VERIFIER:** L2 (socket-patch property test = no outbound connection during ingest).
- **DEPENDENCIES:** none structurally; **success GATES L4**.
- **RISK NOTE (F-OFFLINE-FAIL):** offline guard hard-fails un-provisioned machines → provisioning is a mandatory documented pre-step.

### L4 — Flip default synthetic→bge; suite green both modes · P2
- **GOAL:** Default mode is bge; synthetic is opt-in fallback; full suite passes under both.
- **CONTRACT:** `vector.DEFAULT_MODE == "bge"`; `from_env()` with no env → `"bge"`; `BRIDGE_EMBEDDER_MODE=synthetic` → `"synthetic"`; full bridge suite green under **both** modes.
- **VERIFIER:** L0 + L1 (run suite twice, both modes).
- **DEPENDENCIES:** L3 (offline-safe), L2 (compat guard green), L1 (embedder verified).

### L5 — Cross-session wire into write_capsule + e2e · P7 / M1 (the Outcome)
- **GOAL:** `write_capsule` injects top-k cross-session semantic `recall()` hits as `notes` entries, within the existing capsule schema, so session B's capsule surfaces a semantically-relevant session-A memory.
- **CONTRACT:** (a) in bge mode, `write_capsule` calls `recall()` over content and appends top hits from **other** sessions as `notes` entries of an **existing** type (e.g. `"observation"`); (b) the augmented capsule validates against the schema `Cozy-Comfy/agent/memory/session.py` already loads — **NO new field, NO Comfy-Cozy edit** (verify `load_session` ingests it unchanged); (c) **e2e**: ingest sessions A+B under one `storage_uri`; `write_capsule` for B with a query semantically related to an A memory → `sessions/B.json` contains ≥1 note originating from session A; (d) **HALT + escalate (OP-9)** if the wire cannot fit existing schema.
- **VERIFIER:** L1 (e2e) + L3 (schema-compat with unchanged `session.py`; SPEC Outcome fit).
- **DEPENDENCIES:** L4 (bge default), L1.

### L6 — Mac SMOKE latency · P6 (partial, non-gating)
- **GOAL:** Screen catastrophic ingest latency on Mac. **Not** the P6 record.
- **CONTRACT:** bge-mode ingest of a small batch completes under a generous catastrophic ceiling (e.g. <2s/outcome median, Mac); output labeled `"SMOKE — not P6 record"`. Real P6 deferred to PASS 6 on Threadripper.
- **VERIFIER:** L4-lite (informational timing).
- **DEPENDENCIES:** L4.

---

## SPEC predicate ownership (PASS 3 gate)

| Predicate | Owner leaf |
|---|---|
| P1 | L1 |
| P2 | L4 |
| P3 | L1 |
| P4 | L3 |
| P5 | L2 |
| P6 | L6 (smoke) + **PASS 6** (real bench, Threadripper — deferred) |
| P7 | L5 |

Every predicate owned. ✅

---

## Ledger Hits

`ledger/recipes` empty (first harness run). **All leaves novel.** Successful traces
become `ledger/candidates`; promotion deferred to SLEEP after N-shot consolidation.

---

## Escalations

**None.** No leaf modifies frozen substrate. M1/L5 fits the existing capsule schema
(verified: `notes` entries, `capsule.py:37-57` ↔ `session.py:131-133,242-264`), so the
Comfy-Cozy NO-TOUCH boundary holds. L5 carries a halt-condition as a tripwire only.

## Bounded / out-of-scope (documented, not leaves)

- **F-THINTEXT / A4** → F4 separate brief ("capture more text").
- **F-CURSORLOSS** → separate brief.
- **F-SCHEMA2** → drift trap noted; ingest drops `schema_version!=1`.
- **F-EMPTYTEXT** → minor; optional guard folded into L1.
- **M6 batch-encode** → conditional; only if P6 fails at PASS 6.
