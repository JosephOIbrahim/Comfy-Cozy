# Comfy-Cozy — CTO Codebase Review (June 2026)

> First-principles review from the CTO seat: 10 domain reviewers + 1 empirical
> latency-measurement agent, each finding adversarially verified against the code,
> then synthesized. **Read-only** — this document is the only artifact produced;
> no source was modified. Method: multi-agent harness (`wf_2ba4a767-728`),
> 74 agents, ~9.0 M agent-tokens, measured live against the repo + a running
> ComfyUI at `127.0.0.1:8188`.

> **Verification caveat (read this first).** The adversarial-verification wave was
> **interrupted by a monthly spend cap** partway through. The harness conservatively
> treats a *killed* verifier the same as a refutation, so ~29 medium findings —
> **the entire UI-panel dimension plus scattered dispatch/MCP/tests-CI/brain items** —
> were dropped from the ranked top-15 but preserved in the **per-dimension appendix**.
> The **two P0s and every latency finding (ranks 3–13) were confirmed before the cap.**
> Treat §3 (Top Changes) as verified; treat the appendix's unverified items as
> *leads requiring a verification pass* before roadmap commitment.
> Counts: **53 findings surviving, 30 marked refuted** (of which ~29 are cap-kills,
> not genuine refutations).

---

## 1 · Executive summary

Comfy-Cozy's architecture is sound — clean three-layer dispatch, a safety gate whose
per-call cost is microseconds (0.77–5.6 µs **measured**), deterministic JSON, 4,437
mocked tests, and a **real 2-OS CI matrix** (the hypothesized "no CI" P0 was *false* —
`.github/workflows/ci.yml` exists). The review found no rot in the bones. What it found
is that **two headline behaviors are broken in production** and **a single class of
economic waste — "construct/fetch fresh on every call" — repeats across every network seam.**

- **P0 #1 — the documented one-shot repair loop is dead code.** `repair_workflow` reads
  the key `"missing"` while `find_missing_nodes` returns `"missing_nodes"`
  (`comfy_provision.py:1013` vs `comfy_discover.py:1364`), so repair always reports
  `"clean"` when nodes are actually missing. Tests mock the wrong contract, masking it.
- **P0 #2 — the standalone CLI's system prompt bypasses the human-confirmation gate.**
  `system_prompt.py:24` instructs the model to run code-executing installs "in one
  continuous flow without stopping to ask," directly countermanding the
  `needs_confirmation` gate the tool layer built. The MCP-side rule was fixed; this
  prompt was not.

The **latency story is concentrated and measured**: the full 4.58 MB `/object_info`
fetch costs 4.3–4.9 s and is re-downloaded uncached at **7 call sites** (the per-class
endpoint returns 3.3 KB in 1.4–186 ms — a ~1400× payload gap); the engine adapter builds
a fresh `httpx.Client` per call at ~200–240 ms each, paid **every poll second**; the
vision path constructs a fresh Anthropic client (~0.25–0.29 s) per call; and the eagerly
imported stage layer is **~600 ms of the 896.5 ms cold import** every process pays.
**Four small confirmed fixes** (one TTL cache, two pooled clients, one lazy-registration
loop) recover essentially all of it.

The cognitive persistence layer rewrites its full 10.9 MB JSONL on every pipeline run
(O(n²) lifetime IO) and skips the `fsync` the repo's own durability convention requires.
A WebSocket robustness bundle (keepalive defaults + untranslated `ConnectionClosed` + a
silently-ineffective 1 MB message cap) can waste an entire 900 s NIM warmup.

Nearly nothing here was already tracked: `docs/IMPROVEMENT_AREAS_JUNE_2026.md` covers
portability guards, branch-#55 disclosure, NIM environmental setup, and hygiene — an
entirely different class from what this review surfaced.

---

## 2 · Scorecard

