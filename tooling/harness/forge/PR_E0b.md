# [v6/e0b-runway] Build-harness runway: mechanical ratchet, census, constitution

Opens the v2 program's runway (epoch E0b of the green-lit v2 plan; LEDGER V2-E0A/V2-E0B).

## What this adds

- **`tooling/harness/verify_ratchet.py`** — the single mechanical accept authority for v2
  epochs: full-suite floor, collected-count anti-gaming tripwire, skip-count diff, ruff,
  cold-import budget (1.25×), coverage floor (canonical leg), doc-drift (no-NEW-drift mode),
  disclosure-guard range scan (fail-closed). Known flakes tolerated **by name**, never by
  count. Baseline decreases only via `baseline_deltas.jsonl` rows citing LEDGER IDs.
- **`tooling/harness/v2/baselines.json`** — measured-then-pinned @ a74b4c1: floor 4,685 /
  collected 4,687 / import 334.0ms / registry 133.
- **`tooling/harness/v2/census.json` + `CENSUS.md` + `make_census.py`** — the BINDING strict
  partition of all 133 registered tools (asserted mechanically: no dupes/missing/phantoms):
  `133 = 69 keep + 21 merge-away + 25 delete + 11 provisioning + 4 scene + 3 nim` →
  **75-tool core (+ping)**, 28 aliases, 25 tombstones.
- **`tooling/harness/ORCHESTRATOR_v2.md`** — the build-harness constitution (§1 boot →
  §10 recursion contract). Roles, epoch loop, ratchet contract, gates, failure ladder,
  Utility Track tiers (recursion stops at the judge).
- **`tooling/harness/v2/{STATE,STATUS,GATES,BACKLOG,RESUME_E0b}`** — durable program state;
  any fresh session cold-starts from files, never transcripts.
- **Hygiene:** `.claude/settings.local.json` untracked (machine-personal permission state
  does not belong in history) + gitignored; `.env.bak` / `*.log` gitignored.

## Verification

- Suite on this exact content, twice: 4,686 passed / 0 failed (union-2 run + `--baseline` run)
- ruff clean · candidate-file disclosure scan clean (2 authored-prose hits found pre-stage
  and rewritten to neutral language per the standing composition rule)
- CI recomputes independently on this PR (the ratchet's design assumption)

## Notes for review

- Local-only guard hardening (hooks) rides outside this PR by design — hooks are untracked.
- `gen_tool_docs.py` full generator is deliberately deferred to E4a; the registry-count
  check covers no-NEW-drift until then.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
