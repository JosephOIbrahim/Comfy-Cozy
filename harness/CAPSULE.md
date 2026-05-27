# CAPSULE — PASS 6 (STRESS)

Supersedes: PASS 5 capsule (integrate — git history + TRACE.md).
Consumed by: PASS 7 (SHIP).

---

## Attacks run (PASS 2 findings vs the real artifact)

| Attack | Result | Verdict |
|---|---|---|
| **F-MIGRATE** mixed-mode (synthetic+bge, 1 URI, bge query) | only bge returned; zero synthetic leak | ✅ SAFE |
| Strong bge match vs 100 synthetic noise vectors | match survives (over-fetch + high real cosine) | ✅ SAFE |
| **F-COLDSTART** all-synthetic store, bge query | empty, clean (no error) | ✅ SAFE |
| schema_version=2 drift | dropped at ingest, not stored | ✅ SAFE |
| Cross-session injection cap (8 candidates, top_k=3) | ≤3 injected | ✅ SAFE |
| **F-CURSORLOSS** replay (ingest 2×) | 2 duplicate copies | ⚠️ BOUNDED (out of scope) |
| **F-THINTEXT** templated vs distinct cosine | templated 0.984 / distinct 0.863 | ⚠️ BOUNDED |

5 safety invariants committed as tests (`test_stress_mixed_mode.py`); 2 bounded
weaknesses characterized by measurement (informational, not committed).

## Categorization

**Showstoppers: NONE.** No finding requires re-decomposition. The load-bearing
safety claim (mixed-mode isolation) holds — the `_embedder` filter + over-fetch
keep synthetic vectors out of bge results even at scale, because a real semantic
match (cos ~0.7) dominates random synthetic noise (cos ~±0.05).

**Bounded weaknesses (→ SPEC limitations, SHIP report):**
- **F-THINTEXT** — bare templated outcomes cluster (cos 0.984); P7 relevance
  scales with outcome text richness. Differentiation is content-driven (distinct
  summaries separate at 0.863). Fix = capture more text → F4, separate brief.
- **F-OFFLINE-FAIL** — offline ingest hard-fails on an un-provisioned machine;
  `provision_model()` is a mandatory install step (documented).
- **bge-small similarity floor** — absolute cosines run high (~0.86 even for
  distinct text); ranking works, absolute scores compressed. Inherent to the model.

**Out of scope (logged, separate briefs):**
- F-CURSORLOSS replay duplicates (no bridge-side dedupe).
- WAL behavior past ~1k ECS (not exercised; P6/perf territory).
- Synthetic PRNG same-name collision (fallback path only; bge default avoids it).

## P6 status

Still **PENDING** — Threadripper bench (Amendment A1). Mac smoke (16.9ms median)
is the only datum and is explicitly not the record. P6 is the sole predicate not
green; it gates nothing in PASS 4/5/6 and is carried to SHIP as a known-open item.

## PASS 6 gate

No showstopper findings ✅ · all bounded weaknesses documented ✅ → proceed to SHIP.

## Final test tally

296 passed (282 baseline + 14: 2 P5, 2 P4, 3 P7, 2 integration, 5 stress).
4 commits on `feat/bge-default-semantic` (aa0ae21, bb1b32a, 3b23bc5, c0c26ef), unpushed.