| Area | Grade | One-line |
|---|:---:|---|
| Tool dispatch & safety gate | **B** | Per-call cost negligible (0.77–5.6 µs, O(1) lookups); scope check only partially mirrors `_util` path guards; risk-map drift has precedent. |
| Engine & HTTP layer | **D+** | Clean `IAIEngine` abstraction undermined at every joint: fresh client per call (~200–240 ms), 7 uncached 4.58 MB fetches, WS errors escaping the adapter's own translation contract. |
| Workflow edit hot path | **B+** | Per-edit latency healthy (`to_json` 0.407 ms, undo deepcopy 0.7 ms @150 nodes); waste limited to `jsonpatch.make_patch` run on every apply/undo/save just for a count. |
| MCP server | **B** | Startup ~1.2 s, schema conversion 0.08 ms (non-issue), good error wrapping; debits are a blanket 120 s `wait_for` and per-call auth-warning log spam. |
| Brain & vision | **C** | Architecture right (lazy 0.03 s, provider singleton, no locks over I/O) but every per-call economy missed: fresh Anthropic client, full-res uploads, a prompt-cache that can never hit, a stale-serving cache. |
| Cognitive library | **B-** | In-memory growth well-bounded, SHA-256 cheap (4.5 µs/create), but persistence is O(n²)-lifetime (full 10.9 MB rewrite/run), un-fsynced, and `EXPERIENCE_FILE` defined twice. |
| CLI & agent loop | **C+** | Good downstream error translation, but the system prompt bypasses the install gate, compaction can orphan `tool_result` blocks, ollama users blocked on an Anthropic key, typo'd env crashes `--help`. |
| Discovery & provisioning | **D** | `repair_workflow` always reports clean in production, `discover` strictly serial (~45 s worst case), silent downloads with no resume, pip installs land in the *agent's* venv. |
| UI panel *(mostly unverified)* | **C** | Token streaming wired but never rendered, tab-switch can drop the reply, `MCP_AUTH_TOKEN` silently 401s the canvas bridge, ~50 KB dead modules, 429s shown as raw codes. |
| Tests & CI | **B-** | 4,437 mocked tests + real CI, but stage layer is green-by-skip (usd-core never installed), the daily dev interpreter (3.14) is never tested, and the documented `-m "not integration"` default isn't configured. |
| Startup & cold path | **C+** | 896.5 ms cold / ~480 ms warm import, ~600 ms of it eager stage imports (networkx 293.6 ms + pxr ~310 ms); the brain lazy pattern (55.7 ms) proves the fix. |

---

## 3 · Top changes (ranked, verified)

### P0 — fix now

**1. `repair_workflow` ↔ `find_missing_nodes` contract mismatch — repair always reports "clean" in production** · *correctness · S*
`agent/tools/comfy_provision.py:1013,1025-1027`; `agent/tools/comfy_discover.py:1317-1321,1359-1364`; `tests/test_comfy_provision.py:231-245`
Consumer reads `result.get("missing", [])` with `class_type`/`pack_name` keys; the real producer returns the list under `"missing_nodes"` with `node_type`/`pack_title` keys. When nodes ARE missing, `repair_workflow` gets an empty list and returns `{"status": "clean"}`. Tests mock the shape production never emits, so the suite is green. The documented one-shot repair flow (CLAUDE.md Tool Rule 5) is dead code.
→ Consumer-side remap (~3 lines): read `"missing_nodes"`, map `node_type→class_type`, `pack_title→pack_name`. Fix the wrong-contract mocks in all three test files, and add **one seam test** that drives the REAL `_handle_find_missing_nodes` (HTTP mocked) through `repair_workflow` so the joint can't drift again.

**2. CLI system prompt instructs the model to bypass the install-confirmation gate** · *security · S*
`agent/system_prompt.py:24` (also rule 14 at `:33`); `agent/tools/comfy_provision.py:1040-1070,475-477,1098`
Rule 5 says "call `repair_workflow(auto_install=true)`… in one continuous flow without stopping to ask," but installs (git clone + pip install) are gated behind a `needs_confirmation→confirm=true` handshake whose payload contains the literal re-call instruction — an obeying LLM self-confirms. The in-code comment calls the prompt-level handshake the "keystone" gate; rule 5 countermands it. CLAUDE.md's MCP rule was updated; this standalone prompt was not.
→ One string edit: rewrite rule 5 to mirror the CLAUDE.md flow (no auto-install; show the artist the pack list and wait for yes before `confirm=true`). Add a test asserting the prompt no longer contains the `auto_install=true` instruction.

### P1 — this month

**3. Cache `/object_info` + use per-class lookups — 4.58 MB / 4.3–4.9 s fetched uncached at 7 sites, incl. a false-failing NIM preflight** · *latency · M*
`comfy_api.py:243,359,364`; `comfy_execute.py:593-596`; `workflow_parse.py:679-682`; `comfy_discover.py:1280-1287`; `ui_api_parser.py:50-51`; `nim_lifecycle.py:182-193,249-252,276`
Measured: full fetch 4,578,205 B / 4.3–4.9 s vs per-class 3.3 KB / 1.4–186 ms; zero cache anywhere. The validate→fix→re-validate cycle pays ~9–10 s just for this. Acute: `nim_preflight` gives the fetch a 5 s budget to check 3 keys, and a blanket `except` converts a timeout into "all NIM nodes missing" → `nim_run` hard-fails before queueing, telling artists to reinstall an installed pack; re-pays the full fetch again at `:276`.
→ (1) Module-level ~120 s TTL cache in `comfy_api.py` with explicit `invalidate()` from install/uninstall. (2) Membership-only consumers switch to `GET /object_info/{class_type}` (ComfyUI returns 200+`{}` for missing → empty-body = missing). (3) `:276` liveness re-check uses `/system_stats`. (4) Distinguish "ComfyUI unreachable" from "nodes missing". (5) Add a cache-reset hook for the mocked suite + normalize the three timeout budgets to one constant.

