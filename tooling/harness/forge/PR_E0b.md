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

## Verification — including a full adversarial refutation round

- **Skeptic panel round 1: REFUTED 3/3** (LEDGER V2-E0B-R1) — 2 BLOCKERs
  (branch-writable thresholds; a wrong flake node id that made the name-based
  tolerance inert) + 6 MAJORs. All 18 findings fixed in the follow-up commit:
  ratchet v2 reads thresholds from **master's** baselines with a byte-integrity
  check, counts from junit XML (injection-proof), pytest errors refuse, disclosure
  scan fail-closed with auto-derived range (CI's `--brightline skip` explicitly
  does NOT certify disclosure), `--reset-original` gates the reconciliation anchor,
  and the constitution's §4/§6 now state the authority model precisely.
- Suite on the original content, twice: 4,686 passed / 0 failed; re-baselined with
  coverage after the ratchet rewrite (junit-sourced counts).
- ruff clean · pre-stage disclosure scans clean (2 authored-prose hits caught and
  neutralized BEFORE staging, per the composition rule)
- CI recomputes independently on this PR; skeptic round 2 runs on the fix commit

## Notes for review

- Local-only guard hardening (hooks) rides outside this PR by design — hooks are untracked.
- `gen_tool_docs.py` full generator is deliberately deferred to E4a; the registry-count
  check covers no-NEW-drift until then.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
