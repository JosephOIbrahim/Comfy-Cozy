# PROD-HARDEN LEDGER

> Append-only. Conventions: `ORCHESTRATOR.md` §2 (inherited from `../LEDGER.md`).
> Seeded 2026-07-07 from external audit `audit.md`. All entries V0 at load —
> the audit's evidence is credible but external (Python 3.14, clean venv,
> different machine). Wave-0 probes convert each Lead to a Confirmation or a
> non-repro DeadEnd before any fix is permitted.

---

## INITIAL LOAD — 2026-07-07 · Leads (V0) — forge-FORBIDDEN until Wave-0 probe

### Wave 1 targets — solo-critical

```
F-S1   .[dev] install promise broken: pytest collects 27 ERRORS from
       tests/test_provisioner.py because agent.stage imports USD (usd-core/pxr)
       at module level and the [dev] extra excludes it. README advertises
       .[dev] as the full test repro.
       locus  tests/test_provisioner.py (module-level import) ; README Get-Running
       class  mechanical    wave 1    fix-branch harden/s1-stage-test-skips
       probe  fresh venv → pip install -e ".[dev]" → pytest -m "not integration"
       audit  solo-critical #1        verified_by V0

F-S2   requirements.txt pins torch==2.5.1 / sentence-transformers==3.3.1 (CPU
       extra-index) while pyproject puts both behind optional [embed]; no
       lockfile exists. The two documented install paths diverge (~200 MB).
       locus  requirements.txt:9-10 ↔ pyproject.toml deps/extras
       class  mechanical    wave 1    fix-branch harden/s2-lockfile
       probe  diff dependency stories + lockfile existence check
       audit  solo-critical #2        verified_by V0

F-S3   ComfyUI discovery helper is PowerShell-only and hardcodes
       G:\COMFYUI_Database; no macOS/Linux equivalent. config.py auto-detect
       (Path.home()/'ComfyUI' + port validation) partially covers.
       locus  _find_comfyui.ps1 ; agent/config.py auto-detect
       class  mechanical    wave 1    fix-branch harden/s3-discovery
       probe  read helper + search repo for any cross-platform path
       audit  solo-critical #3        verified_by V0

F-S4   mcp_server.py (~333-365) points users at an SSE/HTTP authenticated
       transport (run_sse) that is not implemented anywhere in the repo;
       MCP_AUTH_TOKEN defined in config.py but never enforced.
       Gate-B Option A resolution: REMOVE the promise, document the
       single-tenant trust boundary. Do not build the transport.
       locus  agent/mcp_server.py:333-365 ; agent/config.py MCP_AUTH_TOKEN
       class  mechanical (honesty fix)   wave 1   fix-branch harden/s4-sse-honesty
       probe  grep run_sse/SSE + read docstring + token enforcement sites
       audit  studio-critical #1, converted by Gate-B Option A   verified_by V0
```

### Wave 1 rider — maturity

```
F-M1   mypy declared as a dev dependency but never run in CI.
       locus  pyproject dev deps ↔ .github/workflows/*.yml
       class  mechanical    wave 1    fix-branch harden/m1-mypy-ci
       probe  grep workflows for mypy; inventory what CI does run
       note   lands as non-blocking baseline first     verified_by V0
```

### Wave 2 targets — docs & policy

```
F-D1   SECURITY.md absent — for a tool that executes git clone + pip install
       on approval, no vuln-disclosure path exists.
       class  generative    wave 2    branch harden/docs-pack
       probe  existence check root + .github/ + docs/    verified_by V0

F-D2   CONTRIBUTING.md + CODE_OF_CONDUCT.md absent.
       class  generative    wave 2    branch harden/docs-pack
       probe  existence check (same probe as F-D1)       verified_by V0

F-D3   No upgrade/migration runbook or per-user config strategy doc.
       class  generative    wave 2→3 (absorbed by F-A3)  verified_by V0

F-M2   ~32 root-level markdown files bury README/QUICKSTART under working
       docs (phase reports, blueprints, session capsules).
       class  mechanical    wave 2    branch harden/m2-root-docs
       probe  git ls-files census at root depth          verified_by V0

F-M3   Doc drift: 77-vs-133 tool counts across docs; README "production
       software / 4,680+ tests" vs pyproject Development Status :: 4 - Beta;
       claims a fresh .[dev] clone cannot reproduce.
       class  mechanical    wave 2    branch harden/m3-doc-drift
       probe  grep claims with file:line for reconciliation   verified_by V0
```

