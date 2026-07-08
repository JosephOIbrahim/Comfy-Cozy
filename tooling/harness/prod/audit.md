# Comfy‑Cozy (`comfyui-agent`) — Production‑Readiness Audit

**Repo:** `github.com/JosephOIbrahim/Comfy-Cozy` · **Version audited:** 5.5.0 (`pyproject.toml:3`)
**Audit date:** 2026-07-07 · **Method:** disabled sparse checkout to materialize all 645 tracked files, then read source, installed the package in a clean venv, and ran lint + the full mocked test suite.

---

## What this project is

Comfy‑Cozy is a Python "AI co‑pilot" that drives **ComfyUI** (the node‑based Stable‑Diffusion/Flux/SDXL workflow tool) on behalf of non‑engineer VFX artists. It exposes **133 tools** primarily as an **MCP server** (`agent mcp`, consumed by Claude Code/Desktop) with a standalone CLI fallback (`agent run`). An LLM "brain" (Anthropic default; OpenAI/Gemini/Ollama/NVIDIA Nemotron pluggable) translates plain‑English intent ("make it dreamier") into *surgical, validated, reversible* edits to an existing workflow's JSON — it explicitly never generates workflows from scratch. Supporting subsystems: a default‑deny safety gate, LIVRPS delta/undo layers, a USD "stage" persistence layer (optional `stage` extra), cross‑session learning ("experience"), an autonomous overnight harness, EXR‑aware vision, and `workflow.lock` provenance. It is a **single‑process, single‑tenant developer/desktop tool**, not a multi‑tenant service.

---

## Evidence appendix — files & commands inspected

**Commands run (this environment, Python 3.14.3, clean venv):**
- `git sparse-checkout disable` → materialized 390 `.py` files (repo ships sparse; code was not on disk initially).
- `pip install -e ".[dev]"` → **exit 0**, 71 packages, resolved with *latest unpinned* deps.
- `ruff check agent/ tests/` → **"All checks passed!"** (exit 0).
- `pytest tests/ -m "not integration"` → **4231 passed, 173 skipped, 44 deselected, 27 errors** in 60.8s. The 27 errors were *all* `tests/test_provisioner.py` failing at fixture setup because `usd-core` (the `stage` extra) was absent.
- `pip install "usd-core>=24.0"` → installed **usd-core 26.5** (works on 3.14), then `pytest tests/test_provisioner.py` → **33 passed**. Confirms the 27 errors are an install‑extra artifact, not real failures.

**Files read:** `pyproject.toml`, `requirements.txt`, `package.json`, `.env.example`, `README.md` (head + Get‑Running + claims), `CHANGELOG.md`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `agent/cli.py`, `agent/config.py`, `agent/mcp_server.py`, `agent/main.py`, `agent/tools/__init__.py`, `agent/tools/_util.py`, `agent/tools/comfy_provision.py`, `agent/tools/workflow_patch.py`/`workflow_session.py`, `agent/brain/_sdk.py`, `agent/stage/provisioner.py`, `cognitive/pipeline/autonomous.py`, `tests/conftest.py`, `tests/test_workflow_patch.py`, `_find_comfyui.ps1`, `Dockerfile`, `docker-compose.yml`, `LICENSE`.

---

## 1. Product shape

- **Confirmed** via `pyproject.toml:2` and `README.md:9-44`. Entry points `agent run` / `agent mcp` via `[project.scripts]` (`pyproject.toml`). MCP is the primary surface (`agent/mcp_server.py`).
- **"Production use" for this tool** = a solo artist (or a studio floor) can install it, point it at a running ComfyUI, and trust it to edit/execute workflows without corrupting files, leaking secrets, running unwanted installs, or crashing on transient failures — repeatedly, across upgrades.
- **ComfyUI compatibility assumption:** it talks to a *live, separately‑installed* ComfyUI over REST/WebSocket (`agent/tools/comfy_api.py`, `COMFYUI_HOST`/`COMFYUI_PORT`). It does not bundle or version‑pin ComfyUI; it reads node interfaces live (`get_node_info`) rather than from memory — a sound design for a fast‑moving ecosystem.

## 2. Install / run path

**Good:**
- Clean single‑command install: `pip install -e .` (README `Get Running`). Verified working (exit 0) even on Python 3.14 (outside the advertised 3.10–3.13).
- First‑run fails *gracefully*, not with a traceback: `agent/cli.py:117-125` prints a red "ANTHROPIC_API_KEY not set" and `raise typer.Exit(1)`; `config.py` key‑warning is deferred/idempotent so import never explodes.
- `.env.example` marks `ANTHROPIC_API_KEY` as the sole required var and honestly warns it stays required for *vision* even under `LLM_PROVIDER=nvidia` (a real trap, documented).
- Cross‑platform config default is correct: `config.py` uses `Path.home() / "ComfyUI"` with auto‑detect and port range‑validation — **no hardcoded drive letters in the config path.**
- Docker path is clean: `python:3.11-slim`, non‑root `agent` user, no torch extras.

