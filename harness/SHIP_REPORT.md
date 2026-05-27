# SHIP REPORT — Real Semantic Embeddings for comfy-moneta-bridge

Brief B · first-run harness validation · 2026-05-27
Branch `feat/bge-default-semantic` (comfy-moneta-bridge), 4 commits, unpushed.

---

## SPEC Compliance (predicate by predicate)

| ID | Predicate | Status | Evidence |
|---|---|---|---|
| **P1** | Real local embedder, clean import, deterministic | ✅ MET | `vector.py:encode_outcome` (BGE-small, 384d, lazy); `test_vector_bge.py` |
| **P2** | Real embedder by default; config flag → synthetic | ✅ MET | `DEFAULT_MODE="bge"`; `from_env` synthetic opt-in; suite green both modes |
| **P3** | Vector dim exactly 384 | ✅ MET | `DIMENSION=384`; encode output length asserted |
| **P4** | No network at ingest in default config (provisioned at install) | ✅ MET | `local_files_only=True` + `provision_model()`; socket-patch test, no env crutch |
| **P5** | Synthetic storage_uris remain queryable (mode-matched) | ✅ MET | `test_p5_synthetic_compat.py` real round-trip; mixed-mode isolation stress |
| **P6** | Ingest latency ≤100ms med / ≤200ms p95 on Threadripper, ECS≤1000 | ⏸ PENDING | Threadripper bench deferred (Amendment A1); Mac smoke 16.9ms (not the record) |
| **P7** | Cross-session retrieval end-to-end | ✅ MET | `test_p7_cross_session.py` + full-chain integration + **real Comfy-Cozy `load_session`** |

**6 of 7 met; P6 deferred by ratified amendment, not failed.** The Outcome —
session B retrieves a semantically-related session-A memory, reaching Comfy-Cozy's
real read path — is demonstrated end-to-end with the NO-TOUCH boundary intact.

## Known Limitations (from PASS 6)

| Limitation | Severity | Disposition |
|---|---|---|
| Thin/templated outcomes cluster (cos 0.984); P7 relevance scales with text richness | Medium | F4 — "capture more text," separate brief |
| Offline ingest hard-fails on un-provisioned machine | Low | `provision_model()` mandatory install step (documented) |
| bge-small absolute-cosine floor high (~0.86 even for distinct text) | Low | Inherent to model; ranking unaffected |
| Cursor-loss replay → duplicate deposits (no dedupe) | Medium | Out of scope — separate brief |
| WAL behavior past ~1k ECS unverified | Unknown | Out of scope — perf/P6 territory |
| P6 latency unverified on target hardware | Open | Threadripper bench required before production |

## Verifier Coverage

| Layer | Coverage |
|---|---|
| L0 static | ✅ ruff clean across changed surface |
| L1 behavioral | ✅ 296 passed (282 baseline + 14 new) |
| L2 property | ✅ socket-patch no-network; recall-failure isolation; mixed-mode isolation |
| L3 semantic | ✅ SPEC-fit per predicate; **real cross-repo consumer load** |
| L4 stress | ✅ 5 safety invariants; 2 bounded weaknesses measured |
| **Not tested** | **P6 latency on Threadripper** (no access from this host) — the only gap, by ratified deferral |

## Ledger Deltas

- **Candidates added (3):** `default-flip-env-stripped`, `offline-load-socket-patch`,
  `cross-session-within-existing-schema`.
- **Recipes promoted:** 0 (first run; promotion needs 3-shot consolidation at SLEEP).
- **Recipes archived:** 0 (none existed).

## Deployment Artifact

Branch `feat/bge-default-semantic` @ `c0c26ef` — 12 files, +607/-20.
Source: `vector.py` (default flip, offline load, provisioning), `capsule.py`
(cross-session injection). 10 test files. **Unpushed; not merged.**

Deploy sequence (when authorized): run `provision_model()` at install →
merge to the bridge's integration branch → **run the P6 bench on Threadripper**
before declaring production-ready.

## Recommended Next

1. **P6 bench on Threadripper** — close the one open predicate.
2. **F-THINTEXT** — enrich outcome payloads (capture more NL) so P7 relevance
   holds on real templated data. Separate brief.
3. **Cursor-loss dedupe** — v1 bridge candidate.
4. Consider `bge reembed` only if real synthetic data on Threadripper must be
   surfaced under the bge default (currently mode-matched; M2 was dropped).