### Wave 3 targets — studio (Option A, ratified 2026-07-07)

```
F-A1   Per-user config layer above project .env — user-level config file,
       precedence designed and documented (not improvised).
F-A2   Fleet deployment runbook — pinned installs from F-S2's lockfile,
       config distribution for N artist desktops.
F-A3   Upgrade/migration runbook (absorbs F-D3).
F-A4   Trust-boundary document — single-tenant desktop; states plainly what
       the tool will never do (no network transport, no shared server).
       all: class net-new-lite / generative    verified_by V0 (design targets)
```

### GATED:JOE — evidence-prep only; agents never act

```
G-1    "Patent Pending" banner vs MIT license tension. Counsel-adjacent.
       Harness may collect exact locations + audit language; NO agent drafts
       or edits the resolution.
G-2    pyproject Development Status :: 4 - Beta → Production/Stable flip.
       Unlocks only after Gate A + Wave 3. Joe's edit, not an agent's.
```

### DEFERRED — out of harness scope

```
X-1    Shared-service transport (authenticated HTTP/SSE, user identity,
       multi-tenancy) — Option B. Someday-RFC; candidate v2-program epoch.
       forge-FORBIDDEN in this harness.
```

---

## APPEND LOG

### 2026-07-07 · E-001 — Claude-API surface findings (outside the external audit)

> Source: /claude-api skill pass over the repo's Anthropic integration. Code
> loci read live on this machine (V1); the API-behavior premises (model
> retirement dates, 400-on-legacy-thinking) come from the claude-api skill
> reference cached 2026-06-24 — the Wave-1 Verifier should confirm with one
> live API call if ANTHROPIC_API_KEY is available.

```
F-API1 Confirmation (code shape) — forward-compat 400 trap in the thinking gate.
       _ADAPTIVE_THINKING_MODEL_PREFIXES is an ALLOWLIST frozen at
       {claude-opus-4-7, claude-opus-4-6, claude-sonnet-4-6}. Any newer
       Anthropic model (claude-opus-4-8, claude-sonnet-5, claude-fable-5)
       falls through to the legacy branch and sends
       {"type": "enabled", "budget_tokens": N} — which those models reject
       with HTTP 400. THINKING_BUDGET defaults to 4000 (thinking ON), so
       AGENT_MODEL=claude-opus-4-8 breaks every agent-loop call. README's
       "swap one env var" promise fails for every post-4.7 model.
       locus  agent/llm/_anthropic.py:297-306,332 ; agent/config.py:136
       fix    invert the gate: denylist of LEGACY (pre-4.6) prefixes, adaptive
              as the default path — future models then work unmodified.
       class  mechanical   wave 1   fix-branch harden/api1-adaptive-gate
       verified_by V1 (code) / V0 (API premise, skill ref 2026-06-24)

F-API2 Confirmation (code shape) — docs recommend deprecated + nonexistent IDs.
       .env.example:24 + config.py:99 comment suggest
       AGENT_MODEL=claude-sonnet-4-20250514 — deprecated, retirement listed
       as 2026-06-15 (three weeks BEFORE today; may already 404).
       .env.example:26 suggests claude-opus-4-6-20250929 — a constructed ID
       that never existed (Opus 4.6 has no dated suffix; 20250929 is Sonnet
       4.5's date) — guaranteed 404 for anyone who uncomments it.
       locus  .env.example:24,26 ; agent/config.py:99 (comment)
       fix    replace with current verified IDs; folds naturally into F-M3's
              doc-drift reconciliation.
       class  mechanical (docs)   wave 2   fix-branch harden/m3-doc-drift
       verified_by V1 (code) / V0 (retirement date, skill ref 2026-06-24)

note   Defaults claude-opus-4-7 / claude-haiku-4-5-20251001 are Active
       models — no defect. Bumping the default to claude-opus-4-8 is a
       product choice, not a harness item; left to Joe.
```