**4. Pool HTTP clients in the engine adapter — ~200–240 ms pure connection overhead per call, every poll second** · *latency · S-M*
`agent/engine/comfyui_adapter.py:105,159,191`; `agent/engine/__init__.py:47-80`; `comfy_execute.py:593,823`; `ui_api_parser.py:51`
`queue_prompt`, `interrupt`, `get_history` each open `with httpx.Client()` per call — 198–238 ms vs 0.5–1 ms pooled. `_poll_completion` calls `get_history` every 1.0 s → ~20% of every polling second is connection setup, and every submission eats ~200 ms before ComfyUI sees the prompt. The correct pooled pattern already exists at `comfy_api.py:24-35`.
→ Lazily-created `self._client` guarded by `threading.Lock` on the (singleton) adapter, mirroring `comfy_api._get_client`; keep per-request timeout args. **Verifier caveat:** several tests patch `httpx.Client` at module scope and conftest has no engine-cache reset — add an autouse reset fixture + client-reset hook, or repoint mocks at the client-getter seam.

**5. Reuse the Anthropic client on the vision path via `with_options` — fresh client + TLS handshake + leaked FD per call** · *latency · S*
`agent/llm/_anthropic.py:146-149`; `agent/brain/vision.py:31,211-218`; `agent/mcp_server.py:351-359`
`AnthropicProvider.create()` builds a new `anthropic.Anthropic` whenever a timeout is passed — and every vision tool always passes `_VISION_TIMEOUT=120`. ~0.25–0.29 s construction + fresh TCP/TLS + a never-closed client. On SDK 0.75.0, `with_options` reuses the parent httpx client (~40 µs). **Companion confirmed:** the inner 120 s timeout exactly equals the MCP server's 120 s hard kill, so vision's structured error can never win — and default `max_retries=2` means lowering the constant alone is insufficient.
→ One line: `client = self._client.with_options(timeout=timeout)`. Same PR: `max_retries=0` on the scoped client + drop `_VISION_TIMEOUT` to ~90 s. **Both changes are required together** for the timeout fix to be sound.

**6. WebSocket robustness bundle: keepalive kills long model loads, `ConnectionClosed` escapes untranslated, the 1 MB cap closes on big previews** · *correctness · M*
`agent/engine/comfyui_adapter.py:229,234,236-256`; `nim_lifecycle.py:269-349,438-460`; `comfy_execute.py:497-507`
Three confirmed findings, one PR. (a) `connect()` inherits websockets 15.0.1 `ping_timeout=20 s`: a server stalled >20 s on a checkpoint/NIM load gets killed client-side. (b) `_events` catches only `TimeoutError`, so `ConnectionClosedError` escapes raw past the adapter's contract — `comfy_execute` survives via broad-except→polling, but `nim_run` has **no polling fallback** and can waste its full 900 s budget. (c) `:234` sets `recv_bufsize=16MB` believing it raises the message cap; the actual cap is the `max_size` connect kwarg, still at 1 MB default → any preview frame >1 MB triggers a 1009 close mid-render.
→ (1) Translate `ConnectionClosed → EngineConnectionError` with a human message. (2) `ping_timeout=60` at `:229`. (3) `max_size=16*1024*1024`, delete the dead `recv_bufsize` line. (4) In `nim_run`, degrade to `get_history` polling on mid-stream `EngineConnectionError`. **Parts 1+2 are the minimal viable fix.**

**7. `install_node_pack` runs bare `pip` from PATH — deps land in the agent's venv, not ComfyUI's Python** · *correctness · S*
`agent/tools/comfy_provision.py:552-567,327,564`
`subprocess.run(["pip", ...])` resolves the *agent's* venv pip; Windows ComfyUI commonly runs `python_embeded`, so node-pack imports fail inside ComfyUI even though the tool reports "Dependencies installed successfully" — every step "succeeded" and the nodes still don't appear (the worst shape for a non-engineer). Secondary: 120 s pip timeout is tight; raw `TimeoutExpired` (full command array) leaks to the artist at `:567`.
→ Add `COMFYUI_PYTHON` (probe `<install>/../python_embeded/python.exe`, else `sys.executable`); invoke `[comfy_python, "-m", "pip", "install", ...]`. Say so when falling back. Bump timeout to 300 s, humanize the message.