**Gaps:**
- **Dependency pinning is inconsistent / no true lockfile.** `pyproject.toml` uses loose ranges (`anthropic>=0.52.0`) and puts `torch`/`sentence-transformers` behind the optional `embed` extra — but `requirements.txt:9-10` *pins* `sentence-transformers==3.3.1` + `torch==2.5.1` (via a CPU `--extra-index-url`). The two files disagree about what a default install contains, and there is no `uv.lock`/`poetry.lock`. Installing via `requirements.txt` drags ~200 MB of torch that `pip install -e .` does not. **Non‑deterministic installs across the two documented paths.**
- **ComfyUI discovery helper is Windows‑only and stale:** `_find_comfyui.ps1` is PowerShell‑only and hardcodes `G:\COMFYUI_Database`. No macOS/Linux equivalent — non‑Windows users must set `COMFYUI_DATABASE` by hand.
- **Provider SDKs not bundled:** OpenAI/Gemini require a separate manual `pip install openai` / `google-genai` (documented inline in README, but it means "swap one env var" isn't quite one step).
- **Doc/count drift:** README repeatedly says "133 tools" and "production software / 4,680+ tests" while `pyproject.toml` classifier says **`Development Status :: 4 - Beta`** and the README also carries a **"Patent Pending"** banner alongside the MIT license — mixed signals a studio's legal/procurement will notice.

## 3. Safety / reliability — **strongest area**

- **Path sandbox is robust.** `agent/tools/_util.py:validate_path()` blocks UNC paths, drive‑relative paths, NTFS alternate data streams, and system prefixes (`/etc /usr /bin /var /root` + Windows), then enforces a `_SAFE_DIRS` allowlist via `is_relative_to` on *resolved* paths (traversal‑resistant).
- **Code‑executing installs are gated exactly as CLAUDE.md promises.** `agent/tools/comfy_provision.py`: `install_node_pack` validates the pack name, confirms the resolved target stays inside `Custom_Nodes`, and returns a `needs_confirmation` block before any `git clone --depth 1` (timeout‑bounded, `shutil.rmtree(..., ignore_errors=True)` cleanup on failure at `:523`). `download_model` does zero network I/O before consent.
- **Real SSRF defense:** private‑IP/CGNAT/cloud‑metadata blocking + host allowlists (`_ALLOWED_DOWNLOAD_HOSTS`/`_ALLOWED_GIT_HOSTS`) + DNS‑rebinding resolution checks (`comfy_provision.py`).
- **Thread‑safety / state:** `agent/tools/workflow_session.py` locks every accessor with `RLock`, snapshots under lock (avoids TOCTOU), bounds the session registry (`_MAX_SESSIONS=100`) and undo history (`_MAX_HISTORY=50`). Per‑connection isolation via `_conn_session` ContextVar.
- **Error hygiene:** no bare `except:` anywhere; `except Exception` sites are typed; errors translate to human messages rather than tracebacks (`errors.py`). Structured logging with JSON/human formatters, correlation IDs, and a rotating file handler.
- **Graceful degradation:** "ComfyUI is not running" surfaces as a readable message (`comfy_api.py`), circuit breakers guard sustained failures, cognitive‑import failure degrades to `_HAS_COGNITIVE=False`.

Minor: `agent/stage/provisioner.py:26` still shows `G:/COMFYUI_Database/models` — but it is inside a *docstring usage example*, not a live default.

## 4. Studio readiness — **the weak axis**

- **No authentication / authorization anywhere.** `MCP_AUTH_TOKEN` is *defined* (`config.py`) but `agent/mcp_server.py:333-365` explicitly logs that stdio "cannot enforce token‑based auth" and defers to an **auth/reverse proxy that does not exist in‑repo**. Grep found **no SSE/HTTP transport implementation** (`run_sse` absent) despite the docstring pointing users to it — so the recommended authenticated path isn't actually shipped. No RBAC, no per‑artist permissions.
- **Isolation is per‑connection, not per‑user.** State is a ContextVar keyed to a per‑process UUID (`mcp_server.py`). Concurrent processes don't trample each other, but there is **no user identity** and no shared‑instance multi‑tenant story.
- **Config is per‑machine, env‑var only** (single project‑root `.env`, `override=True`) — no per‑user profiles, no central config service.
- **Upgrade/migration is partially real:** session schema migration is genuine code (`session.py` `_migrate_session`, v0→v1→v2 with `schema_version`) and `migrate_deprecated_nodes` is a shipped tool. But the many `MIGRATION_MAP*.md` files are design docs, not tooling.
- **Offline behavior** degrades cleanly (see §3).

## 5. Engineering maturity

- **Tests: substantive and genuinely mocked.** `tests/conftest.py` needs no ComfyUI/API key; five autouse fixtures enforce isolation (ContextVar snapshot, circuit‑breaker reset, experience‑store redirect to tmp, cache reset, workflow deepcopy/restore). ~179 test files, **~8,000+ asserts**; `test_workflow_patch.py` alone is 1,338 lines with real behavioral checks (rollback, before/after values, DAG‑safety rejection). **I independently ran the suite: 4231 passed / 0 real failures** (the 27 "errors" were a missing `stage` extra and vanish once `usd-core` is installed → +33 pass).
- **CI is honest and broad:** `ci.yml` runs the *full* 3.10–3.13 × Ubuntu/Windows matrix, installs `[dev,stage,exr]`, hard‑verifies `usd-core` imports (no green‑by‑skip), runs `pip-audit` (continue‑on‑error), ruff, and `pytest -m "not integration"`.
- **Lint clean** (verified). **Release automation** exists (`release.yml`: tag‑triggered build + GitHub release).
- **CHANGELOG is exemplary** — Keep‑a‑Changelog + SemVer, dated entries, per‑release verified test counts, `[Unreleased]` section. **LICENSE = MIT.**

**Maturity gaps:**
- **`mypy` is a declared dev dep but CI never runs it** (`grep mypy .github/workflows/*.yml` → 0). Type‑checking is aspirational, not enforced.
- **No `SECURITY.md`, `CONTRIBUTING.md`, or `CODE_OF_CONDUCT.md`** (confirmed absent at root and `.github/`). For a tool that runs `git clone`/`pip install` on a user's machine, the missing vuln‑disclosure path is a notable omission.
- **README ⇄ reality drift on the test story:** README says `pip install -e ".[dev]"` gives "+4,680+ passing tests", but that exact command yields **27 collection errors** (not skips) because `test_provisioner.py` imports `agent.stage` at module load without USD. Repro requires `.[dev,stage]`. Tests should *skip* cleanly when USD is absent, not error.

## 6. Code architecture

- **Clean layered dispatch.** `agent/tools/__init__.py` imports tool modules individually (one failure degrades gracefully), detects duplicate‑registration collisions, and lazy‑loads the brain/stage layers to avoid cold‑start cost. Three layers (tools / brain / stage) share a uniform `TOOLS + handle()` contract.
- **BrainAgent SDK** (`brain/_sdk.py`) is proper dependency injection (`BrainConfig` dataclass, auto‑registration via `__init_subclass__`), deliberately reusing the canonical `validate_path`.
- **Cognitive boundary is *soft*, not absolute** (CLAUDE.md overstates it). `cognitive/pipeline/autonomous.py:59,72,73` imports `agent.circuit_breaker` / `agent.brain.*` — but all inside `try/except` returning `None` (lazy, optional coupling). Functional and defensible; the docs' "does NOT import agent.*" is inaccurate.
- **Very low tech debt:** only ~10 TODO/FIXME/HACK hits repo‑wide, most false positives (stub‑detection regexes). Destructive ops (15 `rmtree`/`remove`/`unlink`) are cleanup‑on‑failure and guarded.
- **Repo hygiene noise:** **32 markdown files at the repo root** (phase reports, blueprints, dispatch specs, session capsules) alongside README — heavy clutter that obscures the docs a user actually needs and signals "working repo" rather than "shipped product."

## 7. Docs

- README is thorough, scannable, honest about the vision‑key trap and the install‑confirmation gate. QUICKSTART/SETUP_GUIDE present. `docs/` holds 61 files incl. `ARCHITECTURE.md`.
- **But:** no API reference for the 133 tools beyond the CLAUDE.md table; a troubleshooting section is thin; the root is buried under design docs; and several counts/paths drift (77 vs 133 tools in some docs, `G:/` examples, `.[dev]` test promise).

## 8. Ran‑what‑is‑feasible (results)

| Check | Result |
|---|---|
| `pip install -e ".[dev]"` | ✅ exit 0 (latest unpinned deps, Py 3.14) |
| `ruff check agent/ tests/` | ✅ All checks passed |
| `pytest -m "not integration"` (`.[dev]` only) | ⚠️ 4231 passed / 173 skipped / **27 errors** (missing `stage` extra) |
| `pip install usd-core` + `pytest test_provisioner.py` | ✅ 33 passed — confirms errors are extra‑only |
| `mypy` | Not run by CI; declared but unenforced |
| Dependency count | 13 core + 5 dev + 3 extras (pyproject); `requirements.txt` pins ~130 packages |
| Known‑vuln deps | `pip-audit` wired in CI (continue‑on‑error); not independently run here |

---

## Blocking gaps before production

### For solo users (few, mostly cosmetic/repro)
1. **Reconcile the `.[dev]` test promise** — either make `test_provisioner.py` (and other `agent.stage` importers) *skip* cleanly without USD, or change the README to instruct `.[dev,stage]`. Today the advertised command errors.
2. **Fix the `requirements.txt` ⇄ `pyproject.toml` torch inconsistency** (or delete `requirements.txt` in favor of the extras). Non‑deterministic install surface.
3. **Ship a cross‑platform ComfyUI‑discovery fallback** (Python/shell) — the PowerShell `G:\`‑hardcoded helper strands macOS/Linux users.

### For studios (hard blockers)
1. **No authentication/authorization, and the recommended authenticated transport (HTTP/SSE + proxy) is not actually implemented in‑repo** (`mcp_server.py:333-365`). A studio cannot expose this beyond a single trusted desktop.
2. **No per‑user identity or multi‑tenant model** — isolation is per‑process only.
3. **No `SECURITY.md` / vuln‑disclosure policy** for a tool that executes `git clone` + `pip install` on approval.
4. **No centralized/per‑user config or upgrade‑migration story** beyond a single machine‑local `.env`.

## Important non‑blockers
- `mypy` not enforced in CI (declared dep) — quality gap, not a runtime risk.
- 32 root‑level markdown docs — clutter; move to `docs/` or `docs/archive/`.
- Doc count drift (77 vs 133 tools), `G:/` docstring examples, "Patent Pending" vs MIT tension.
- Provider SDKs (OpenAI/Gemini) require a manual extra install.
- Cognitive‑boundary doc overstatement (soft not hard).

## Prioritized wrap‑up checklist
1. **[studio‑critical]** Implement (or clearly remove the promise of) authenticated HTTP/SSE transport with token verification; document the trust boundary. 
2. **[studio‑critical]** Add `SECURITY.md` (disclosure path) + `CONTRIBUTING.md` + `CODE_OF_CONDUCT.md`.
3. **[solo‑critical]** Make `agent.stage`‑dependent tests skip without USD; align README to `.[dev,stage]` OR guard module‑level imports.
4. **[solo‑critical]** Resolve `requirements.txt`↔`pyproject` torch pinning; commit a real lockfile (`uv.lock`) for deterministic installs.
5. **[solo]** Add cross‑platform ComfyUI discovery; remove/replace the PowerShell‑only `G:\` helper.
6. **[maturity]** Run `mypy` in CI (even non‑blocking at first). 
7. **[polish]** Flip `Development Status` to Production/Stable *only after* 1–4; reconcile tool counts and the Patent‑Pending/MIT messaging; declutter root docs.
8. **[studio]** Document an upgrade/migration runbook and per‑user config strategy.

---

## Honest readiness verdict

| Audience | Verdict | Rationale |
|---|---|---|
| **Solo users** | **Beta → near‑production** | Installs and runs cleanly, lint‑clean, ~4,260 real tests pass, safety surfaces (path sandbox, confirmation gates, SSRF, thread‑safety, graceful degradation) are genuinely well‑built. Held back from "production" only by the `.[dev]` test‑repro error, the torch pinning inconsistency, and Windows‑only ComfyUI discovery — all small, fixable. The README's own "production software" claim is *defensible for this audience* once those are fixed. |
| **Mid‑sized studios** | **Alpha for shared/multi‑user use** | The engineering core is strong, but the tool is architecturally single‑tenant: **no auth, no user identity, no shipped networked transport, no security policy, no central config/upgrade story.** It is safe as a *per‑artist desktop copilot*, but not deployable as shared studio infrastructure without net‑new work (items 1–2, 8). |

**Bottom line:** This is an unusually well‑engineered *single‑user desktop tool* — the safety and test discipline are real, not cosmetic — mislabeled in places as broadly "production." Close the four solo‑critical items and it is legitimately production‑ready for individual VFX artists. Studio deployment needs a genuine security/multi‑tenancy layer that does not yet exist in the repo.
