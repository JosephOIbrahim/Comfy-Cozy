# [release] v5.6.0 — production hardening: solo-critical fixes + community docs

## Summary

Converts an external production-readiness audit into a verified fix set, plus two
defects the audit missed (found by a claude-API pass). 10 commits over `origin/master
(9d35b0e)`, Gate-A green under independent verification. The advertised
`pip install -e ".[dev]"` + `pytest` now runs with **zero errors** (it threw 27),
model swaps to current-generation Claude no longer 400, installs are deterministic,
and the repo finally has a security-disclosure path.

## What ships

| Commit | Finding | One-liner |
|---|---|---|
| `eeab902` | F-S1 | `.[dev]` suite: 27 collection errors → clean module skip (`importorskip("pxr")`) |
| `ae1bff8` | F-API1/2 | Thinking gate inverted to a legacy denylist — Opus 4.8 / Sonnet 5 / Fable 5 no longer 400; dead example model ids fixed |
| `3b11b72` | F-S4 | Unshipped SSE/`--sse` transport promise removed (stdio-only; `MCP_AUTH_TOKEN` is enforced on the panel/UI/bridge HTTP surfaces, where it belongs) |
| `e28a7f8` | F-M1 | mypy in CI, non-blocking (baseline: 126 errors / 42 files; ratchet to blocking when clean) |
| `da05048` | F-S3 | Cross-platform `agent doctor`; retires the Windows-only, `G:\`-hardcoded `_find_comfyui.ps1` |
| `1665d01` | F-S2 | `uv.lock` committed (124 pkgs, universal); self-contradicting `requirements.txt` deleted |
| `a98cb26` | F-D0/1/2 | `SECURITY.md` + `CONTRIBUTING.md` + `CODE_OF_CONDUCT.md` (drafted, adversarially red-teamed) |
| `6a5a411` | F-M2 | Root: 32 → 11 markdown files (24 working docs → `docs/archive/`) |
| `cef56bd` | F-M3p1 | Tool counts trued to 84 intelligence / 133 dispatched; `.[dev]` story made truthful |
| `a0cc6c2` | F-M3p2 | Test count corrected to verified **4,640+** (was overclaiming 4,680+) |

Two release-prep commits on top (version bump `5.5.0→5.6.0`, `__init__` drift
`5.4.0→5.6.0`, CHANGELOG). Tip `f90fea9`.

## Verification

Independent fresh-venv run (Python 3.13, read-only verifier, on the final tip):

- `pip install -e ".[dev,stage,exr]"` → exit 0 (usd-core 26.5, openexr 3.4.13)
- **4,646 passed / 0 failed / 0 errors / 9 skipped / 46 deselected** (~8 min)
- `ruff check` — all checks passed
- `uv lock --check` — exit 0 (lockfile matches pyproject)
- `agent doctor` — exit 0 offline; graceful WARN rows; single local ping
- Honesty greps all zero: no `run_sse`/`--sse`, no `requirements.txt`, no `_find_comfyui.ps1`, root `.md` = 11
- Brightline disclosure scan: **CLEAN** on all 10 commits
- 5-lens adversarial pre-push verify: **0 blockers**

The `.[dev]`-only path (the audit's broken promise) runs **4,236 passed / 0 errors**.

## What's NOT in this PR

Deliberately left for separate human decisions, not part of this SemVer bump:

- **`Development Status :: 4 - Beta` classifier** (`pyproject.toml:17`) — flipping to
  `5 - Production/Stable` + the README "production software" phrasing is the owner's
  edit, gated on this merge + Wave 3.
- **Patent-Pending block** (`README.md:6`, `:1594`) — counsel-adjacent; not agent-touched.
- A separate, pre-existing public-content question that is independent of this diff and
  counsel-gated — out of scope here by design.

## Merge notes

- `release.yml` is **tag-triggered** (`v*`); this PR does not produce a release artifact
  until the tag is cut.
- **Local `master` is stale at v5.3.1** — fast-forward after merge (`git checkout master
  && git pull`) before branching anything new off it.
- Post-F-S1, `release.yml`'s `--ignore=tests/test_provisioner.py` is vestigial (the file
  skips cleanly); optional follow-up to drop the flag, not blocking.

🤖 Generated with [Claude Code](https://claude.com/claude-code)