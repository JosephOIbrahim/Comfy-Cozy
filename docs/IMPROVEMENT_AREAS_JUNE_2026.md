# Comfy-Cozy — Areas of Improvement (June 2026)

> Forward-looking engineering roadmap compiled at the close of the 2026-06-04
> session. Every item below is grounded in first-hand evidence from that session
> or a live grep against `master` — not from memory. Each carries **evidence**,
> a **proposed action**, an **effort** estimate (S ≤ half-day · M ≤ 2 days · L > 2 days),
> and a **priority** (P0 ship-blocker-adjacent · P1 do-this-month · P2 opportunistic).
>
> Master snapshot at authoring: `20361d4` (after #56 route-auth + #57 debt-closeout merged).

---

## State of master after this session

Two PRs merged to production:
- **#56** — UI route-auth hardening (closed a 35-finding multi-agent audit).
- **#57** — five audit-verified fixes: atomic-overwrite durability on Windows
  (`os.replace`), two PIL file-descriptor leaks, one dead test skip.

A live sweep confirms the **Windows-durability class is now clean on master**:
`shutil.move`, raw `os.rename`, top-level POSIX-only imports, and
`datetime.utcnow()` all return **0** in non-test source. The improvement areas
below are therefore about *preventing regression* and *closing gated work*, not
clearing a backlog of open defects.

---

## P0 — Lock in the wins (regression prevention)

### 1. CI guard against the "Unix-first" pattern
**Evidence.** This session fixed *three* instances of the same class —
a POSIX-only `resource` import that aborted all Windows CI collection, and two
non-atomic `shutil.move` finalizers that silently defeated documented durability
guarantees on Windows. The pattern keeps recurring because nothing stops it at
author time; sibling modules had already been fixed one-by-one (`planner.py`,
`image_metadata.py`, `accumulator.py` use `os.replace`).
**Action.** Add a cheap, deterministic guard so the class cannot come back:
- a lint/test that fails on a module-top `import resource|fcntl|pwd|grp|termios`
  outside a `try/except ImportError`;
- a lint/test that flags `shutil.move`/`os.rename` used as an atomic-write finalizer
  (prefer `os.replace`);
- a lint that flags `datetime.utcnow()` (deprecated 3.12+, removal-track).
A small `tests/test_portability_guards.py` that greps the tree is enough; no new deps.
**Effort.** S · **Priority.** P0 — it protects every future PR, including the gated
ones below that will re-introduce the debt when they land.

---

## P1 — Close gated / known work

### 2. Latency branch (#55) — disclosure remediation, then merge
**Evidence.** #55 is green and mergeable but **held**: the pre-merge bright-line
scan flagged a counsel-gated proprietary-coupling reference in
`docs/perf/LATENCY_PRD.md`. The reference is already on the public remote (the
branch was pushed), so this is a remediation item, not only a merge gate.
**Action.** Owner-level (not agent): decide to land as-is, or remove the coupling
reference and re-scan the full branch before merge. Tip-redaction alone will not
clear it from already-pushed history — treat history scrubbing as a separate task.
Tracked privately; intentionally not detailed in this public doc.
**Effort.** S (decision) + variable (scrub) · **Priority.** P1.

### 3. Latency branch carries deferred deprecation debt
**Evidence.** The `agent/perf` module (present only on #55, not master) emits
`datetime.utcnow()` deprecation warnings during tests (`baseline.py`, `profile.py`).
It will arrive on master the moment #55 lands.
**Action.** Sweep `utcnow()` → `datetime.now(datetime.UTC)` as a fast-follow the
same day #55 merges. The P0 lint (item 1) prevents new occurrences in the meantime.
**Effort.** S · **Priority.** P1 (gated behind #55).

### 4. NIM lifecycle — Track-A is RED on a single runtime prerequisite
**Evidence.** The NIM node pack is on disk but absent from `/object_info`; the
real class types are now verified (`InstallNIMNode` / `LoadNIMNode` / `NIMFLUXNode`
/ `Get_HFToken`) and written into the wrapper. The blocker is environmental, not
code: the NVIDIA-Workbench WSL2 distribution (the container host installed by
`NIMSetup.exe`) is **not installed** (`wsl -l -v` shows only Ubuntu + docker-desktop),
`HF_TOKEN` is unset in the ComfyUI process env, and free VRAM was ~5 GB vs the
~12 GB a NIM FLUX load wants.
**Action (ordered, mostly operator/network steps):**
1. Run `NIMSetup.exe` to install the NVIDIA-Workbench WSL distro.
2. `setx HF_TOKEN …` and restart ComfyUI so the new process inherits it.
3. Confirm `pynvml` / `grpcio` are importable in ComfyUI's Python; restart; verify
   the four NIM class types appear in `/object_info`.
4. Free VRAM to ≥ 12 GB; export the example workflow to API format.
**Note.** The wrapper branch (`feat/nim-lifecycle`) is held local pending a
proprietary-coupling review of its seam comments; the engineering is otherwise done.
**Effort.** M (mostly install/config) · **Priority.** P1 if NIM is on the near roadmap, else P2.

---

## P2 — Hygiene & opportunistic

### 5. Standing skip / TODO audit
**Evidence.** Master carries ~16 `skip`/`xfail` markers and ~10 TODO/FIXME/HACK
comments; this session's audit found and removed exactly one dead skip that was
silently disabling a passing test. The rest are plausibly legitimate
(platform/integration gates) but unaudited.
**Action.** Re-run the repeatable `master-closeout` audit workflow on a schedule
(e.g. monthly) — it already classifies each marker CLOSE/ESCALATE/SKIP with
file:line evidence. Cheap signal, prevents silent coverage erosion.
**Effort.** S (it's already built) · **Priority.** P2.

### 6. Branch hygiene
**Evidence.** `fix/comfy-cozy-issues` sits 3 commits ahead of origin carrying only
superseded duplicates (its one valuable commit, the LTX 15.5× win, was rescued to
`perf/ltx-resident-gguf-q4`). Several older `claude/*` branches appear stale.
**Action.** Reset/retire `fix/comfy-cozy-issues` (owner-run `git reset`); triage and
prune merged/stale branches. Decide whether `perf/ltx-resident-gguf-q4` (pushed,
no PR) becomes a PR or stays a parked checkpoint.
**Effort.** S · **Priority.** P2.

### 7. Test-collection robustness for `tests/manual/`
**Evidence.** `tests/manual/` imports a module that exists only on feature branches,
so an ad-hoc full `pytest` run on master errors at collection unless `--ignore=tests/manual`
is passed. Easy to forget; makes "run the whole suite" branch-dependent.
**Action.** Guard those imports (`pytest.importorskip`) or move branch-specific
manual tests behind a marker so collection never hard-fails on master.
**Effort.** S · **Priority.** P2.

### 8. Earlier disclosure-guard placement
**Evidence.** The bright-line scan caught **two** real proprietary-coupling
references this session — both in otherwise-clean branches, both only at *push* time.
The guard worked, but catching it later costs rework.
**Action.** Run the scan at **pre-commit** (not only pre-push) and add a short
contributor note: keep proprietary integration names out of public-bound docs and
code comments; use neutral seam language. Shifts the catch left by one step.
**Effort.** S · **Priority.** P2.

---

## Project's own stated roadmap (carried forward)

From `CLAUDE.md` Phase 7, still open and larger in scope (each is L unless noted):
- **Vision-based evaluator** — replace the rule-based 0.7/0.1 QualityScore with
  `analyze_image` scoring.
- **Auto-retry loop** — re-COMPOSE when `quality.overall < threshold` (pipeline stub exists).
- **Integration test harness** — `@pytest.mark.integration` against a live ComfyUI.
- **Real external-memory wire format** — replace the file-watch transport once the
  API contract lands (counsel-gated; not agent-actionable until cleared).

These are features, not debt; prioritize against product goals, not this list.

---

## How to read this list

The highest-leverage single item is **#1 (the portability CI guard)**: it is small,
it protects every future PR, and it specifically backstops the debt that items #3
and #4 will otherwise re-introduce. Everything in P1 is gated on an
owner/environment decision rather than engineering effort. P2 is steady-state hygiene
that the existing audit workflow can largely automate.

*Compiled 2026-06-04. Bright-line clean — contains no proprietary-coupling content.*
