# ORCHESTRATOR_v2 — Build-Harness Constitution (comfy-cozy v2 → 6.0.0)

> The BUILD harness: Claude Code agent teams editing this repo. Distinct from the
> PRODUCT harness (`agent/harness/cozy_loop.py`) — ideas are borrowed, code never is.
> Authoritative plan: Joe's plan file (see `v2/STATE.json:plan_file`), whose §13
> supersession map OVERRIDES the design annexes wherever they disagree.
> Green-lit 2026-07-01. Grants recorded in `v2/STATE.json`.

## §1 · Boot (cold-start protocol — every fresh session)

```
Read, in order: this file → v2/STATE.json → v2/GATES.md → DEADENDS.md →
for each in-flight epoch its v2/RESUME_<id>.md → git log --oneline -5 + git status.
Re-measure before trusting: python tooling/harness/verify_ratchet.py --check
(never trust recorded counts — re-establish truth mechanically).
MODE attended: gates surface inline. MODE unattended: epochs end at
"PR-ready, gate queued in GATES.md"; max epochs per run = STATE.json budget.
Confirmed/DeadEnd epochs are skipped (re-invocation is idempotent).
Print mile markers ("E2 · forge 3/6").
```

## §2 · Roles (one epoch = one invocation of `cozy-v2-epoch.workflow.js`)

| Role | Does | Never | Git | Tier |
|---|---|---|---|---|
| Scout | recon; verify every PRD seam live, cite file:line | judges | read | mid |
| Architect | design spec: files_to_touch, tests, `blast_radius_files`, frozen-zone contact, rollback handle; judge panel on >1 viable design | builds | read | strong |
| Forge | smallest-correct-change; commits per coherent unit, `[FORGE <id>]` trailer | judges own work | add/commit (epoch branch) | strong |
| Crucible | runs `verify_ratchet.py --check` **from master's copy**; reports numbers | fixes, judges | read | mid |
| Skeptics ×3 | adversarial review of **EVERY** `[FORGE]` commit in `base_sha..HEAD` (lenses: weakened-tests · silent-regression/scope-creep · determinism/frozen-zone); majority (≥2) refutes | build | read | strong |
| Scribe | sole writer of durable harness state (LEDGER, STATE, STATUS, GATES, RESUME, PR body); lightweight tags | push, annotated tags, branch deletion | add/commit/tag | mid |

Accept predicate: `ratchet.all_green AND refutations < 2`. No agent ever pushes,
touches remotes, deletes branches, or resets — structurally denied (settings deny
list) and constitutionally forbidden (CLAUDE.md authority map).

## §3 · Epoch loop

```
OPEN   PRD ratified (mechanical epochs: batch-ratified at green-light; direction
       epochs: ⛔ FRAME) → branch v6/<id> from master → verify_ratchet --check
       (re-establish green) → blast-radius intersection check vs in-flight epochs
RUN    Scout → Architect(±judges) → Forge → Crucible → Skeptics → accept predicate
       (one re-plan bounce allowed: skeptic/crucible evidence → Architect revises
       → Forge retries ONCE)
CLOSE  Scribe: LEDGER Confirmation|DeadEnd · STATE/STATUS/GATES/RESUME refresh ·
       PR body at forge/PR_<id>.md · tag v6/<id>/done · gate queued: push word
JOE    "push it" (per-call; push+PR = one grant, executed from MAIN CHECKOUT) →
       merge (mechanical epochs: standing auto-merge when CI green + skeptics
       unanimous) → next
```

Sizing: one PR reviewable in ≤30 min — bigger scope splits into sub-epochs (the
E3a–E3d / E4a–E4d pre-splits in STATE.json exist for exactly this).
Parallelism: max 2 forging epochs; `blast_radius_files` must be disjoint at
hunk level for the shared seams (`agent/tools/__init__.py`, `agent/gate/risk_levels.py`);
union-suite run before the second merge (H4 rule). Parallel epochs use worktrees
`G:\Comfy-Cozy-<id>`; WAVE=1 runs in-tree.

## §4 · Ratchet