### 2026-07-07 · E-002 — Wave 0 COMPLETE: 8/8 probes reproduced, all V1

> Run wf_fbe86063-b6c (8 agents, 0 errors, ~11.5 min wall-clock). Full
> per-probe evidence: the run's journal.jsonl + task output wxvu5hosq.
> Every Wave-1/2 Lead converts to a Confirmation. Wave 1 is forge-ELIGIBLE.

```
F-S1   Confirmation V1 — 27 errors reproduced exactly (fresh venv, py3.13.14,
       pip install -e ".[dev]" → pytest: 4281 passed / 173 skipped / 27 errors,
       all tests/test_provisioner.py). AUDIT CORRECTION: mechanism is wrong —
       agent.stage guards its pxr import (cognitive_stage.py:31-35 try/except);
       the errors are per-test FIXTURE SETUP failures: fixture `cws`
       (test_provisioner.py:30) → CognitiveWorkflowStage.__init__ raises
       StageError (cognitive_stage.py:125). test_provisioner.py is missing the
       pytest.importorskip("pxr") guard its sibling tests carry
       (pattern: tests/test_cognitive_stage.py:8).
       fix    add the importorskip guard (matches repo convention → clean skips)
       branch harden/s1-stage-test-skips

F-S2   Confirmation V1 — divergence is WORSE than audited: bidirectional.
       requirements.txt pins the embed stack + CPU torch but OMITS networkx
       (pyproject L40 requires it) → `pip install -r requirements.txt` alone
       yields a broken agent env. Header cites a nonexistent [mcp] extra.
       anthropic ==0.75.0 (req) vs >=0.52.0 (pyproject). No Python lockfile
       anywhere (package-lock.json is Node).
       fix    one source of truth (uv.lock + extras); retire requirements.txt
       branch harden/s2-lockfile

F-S3   Confirmation V1 — _find_comfyui.ps1 is 3 lines, PowerShell-only,
       hardcodes G:\COMFYUI_Database, predates config.py auto-detect
       (_default_comfyui_install(), config.py:236-255). No doctor command.
       scripts/comfyui_with_agent.bat also carries machine-local paths.
       fix    delete vestigial ps1 + add cross-platform `agent doctor`
              reusing _default_comfyui_install() candidates
       branch harden/s3-discovery

F-S4   Confirmation V1 — mcp_server.py:7 docstring advertises an "--sse flag"
       that does not exist (zero sse/run_sse/uvicorn/starlette hits repo-wide;
       agent/cli.py has no flag). AUDIT CORRECTION: "MCP_AUTH_TOKEN never
       enforced" is overstated — it IS enforced (Bearer + compare_digest) on
       panel/server/middleware.py:58-68, ui/server/routes.py (3 sites),
       node_pack/comfy_agent_bridge/__init__.py:52-65, with tests. Only the
       MCP stdio server lacks enforcement — which is the surface the docstring
       misleads about.
       fix    Option-A honesty fix: correct docstring:7 + :333-335 + warning
              :361-366 to stdio-only; do NOT touch the live HTTP enforcement
       branch harden/s4-sse-honesty

F-M1   Confirmation V1 — zero mypy hits in workflows; mypy>=1.10 in [dev];
       no [tool.mypy]/mypy.ini/setup.cfg config exists.
       fix    non-blocking step after ruff (ci.yml:45-46), continue-on-error
              mirroring pip-audit; expect noisy first run → minimal config
       branch harden/m1-mypy-ci

F-M2   Confirmation V1 — exactly 32 root .md files. Classified: 7 user-facing
       (README, QUICKSTART, SETUP_GUIDE, CHANGELOG, SPONSORS, PRODUCT_VISION,
       DEPLOY_NOTES) + 1 policy (CLAUDE.md) + 24 working-docs (movable).
       MIGRATION_MAP.md has a dated duplicate. Grep inbound links before moving.
       branch harden/m2-root-docs

F-M3   Confirmation V1 — drift confirmed with corrected values: the audit's
       "77" appears NOWHERE; real spread is 53/76/80/113/129/133 across
       README/CLAUDE.md/docs (worst: ARCHITECTURE.md:71,:207 "all 80 tools";
       CODEBASE_SYNOPSIS.md:36 "129"). Live probe len(_HANDLERS)=84 confirms
       the intelligence-layer figure. Test counts: 4,680+ / ~4540 / 4150+ /
       4,437 / 4,268 across docs. README:89 "production software" vs
       pyproject:16 Beta. README:6,:1542 "Patent Pending" links to EXTERNAL
       repo (Harlo/PATENTS.md) → confirms G-1 GATED:JOE; Wave-2 fixer must
       not alter patent wording.
       branch harden/m3-doc-drift

F-D0   Confirmation V1 — SECURITY.md / CONTRIBUTING.md / CODE_OF_CONDUCT.md
       absent at root and .github/ (only FUNDING.yml + workflows/). Partial
       content to fold in, not duplicate: docs/rfc-stage-provisioner-ssrf.md,
       docs/rfc-stage-write-injection.md (vuln write-ups ≠ policy),
       CLAUDE.md Git Authority Map + docs/AUTHORITY_MAP.md + SESSION_CONTRACT.
       note   SECURITY.md must stay generic — no internal-RFC references.
       branch harden/docs-pack

BASELINE (Gate A reference) — on branch claude/perf-salvage the suite also
       shows 5 FAILs unrelated to any finding (tests/test_perf_tools.py ×4,
       test_portability_guards.py::test_no_datetime_utcnow), caused by the
       branch's pre-existing UNTRACKED perf files. Wave-1 fix branches MUST
       fork from master and measure baseline there; expected clean baseline ≈
       audit's counts. Working tree untouched by all probes (porcelain
       before == after, no egg-info).
```

