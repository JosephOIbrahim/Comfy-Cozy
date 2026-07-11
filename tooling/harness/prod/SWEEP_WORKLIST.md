# Production Sweep — Forge-Ready Worklist

> Target: the S-tier mechanical sweep from the production-readiness report.
> Branch strategy: **one branch off post-merge master** — `harden/release-sweep`.
> Do NOT fork from local `master` (stale at v5.3.1) or stack on the unmerged
> `harden/wave2-docs` (which touches `ci.yml` and `pyproject.toml` → conflicts).
> Land this **after** v5.6.0 merges and you fast-forward master.
> All edits are local; the agent cannot push — hand the branch to Joe.

---

## Sequencing (single forge session)

1. `git checkout master && git pull` (un-stale master post-v5.6.0-merge)
2. `git checkout -b harden/release-sweep`
3. Apply S10 → S11 → S1 → S6 → S4 → S5 (order: cheapest-first; S6 before S4/S5 since S6 touches `pyproject` deps and forces a `uv lock` regen you only want to run once)
4. `uv lock` (regenerate — **required** by S6; `uv lock --check` will FAIL until this runs)
5. Verify: `ruff check agent/ tests/ && ruff format --check agent/ tests/ && python -m pytest tests/ -v -m "not integration" --cov=agent --cov-report=term-missing`
6. `agent doctor` (offline exit 0 sanity)
7. Commit per item (6 commits, `[PILOT]`/`[TEST]` prefixes); brightline scan runs at commit time
8. Hand to Joe: `git push -u origin harden/release-sweep` + PR → merge → fold into next release tag

---

## S10 — fix stale `v0.4` version in `agent run` header  *(lowest risk, do first)*

**File:** `agent/cli.py`
**Problem:** line 154 prints `title="ComfyUI Agent v0.4"` while the package is 5.6.0. The header is the first thing a user sees on every `agent run`.

**Edits:**
1. Add import near the top of `agent/cli.py` (with the other top-level imports). First verify `agent/__init__.py` exports `__version__` (it does: `agent/__init__.py:3` → `__version__ = "5.6.0"`):
   ```python
   from agent import __version__
   ```
2. `agent/cli.py:154`
   - **current:** `title="ComfyUI Agent v0.4",`
   - **proposed:** `title=f"ComfyUI Agent v{__version__}",`

**Verification:** `agent run --help` (no crash on import); `python -c "from agent.cli import app; from agent import __version__; print(__version__)"` prints `5.6.0`.
**Branch note:** harden branch did not touch `cli.py:154` → no conflict, but apply post-merge for a clean base.

---

## S11 — QUICKSTART tool-count + stale slash-command doc

**File A:** `QUICKSTART.md`
- `QUICKSTART.md:63`
  - **current:** `can use all 77 ComfyUI tools alongside its normal coding abilities.`
  - **proposed:** `can use all 133 ComfyUI tools alongside its normal coding abilities.`
- `QUICKSTART.md:95`
  - **current:** `The 77 tools will appear automatically.`
  - **proposed:** `The 133 tools will appear automatically.`

**File B:** `.claude/commands/QUICKSTART.md` — **mark internal/stale, do not rewrite** (lower risk than a rewrite; this is a MoE-team slash-command doc referencing removed scripts).
- Insert at the very top (line 1, before the `# MoE AGENT TEAM — QUICK REFERENCE` heading):
  ```markdown
  > ⚠️ **INTERNAL MoE-team reference — STALE.** Not user-facing. References
  > `bootstrap_hardening.py` / `.claude/agents/orchestrate.py` (removed) and the
  > pre-4,744-test "497+ pass" count. Kept for archaeology; do not follow its
  > commands. User quickstart lives at repo-root `QUICKSTART.md`.
  ```

**Verification:** `grep -n "77" QUICKSTART.md` returns nothing; the banner renders at the top of `.claude/commands/QUICKSTART.md`.
**Branch note:** harden's F-M3 trued counts in `ARCHITECTURE.md`/README, not in repo-root `QUICKSTART.md` → no conflict expected. Apply post-merge.