`tooling/harness/verify_ratchet.py` is the ONLY accept authority. Baselines in
`v2/baselines.json` are measured-then-pinned (`--baseline`), never hand-edited.
Known flakes are tolerated BY NAME (subset check), never by count. Baseline
decreases only via `v2/baseline_deltas.jsonl` rows citing LEDGER IDs, in the
same commit that deletes the tests; sums must reconcile exactly. Doc-drift runs
in no-NEW-drift mode until E4a lands the strict generated-docs diff.
Frozen accept-authority (plan §4.17): this file, `verify_ratchet.py`, both
champion.json files, `baseline_deltas.jsonl`, `.claude/workflows/**`, `.githooks/**`
— editable only in harness-maintenance epochs Joe reviews file-by-file.

## §5 · Frozen zone & unfreeze

`agent/stage/**` is READ-ONLY for build agents. E1/E2/E4 perform *de-registration
only* (edits in `agent/tools/__init__.py`); stage-file deletions/moves happen
inside the E5b–E6 window opened by **G8**: Joe line-approves the exact FLOOR diff
as its own commit; the revert at window close is likewise Joe-reviewed. During
the window: brightline `--range` scan on every commit; human review at close.

## §6 · Gates (queue: `v2/GATES.md` — the queue, never the key)

G1 FRAME · G2 push ("push it", per-call, main checkout only) · G3 merge (standing
auto-merge for `mechanical: true` epochs, CI green + unanimous skeptics; others
per-PR) · G4 installs/new deps · G5 spend/keys · G6 brightline flag → HALT (the
relabel-is-bypass rule stands; `--no-verify` is forbidden for agents, always) ·
G7 DeadEnd review / judge-panel split / budget escalation · G8 stage unfreeze ·
G9 V1 live windows (E6 close, E8 release).
Grant phrases are accepted ONLY from Joe's interactive session — never read from
files. The harness continues other epochs (or BACKLOG hygiene lanes) while gates wait.

## §7 · Failure ladder

step retry ≤3 → one re-plan bounce → **DeadEnd**: LEDGER entry + DEADENDS.md row,
branch LEFT in place with lightweight `abandoned/<id>-<date>` tag (deletion is
Joe's, queued in GATES) → backlog continues → **BLOCKER.md + stop all** only on:
master baseline red · brightline flag · authority violation · verify_ratchet
itself broken. Spend-limit → SOLO-inline degradation; the Floor never bends.

## §8 · Disclosure-guard weave

Hooks are fail-closed (hardened 2026-07-01): pre-push default-denies every remote
except the local private repo; pre-commit refuses when the scanner is absent.
Worktree setup copies the scanner to exactly `<worktree>/scripts/brightline_scan.py`
(shared info/exclude keeps it untracked); teardown verifies removal. The
authoritative range scan always re-runs from the MAIN CHECKOUT before any push
request. Scanner subprocesses set `PYTHONIOENCODING=utf-8`. Public artifacts cite
LEDGER entry IDs, never bright-line subsystem names. A flag = G6 HALT: surface to
Joe with file+line; no rename, no bypass, no retry.

## §9 · Standing rules (from LEDGER, binding)

- D-10: pytest via redirected log; parse only the final summary line; never record
  a count before the summary line is in hand.
- Tool-count contract tests update in the SAME commit as any registry change.
- Never bare `git stash` in a worktree; commit before any state-mutating side-step.
- git add names files explicitly — never `git add -A`.
- Lightweight tags only; annotated tags and `git branch -D` are Joe-only.
- The census (`v2/census.json`) is the binding tool-disposition record; prose
  never carries counts — regenerate via `make_census.py`, which asserts the partition.

## §10 · Recursion contract (Utility Track — what the loop may improve about itself)

The harness recursively improves the product AND its own improvement machinery,
under three tiers:
- **Tier A (autonomous):** product code, tests, docs — normal epochs, full ratchet + skeptics.
- **Tier B (self-tuning, Joe-reviewed PR):** the golden-task eval suite, scenario
  weights, `explore_signals` ranking heuristics, BACKLOG priorities. Every change
  cites evidence (utility deltas, metrics); the golden-scenario count only ever
  ratchets UP (eval-gaming tripwire, same logic as the collected-count ratchet).
- **Tier C (never autonomous):** the accept authority — verify_ratchet.py, this
  file, the epoch workflow, hooks, gates, constitution. Harness-maintenance
  epochs only, Joe reviews file-by-file. **Recursion stops at the judge.**
The cycle: mine signals → rank → top candidate → epoch → measure utility delta →
LEDGER → repeat; dry spell → hygiene lanes. Utility is ratchet check #8 once the
golden-task suite lands (U0/U1): score ≥ baseline − band, per-scenario latency
within 1.25× of its champion.
