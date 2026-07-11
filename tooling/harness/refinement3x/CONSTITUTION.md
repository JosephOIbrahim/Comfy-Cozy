# REFINEMENT 3× LOOP — CONSTITUTION

Governs every run of the refinement loop (`.claude/workflows/refinement-pass.js`,
invoked up to three times per campaign with a commit-ratchet between passes).

## Article I — Evidence or it doesn't exist

A finding enters a pass only with a `file:line` citation the adjudicator has
re-read and confirmed. No speculative refactors, no "would be nicer", no
features. Forbidden ground: `agent/stage/**` (C1), public tool schemas,
CLI/MCP behavior visible to artists, and repo-wide mechanical churn
(the 292-file format normalization is PARKED as a Joe-timed one-shot).

## Article II — Pass cap

At most 4 refinements per pass, ranked by leverage ÷ risk. A pass that ships
one excellent refinement beats a pass that ships six mediocre ones. Findings
that miss the cap are recorded, not forgotten.

## Article III — The ratchet

After every pass: full suite green at the campaign baseline + `ruff check`
clean. A regression reverts the offending refinement (3 attempts, then park).
One commit per pass, message listing applied + parked findings.

## Article IV — Diminishing returns

The loop runs at most 3 passes and ends EARLY the moment the adjudicator
scores no candidate at or above threshold (leverage ≥ 3/5 at risk ≤ 2/5).
An early exit is a result: the loop's job is to converge, not to fill quota.

## Article V — Inherited law

Blueprint C1–C8, session git law (commit under grant; push/merge per the
session's standing instruction), brightline guard never bypassed or renamed
around. Forge agents own disjoint file sets and never run git.

## Article VI — Roles

| Role | Authority |
|------|-----------|
| Scout lenses (robustness · simplification · truth) | read-only, ≤6 candidates each |
| Adjudicator | re-reads every citation; kills, ranks, caps, assigns ownership |
| Forge agents | owned files only; ruff + targeted tests |
| Crucible agent | full suite + ruff verdict |
| Conductor | commits, loops, reverts, reports |