---

## S1 — `release.yml` parity with `ci.yml`

**File:** `.github/workflows/release.yml`
**Problem:** the release gate is weaker than CI. It installs only `.[dev]` (missing `stage`/`exr` → all 21 stage-layer tests silently SKIP, green-by-skip) and `--ignore`s `test_provisioner.py` that CI deliberately un-ignores (it skips cleanly post-F-S1).

**Edits:**
- `release.yml:24`
  - **current:** `          pip install -e ".[dev]"`
  - **proposed:** `          pip install -e ".[dev,stage,exr]"`
- `release.yml:31`
  - **current:** `        run: python -m pytest tests/ -v --ignore=tests/test_provisioner.py`
  - **proposed:** `        run: python -m pytest tests/ -v -m "not integration"`
- **Recommended add** (parity with `ci.yml:35-37` — fail loud if the usd-core wheel breaks, never green-by-skip): insert after the Install step (after `release.yml:25`):
  ```yaml
        - name: Verify the stage substrate imports
          run: python -c "from pxr import Usd; print('usd-core OK:', Usd.GetVersion())"
  ```

**Verification:** trigger a dry run of the release workflow on the branch (`workflow_dispatch` if added, or cut a throwaway `v0.0.0-test` tag after merge) and confirm the Test step reports >0 stage tests collected (not skipped) and 0 errors.
**Branch note:** harden did not touch `release.yml` extras/ignore → no conflict. Apply post-merge.

---

## S6 — add upper bounds to 12 unbounded runtime deps

**File:** `pyproject.toml` (`dependencies`, lines 29-43)
**Problem:** core deps use `>=` with no upper bound. A breaking upstream major can break installs. Only `mcp` is bounded. Bounds chosen are **next-major above the currently-shipping version** (verified against the installed/`uv.lock` set) so nothing in the current lockfile is excluded.

**Edits** (keep each existing lower bound; append the upper bound):
| Line | current | proposed |
|---|---|---|
| 30 | `"anthropic>=0.52.0",` | `"anthropic>=0.52.0,<1",` |
| 31 | `"jsonpatch>=1.33",` | `"jsonpatch>=1.33,<2",` |
| 32 | `"jsonschema>=4.20.0",` | `"jsonschema>=4.20.0,<5",` |
| 33 | `"httpx>=0.27.0",` | `"httpx>=0.27.0,<1",` |
| 34 | `"websockets>=12.0",` | `"websockets>=12.0,<17",` |
| 35 | `"python-dotenv>=1.0.0",` | `"python-dotenv>=1.0.0,<2",` |
| 36 | `"typer>=0.12.0",` | `"typer>=0.12.0,<1",` |
| 37 | `"rich>=13.0.0",` | `"rich>=13.0.0,<15",` |
| 38 | `"mcp>=1.20.0,<2.0",` | *(unchanged — already bounded)* |
| 39 | `"pyyaml>=6.0",` | `"pyyaml>=6.0,<7",` |
| 40 | `"aiohttp>=3.9.0",` | `"aiohttp>=3.9.0,<4",` |
| 41 | `"networkx>=3.0",` | `"networkx>=3.0,<4",` |
| 42 | `"Pillow>=10.0",` | `"Pillow>=10.0,<12",` |

Optional (same pattern, optional-dep extras — lower priority): `sentence-transformers<5`, `openexr<4`, `usd-core<28`.

> ⚠️ **Bound sanity (do NOT regress these):** the installed/lockfile set is
> `anthropic 0.91`, `httpx 0.28`, `typer 0.24`, `rich 14.3`, `websockets 16.0`,
> `Pillow 11.x`, `mcp 1.27`. The bounds above are all above these. Do **not**
> set `rich<14` or `websockets<16` — those would exclude the shipping version and
> break `uv lock`.