**8. Vision economics: downscale before upload, fix the 10×-too-loose size guard, retire the dead prompt-cache, re-key the stale cache** · *latency · M*
`agent/brain/vision.py:157-191,198-205,232-234` (call sites `:260,:331-332,:397`); `agent/tools/vision_cache.py:13-20,45-60,77-78,96`
Images base64'd at full resolution; only guard is 50 MB (~10× above API limits) → a 10–40 MB upscale passes locally then fails server-side. `compare_outputs` sends TWO images; the default model charges up to ~4784 tokens per full-res image. The prompt-cache block can never hit (~200-token prompts vs 4096-token minimum). `analyze_image_cached` keys on a 64-bit aHash (hamming≤2) ignoring the prompt — can serve the "before" analysis for the exact small-tweak loop it targets. All gate the Phase 7 vision-evaluator.
→ Downscale to ≤1568 px long edge in `_read_image_as_base64` only (prefer lossless PNG; JPEG q~90 only if still over). Lower the hard guard to API reality with a readable message. Correct the dead cache comment. Re-key `vision_cache` on `(SHA-256 of bytes, prompt)`, fix the substring error-guard with `json.loads`, fold the lookup into `analyze_image`.

**9. Misconfiguration → raw-error cluster: missing key shows SDK jargon, ollama blocked on an Anthropic key, env typos crash `--help`** · *usability · S*
`agent/brain/vision.py:209-218,232-237`; `agent/cli.py:96-104`; `agent/config.py:112-113,131-146,223`; `agent/llm/__init__.py:77`
(a) Reproduced live: with no key, `analyze_image` returns `'Vision API timeout or transport error: "Could not resolve authentication method..."'`; MCP path has no key warning anywhere. (b) `cli.py:96` hard-requires `ANTHROPIC_API_KEY` even with `LLM_PROVIDER=ollama`. (c) `THINKING_BUDGET=high` crashes every command incl. `--help` with a raw `ValueError` (`COMFYUI_PORT` already has the warn-and-default guard; three parses were missed).
→ Pre-check the key at the top of `_call_vision`; condition the `cli.py:96` gate on `LLM_PROVIDER=="anthropic"`; apply the `COMFYUI_PORT` try/except pattern to the three bare `int()` parses via a tiny `_int_env` helper.

**10. Persistence hygiene: experience JSONL rewrites 10.9 MB/run, nim warm-state grows unbounded with a lost-update race, neither fsyncs** · *latency · M*
`cognitive/experience/accumulator.py:185-204,224-238`; `cognitive/pipeline/autonomous.py:38-41,559-565`; `nim_lifecycle.py:101-117,143-156`; `agent/config.py:161,210`; `agent/session_context.py:219-221`
`accumulator.save()` rewrites ALL chunks per run — 109.3 ms / 10.9 MB at the 10k cap → ~11 GB written per 1,000 runs to persist ~1 MB. nim warm-state reads-all/appends-one/rewrites, never prunes its own 24 h-dead records, and concurrent writers drop each other's records. Neither fsyncs before `os.replace` while four modules already do (`brain/memory.py:317`, `image_metadata.py:227-232`, `workflow_patch.py:672`). Companion: `EXPERIENCE_FILE` defined twice with different defaults → learning can silently fork across two files.
→ Append-only writes for both (open `'a'`, one `sort_keys` line, `flush()`+`os.fsync()`, take `_save_lock`). Keep tmp+`os.replace` only for compaction. Resolve the path fork via `create_default_pipeline(experience_path=None)` lazily; keep the config constant (`panel/server/routes.py:493` is a live consumer).

**11. `discover`: parallelize the two network legs, memo results, surface registry staleness — ~45 s serial worst case** · *latency · S*
`agent/tools/comfy_discover.py:848-886,1155-1163,339-359`; `civitai_api.py:156-175,290-304`; `comfy_inspect.py:240-243,255-287`
CivitAI (5 s limiter + 20 s timeout) then HuggingFace (5 s + 15 s) run serially → ~45 s blocking, a slow CivitAI delaying even instant local hits; no per-query cache; `discover` never consults the freshness machinery one function away. Compounding: `_check_installed` probes EVERY model subdir per uninstalled result; `list_models`/`get_models_summary` do full `rglob` walks + double `stat()` per file — seconds on VFX network shares.
→ `ThreadPoolExecutor(2)` for the two legs with a ~20 s deadline (`shutdown(wait=False, cancel_futures=True)`); 5-min TTL memo keyed on the filter tuple; one-line registry-age note. Companion: one mtime-keyed model-dir listing cache (~60 s TTL) shared by both listers + an exported `is_installed()`.

