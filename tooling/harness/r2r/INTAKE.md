# R2R — Review → Release (intake harness)

> The **front door** for turning a prose review into shipped, verified,
> human-mergeable branches. R2R is a *conveyor, not an engine*: it ingests,
> triages, orders, and dispatches — the existing v2 machine executes.
> Authoritative execution law is `../ORCHESTRATOR_v2.md`; R2R never restates it.
> Built 2026-07-03 from `Comfy-Cozy_Review.md` (v5.5.0 first-principles review).

## What R2R owns (and what it does not)

| R2R owns (NEW) | R2R reuses verbatim (INHERITED from v2) |
|---|---|
| `FINDINGS.json` — parsed review, one immutable row/finding, append-only status | epoch loop: Scout → Architect → Forge → Crucible → Skeptics → Scribe |
| `triage.py` — deterministic (tier, consent, dispatch) policy | `verify_ratchet.py` — the ONLY accept authority |
| wave ordering (topo-sort on `depends_on` + blast-radius disjointness) | skeptics ×3 · gate queue (`../v2/GATES.md`) · failure ladder · disclosure hooks |
| dispatch shim (scoped finding → epoch id → `cozy-v2-epoch.workflow.js`) | STATE.json / LEDGER durable epoch state |

R2R adds **nothing** to the accept path. It decides *what* and *in what order*;
the epoch loop decides *how*; the ratchet decides *whether it lands*.

## The line R2R must never cross (consent asymmetry, build layer)

The review's top praise is the product's asymmetry — *edits act, fetches ask*.
R2R mirrors it one level up via `triage.py`:

- **Autonomous (no keystroke):** Tier-A product/test/doc edits → PR-ready via ratchet + skeptics.
- **Gated (Joe's keystroke):** push (G2) · merge (G3) · install/new-dep (G4) ·
  spend/keys (G5) · disclosure flag (G6 HALT) · stage unfreeze (G8) · release (G9) ·
  **accept-authority or consent-model edits (Tier C, file-by-file).**

`triage.py --selftest` is the executable proof this line holds — for the 11 live
findings *and* for synthetic probes (install→G4, accept-authority→Tier-C,
frozen-stage→G8, precedence). CI/dev runs it before any dispatch.

## Lifecycle (per finding)

```
parsed     row exists in FINDINGS.json (facts only)
verified   Scout confirms the seam LIVE on the branch (review cites `main`;
           we are elsewhere) — `verified:true` gates dispatch
scoped     triage.py verdict + Architect spec (files_to_touch, tests, blast_radius,
           rollback handle). link-existing findings STOP here (dedup)
forging    dispatched to one v2 epoch (id recorded on the row)
pr-ready   ratchet all_green · refutations<2 · disclosure_certified locally
gated      queued in ../v2/GATES.md (push/merge word from Joe)
merged | deadend | rejected
```

Resumable: cold-start reads `FINDINGS.json`, skips merged/deadend, resumes forging
(idempotent, same contract as ORCHESTRATOR_v2 §1 boot).

## MVP & waves

**MVP = one finding, prose → PR-ready.** Golden finding = **F-05** (MAX_DELTAS cap
+ compaction) — isolated blast radius in `cognitive/core/delta.py`, crisp test
(add >cap deltas → assert cap enforced + successive same-opinion Local edits
collapse). If the conveyor lands F-05 green, it scales.

- **W0** F-05 (golden) · F-10 (Scout-verify prediction path) · F-11 (README honesty, rides H-DOCSWEEP)
- **W1** F-04 (canonical outcome record — gates F-02/F-06)
- **W2** F-01 ∥ F-02 (disjoint seams) → F-06 · F-09
- **W3** F-07 (Tier-3 writeback, own milestone + Vitest) · F-08 (Tier-C-adjacent, Joe-reviewed)
- **LINK** F-03 → the E-track (census/de-registration) + L-PROMPTS. *Not a new epoch.*

## Evaluation (how we know it works)

- **Golden:** intake parses 11 findings each with a source cite, zero hallucinated rows;
  triage routes F-01→autonomous, F-08→Tier-C, F-02→G4, F-03→link; F-05 reaches PR-ready green.
- **Boundary:** `triage.py --selftest` green (consent + accept-authority + frozen-zone + precedence).
- **Failure:** kill mid-forge → cold-start resumes; 3-retry+1-replan exhaustion → DeadEnd + backlog continues.
- **Product-side:** each landed finding adds a golden scenario to U-track `utility_eval.py`
  (F-01→save_recipe round-trip; F-02→retrieval accuracy at N=30). Scenario count only ratchets **up**.

## Acceptance (R2R Phase 0–1 done)

1. `FINDINGS.json` holds all 11 findings, each Scout-verifiable **against the branch tree**.
2. `triage.py --selftest` passes (boundary asymmetry proven).
3. F-05 lands PR-ready, ratchet green, 0 refutations, gate queued — no keystroke
   consumed except the final push/merge word.
4. F-03 is linked, not duplicated (dedup proof).
5. LEDGER audit: no autonomous action touched a gated seam.

## Known risks

- **Duplication** → triage dedups vs STATE.json before minting an epoch (F-03 is the canary).
- **Stale seams** → review cites `main`; Scout re-verifies, `verified` gates dispatch.
- **Dep-creep** → F-02's embedder may pull MiniLM/torch → G4 until Scout confirms vendored.
- **Blast collision** → F-01/F-04/F-06 share `agent/tools/__init__.py` + accumulator →
  §3 disjoint-hunk + max-2-parallel + union-suite before the 2nd merge.
- **Consent drift** → F-08 tempts an autonomous gate edit → hard Tier-C. Recursion stops at the judge.
