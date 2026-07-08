# PROD-HARDEN — Production-Readiness Harness (Orchestrator)

> Converts the 2026-07-07 external audit (`audit.md`, checked in verbatim) into
> verified, ratcheted fixes. Destination: **v5.6.0** (solo production) →
> **v6.0** (studio, Option A fleet-of-desktops).
> Sibling of the Science Harness — conventions inherited from `../LEDGER.md`.
> Seeded 2026-07-07.

## §0 Ratified decisions

- **2026-07-07 · Gate B RESOLVED (Joe): Option A — fleet-of-desktops.**
  "Studio-ready" = every artist runs their own single-tenant desktop instance.
  Studio-readiness is delivered through deterministic pinned installs, a
  per-user config layer, SECURITY.md + disclosure path, an upgrade/migration
  runbook, and a documented trust boundary that *removes* the unshipped
  SSE/HTTP promise rather than building it.
- **Option B (shared-service transport, auth, multi-tenancy) is a someday-RFC.**
  Candidate epoch for the v2 program (`../ORCHESTRATOR_v2.md`), NOT this
  harness. Ledger entry X-1 is forge-FORBIDDEN here.

## §1 Boot protocol — resume from here, never from memory

1. Read `LEDGER.md` top-to-bottom. The ledger is the only state; no other file
   or recollection overrides it.
2. Current wave = lowest-numbered wave with unresolved (non-DEFERRED,
   non-GATED) entries.
3. `GATED:JOE` entries: prepare evidence only. Never edit files, never draft
   the change, never "helpfully" resolve. G-1 (Patent/MIT) is counsel-adjacent.
4. Fixes require reproduce→clean: no forge work for a finding whose Wave-0
   Confirmation is missing from the ledger.
5. Every mutation step emits verification output before the next step.
   3 failed retries on one step → write `BLOCKER.md`, halt the wave.

## §2 Conventions (inherited from `../LEDGER.md`)

- Append-only ledger; supersede, never edit in place.
- `verified_by ∈ {V0, V1, V1-degraded}`; V1 = probed live on this machine.
- A Confirmation of a FINDING ≠ a verified FIX — "fixed" is reserved for
  reproduce→clean with its own appended Confirmation.
- Leads are forge-FORBIDDEN until probed. DeadEnds are recorded, not deleted.
- Markers specific to this track: `GATED:JOE` (legal/positioning;
  evidence-prep only) and `DEFERRED` (out of harness scope).

## §3 Waves & gates

### Wave 0 — Prove (read-only)
Eight parallel Prover agents re-run the audit's checks on this machine.
Output: Confirmation or non-repro DeadEnd per finding, appended to the ledger.
Nothing is fixed in Wave 0.

### Wave 1 — Solo-critical fixes → GATE A
One worktree-isolated Fixer + independent Verifier per finding:
F-S1 stage-test skips · F-S2 lockfile/requirements reconciliation ·
F-S3 cross-platform discovery · F-S4 SSE-promise removal · F-M1 mypy-in-CI.

**GATE A acceptance (all in a FRESH venv):**

```
pip install -e ".[dev]"            → exit 0
pytest tests/ -m "not integration" → 0 errors (skips allowed)
ruff check agent/ tests/           → clean
```

plus: both documented install paths resolve identical core deps; discovery
has no `G:\` and no PowerShell dependency; no README claim a fresh clone
can't reproduce; total pass count ≥ the Wave-0 baseline.

### Wave 2 — Docs & policy pack (parallel with Gate A review)
Docsmith + Red-team pairs: F-D1 SECURITY.md · F-D2 CONTRIBUTING +
CODE_OF_CONDUCT · F-M2 root-md sweep · F-M3 count/claim reconciliation.
Brightline scan before anything reaches Joe. → Joe ships **v5.6.0**
(Waves 1+2, one release).

### Wave 3 — Studio (Option A, concrete)
F-A1 per-user config layer (user-level config file above project `.env`;
precedence designed and documented, not improvised) ·
F-A2 fleet deployment runbook (pinned installs from F-S2's lockfile) ·
F-A3 upgrade/migration runbook (absorbs F-D3) ·
F-A4 trust-boundary document (single-tenant desktop; what the tool will
never do). → Joe ships the **v6.0** candidate. G-2 (Development Status flip)
unlocks only after Gate A + Wave 3.

## §4 Agent roles (workflow-internal; no new subagent files)

- **Prover** — reproduces one finding; read-only; a non-repro is a valid
  result, recorded as a DeadEnd.
- **Fixer** — one finding, one worktree, surgical diff; forbidden from
  adjacent code, legal text, and GATED items.
- **Verifier** — independent of the Fixer; fresh venv where the finding
  demands it; reproduce-was-dirty → now-clean → V1.
- **Docsmith + Red-team** — draft + adversarial pass (overpromising,
  disclosure-path gaps, brightline tokens).

## §5 Permission spine

- Agents read/build/test freely in worktrees + scratchpad.
- `git add`/`commit` only on `harden/*` branches, only under an explicit
  per-session grant from Joe. Never `git add -A`.
- Push, merge, release, remote-touching tags, and every GATED:JOE item =
  Joe's keystroke, per-call, no exceptions. The exfil pre-push hook stays
  in the path.
- 3 retries per step → `BLOCKER.md`.