**12. `download_model`: show the progress it promises, resume partials, put size/host/destination in the prompt** · *usability · M*
`agent/tools/comfy_provision.py:84-86,328,670-694,776-793,837-847`; `agent/tools/__init__.py:416-418`
Schema claims "Shows progress during download" but the write loop emits nothing — an artist approving a 12 GB FLUX checkpoint stares at silence for 30–60 min. Any failure deletes the `.download` temp; no Range resume → dying at 95% of 18 GB restarts from zero. The confirm prompt omits size/host/destination; the exists-check runs AFTER approval. **The MCP progress pipe already exists end-to-end.**
→ Thread `progress=` into `_handle_download_model`, read `Content-Length`, report at ~5% increments. Keep the part-file; resume with `Range: bytes=<size>-`. Hoist `target.exists()` above the gate; enrich the prompt with hostname/path/approx size.

**13. Lazy-register the stage layer — ~600 ms of the 896.5 ms cold import in every process** · *latency · M*
`agent/tools/__init__.py:31-47,85-103,171-214` (evidence only, no edits inside frozen stage: `agent/stage/cognitive_stage.py:31-35` **[RFC-stage]**)
`-X importtime`: `agent.tools` 896.5 ms cold (~480 ms warm); eager stage modules pull networkx (293.6 ms) + pxr/USD (~310 ms) — ~two-thirds — paid by every CLI command, MCP start, and pytest run, including paths that never touch a stage tool. The brain layer already defers its 27 tools (55.7 ms first-touch), proving deferred registration works within the `TOOLS/handle` contract.
→ Importer-side only: fold the `_STAGE_MODULE_NAMES` loop into the brain's `_init_once`/`_ensure` lazy path (MCP `list_tools` already triggers it, so the surface is unchanged). **[RFC-stage]** moving the in-module networkx/pxr imports to function scope is a post-2026-06-16 follow-up; the importer-side fix captures nearly all the win without touching frozen files.

### P2 — opportunistic

**14. `model_compat`: unanchored regexes mis-classify, WAN 2.2 unrecognized, unknowns silently pass — and the profiles YAML is never consulted** · *correctness · S*
`agent/tools/model_compat.py:110-114,148,223-234,263-274`; `agent/profiles/loader.py:170-208`
`r"(?i)bark"` first-match-wins classifies `tree_bark_detail_lora.safetensors` as audio; WAN patterns stop at 2.1 (`wan2.2_t2v_14B` → unknown); `_check_compatibility` excludes unknowns and reports `compatible=True` for mixed known+unknown — the exact silent mismatch this module exists to prevent. The curated profiles YAML is a parallel, never-imported knowledge base. **Verifier trap:** `\b` doesn't treat `_` as a boundary.
→ Underscore-aware anchors `r"(?i)(^|[-_.])bark([-_.]|$)"`; broaden WAN to `r"(?i)wan[-_]?2[\._]?[0-9]"`; return compatible-with-caution when unknowns present. Medium-term: move detection patterns into the profile YAML meta blocks.

**15. Compaction can orphan `tool_result` blocks at the 120k boundary — and the dict-only block checks are dead code in live sessions** · *correctness · M*
`agent/context.py:130,147-154,179,195`; `agent/main.py:211,297-301,350,363-377`; `agent/llm/_types.py:33-37`
`compact()` pass 2 slices `[summary] + last-6` with no tool_use/tool_result pairing check; an orphaned `tool_result` is API-rejected. **Verifier downgraded severity:** roles strictly alternate in the CLI loop, so it needs a user/user seam, self-heals in a few turns, and affects only `agent run`, not the MCP path. **Latent companion:** live tool results are typed `ToolResultBlock` objects, so the dict-only `isinstance` checks at `:130/179/195` are no-ops — pass-1 truncation silently does nothing.
→ Snap the keep boundary inside `compact()` with a guard matching BOTH dict blocks and typed `ToolResultBlock`. File the dict-only no-op as its own bug. Add a typed-block threshold test.

---

## 4 · Measured latency table

All numbers measured live (venv Python 3.12, ComfyUI at `127.0.0.1:8188`), not estimated.