**Verification:** `uv lock` (regenerate), then `uv lock --check` → exit 0; `pip install -e ".[dev,stage,exr]"` → exit 0.
**Branch note:** harden touched `pyproject` (added mypy dev dep, committed `uv.lock`). Editing the `dependencies` block is adjacent but distinct from the mypy line → likely clean, but **regenerate `uv.lock` once** after all S6 edits. Apply post-merge so the regen is against the merged lockfile.

---

## S4 — add a coverage gate

**File:** `pyproject.toml` (`[tool.coverage.report]`, line 92) + `.github/workflows/ci.yml` (Test step, line 55)
**Problem:** no `fail_under` and no CI `--cov` step → uncovered regressions ship silently. `pytest-cov` is already in the `dev` extra.

**Edits:**
- `pyproject.toml:92` — add a `fail_under` to the existing `[tool.coverage.report]` block (currently only `show_missing`/`skip_empty`):
  - **proposed addition:** `fail_under = 70`  *(ratchet start — current real coverage is unknown; 70 is a defensible floor that won't block a clean run. Raise it as coverage improves. If the first CI run shows coverage already well above, bump to the measured number minus 2.)*
- `ci.yml:55` — add `--cov` to the existing test invocation (keeps one pytest step):
  - **current:** `        run: python -m pytest tests/ -v -m "not integration"`
  - **proposed:** `        run: python -m pytest tests/ -v -m "not integration" --cov=agent --cov-report=term-missing`

**Verification:** local `python -m pytest tests/ -m "not integration" --cov=agent --cov-report=term-missing` → exits 0 (coverage ≥ 70); deliberately break the bound by setting `fail_under = 99` to confirm it fails, then restore 70.
**Branch note:** harden added a mypy step to `ci.yml`; this edits the Test step above it → likely clean. Apply post-merge. Run S6's `uv lock` regen **before** this so the lockfile is settled.

---

## S5 — gate `ruff format` + harden `pip-audit`

**File:** `.github/workflows/ci.yml`
**Problem:** (a) `ruff check` runs but `ruff format --check` never does → formatting drift lands on master. (b) `pip-audit` has `continue-on-error: true` → known-vuln deps ship green.

**Edits:**
- After `ci.yml:46` (the Lint step), add a format step:
  ```yaml
        - name: Format check
          run: ruff format --check agent/ tests/
  ```
- `ci.yml:40` — remove the `continue-on-error` line so pip-audit hard-fails on a known vuln:
  - **current:**
    ```yaml
          - name: Security audit (pip-audit)
            continue-on-error: true
            run: |
              pip install pip-audit
              pip-audit --desc
    ```
  - **proposed:**
    ```yaml
          - name: Security audit (pip-audit)
            run: |
              pip install pip-audit
              pip-audit --desc
    ```
  *(If the first hard-fail is too noisy — e.g. an unfixed upstream advisory outside our control — re-add `continue-on-error: true` temporarily and file a follow-up to drop it when the advisory clears. Prefer hard-fail; document exceptions inline.)*

**Verification:** push the branch and confirm the CI matrix shows a "Format check" step and that pip-audit failing would fail the job (introduce a known-vuln pin locally to confirm, then revert).
**Branch note:** harden added the mypy step after Lint; insert the format step **between** Lint and mypy to keep groupings clean. Apply post-merge.

---

## Out of scope for this sweep (tracked separately)

- **S2** (tag v5.6.0) — Joe's keystroke, not a code edit.
- **S3** (PyPI publish) — product decision; add trusted-publishing job to `release.yml` if PyPI is in scope. Park until Joe decides.
- **S7** (`openai`/`google-genai` extras), **S8** (`agent autonomous` install hint), **S9** (`.env.example` completeness) — provider/UX tier; fold into the same `harden/release-sweep` branch as a second commit batch if time allows, else a follow-up.
- **M1/M2/M3** — Joe's decisions (classifier flip, patent wording, leak).