# PROD-HARDEN — Ship Report: v5.6.0 candidate (Waves 1+2)

> 2026-07-07 · Gate A: **PASS** (LEDGER E-004). Everything below is built,
> committed, and independently verified. What remains is exclusively
> Joe-keystroke territory.

## What ships

**10 commits**, `origin/master (9d35b0e) → harden/wave1 (6) → harden/wave2-docs (4)`,
tip `a0cc6c2`. Every audit finding that was solo-critical or docs-tier is fixed
with reproduce→clean evidence; plus two defects the audit missed (F-API1/2,
found by the claude-api pass).

| Commit | Finding | One-liner |
|---|---|---|
| eeab902 | F-S1 | `.[dev]` suite: 27 errors → clean module skip |
| ae1bff8 | F-API1/2 | Thinking gate inverted — Opus 4.8 / Sonnet 5 / Fable 5 no longer 400; example model ids fixed |
| 3b11b72 | F-S4 | Unshipped SSE transport promise removed (Option A honesty fix) |
| e28a7f8 | F-M1 | mypy in CI, non-blocking (baseline: 126 errors / 42 files) |
| da05048 | F-S3 | Cross-platform `agent doctor`; `_find_comfyui.ps1` deleted |
| 1665d01 | F-S2 | `uv.lock` committed; divergent `requirements.txt` deleted |
| a98cb26 | F-D0/1/2 | SECURITY / CONTRIBUTING / CODE_OF_CONDUCT (red-teamed) |
| 6a5a411 | F-M2 | Root: 32 → 11 markdown files (24 → docs/archive/) |
| cef56bd | F-M3p1 | Tool counts 53/80 → 84/133; `.[dev]` story truthful |
| a0cc6c2 | F-M3p2 | Test counts cite the verified 4,640+ (was overclaiming 4,680+) |

## Verification (independent, fresh venv, py3.13)

- `.[dev,stage,exr]` (CI mirror): **4646 passed / 0 failed / 0 errors**, ruff clean,
  `uv lock --check` clean, `agent doctor` exit 0 offline, honesty greps all zero.
- `.[dev]` alone (the audit's broken promise): **4236 passed / 0 errors**.

## Joe's keystrokes (in order)

```bash
cd G:/Comfy-Cozy
git push -u origin harden/wave2-docs        # contains all 10 commits
# single PR is the recommended review shape:
gh pr create --base master --head harden/wave2-docs \
  --title "[release] v5.6.0 prep: production hardening — solo-critical fixes + community docs"
# after merge, locally:
git checkout master && git pull             # also fixes the STALE local master (still at v5.3.1!)
git worktree remove G:/Comfy-Cozy.wt/wave1 && git worktree remove G:/Comfy-Cozy.wt/wave2
# then the usual release flow: CHANGELOG entry + tag v5.6.0 (release.yml is tag-triggered)
```

The pre-push exfil hook will run on your push — all 10 commits already passed
the commit-time brightline scan. `harden/wave1` can be pushed separately if you
want a two-PR review instead.

## Decisions parked on your desk (agents will not touch)

1. **G-1** — "Patent Pending" (README:6, :1542, links to Harlo/PATENTS.md) vs MIT. Counsel-adjacent.
2. **G-2** — pyproject `Development Status :: 4 - Beta` → Production/Stable + README:89
   "production software" phrasing. Unlocks after this merges + Wave 3, your edit.
3. **CHANGELOG + version bump** — left to your release flow (harness didn't guess a date/number).

## Next on the conveyor

**Wave 3 (Option A, fleet-of-desktops → v6.0):** A1 per-user config layer above `.env`,
A2 fleet deployment runbook (pinned installs from uv.lock), A3 upgrade/migration runbook,
A4 trust-boundary doc. **X-1** (shared-service transport) stays a someday-RFC for the v2 program.

## Housekeeping notes

- Local `master` ref is stale at v5.3.1 — fork anything new from `origin/master`, not `master`, until you fast-forward.
- Fresh-install suite wall time is ~8 min (docs updated); warm runs are faster.
- mypy ratchet: 126 errors is the baseline; flip `continue-on-error` off when it hits zero.