| Path | Measured | Fix | Expected gain |
|---|---|---|---|
| `GET /object_info` (full, 7 sites) | 4.58 MB / 4.3–4.9 s (json.loads only 25.4 ms); per-class 3.3 KB / 1.4–186 ms | ~120 s TTL cache + per-class GETs for membership checks | ~4.5 s/fetch; ~9 s/validate→fix→re-validate; kills the false "NIM nodes missing" hard-fail |
| `httpx.Client` per engine call | 198–238 ms vs 0.5–1.0 ms pooled | Pooled client on the singleton adapter | ~200 ms off every queue/history call; ~20% of every 1 s tick |
| `anthropic.Anthropic` per vision call | ~0.25–0.29 s + TLS + leaked FD; `with_options` ~40 µs | `with_options(timeout=…)` + `max_retries=0` + `_VISION_TIMEOUT→90s` | ~0.25–0.8 s/call; FD churn gone; error path beats the 120 s kill |
| `import agent.tools` (every process) | 896.5 ms cold / ~480 ms warm; stage ≈600 ms (networkx 293.6, pxr.Sdf 238.5 + pxr.Ar 119.1); brain lazy 55.7 ms | Defer stage registration into the brain-style lazy path | ~600 ms off every CLI command, MCP start, pytest run |
| `ExperienceAccumulator.save` /run | 109.3 ms / 10.9 MB full rewrite @10k cap | Append-only line + fsync; tmp+replace only for compaction | O(n)→O(1)/run; ~11 GB → ~1 MB per 1,000 runs |
| `ExperienceAccumulator.retrieve` | 46 ms/call @10k (pure signature recompute) | Cache signature per chunk at record()/load() | ~6× (to ~10 ms) |
| `jsonpatch.make_patch` /apply/undo/save | 2.93 ms @150 / 9.94 ms @500 — discarded except `len()` | Drop the count / use a cheap proxy; keep only in `get_workflow_diff` | Removes the single most expensive edit-path op |
| `discover` serial fan-out | worst case ~45 s; zero result caching | `ThreadPoolExecutor(2)` + ~20 s deadline + 5-min memo | worst case ~20 s; repeats near-instant |
| Pre-dispatch gate /call | 0.77 µs (read-only) / 5.6 µs (full) / 116 µs (with path arg) | **None** | No action — 3–4 orders below any budget |
| MCP schema convert / `to_json` / config import | 0.08 ms / 0.407 ms / 35.4 ms | **None** | No action — healthy; keep `sort_keys` |
| pytest collection (4,437 tests) | 24.17 s cold / 6.92 s warm | **None** — document targeted runs | Cold cost is once-per-checkout |

---

## 5 · Strategic calls (CTO-level)

1. **Adopt one caching policy instead of seven point fixes.** The dominant latency pattern
   is "fetch/construct fresh per call" repeated independently (7 uncached `/object_info`,
   3 per-call client constructions, per-call model `rglob`s, per-result installed-checks,
   zero `discover` memo). Decide on a single `comfy_api`-level caching layer — TTL +
   explicit invalidation on the only state-changing actions (install/uninstall), pooled
   clients as default transport — plus a **test-suite cache-reset convention** (the
   all-mocked suite resets only ContextVar/workflow state today). This collapses ranks 3,
   4, 11, and the model-dir findings into **one architectural decision**, not four PRs.

2. **Treat vision economics as a prerequisite to Phase 7, not a follow-up.** The roadmap's
   vision-based evaluator multiplies call volume, and today every call pays a fresh client,
   full-res upload, a dead prompt-cache, and a cache that can serve stale analyses — while
   the rule-based stub writes flat `quality=0.7` chunks into the persistent store
   (migration risk: filter `source in ('', 'rule')`, patch the untagged float at
   `autonomous.py:501-502`). Sequence: client reuse + downscale + cache re-key **first**,
   then the evaluator swap with the migration filter baked in.

3. **The systemic disease is contract drift between layers that tests mock instead of exercise.**
   The dead repair loop, the CLI prompt countermanding the install gate, the gate's partial
   mirror of `_util`'s path guards, and the help-text drift are all the same failure: two
   sides of a seam evolve independently with no test driving the real producer through the
   real consumer. **Institute seam tests as a review requirement** for any cross-module
   contract, and single-source prompts/rules (CLAUDE.md rule 5 and `system_prompt.py` rule 5
   should be generated from or asserted against one canonical text).

4. **Make CI test what actually ships.** Three confirmed gaps: the stage layer is
   green-by-skip (usd-core in an extra CI never installs → 21 files SKIP,
   `test_provisioner.py` hard-ignored in two workflows); the daily dev interpreter is 3.14
   while CI tops at 3.12 and classifiers advertise a never-tested 3.13; and the documented
   `-m "not integration"` default exists nowhere — it holds by accident. Cheap matrix/addopts
   decisions, but CTO-level: they define whether green CI *means* anything for the stage layer.

5. **Decide the process-lifetime posture, then fix cold start once.** If Comfy-Cozy is
   primarily a long-lived MCP server, 896.5 ms cold import is tolerable — but the CLI, the
   harness, and every pytest run pay it too, ~600 ms of it stage imports for tools most
   invocations never touch. Apply the brain's proven lazy pattern importer-side now;
   **[RFC-stage]** queue the in-module import deferral for after the 2026-06-16 freeze.

