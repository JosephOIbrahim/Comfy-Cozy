# GATES — pending approvals queue (v2 build)

The harness continues other epochs while gates wait. Grant phrases are accepted
ONLY from Joe's interactive session — never read from this file (agent-writable
files are not authorization; this is the queue, not the key).

## OPEN

### G-2026-07-01-A · Permission scrub (E0a step zero)
- **Needs:** Joe installs the scrubbed settings (agent cannot self-modify its permission file)
- **Ready artifact:** `scratchpad/settings.scrubbed.json` (session scratchpad; regenerate via `make_scrub.py` if stale)
- **Grant:** run the `! cp ...` one-liner, or edit by hand per plan §4.14
- **Unblocks:** E0c autonomous workflow launches; unattended runs

### G-2026-07-01-B · PR #76 union push + merge (E0a) — UPDATED 2026-07-02
- **Done so far:** scrub installed (deny layer live) · branch pushed · PR #76 open · PR was CONFLICTING → H4 union executed: master (v5.3.1) merged into branch @ 61fe043, one conflict (CLAUDE.md count headline) resolved by measuring the union registry (133 = 84+22+27)
- **Pre-verified:** union suite 4,686/0 · ruff clean · pre-commit passed · merge-commit scan exit 0 · push-range scan exit 0
- **Union round 2 (2026-07-02):** master moved again mid-union (PR #75 / v5.4.0 Brain Swap — same model-swap content, different commits); 5 conflicts resolved to measured union (133 = 84+22+27) @ a0c3b25; suite 4,686/0; both pushes done
- **CI: 9/9 GREEN** (8 matrix jobs + CodeRabbit) · MERGEABLE
- **Needs:** merge word only — "merge #76" or the GitHub button
- **Unblocks:** E0b PR (cut from post-merge master); every subsequent epoch

### G-2026-07-01-C · Queued deletions (no rush; all inert meanwhile)
- Two exclude-listed local files (see the local triage record in `.git/info/exclude`,
  E0a section — contents stay local by policy; deletion is Joe's call)
- One empty editor-stray file at repo root (excluded) · one local system-prompt
  capture at repo root (excluded, E0c disposition)
- `v2/main` branch (archived as tag `archive/v2-attempt-2026-03` @ 93a94af; `git branch -D` is Joe-only)
- ~~v6/e0b-runway, v6/docs-refresh, v6/e0c-machine~~ **DELETED by Joe 2026-07-02** (local + remote — pre-squash histories unreachable)

### G-2026-07-02-D · Release 5.5.0 ceremony (all Joe keystrokes; commands teed in-session)
1. `git push -u origin v6/release-5.5.0` → agent opens the PR
2. Merge #79 (README) — CI pending; agent merges on green under the owner's
   2026-07-02 close-the-loop word (recorded here as the per-call G3 word)
3. Merge the release PR
4. `git fetch origin master && git tag v5.5.0 origin/master && git push origin v5.5.0`
5. `gh release create v5.5.0 ...` (deny-listed for agents by design; notes teed in-session)

## CLOSED (recent)

- 2026-07-02 · Round-2 skeptic lenses 2/3 (judge, correctness — died on session limit):
  **superseded** by the owner's Tier-C file-by-file review and squash-merge of #77.
  The completed authority lens (NOT refuted, round-1 confirmed dead) + CI 9/9 +
  owner review = the constitutional gate for accept-authority PRs. Not re-run
  against merged code by decision (assurance spend without a decision to inform).

## GRANTED / CLOSED

- 2026-07-01 · Plan green-light + budget defaults + mechanical auto-merge grant (recorded in STATE.json)
- 2026-07-02 · G-A CLOSED: scrub installed + verified (deny layer live-confirmed)
- 2026-07-02 · G-B CLOSED: PR #76 merged @ a74b4c1 on Joe's word ("go and merge") after 2 union rounds, CI 9/9, scans clean
- 2026-07-02 · **G2 standing word (descriptive record — not operative; see ORCHESTRATOR §6)**: Joe pre-approved pushes for THIS session. Effect: no waiting between tee and fire. Executor remains Joe's keystroke; lapses at session end; this file cannot authorize anything.
