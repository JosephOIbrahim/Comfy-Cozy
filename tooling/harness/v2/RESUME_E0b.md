# RESUME — E0b (ratchet + hooks + census + baselines)

**Phase:** artifacts COMPLETE, gated on E0a's recipe merge (PR cuts from post-merge master).

## Done (2026-07-01/02, attended, inline — no workflow needed)
- `tooling/harness/verify_ratchet.py` — 7-check accept authority; name-based flake
  predicate (subset of KNOWN_FLAKES, never count-based); compiles, ruff-clean
- `tooling/harness/v2/baselines.json` — pinned via `--baseline` end-to-end @ 637049c:
  passed-floor 4567 (4568 measured − 1 flake allowance), collected 4569,
  import 516.6ms, registry 133; coverage deferred (--with-coverage at PR close)
- `.githooks/pre-push` — default-deny remote classifier (spoof-tested: a
  lookalike-named GitHub repo still gets SCANNED); fail-closed on absent scanner
- `.githooks/pre-commit` — fail-closed on absent scanner; --no-verify advice
  replaced with surface-to-owner; clean-staged pass verified
- `tooling/harness/v2/census.json` + `CENSUS.md` via `make_census.py` — strict
  partition asserted: 133 = 69+21+25+11+4+3 → 75 core (+ping), 28 aliases, 25 tombstones
- `tooling/harness/ORCHESTRATOR_v2.md` — harness constitution (9 sections)
- `tooling/harness/v2/{STATE.json,STATUS.md,GATES.md,BACKLOG.md}` seeded

## Next (in order)
1. Joe: scrub + recipe push/PR/merge (GATES.md G-A, G-B)
2. Cut `v6/e0b-runway` from post-merge master; `git add` the E0b artifacts BY NAME.
   Baselines: `--baseline --with-coverage` pins everything including the coverage
   floor in ONE sanctioned run. NOTE (post skeptic round R1): re-baselining is NOT
   a routine act — the `original` reconciliation anchor is preserved across runs
   and re-seeding it requires `--reset-original`, a Joe-reviewed harness-maintenance
   act; --check reads thresholds from MASTER's copy, so a branch-local re-baseline
   changes nothing until Joe merges it.
3. PR → Joe merge → E0c (author cozy-v2-epoch.workflow.js + 6 acceptance tests;
   push-denial + canary tests need the scrub done first)

## Open items riding along
- H-LOGHYG (.gitignore *.log/.env.bak) lands in this PR
- gen_tool_docs.py full generator deferred to E4a (verify_ratchet's registry-count
  check covers no-NEW-drift mode until then)