6. **Schedule a consolidation pass before parallel implementations diverge further:** two
   model-family knowledge bases (`model_compat` regex dict vs profiles YAML), two
   `EXPERIENCE_FILE` definitions, three dot-directory spellings, duplicated
   format-extraction in `workflow_patch` vs `workflow_parse`, and a 523-line panel chat
   backend with no living frontend consumer + ~50 KB dead panel modules. None urgent alone;
   together they are the next generation of the contract-drift bugs above. One M-sized sprint
   with targets pre-agreed beats five more masked-by-mocks incidents.

---

## 6 · Not covered (honest gaps)

- **`agent/stage/**` internals** — design-frozen until 2026-06-16; import cost + persistence
  call sites measured, but USD composition, the DAG engine, and stage tool semantics were not
  audited. Flagged for a post-freeze review: `stage://` resources walking only one prim level;
  an atexit/autosave race on the checkpoint `.tmp` path.
- **The gated external integration** — branches, transport adapter, and related docs excluded
  per standing constraints; no findings cover those paths.
- **UI/panel verification** — the ui-panel findings (streaming never rendered, tab-switch reply
  truncation, `MCP_AUTH_TOKEN` 401ing the canvas bridge, `node_pack /agent/*` routes absent
  from the route-auth audit) are **dimension-level and unverified** (their verifiers were
  cut off by the spend cap) — they need their own adversarial pass before commitment.
- **No end-to-end render profiling** — execution numbers are microbenchmarks + live endpoint
  measurements, not a profiled real workflow under load; WS/polling findings are code-verified,
  not soak-tested.
- **Security depth** — covered the install gate, the scope-check mirror gap, and path
  sanitization; **no** dependency/supply-chain audit (node-pack git-clone trust, pip transitive
  deps), no workflow-JSON fuzzing, no panel auth review beyond the rate-limit finding.
- **Concurrency under multiple writers** — the nim warm-state lost-update race is code-verified,
  but multi-connection MCP behavior (two clients mutating the same files/stage) wasn't exercised;
  integration soak tests weren't run.
- **Zero-coverage modules** — `agent/startup.py` (372 lines), `local_assets`, `output_watcher`,
  `proactive_memory`, `vision_cache` have no behavioral tests and weren't reviewed in depth.
- **LLM behavioral quality** — prompt effectiveness, tool-selection behavior, conversation
  quality were out of scope; only the mechanical tool/transport surface was reviewed.

---

## 7 · Appendix — per-dimension summaries

> Verbatim reviewer conclusions. Findings whose verifiers were cut off by the spend cap
> (chiefly **UI panel**) live here rather than in §3; treat them as leads to verify.

**Dispatch & gate.** Gate is NOT a latency problem (0.77–5.6 µs/call, O(1) lookups; only per-dispatch I/O is `Path.resolve()` ~116 µs with a path arg). Real issues are architectural: three of the five checks are vacuous in production (`handle()` never wires `breaker_state`/`validated`/`action_history`); a broken gate import **fails OPEN and silent** (`except ImportError: pass`) and is import-coupled to the stage package; the risk-tier map has live drift — 9 of 129 tools fall to the REVERSIBLE default incl. GPU-executing `nim_run`, with in-file "Cycle 64: was missing" comments proving the drift class let a downloader bypass ESCALATE once. Denial messages leak engineer jargon to a VFX-artist product.

**Engine & HTTP.** Clean abstractions leaking latency at every joint (verified live): full `/object_info` 4.58 MB / 2593 nodes / 4.79 s, uncached at 7 sites; fresh `httpx.Client` ~200–240 ms/call; plus a deterministic circuit-breaker wedge (HALF_OPEN slot consumed by a double-gate → permanent fast-fail until restart) and WS translation gaps. Top movers: pool the client (S), per-node lookups + TTL (S+M), fix the breaker double-gate (S).

**Hot-path patch.** Every mutating tool deep-copies the workflow onto a 50-deep undo deque (0.7 ms / ~6 MB @150 nodes); same state bookkept three times; `jsonpatch.make_patch` on apply/undo/save purely for a count is the most expensive edit op (3–10 ms). `ui_only` conversion confirmed lossy (inputs `{}`, links ignored) — but a complete reconstructor already exists in `ui_api_parser.py:_ui_to_api` (this is a wiring problem, not a build problem). Session eviction is FIFO not LRU → 100 ephemeral connections can evict the artist's live session and wipe their workflow+undo. Bonus: the cognitive delta-stack FIFO at 1000 layers silently reverts the oldest edit — matches the 1000-experiment harness profile.

