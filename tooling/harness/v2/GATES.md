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
- `.env.bak` (brightline-FLAGGED + credential-like lines; excluded)
- `Comfy-Cozy.claudesettings.local.json` (empty notepad stray; excluded)
- `v2/main` branch (archived as tag `archive/v2-attempt-2026-03` @ 93a94af; `git branch -D` is Joe-only)

## GRANTED / CLOSED

- 2026-07-01 · Plan green-light + budget defaults + mechanical auto-merge grant (recorded in STATE.json)
- 2026-07-02 · G-A CLOSED: scrub installed + verified (deny layer live-confirmed)
- 2026-07-02 · G-B CLOSED: PR #76 merged @ a74b4c1 on Joe's word ("go and merge") after 2 union rounds, CI 9/9, scans clean
- 2026-07-02 · **STANDING G2 GRANT**: Joe pre-approved "push it" for the session/program. Operational meaning: no per-push waiting — the harness tees verified pushes and Joe fires `!git push` on sight. The keystroke stays Joe's via the deny layer (structural, by design; his verbal grant does not reopen agent-push).