### 2026-07-07 · E-003 — Waves 1+2 BUILT under Joe's CTO session grant

> Grant: "you are CTO work towards closing-the-loop you are pre-approved"
> (2026-07-07) = session-level add/commit on harden/* branches. Push, merge,
> release, and GATED:JOE items remain Joe's keystrokes.
> Fork point 9d35b0e == origin/master (verified). Local `master` ref is STALE
> at v5.3.1 (183a611) — do not fork from it; fast-forward is Joe's call.
> Worktrees: G:/Comfy-Cozy.wt/wave1 + /wave2. The fail-closed brightline
> commit guard fired in the fresh worktree (scanner is git-excluded); resolved
> by copying scripts/brightline_scan.py from the main checkout so the guard
> RUNS — never bypassed. All 10 commits passed the scan.

```
harden/wave1 (6 commits off 9d35b0e):
  eeab902 [TEST]   F-S1  importorskip guard; .[dev] suite: 27 errors -> 1 clean
                   module skip "usd-core not installed" (verified in venv)
  ae1bff8 [PILOT]  F-API1 gate inverted to legacy-denylist; 36/36 thinking
                   tests pass incl. new opus-4-8/sonnet-5/fable-5/unknown-id
                   adaptive cases + 5-model legacy parametrize. Also F-API2
                   .env/config example ids fixed (sonnet-5, opus-4-8).
  3b11b72 [PILOT]  F-S4  SSE promise removed (docstring x2 + warning +
                   .env comment); 24/24 mcp_server tests pass untouched.
  e28a7f8 [VERIFY] F-M1  mypy non-blocking CI step after ruff; measured
                   baseline 126 errors / 42 of 161 files.
  da05048 [PILOT]  F-S3  `agent doctor` (cross-platform, read-only, 3s ping,
                   3 new tests) + _find_comfyui.ps1 deleted; ruff clean.
  1665d01 [PILOT]  F-S2  uv.lock committed (124 pkgs, universal); divergent
                   requirements.txt deleted (README's single ref rewritten;
                   Dockerfile/CI/tests confirmed non-consumers).

harden/wave2-docs (4 commits on top of wave1):
  a98cb26 [DOCS]   F-D0/D1/D2 SECURITY.md + CONTRIBUTING.md +
                   CODE_OF_CONDUCT.md — drafted by agent pair, adversarially
                   red-teamed (verdict: 2 should-fix, both applied: safe-harbor
                   scoped to maintainer conduct; CoC reports routed private).
                   Forbidden-token scan: zero hits.
  6a5a411 [DOCS]   F-M2  24 root docs -> docs/archive/ + breadcrumb README;
                   inbound-link grep first (nothing load-bearing). Root: 11 .md.
  cef56bd [DOCS]   F-M3p1 ARCHITECTURE.md counts 53->84, 80->133 (current-state
                   sites only; dated reviews left verbatim); README .[dev]
                   test story updated to skip-cleanly truth. Note: prover's
                   "CODEBASE_SYNOPSIS.md:36" citation was a bad filename — the
                   129 figure lives in dated CTO_REVIEW_JUNE_2026.md (left).
  (pending) [DOCS] F-M3p2 README test counts (4 sites) — awaits the verified
                   number from the Gate-A run.

GATED:JOE untouched, as required: README:89 "production software" phrasing,
README:6/:1542 Patent-Pending lines, pyproject Development Status classifier.
DEFERRED X-1 untouched (no transport code written).
```

### 2026-07-07 · E-004 — GATE A: PASS (verified_by V1, independent verifier)

```
Verifier: fresh agent, fresh venv (py3.13), repo read-only, on the final tip
a0cc6c2 (harden/wave2-docs, 10 commits over origin/master 9d35b0e).

  install  pip install -e ".[dev,stage,exr]"  -> exit 0 (usd-core 26.5, openexr 3.4.13)
  suite    4646 passed / 9 skipped / 46 deselected / 0 FAILED / 0 ERRORS  (8:05)
  ruff     All checks passed
  uv lock  --check exit 0 (lockfile matches pyproject)
  doctor   `agent doctor` exit 0 offline; graceful WARN rows; single local ping
  honesty  run_sse|--sse: 0 hits · requirements.txt in README: 0 hits ·
           no _find_comfyui.ps1 · no requirements.txt · root .md = 11
  [dev]    separate evidence run on harden/wave1 tip: 4236 passed / 174 skipped /
           0 failed / 0 errors (7:20) — the audit's solo-critical acceptance.

Notes: verifier's "9 vs 10 commits" flag = orchestrator's own prompt error
(M3p2 was pending at launch); resolved, final count 10. Measured 4646 <
README's old "4,680+" claim -> claims corrected DOWNWARD to 4,640+ (a0cc6c2).
Fresh-install suite is ~8 min, not CLAUDE.md's old ~3 min -> corrected.

FIXED (reproduce->clean, per the Floor): F-S1 F-S2 F-S3 F-S4 F-M1 F-M2 F-M3
F-D0/D1/D2 F-API1 F-API2.
REMAINING for v5.6.0: Joe's keystrokes only (push, PR, merge, tag/release).
REMAINING after that: Wave 3 (A1-A4, Option A fleet story) -> v6.0 candidate;
G-1/G-2 decisions; X-1 someday-RFC.
```

### 2026-07-07 · E-005 — HALT before push: pre-existing public disclosure found by adversarial pass

> The full release-prep run completed (v5.6.0: ADHD docs pass + mermaid label +
> version bump 5.5.0->5.6.0 + __init__ drift 5.4.0->5.6.0 fix + CHANGELOG). 12
> commits, tip f90fea9. Gate A green; brightline scan CLEAN; adversarial pre-push
> verify (5 lenses, run wf_5ce0e32d) returned 0 blockers. PUSH HELD anyway.

```
WHY HELD — the leak lens surfaced (and I confirmed deterministically):
  COUNCIL_DECISIONS.md  — 8x "Moneta" + patent-CIP/counsel-review strategy
  RUN_INSIDE_OUT_PASS.md — 2x "Harlo" + Moneta-in-process + counsel review
  Both are ALREADY on PUBLIC origin/master (git show origin/master:<f>|grep -ic
  confirmed 8 and 2). Same class as the Moneta public-disclosure incident.

MY DIFF adds ZERO confidential tokens (git diff origin/master..HEAD | grep '^+' |
  grep -ic moneta|harlo|counsel = 0). Exposure is PRE-EXISTING, not introduced.
  BUT the archive-sweep commit 6a5a411 R100-renames both files into docs/archive/
  AND adds docs/archive/README.md that NAMES them -> marginal discoverability
  increase + entangles the cosmetic F-M2 declutter with a counsel-gated decision.

GUARDRAIL NOTE: the deterministic brightline_scan is BLIND to this class — it
  scans ADDED lines; a pure rename adds none, so tokens in the moved file body
  are invisible to it. The adversarial rename-aware lens caught it. Keep both.

DECISION FORK (Joe's — bigger than the release):
  Leak itself: counsel territory (scrub+history-rewrite / repo-private / accept).
    Agent CANNOT: force-push, filter-branch, or decide patent-content fate.
  Release shape:
    R1 ship all 12 (relocates+indexes the two files) — NOT recommended.
    R2 ship 11, DROP 6a5a411 + amend CHANGELOG's declutter line — leaves the two
       files exactly as they are on master today; F-M2 defers to bundle with the
       leak fix. RECOMMENDED. Not yet built — awaiting Joe.
    R3 hold entire release until leak resolved — overkill; fixes are independent.

STATE: nothing pushed. branch harden/wave2-docs @ f90fea9 intact, local only.
F-M2 status downgraded: FIXED -> BUILT-BUT-GATED (entangled with E-005).
```

### 2026-07-07 · E-006 — Joe cleared the content; agent push DENIED at tool boundary → handed to Joe

```
Joe (patent holder) authorized the push including the sensitive content, satisfying
the counsel gate by asserting his own authority over his own IP. Chosen shape: R1
(full 12 commits, as built). Facts re-confirmed before proceeding: content is
ALREADY public on origin/master; agent diff adds ZERO confidential tokens; push is
a normal branch push, NOT a force-push.

Agent attempted `git push -u origin harden/wave2-docs` — DENIED at the tool-permission
layer (remote ops reserved for the human; boundary held regardless of verbal auth).
Also `gh auth status` / `git ls-remote` bundle DENIED. Per instructions ("a denied
call means declined — do not retry verbatim") the push was NOT retried, and per
durable guidance [[brightline-token-rename-is-bypass]] ("hand the push to Joe outside
the agent") this is the CORRECT terminal shape: Joe executes the outward sequence.

HANDED TO JOE: exact push→PR→CI→merge→tag v5.6.0→metadata sequence + PR body file
(tooling/harness/prod/PR_BODY_v5.6.0.md). Everything agent-side is DONE and green:
build, Gate A (E-004), brightline CLEAN, 5-lens adversarial verify 0 blockers.
Nothing further the agent can execute — all remaining steps are remote/human.

NOTE for the record: release.yml runs pytest with --ignore=tests/test_provisioner.py
— now vestigial post-F-S1 (the file skips cleanly) but harmless; optional follow-up
to drop the flag.
```