**MCP server.** Structurally sound (startup ~1.2 s; `_convert_schema` 0.1 ms total; no tracebacks reach the client). Roadmap items elsewhere: a blanket 120 s `wait_for` contradicting tools' own timeouts (renders/downloads routinely exceed it → reported as failure while the orphaned thread keeps working); `stage://` resources advertise a subtree but walk one prim level; `read_resource` does blocking disk I/O on the event loop; the atexit flush races an in-flight autosave on the same unlocked `.tmp`; tool descriptions bimodal (core LLM-ready, stage/NIM periphery jargon-heavy).

**Brain & vision.** Architecture sound (lazy 0.03 s, singleton provider, no locks over I/O). Vision hot path leaks at four points: fresh client per call (~0.29 s), full-res base64 with a 50 MB guard ~10× over API limits (real money on Opus-class models), a prompt-cache that can never hit, and a per-call full re-read of the outcomes JSONL just for a count. Cache keys on a 64-bit aHash ignoring the prompt → stale "before" analyses; missing key surfaces as mislabeled SDK jargon.

**Cognitive library.** In-memory growth well-defended (caps + eviction); SHA-256 a non-issue (4.5 µs/create). Costs all in persistence: full 10.9 MB rewrite/run; no fsync (4 other modules do); nim warm-state read-all-rewrite-append + never prunes 24 h-dead records; `retrieve()` recomputes 10k signatures/call (46 ms); `EXPERIENCE_FILE` defined twice. `agent.*` import boundary holds (grep-verified).

**CLI & harness.** Two roadmap items (P0 #2 prompt gate; compaction tool_result orphan). Below: ollama blocked on an Anthropic key; `THINKING_BUDGET=high` crashes `--help`; `--checkpoint-every-seconds` is a no-op (`checkpoint_every_n=1` makes the modulo always true → full USD flatten+export every iteration); `agent run` never probes ComfyUI at startup; help-text drift. Cold start fine (0.61 s warm). Rate-limit retry gives up after ~7 s with raw provider text.

**Discovery & provisioning.** `discover` serial (~45 s worst case, no result cache, never consults freshness); `download_model` silent + no resume; confirm text omits size/host/dest; `model_compat` pure filename-regex with its own dict (never reads profiles), false positives + unknowns silently pass; `list_models`/`get_models_summary` full `rglob` per call, double `stat()`. The roadmap-changer is the `repair_workflow` wrong-key dead loop (P0 #1).

**Tests & CI.** CI exists (2-OS × 3-Python + ruff + pytest) — "no CI" P0 is false. Three gaps: CI never passes `-m "not integration"` (documented default is fiction, saved by accident); stage layer green-by-skip (usd-core never installed, `test_provisioner.py` hard-ignored); dev runs 3.14, CI tops at 3.12, classifiers advertise 3.13. Real measured tax is **29.86 s collection** dominated by `tests/embedder/test_minilm_clustering.py` importing torch at collection (and doing real HF downloads, unmarked as integration) — NOT the autouse deepcopy. Five shipped modules have zero behavioral tests.

**UI panel** *(dimension-level, unverified — spend cap).* All three bridges mounted simultaneously (verified 200 via GET). Biggest artist-perceived: token streaming wired but never rendered (typing dots for the whole response). Biggest correctness: tab-switch mid-turn truncates/drops the reply. Biggest architecture: a 523-line panel chat backend with no living frontend + ~50 KB dead modules + two independent canvas-sync reporters. Biggest deployment trap: `MCP_AUTH_TOKEN` (the documented hardening step) silently 401s the entire browser canvas bridge (no JS sends a bearer; panel middleware lacks the origin exemption `ui/` has). Raw `str(e)` leaks into chat. `node_pack /agent/*` routes escaped the route-auth audit.

**Measurement.** All 7 ran against the live repo. Headlines: `import agent.tools` ~480 ms warm / ~900 ms cold, ~600 ms of it stage; full `/object_info` 4.58 MB / 4.3–4.9 s vs per-class 3.3 KB / 186 ms (23–26× latency, ~1400× payload); MCP convert / `to_json` / config all healthy; collection 24.2 s cold / 6.9 s warm. Two actionable levers: lazy-load stage (importer side) + a short-TTL `/object_info` cache.

---

*Compiled 2026-06-08 by a verified multi-agent review (`wf_2ba4a767-728`). Read-only; no
source modified. Cross-referenced against `docs/IMPROVEMENT_AREAS_JUNE_2026.md` — findings
here are a distinct class (latency/correctness/usability), not duplicates of that doc's
portability/disclosure/NIM/hygiene items. Adversarial verification partially interrupted by a
spend cap; §3 + §4 are verified, the UI-panel set is not. Brightline-clean — no proprietary
content.*
