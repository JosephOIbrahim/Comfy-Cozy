# WP-1.1 SCOUT FINDINGS — [PACKAGING × SCOUT]

```
+== SCOUT CAPSULE ==========================================================+
| WP:            WP-1.1 (PyPI package) — Scout items only, per             |
|                LOCAL_TWIN_BLUEPRINT.md. Constraints C1-C8 in force.     |
| SESSION:       2026-07-11 · read-only recon · this file is the only     |
|                mutation. No installs, no pushes, no forge.              |
| METHOD:        12-agent workflow harness (4 recon scouts + 4-area path  |
|                census + 4 adversarial verifiers + 1 risk synthesizer),  |
|                conductor-spot-checked. Every claim below carries a      |
|                file:line read this session or an HTTP status observed   |
|                this session. Verify ledger in §6.                       |
| NEXT ACTION:   Joe reviews. Forge ([PACKAGING × FORGE]) only after      |
|                sign-off.                                                 |
+===========================================================================+
```

**Headline:** `comfy-cozy` is **free on PyPI** (and `comfycozy` as fallback). The
wheel-safe refactor is real but tractable: **one anchor** (`agent/config.py:295`
`PROJECT_DIR` + the `.env` climb at `:12`) drives most of the breakage, the four
data families already live inside the package, and the in-tree exemplar pattern
to clone already exists (`agent/llm/_selection.py:25-28`). The sleeper finding:
the **top-level import package `agent` collides with the existing PyPI `agent`
distribution** — a publish blocker independent of console-script naming.
**Zero `importlib.resources` / `importlib.metadata` usage exists anywhere
in-tree** — every conversion is first-time work, not cleanup.

---

## 1 · PyPI availability

All statuses observed live this session via `GET https://pypi.org/pypi/<name>/json`
(404 = name free, 200 = taken):

| Name | Status | Verdict |
|------|--------|---------|
| **`comfy-cozy`** | **404 — FREE** | Primary per D1. Register at first publish. |
| `comfy_cozy` | 404 — FREE | Same normalized name as `comfy-cozy` (PEP 503); checked empirically to rule out a blocker. |
| **`comfycozy`** | **404 — FREE** | Fallback. A **different** normalized name (no separator) — independently squattable; consider defensive registration. |
| `cozy` | 200 — taken | Abandoned test package `Cozy` 1.0 (single release 2020-03-24, palindrome-check module). Package name irrelevant to us, but see §4 for the `cozy` *console-script* note. |
| `agent` | 200 — taken | `agent` 0.1.3 ("Async generators for humans", last release 2025-01-10). See §4 — this collides with our **import package name**, not just branding. |

**Normalization (PEP 503):** `comfy-cozy`, `comfy_cozy`, `comfy.cozy`, and
`Comfy-Cozy` all normalize to `comfy-cozy` — one registration covers all
spellings. `comfycozy` does not; it is a separate name.

---

## 2 · pyproject.toml audit

Current file, cited as read this session:

| Item | Value | Cite |
|------|-------|------|
| Distribution name | `comfyui-agent` — **D1's `comfy-cozy` is a rename**, not an addition | `pyproject.toml:2` |
| Version | `5.6.0`, hardcoded | `pyproject.toml:3` |
| requires-python | `>=3.10` | `pyproject.toml:8` |
| Console scripts | **exactly one:** `agent = "agent.cli:app"` — no `comfy-cozy`, no `cozy` yet | `pyproject.toml:71-72` |
| Extras | `dev` (`:46-52`), `stage` (usd-core, `:53-55`), `embed` (sentence-transformers→torch, `:56-60`), **`exr`** (openexr, `:61-64`) — blueprint expected three; **`exr` is a fourth** the WP text should absorb | `pyproject.toml:45-64` |
| Build backend | hatchling | `pyproject.toml:74-76` |
| Wheel contents | `packages = ["agent", "cognitive"]` — **this is the entire build config**; no include/exclude/force-include/artifacts blocks exist | `pyproject.toml:78-79` |
| Package data | **No explicit declaration.** `agent/knowledge/` (14 files incl. `triggers.yaml`), `agent/profiles/` (10), `agent/schemas/` (10), `agent/templates/` (8) ride hatchling's implicit whole-dir default. All 42 data files are git-tracked (conductor-verified), so nothing is silently dropped by the ignore-based default excludes *today* | `pyproject.toml:78-79` |
| MANIFEST.in | Does not exist (and is a setuptools mechanism — irrelevant under hatchling) | repo root |
| Version dual-source | `pyproject.toml:3` **and** `agent/__init__.py:3` both hardcode `5.6.0`; nothing links them (no `dynamic = ["version"]`, zero `importlib.metadata` in-tree). Manual dual-bump each release | both cites |
| Publish pipeline | `release.yml` triggers on `v*` tags (`:3-6`), builds sdist+wheel (`:33-34`), attaches to **GitHub Releases only** (`:36-40`). **No PyPI publish step** — no `pypa/gh-action-pypi-publish`, no twine, no `id-token: write` (permissions are `contents: write` only, `:11-12`) | `.github/workflows/release.yml` |
| Not packaged | `panel/`, `ui/`, `node_pack/`, `workflows/`, `assets/`, `scripts/`, `docs/`, `tests/`, `tooling/`, `video-recreation-agent/` — none referenced by shipped code (see §3 notable negatives), so wheel-absence is by design; confirm intentional for the sidebar story (WP-1.2 installs the sidebar from *somewhere* — under a wheel that somewhere isn't the checkout) | `pyproject.toml:78-79` |
| Package hygiene | `agent/perf/` is a **gitignored, empty** dir inside the package (only `__pycache__/`; zero importers — conductor-verified) and `agent/tools/ORCHESTRATOR_nim_lifecycle.md` is gitignored working notes inside `agent/tools/`. Neither ships; both are wheel-hygiene flags for the forge | `git status --ignored` |

---

## 3 · Path-assumption census

Every finding below was produced by a census agent and **independently
re-verified by an adversarial second agent** (citation re-read + tag re-derived
+ completeness hunt). Verify ledger in §6.

### 3a · WHEEL-BREAKS — shipped package code (the refactor worklist)

| # | Site | What | Why it breaks |
|---|------|------|---------------|
| B1 | `agent/config.py:12-13` | `_PROJECT_ROOT = Path(__file__).parent.parent` + `load_dotenv(_PROJECT_ROOT / ".env")` | `.env` discovery climbs above the package → `site-packages/.env`, which never exists. **Silent no-op**: all `.env`-driven config (keys, `COMFYUI_DATABASE`, `STAGE_*`) stops loading. |
| B2 | `agent/config.py:295` | `PROJECT_DIR = Path(__file__).parent.parent` | The repo-root anchor. Becomes `site-packages/` in a wheel. **Feeds B3-B7, B10.** |
| B3 | `agent/config.py:297` | `SESSIONS_DIR = PROJECT_DIR / "sessions"` | Session JSON persists into `site-packages/sessions` (mkdir+writes at `agent/memory/session.py:38`; injected into BrainConfig at `agent/brain/_sdk.py:230`). |
| B4 | `agent/config.py:298` | `LOCAL_WORKFLOWS_DIR = PROJECT_DIR / "workflows"` | **Dead-but-broken**: zero consumers found in agent/ or cognitive/ (verified) — delete or repoint. |
| B5 | `agent/config.py:299` | `LOG_DIR = PROJECT_DIR / "logs"` | Logs write into `site-packages/logs` — mkdir at `agent/logging_config.py:124` on **every start**. Read-only installs → crash at startup. |
| B6 | `agent/mcp_server.py:537-541` | `setup_logging(log_file=LOG_DIR / "mcp.log")` | The **primary `uvx` entry surface** hits B5 immediately on boot. |
| B7 | `agent/cli.py:102-104` (also `:553-555`, `:739-741`) | `setup_logging(log_file=LOG_DIR / "agent.log")` | `agent run` / `orchestrate` / `autoresearch` all hit B5. |
| B8 | `agent/tools/_util.py:32-38` | `_SAFE_DIRS = [... PROJECT_DIR, SESSIONS_DIR, WORKFLOWS_DIR ...]` | **Sandbox inversion.** Under a wheel, `validate_path` whitelists `site-packages` (writable through the gate!) while legitimate user workflow paths stop validating — only `COMFYUI_DATABASE` + tempdir (`:91-93`) survive. Functional break *and* security inversion. Gated consumers: `workflow_parse.py:131`, `workflow_patch.py:654-655`, `integrations/moneta.py:320-321`. |
| B9 | `agent/brain/_sdk.py:84,86-87` | `BrainConfig` defaults `Path("./sessions")`, `Path("./Custom_Nodes")`, `Path("./models")` | CWD-relative — arbitrary under `uvx`. Consumers: `brain/memory.py:239-240` (outcome JSONL), `brain/planner.py:351-352` (goals JSON). The integrated override (`_sdk.py:230-233`) merely swaps in B3's broken `SESSIONS_DIR`. |
| B10 | `agent/harness/cozy_loop.py:586-587` | `path = PROJECT_DIR / "BLOCKER.md"` | TERMINAL-halt post-mortem is buried in `site-packages` where no user looks (atomic write at `:598-599`). |
| B11 | `agent/_build.py:20,26-28` | `_REPO_ROOT = ...parent.parent`; `git` runs with `cwd=_REPO_ROOT` | Degrades to `hash="unknown"` per its own docstring (`:11-13`) — but if the venv nests inside **another** git repo, it silently reports that foreign repo's HEAD as build identity. |
| B12 | `cognitive/pipeline/autonomous.py:155` | `_AGENT_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "agent" / "templates"` | Triple-parent climb **above the cognitive package into the sibling agent package** — coincidentally resolves in flat site-packages, breaks under zipped/split installs, and violates the documented cognitive-does-not-import-agent boundary (its own comment at `:150-154` names the fix). Failure is masked by a **silent SD1.5-only fallback** (`:190-197`) — SDXL templates vanish with no error. |

### 3b · WHEEL-BREAKS — dev/sdist-only (never ships in the wheel; impacts onboarding + the installed-package test gate)

| # | Site | What |
|---|------|------|
| D1 | `scripts/setup.py:20-21` | Onboarding writes `.env` at repo root (`:109`) — a location the installed package will never search (B1). |
| D2 | `scripts/setup.py:55` (echoed `:51`) | **`default_db = "G:/COMFYUI_Database"`** — origin-machine drive letter offered as the default to every new user. |
| D3 | `scripts/setup.py:116,120` | Launcher rewrite targets hardcoded `G:\COMFY\...` and `C:\Users\User\comfyui-agent` literals. |
| D4 | `scripts/deploy.py:30,86` | Repo-root climb + repo-root `.env` discovery; `pip install -e .` at `:63`. Editable-install-only by design. |
| D5 | `scripts/deploy.py:140-146` | Independent second copy of the `C:\Users\User\comfyui-agent` literal (verifier-found; census missed it). |
| D6 | `scripts/validate_project.py:22,48-55` | Repo-root climb; version consistency checked by **regexing source files** — cannot serve as the installed-package gate as written. |
| D7 | `scripts/brightline_scan.py:45-46` | `git` subprocess with no explicit cwd — silently assumes CWD = checkout. Pre-push tooling only. |
| D8 | `tests/test_3d_demos.py:22` | `FIXTURES_DIR = Path(__file__).parent / "fixtures"` — fine in-place, but the sdist must include `tests/fixtures/` or the suite-against-installed-package acceptance leg fails. |

### 3c · WHEEL-SAFE-IF-DATA-INCLUDED — in-package asset loaders (need explicit package-data declaration + `importlib.resources` conversion)

| # | Site | Asset family | Degradation if data missing |
|---|------|-------------|------------------------------|
| A1 | `agent/config.py:296` | `KNOWLEDGE_DIR` → `agent/knowledge/*.md` (consumers: `agent/system_prompt.py:279-356`, `agent/knowledge/embedder.py:154-176`) | Knowledge injection + TF-IDF index silently empty. |
| A2 | `agent/system_prompt.py:79` | `agent/knowledge/triggers.yaml` (read `:92-96`) | `_load_triggers()` → `{}` at `:103-104`; keyword-triggered knowledge silently off. |
| A3 | `agent/schemas/loader.py:34` | `SCHEMAS_DIR` → `agent/schemas/**/*.yaml` (chain `:71-84`) | Note: the `custom/` override dirs would live **in site-packages** — an awkward place for user overrides; relocate with the state-dir move. |
| A4 | `agent/profiles/loader.py:31` | `PROFILES_DIR` → `agent/profiles/*.yaml` | Silent fallback to hardcoded minimal defaults (`:64`). |
| A5 | `agent/tools/workflow_templates.py:22` | `agent/templates/*.json` (used `:191`) | Starter templates not found. (`WORKFLOWS_DIR`/`COMFYUI_BLUEPRINTS_DIR` at `:18` are env-driven — safe.) |
| A6 | `agent/tools/pipeline.py:276` | Duplicate `agent/templates/` resolution (json load `:283`) | Same as A5 — two loaders to convert, or one to deduplicate. |

All six stay **inside** the installed package, so they survive a normal wheel
today via hatchling's implicit whole-dir default (§2) — the conversion is about
making inclusion *declared* and resolution *zip-safe*.

### 3d · WHEEL-SAFE — the patterns to keep (and clone)

| Site | Why it's the pattern |
|------|---------------------|
| **`agent/llm/_selection.py:25-28`** | **The in-tree exemplar:** `MODEL_SELECTION_PATH` env override → `Path.home() / ".comfy-cozy"` default. Risks R1/R2/R9/R10 all collapse into cloning this. |
| `agent/config.py:223,226` | `COMFYUI_DATABASE` env-driven with `Path.home()/"ComfyUI"` default; anchors `CUSTOM_NODES_DIR`/`MODELS_DIR`/`WORKFLOWS_DIR`/`MODEL_CATALOG_PATH`/`EXPERIENCE_FILE` (`:227-275`) safely outside the repo. |
| `agent/tools/nim_lifecycle.py:38-43` | Env + home default — but note **`~/.comfy_cozy` (underscore) vs `~/.comfy-cozy` (hyphen at `_selection.py:28`)**: two different state dirs; unify during the relocation. |
| `agent/config.py:286` | `STAGE_DEFAULT_PATH` purely env-supplied, `""` = in-memory. |
| `agent/recipes/__init__.py:43` + `agent/recipes/builtin.py:116` | **Recipes are pure code** — zero file I/O in `agent/recipes/` (grep-verified). No recipe data dir to package. |
| `agent/integrations/moneta.py:312-329` | Fully env-driven — wheel-safe itself, but validated through B8's inverted sandbox. |
| `agent/harness/cli_callables.py:187-193` | User-supplied `--workflow` path; **bypasses `validate_path` entirely** (verifier-found) — keeps working under a wheel; make the bypass a deliberate decision, not an inheritance. |
| `agent/gate/checks.py:265-291` | Blocked-prefix check on user-supplied values only; the gate subpackage's sole Path construction (verifier-found — census had zero gate coverage). |
| `cognitive/pipeline/autonomous.py:46-47` | Experience-file default mirrors config's home default **without importing agent** — but reads only process env, so it **diverges from agent's value once B1 kills `.env` loading**. |
| `cognitive/tools/execute.py:81-82`, `cognitive/experience/accumulator.py:197-255`, `agent/stage/cognitive_stage.py:131`, `agent/stage/provision_tools.py:55`, `agent/tools/comfy_discover.py:308+` (represents 8 sibling tool modules), `agent/tools/workflow_lock.py:43-46`, `agent/logging_config.py:122-124`, `agent/startup.py:359-363`, `tests/conftest.py` (fully tmp_path/env-isolated — the installed-package gate is unimpeded by conftest) | Env-driven, caller-supplied, or user-argument paths — no repo assumption. |
| `agent/stage/provisioner.py:26,84` | The **only** `G:/` literals in agent/+cognitive/ are these docstring examples; runtime `models_dir` is a required constructor arg (`:92,101`). |

### 3e · Notable negatives (verified absences)

- **Zero `importlib.resources` / `importlib.metadata` anywhere** in agent/ or
  cognitive/ — confirmed independently by all four census areas.
- **Zero `os.getcwd()` / `Path.cwd()`** in shipped code (the CWD reliance is the
  `./`-relative BrainConfig defaults, B9).
- **No shipped code references `panel/`, `ui/`, `node_pack/`, `assets/`, or
  `scripts/`** — the dependency runs the other way (those surfaces import
  `agent.*`). Repo-top `workflows/` is referenced only by the dead anchor B4.
- **One refuted finding** (adversarial verify working as intended):
  `agent/cli.py:131` "Copy .env.example to .env" is advisory *text*, not a path
  assumption — though the guidance itself goes stale under a wheel (folded into R2).

---

## 4 · `agent` console-script collision check

| Check | Result | Evidence class |
|-------|--------|----------------|
| This machine | `Get-Command agent -All` → exactly one entry, `C:\Python314\Scripts\agent.exe` (our editable install). Nothing else named `agent` even on this heavily-used box | observed |
| PyPI package `agent` | Exists (0.1.3, async-generators lib). Wheel fetched and inspected this session: **installs NO console script** (no `entry_points.txt`) — but **owns the top-level `agent` import module**, colliding with our `packages = ["agent", ...]` at the site-packages level. pip will happily co-install both and clobber the namespace **without warning** | observed |
| Linux | Debian **archive-wide contents search**: no package ships `/usr/bin/agent` or `/usr/sbin/agent` (only KF5/KF6 dev headers and a geoclue libexec demo) | observed |
| Windows 11 clean | No OS-provided `agent` executable (`ssh-agent.exe` is not `agent`) | reasoned, corroborated locally |
| Mainstream daemons | All suffixed — `elastic-agent`, `datadog-agent`, `buildkite-agent`; two web searches surfaced **no claimant of the bare name** | observed absence |
| `cozy` (D1's short alias) | PyPI name squatted (§1); **Debian ships `/usr/bin/cozy`** (GTK audiobook player) — a pip-installed `cozy` script and the OS binary would PATH-shadow each other on Linux desktops | observed |

**Verdict:** keeping `agent` as a deprecated alias is **LOW-to-MODERATE risk and
safe short-term** — nothing concrete claims the name today, and D1's shape
(new primary + deprecated `agent` alias with sunset) is confirmed sane. Two
sharp edges for the forge:

1. **The real collision is the import package, not the script** — the top-level
   `agent/` package name blocks a clean PyPI coexistence story regardless of
   what the console script is called (see R4).
2. **`cozy` as short alias:** fine on Windows; on Linux desktops it shadows the
   audiobook player. Worth one line in D1's implementation notes, not a change
   of decision.

---

## 5 · Risk list — ranked by blast radius

*(radius = how much breaks × how many users hit it × how hard to detect before ship)*

| R# | Radius | Risk | Key evidence | Mitigation (WP-1.1 build move) |
|----|--------|------|--------------|-------------------------------|
| **R1** | **5** | **`PROJECT_DIR` climb: sessions, logs, BLOCKER.md written into site-packages** — every wheel/uvx user, every launch; read-only installs crash at startup; invisible in every editable dev/test run | B2-B7, B10 (`agent/config.py:295-299`, `mcp_server.py:540`, `cli.py:104`, `logging_config.py:124`, `memory/session.py:38`, `cozy_loop.py:586`) | Relocate `SESSIONS_DIR`/`LOG_DIR` (+BLOCKER.md) onto the `_selection.py:25-28` exemplar (env override → `Path.home()` dot-dir). Delete consumer-less `LOCAL_WORKFLOWS_DIR`. |
| **R2** | **5** | **`.env` discovery silently no-ops in a wheel** — all `.env`-driven config stops loading; pure silence; CLI guidance trains users to create a file the package will never find | B1 (`config.py:12`), `cli.py:131`, `scripts/setup.py:20`, `cognitive/pipeline/autonomous.py:46` | Explicit search order: CWD `.env` (dev checkouts) → user-home config (`~/.comfy-cozy/.env`) → env override. Update CLI guidance + setup script. Also heals the agent↔cognitive config divergence. |
| **R3** | **4** | **`validate_path` sandbox inverts** — user paths rejected, site-packages whitelisted; functional break + security inversion, undetectable in editable installs | B8 (`_util.py:32`), `workflow_parse.py:131`, `workflow_patch.py:654`, `moneta.py:312`, `cli_callables.py:193` | Rebuild `_SAFE_DIRS` from R1's relocated roots; drop the climb entries; add an installed test asserting site-packages is NOT a sandbox root. Decide the `cli_callables.py:193` bypass deliberately. |
| **R4** | **4** | **Import package `agent` collides with PyPI `agent` 0.1.3** — co-install clobbers the namespace both ways, no pip warning; a **publish blocker** independent of D1's console-script plan | `pyproject.toml:79`, `:71-72`, `:2`; wheel inspection (§4) | Rename the top-level import package (e.g. `comfy_cozy/`) before any PyPI release. Register `comfy-cozy` (free) at first publish; defensively register `comfycozy`. **This is the one finding that may enlarge WP-1.1's scope — surface to Joe before forge.** |
| **R5** | 3 | **Package data ships only by hatchling's implicit default** — a backend switch or build-config edit silently drops all four data families; every consumer degrades gracefully (= invisibly). Asserted from pyproject; never verified against a built wheel (constitution forbade builds) | §3c; `pyproject.toml:78-79` | Explicit include/artifacts declaration naming all four families + `importlib.resources` conversion of the six loaders + an installed test asserting each family loads. |
| **R6** | 3 | **No suite-against-installed-package gate** — the single detection lever for R1/R2/R3/R5, and it does not exist; everything coincidentally works in editable mode | `release.yml:30-31`, `conftest.py:59` (clean), `test_3d_demos.py:22`, `validate_project.py:53` | The WP-1.1 acceptance criterion: build wheel → clean venv → run suite from non-repo CWD. Include `tests/fixtures/` in sdist. Land this gate **before** the relocations so they turn CI red, not ship-blind. |
| **R7** | 3 | **cognitive/ climbs into sibling agent/templates** — breaks under zipped/split installs; masked by silent SD1.5-only fallback (artists would blame the model); violates the cognitive-standalone boundary | B12 (`autonomous.py:155,150-154,190-197`) | Copy templates into `cognitive/templates/` (the fix its own comment names), declare as package-data, make the fallback loud. |
| **R8** | 3 | **No PyPI publish pipeline; free names squattable meanwhile** — GitHub-Releases-only today; anyone can squat `comfy-cozy`/`comfycozy` until first publish | `release.yml:3-6,11-12,33-40`; §1 | Trusted publishing: `id-token: write` + `pypa/gh-action-pypi-publish` on the existing `v*` tag flow. Register both names at first publish. |
| **R9** | 2 | **Version dual-hardcoded; build identity can report a foreign repo's HEAD** | `pyproject.toml:3`, `agent/__init__.py:3`, `_build.py:20,11-13`, `mcp_server.py:208,351` | `dynamic = ["version"]` (hatch reads the dunder) or `importlib.metadata`; guard `_build.py`'s git probe to its own repo or degrade to `unknown`. |
| **R10** | 2 | **BrainConfig standalone defaults are CWD-relative** (`./sessions`, `./Custom_Nodes`, `./models`) — state scatters wherever the process started; integrated branch inherits R1's broken dir | B9 (`_sdk.py:84-87,230-233`, `brain/memory.py:239-240`, `brain/planner.py:351-352`) | Point factory defaults at R1's user-home state dir; unify the `~/.comfy_cozy` vs `~/.comfy-cozy` dot-dir split (`nim_lifecycle.py:38` vs `_selection.py:28`). |
| **R11** | 2 | **Onboarding scripts seed dev-machine paths + a repo-root `.env`** — `G:/COMFYUI_Database` offered as default to every new user; mis-trains exactly the flow R2 relocates | D1-D5 (`scripts/setup.py:55,109,116,120`, `deploy.py:30,86,140-146`) | Fold onboarding into the packaged CLI (an init-style command writing R2's user-home config with a `Path.home()`-based default); demote `scripts/` to checkout-dev-only with a banner. |

**Cross-cutting (binds the forge order):**

1. **One refactor move covers most of the list.** R1, R2, R10, R11 are all
   "clone `agent/llm/_selection.py:25-28`" — and `agent/config.py:295` is the
   single anchor feeding `SESSIONS_DIR`/`LOG_DIR`/`_SAFE_DIRS`/BLOCKER.md/BrainConfig.
2. **Land R6's gate first.** Editable installs mask every break above; the
   installed-package CI gate is the only detection lever and converts
   R1/R2/R3/R5 from ship-blind to CI-red before the relocations start.
3. **R4 has an external clock.** The import-namespace collision blocks PyPI
   publish independent of everything else, and both free names stay squattable
   until R8's pipeline exists. This is the decision to put in front of Joe
   first.

---

## 6 · Method & verify ledger

- **Harness:** 12-agent dynamic workflow (`wp11-packaging-scout`), constitution:
  read-only / evidence-only (file:line or observed HTTP status) / adversarial
  verification / scope = WP-1.1 scout items / C1-C8 inherited / bounded failure.
  Subagents held no write authority; this file is the conductor's single mutation.
- **Verify ledger:** census→verify pipelined per area. **Core:** 14 confirmed,
  0 refuted, 0 missed. **Layers:** 17 confirmed, 0 refuted, 2 missed
  (gate/checks.py, cli_callables.py — folded in above). **Assets:** 22
  confirmed, **1 refuted** (`cli.py:131`, demoted to guidance-note), 1 missed
  (moneta sandbox coupling). **Periphery:** 14 confirmed, 0 refuted, 1 missed
  (`deploy.py:140-146` literal). Conductor independently re-read
  `pyproject.toml`, `agent/config.py:12-13`, `agent/__init__.py:3`, and the
  git-tracked status of all four data families — all consistent with the fleet.
- **Honest limits:** no wheel was built and nothing was installed (read-only
  session), so hatchling's *effective* file list is asserted from config +
  tracked-file state, not from a built artifact — R5/R6 exist precisely to
  close that gap. The PyPI `agent` wheel was **fetched and inspected, not
  installed**. Clean-PATH claims for Windows are reasoned (corroborated
  locally); Linux claims are observed via Debian archive contents search.

---

**STOP — scout complete.** No forge work has been performed. Joe reviews this
file; `[PACKAGING × FORGE]` proceeds only on sign-off, with R4 (import-package
rename) and R6-first ordering as the two decisions to settle before code moves.
