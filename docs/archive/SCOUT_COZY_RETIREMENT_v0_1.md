# SCOUT_COZY_RETIREMENT_v0_1.md — Cozy Legacy Store Retirement Surface

**Mission:** `MISSION_COZY_RETIREMENT_v0_1.md` — read-only scout, single concrete question.
**Sibling:** `SCOUT_COZY_v0_1.md` — integration-surface scout that named the six stores.
**Question:** Of the six legacy filesystem stores, which has the smallest retirement surface — i.e., the cheapest to remove from the dual-write path entirely and serve from Moneta alone?
**Constraint reminder:** Locked premises §1–8 of the mission. Read-only. No interface changes to Moneta v1.1.0. No store rewrites. One recommendation only.

---

## [1/13] Re-Anchor on the Six Stores

`[1/13] Re-anchor…`

For working reference, the six stores from §3 of the prior scout, in the same order:

| # | Name | Path | Owner module |
|---|---|---|---|
| 1 | Session state | `sessions/{name}.json` | `agent/memory/session.py` |
| 2 | Outcome history | `sessions/{name}_outcomes.jsonl` | `agent/brain/memory.py` |
| 3 | Experience accumulator | `${COMFYUI_DATABASE}/comfy-cozy-experience.jsonl` | `cognitive/experience/accumulator.py` |
| 4 | USD stage (optional) | `sessions/{name}.usda` | `agent/stage/cognitive_stage.py` |
| 5 | Ratchet history | `sessions/{name}.ratchet.json` | `agent/stage/ratchet.py` (saved via `agent/memory/session.py`) |
| 6 | Experience replay (USD sidecar) | `sessions/{name}.experience.json` | `agent/memory/session.py:save_experience` / `load_experience` |

Two structural facts cut across the table:

- **Stores 1, 2, 6** live in `sessions/`. **Store 3** lives in `${COMFYUI_DATABASE}` (one global file across sessions). **Stores 4, 5** live in `sessions/` but reference USD identity space (`Sdf` layer paths, prim names).
- **Stores 4, 5, 6** are USD-coupled. Without `usd-core`, write-paths are no-ops, read-paths return None/0. The README explicitly notes "most users skip" the USD extra. Premise §8 forbids Moneta interface changes; Moneta v1.1.0 is a vector substrate, not a USD layer host.

These two facts dominate the scoring. Stores 4, 5, 6 don't have a Moneta-shaped destination at all.

---

## §A — The Six Stores Inventoried

### [2/13] Store 1 — Session State (`sessions/{name}.json`)

`[2/13] Store 1…`

**Function.** Per-session JSON blob holding the loaded workflow (path/format/base/current dict, history-depth integer), typed notes (preference/observation/decision/tip with `added_at`), and metadata. Schema-versioned (currently v2, with v0→v1→v2 migration in `_migrate_session`). Atomic writes via tmp-file + `os.fsync` + `shutil.move`.

**Read surface.** `agent/memory/session.py:load_session` is the single-file owner. Callers (production):
- `agent/cli.py:113` — CLI session reload on `--session NAME`.
- `agent/tools/session_tools.py:169` — MCP/panel `load_session` handler.
- `agent/system_prompt.py` (transitively, via session_context dict passed by the CLI).
- `panel/server/chat.py` (via `session_context.get_session_context()`).
- `agent/brain/_sdk.py` and `agent/brain/planner.py`, `agent/brain/memory.py` import from session paths but do not call load_session directly — they use `cfg.sessions_dir`.

**Write surface.** `agent/memory/session.py:save_session` and `:add_note`. Callers:
- `agent/cli.py:174` — atexit/SIGTERM save with `_save_and_exit`.
- `agent/tools/session_tools.py:117` — MCP/panel `save_session` and `add_note` handlers.
- `add_note` is RMW under module-level `_NOTE_LOCK` (RLock) to coordinate with `save_session`.

**Test coverage.** Three primary files plus indirect coverage:
- `tests/test_session.py` — 34 tests, **60 disk-state hits** (`tmp_path`, `read_text`, file-existence, json-content assertions). These tests rewrite `SESSIONS_DIR` to `tmp_path` and validate disk shape.
- `tests/test_session_tools.py` — 20 tests, 15 path/file hits.
- `tests/test_session_context.py` — 26 tests, 0 disk hits (in-memory context behavior).
- Indirect: `test_routes_panels.py`, `test_panel_chat.py`, `test_main.py` exercise the surrounding flow.

**External dependencies.** The `loaded_path` field references user-owned workflow files (anywhere on disk, configurable via `WORKFLOWS_DIR`); restore validates by file existence at reload time. Schema migration v0→v2 implies users have on-disk session files from prior versions — retirement requires a one-shot migrator. The save_session contract surfaces `stage_saved` and `ratchet_saved` flags, coupling Store 1's response shape to Stores 4 and 5.

---

### [3/13] Store 2 — Outcome History (`sessions/{name}_outcomes.jsonl`)

`[3/13] Store 2…`

**Function.** Append-only JSONL ledger of every workflow execution outcome — `timestamp`, `session`, `workflow_summary`, `workflow_hash`, `key_params`, `model_combo`, `render_time_s`, `quality_score`, `vision_notes`, `user_feedback`, `goal_id`. Per-session file naming (`{name}_outcomes.jsonl`). Size-rotated at `OUTCOME_MAX_BYTES = 10 MB` with `OUTCOME_BACKUP_COUNT = 5`. Per-session `threading.Lock` from a `WeakValueDictionary` (`_outcomes_locks`) prevents interleaved writes from `ThreadPoolExecutor` parallel tool dispatch.

**Read surface.** Single owner: `agent/brain/memory.py`. Two read paths:
- `MemoryAgent._load_outcomes(session)` — single-session file read under per-session lock (TOCTOU-safe vs concurrent writes).
- `MemoryAgent._load_all_outcomes()` — globs `*_outcomes.jsonl` across sessions for `scope=global` queries; acquires each per-session lock during read.

Both feed pure-Python aggregation helpers (`_best_model_combos`, `_optimal_params`, `_speed_analysis`, `_quality_trends`, `_avoid_negative_patterns`, `_workflow_context_recommendations`, `_detect_reuse`, `_detect_abandonment`, `_detect_refinement_bursts`, `_detect_parameter_regression`) that operate over the loaded `list[dict]`.

**Write surface.** Single owner: `MemoryAgent._append_outcome(session, outcome)`. Called only from `_handle_record_outcome` (the `record_outcome` brain tool). The brain tool itself is invoked by the agent loop on the model's discretion (post-execution, post-vision-analyze).

**Test coverage.** `tests/test_brain_memory.py` — **70 tests**. Disk-state density: 20 hits on `_outcomes_path`, JSONL globbing, rotation backup checks, file-existence assertions. The rotation tests (`test_rotation_creates_backup`, `test_rotation_oserror_is_logged`) explicitly assert the on-disk file shape and backup ladder. The aggregation tests (`_best_model_combos`, `_optimal_params`, `_speed_analysis`, etc.) operate on lists and are disk-blind once `_load_outcomes` returns.

**External dependencies.** No external consumers. Path discipline is self-contained: `cfg.sessions_dir / f"{session}_outcomes.jsonl"`. Rotation backups (`*.jsonl.1` … `*.jsonl.5`) are an internal-only convention.

---

### [4/13] Store 3 — Experience Accumulator (`${COMFYUI_DATABASE}/comfy-cozy-experience.jsonl`)

`[4/13] Store 3…`

**Function.** Cross-session JSONL ledger of `ExperienceChunk` objects — `parameters`, `checkpoint`, `model_family`, `prompt`, `QualityScore` (technical/aesthetic/prompt_adherence/overall, `is_scored`, `source`), `decay_weight`, `timestamp`, `output_filenames`. Cap of `max_chunks=10000` with eviction of the lowest-quality (oldest-on-tie) entry. Atomic save via `.tmp + os.replace`, single module-level `_save_lock` against concurrent saves. **One global file across all sessions** — explicitly the cross-session learning store advertised in the README ("After 30+ runs, the agent starts using your personal history to bias parameter selection").

**Read surface.** Two production callers, plus pipeline-internal usage:
- `cognitive/pipeline/__init__.py:31` — `create_default_pipeline()` calls `ExperienceAccumulator.load(EXPERIENCE_FILE)` once at construction.
- `panel/server/routes.py:412` — `/comfy-cozy/experience` GET endpoint loads to surface stats (read-only).
- Internally within `cognitive/pipeline/autonomous.py`: `_get_experience_patterns` calls `accumulator.retrieve(sig, top_k=5, min_similarity=0.0)` during COMPOSE; `_get_avg_experience_quality` calls `get_successful_chunks`.

**Write surface.** A single production call:
- `cognitive/pipeline/autonomous.py:527` — `self._accumulator.record(chunk)` inside the LEARN stage of `_run_locked`, wrapped in try/except (failure is non-fatal; logged and continues).
- `cognitive/pipeline/autonomous.py:536` — `self._accumulator.save(str(EXPERIENCE_FILE))` immediately after, also non-fatal on failure.

**Test coverage.** Three test files plus pipeline interplay:
- `tests/test_cognitive_experience.py` — 42 tests. ~10 hits on `tmp_path` / `.jsonl` (the `save_load_round_trip`, `corrupt_jsonl_line_is_skipped`, `partial_chunk_data_is_skipped_with_warning` cluster). The remaining ~32 tests cover learning phases (PRIOR/BLENDED/EXPERIENCED), `experience_weight` ramp, `retrieve` with similarity thresholds, `get_stats`, `record` cap-eviction logic — all in-memory, disk-blind.
- `tests/test_experience.py` — 46 tests. 0 disk hits in the grep — pure ExperienceChunk + QualityScore + signature behavior tests.
- `tests/test_workflow_signature.py` — 57 tests. 0 disk hits — `GenerationContextSignature.from_workflow` and `.similarity` semantics.
- `tests/test_cognitive_pipeline.py` — 30+ tests inject `accumulator=ExperienceAccumulator()` as a constructor dependency; disk is never touched. Assertions are on `pipeline._accumulator.generation_count`, `learning_phase`, `experience_weight`.

**External dependencies.** Path is `${COMFYUI_DATABASE}/comfy-cozy-experience.jsonl` — `COMFYUI_DATABASE` is a user-config env var with cross-platform default of `~/ComfyUI`. The CHANGELOG flags experience-persistence ("Experience persists across sessions — crash-safe") as a marketed feature; the README explicitly cites it. No downstream tools consume the file.

---

### [5/13] Store 4 — USD Stage (`sessions/{name}.usda`)

`[5/13] Store 4…`

**Function.** USD scene — `/cognitive_state/`, `/experience/`, `/predictions/`, `/foresight/` prims, model registry, ratchet metadata, scene composition. Flat `.usda` file written via `pxr.Usd` API. Optional: requires `usd-core` extra (~200MB).

**Read surface.** `agent/memory/session.py:load_stage` plus a wide subsystem:
- `agent/cli.py` — orchestrate command checks `HAS_USD` and calls `compose_scene` if available.
- `agent/session_context.py:ensure_stage()` — lazy initializer per session.
- `agent/stage/autoresearch_runner.py`, `compositor.py`, `counterfactuals.py`, `creative_profiles.py`, `cwm.py`, `experience.py`, `foresight_tools.py`, `injection.py` — every stage subsystem reads/writes prims directly via the Usd API.
- `agent/stage/morning_report.py` — formats stage state for end-of-session output.

**Write surface.** Same subsystem. Save is via `stage.flush(path)` from `agent/memory/session.py:save_stage`, called from `_handle_save_session`. Live mutations during a session happen in-memory on the `Usd.Stage` object before being flushed.

**Test coverage.** Hundreds of tests across the stage layer:
- `tests/test_cognitive_stage.py` — 63 tests.
- `tests/test_stage_tools.py` — 72 tests.
- `tests/test_session_stage.py` — 19 tests.
- `tests/test_stage_session_isolation.py` — 6 tests.
- Plus `test_compositor*.py`, `test_foresight_*.py`, `test_hyperagent*.py`, `test_provisioner.py` (currently 27 errors in the default no-USD env per prior scout), `test_creative_profiles.py`, `test_cwm_*.py`, `test_counterfactuals.py`, `test_morning_report.py`, `test_scene_*.py`. Conservative tally: **300+ tests** depend on the stage subsystem.

**External dependencies.** The USD format itself is a public contract — `.usda` files are openable by Houdini, USDView, Nuke, omniverse-class tools. The CHANGELOG and architecture docs cite USD-native composition as a value-prop. `pxr` is the bound dependency — Moneta's vector-store API has no analog for `Sdf.Layer` or `Usd.Prim`.

---

### [6/13] Store 5 — Ratchet History (`sessions/{name}.ratchet.json`)

`[6/13] Store 5…`

**Function.** Ratchet decision history — keep/discard binary calls on USD sublayers across configurable axes (aesthetic, depth, normals, camera, segmentation, lighting). Each `RatchetDecision` carries `delta_id`, `kept`, `axis_scores`, `composite`, `timestamp`, plus optional `predicted_scores` / `prediction_accuracy` / `arbiter_mode` from the FORESIGHT integration. The persisted JSON includes `threshold`, `weights`, and the decision history (capped at `_MAX_RATCHET_HISTORY = 10000` with FIFO eviction).

**Read surface.**
- `agent/memory/session.py:load_ratchet` — JSON read, replays `_history`.
- `agent/tools/session_tools.py:199` — load_session handler invokes load_ratchet, attaches result to session_context.
- `agent/stage/morning_report.py` — renders ratchet decisions for end-of-session report.

**Write surface.**
- `agent/memory/session.py:save_ratchet` — JSON write under `_atomic_write`.
- `agent/tools/session_tools.py:154` — save_session handler invokes save_ratchet only if `ctx.ratchet is not None and ctx.ratchet.history`.

**Test coverage.** `tests/test_ratchet.py` — **105 tests** (the densest test file for any single store). The bulk test in-memory `Ratchet` class behavior (axis scoring, composite computation, threshold logic, FORESIGHT-integration paths, weight rebalancing). Disk-state assertions exist but are a minority — the persistence is exercised as a round-trip property, not the focus. Adjacent: `test_session.py` round-trips touch the save/load functions; `test_morning_report.py` reads ratchet state.

**External dependencies.** `delta_id` strings are USD `Sdf.Layer` identifiers — they reference USD-namespace identity. Without USD, ratchet decisions still persist as JSON, but the IDs are dangling. `morning_report.py` is a downstream artifact that reads ratchet history. CHANGELOG mentions ratchet-driven evolution as a feature.

---

### [7/13] Store 6 — Experience Replay (USD sidecar JSON, `sessions/{name}.experience.json`)

`[7/13] Store 6…`

**Function.** Lightweight JSON dump of the USD `/experience/` prims — `experiences: [...]` plus `count`. Each record carries `initial_state`, `decisions`, `outcome`, `context_signature_hash`, `predicted_outcome`, `timestamp`. Designed as a fast-load cache that replays into a fresh `CognitiveWorkflowStage` via `record_experience` so the agent can warm up without re-reading USD.

**Read surface.** **One function:** `agent/memory/session.py:load_experience(name, stage)` — returns `0` if `usd-core` is not installed (`from ..stage import HAS_USD` check). Calls `record_experience(stage, ...)` to replay each entry.

**Write surface.** **One function:** `agent/memory/session.py:save_experience(name, stage)` — calls `query_experience(stage, limit=10000)` from the USD layer and serializes to JSON.

**Wiring status — load-bearing finding.**
- `agent/tools/session_tools.py:11-14` imports `save_session, load_session, list_sessions, add_note, restore_workflow_state, save_stage, load_stage, save_ratchet, load_ratchet, _validate_session_name`. **`save_experience` and `load_experience` are NOT imported.**
- `_handle_save_session` calls `save_stage(name, ctx.stage)` and `save_ratchet(name, ctx.ratchet)`. **It does NOT call save_experience.**
- `_handle_load_session` mirrors the same omission.
- `cognitive/pipeline/autonomous.py` references `EXPERIENCE_FILE` (Store 3, the global accumulator) — *not* Store 6.
- `agent/stage/autoresearch_runner.py`, `agent/stage/foresight_tools.py`, no other production module references `save_experience` or `load_experience`.

**Store 6 has zero production callers.** It exists, has tests, but is not wired into any session-save/load flow that an artist or agent loop traverses. The only consumers in the entire repo are 5 test methods in `tests/test_foresight_session.py`, all of which are USD-gated by `pytest.importorskip("pxr")` — skipped in the default no-USD installation that the README documents.

**Test coverage.** `tests/test_foresight_session.py` — 17 tests total in the file, of which **5 dedicated to save_experience/load_experience** (`test_save_experience`, `test_load_experience`, `test_load_nonexistent`, `test_save_empty_stage`, `test_roundtrip_preserves_signature_hash`). All five `pytest.importorskip("pxr")`. Each patches `_sessions_dir` to `tmp_path`. Assertions: `result["count"]`, `query_experience(fresh)` round-trip equality.

**External dependencies.** None. The data shape is USD-prim-derived; the `.experience.json` is a serialization sidecar, not a contract surface.

---

## §B — Retirement Surface Scoring

### [8/13] Scoring Rubric & Table

`[8/13] Scoring rubric…`

Five dimensions, 1 (small/easy) to 5 (large/hard). Lowest total = smallest retirement surface.

| # | Store | 1. Read | 2. Write | 3. Test blast | 4. Moneta-replaceability | 5. External drag | **Total** |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | Session state | 4 | 3 | 4 | 3 | 3 | **17** |
| 2 | Outcome history | 2 | 2 | 4 | 2 | 1 | **11** |
| 3 | Experience accumulator | 2 | 1 | 2 | 1* | 2 | **8** |
| 4 | USD stage | 5 | 5 | 5 | 5 | 5 | **25** |
| 5 | Ratchet history | 3 | 2 | 4 | 4 | 3 | **16** |
| 6 | Experience replay (USD sidecar) | 1 | 1 | 1 | 4† | 1 | **8** |

*Score 1 reflects the interface fit with Moneta's vector-store shape; the asterisk flags a structural conflict against locked premise §1 (per-session handle ownership) — see §C.

†Score 4 reflects that Moneta v1.1.0 is structurally wrong for a USD prim-cache. The sidecar serializes USD identity references that have no meaning outside USD; substrate.write would store an opaque blob with no retrieval value-add. The technical `1` for read/write/test blast is real; the strategic `4` for replaceability is the pressure-valve calling.

### [9/13] Per-Store Scoring Notes

`[9/13] Scoring notes…`

**Store 1 = 17.** Read sites span CLI, MCP server, panel server, system-prompt builder. Write sites are narrower (cli atexit, session_tools handler) but include RMW under `_NOTE_LOCK` that has TOCTOU semantics across both `add_note` and `save_session`. Test blast is large because `test_session.py` is disk-state-heavy (60 hits) — assertion shape change (substrate calls vs `read_text`) will rewrite most of the file. Schema-migration v0→v2 implies installed-base baggage. Moneta replaceability is workable for the blob shape but the substrate has to honor or absorb the RMW + migration semantics.

**Store 2 = 11.** Read/write sites are minimal — single class (`MemoryAgent`) owns the access boundary. Aggregation is consumer-side, so once `_load_outcomes` returns the same shape, downstream is unchanged. Test blast is the larger drag: `test_brain_memory.py` has 70 tests, ~30 of which include disk-state assertions (rotation, fsync, file-size triggers, backup-ladder semantics). Moneta-replaceability is decent — `embedding=None` plus per-session namespacing maps cleanly; the size-based rotation has no Moneta analog (subscribers must accept either substrate-side TTL/eviction or Cozy-side trim-on-write).

**Store 3 = 8 (numerically smallest, with one footnote).** Read/write surface is genuinely tiny — three call sites total (one in `cognitive/pipeline/__init__.py`, one in `cognitive/pipeline/autonomous.py:_run_locked`, one in `panel/server/routes.py`). Pipeline tests inject the accumulator (no disk involvement) — only the dedicated `test_cognitive_experience.py` round-trip cluster (~10 tests) and possibly 2-3 in `test_e2e_pipeline.py` need rewriting. The interface fit with Moneta is the cleanest of all six (vector retrieval is what Moneta does). **The footnote: locked premise §1 forces a behavior change** — the global cross-session experience pool becomes per-session, contradicting the README's "uses your personal history" framing. Detailed in §C.

**Store 4 = 25.** Maximum on every axis. Subsystem-wide reads/writes; 300+ tests; USD format is a public contract; Moneta's vector-store API has no analog for USD scene composition. Not a retirement candidate — would be a rewrite, forbidden by the mission.

**Store 5 = 16.** Test blast is high (105 tests, the densest in the repo) but mostly behavioral, not disk-bound. The drag comes from `delta_id` referring to USD identity space — retiring the JSON without retiring USD means substrate stores keys that point into a system Cozy still depends on. Moneta-replaceability is mediocre (data is shape-compatible, identity is not).

**Store 6 = 8 (numerically tied with Store 3).** Mechanically the smallest possible: one read function, one write function, five tests, all USD-gated. But the candidate is essentially orphan code — no session-save flow calls it, only test_foresight_session.py exercises it directly. Putting the USD-prim cache in Moneta is a category error (substrate's value-add is vector retrieval; this store is a flat blob of USD-derived dicts). The pressure-valve clause from the mission applies: technically smallest, strategically pointless.

---

## §C — The Recommendation

### [10/13] Named Store: Store 3 (Experience Accumulator)

`[10/13] Recommendation…`

**Recommend retiring Store 3** (`${COMFYUI_DATABASE}/comfy-cozy-experience.jsonl`, owner `cognitive/experience/accumulator.py`) as the demo-phase first plank.

**Why this beats the tied Store 6.** The mission's tie-breaker rule: "the one whose deprecation tells the cleanest substrate-vs-product story to a viewer of the demo." Store 3 is the literal embodiment of *retrieval-by-similarity over generated outputs* — the workload Moneta exists to serve. Retiring Store 3 demonstrates substrate replacement of the canonical workload. Store 6 is a USD prim-cache with no production callers; retiring it is invisible to a demo viewer because no demo path traverses it. Pressure-valve: Store 6 is technically smallest *and strategically weakest*. Don't retire it. Don't pretend it counts.

**Why this beats Stores 1, 2, 5.**
- vs. **Store 2 (11):** Store 2's test surface is 4× larger by disk-state assertion density, and its Moneta fit is worse (`embedding=None` underutilizes the substrate; the rotation+backup semantics need a Cozy-side replacement when the JSONL goes away). Store 2 is the *next-cheapest* retirement and is the right second-plank candidate after Store 3 lands — but for the demo, Store 3's story is sharper.
- vs. **Store 1 (17):** session JSON is widely read, RMW with TOCTOU, schema-versioned, and user-facing. Bigger surface, narrower upside.
- vs. **Store 5 (16):** ratchet decisions reference USD layer paths; retiring the JSON without retiring the USD identity space leaks structural debt into Moneta.

### [11/13] Effort, Sequencing, Test Changes, Premise Conflicts

`[11/13] Effort breakdown…`

**Estimated retirement effort:** **2–3 senior eng days**, on top of the integration envelope.

Breakdown:
- **0.5d** — Add `ensure_moneta_experience()` factory to `agent/session_context.py` (or pass a substrate handle into `cognitive/pipeline/__init__.py:create_default_pipeline()`).
- **0.5d** — Reimplement `ExperienceAccumulator.{record, retrieve, save, load, get_successful_chunks, get_stats}` against the substrate behind the same class API. Keep `experience_weight` / `learning_phase` properties as derived state from a substrate-side count.
- **0.5d** — Rewrite the disk round-trip cluster in `tests/test_cognitive_experience.py` (~10 tests) to mock the substrate. The remaining ~32 tests test signature similarity, learning phases, retrieval scoring, and `record` cap-eviction — they continue to operate against the in-memory class wrapper.
- **0.5d** — Update `cognitive/pipeline/__init__.py:31` and `panel/server/routes.py:412` to construct/consume the substrate-backed accumulator. Update the integration tests that load `EXPERIENCE_FILE` directly.
- **0.5d** — Sweep: retire `EXPERIENCE_FILE` constant from `agent/config.py:149` and `cognitive/pipeline/autonomous.py:38-41`. Update the README's "Experience persists across sessions — crash-safe" line to narrate the substrate replacement honestly. Update the CHANGELOG.

**Sequencing.** Can run **in parallel** with the Cozy × Moneta integration work, *provided the per-session Moneta-handle infrastructure lands first*. Concretely: the integration's day 1–3 (handle ownership site in `agent/session_context.py`, single-substrate connection lifecycle) is a hard prerequisite. Days 4–6 of the integration overlap cleanly with this retirement work — same files (`agent/session_context.py`, `cognitive/pipeline/__init__.py`), shared substrate plumbing, no test-cutover collisions because the test files are different (Store 2's test_brain_memory.py vs Store 3's test_cognitive_experience.py). Total wall-clock additional: ~1 day, not 2-3, if parallelized inside the 8–13 day envelope.

**Specific test changes.**
- **Rewrite (substrate-mock):** `tests/test_cognitive_experience.py::TestSaveLoad::test_save_load_round_trip`, `test_load_nonexistent_file`, `test_corrupt_jsonl_line_is_skipped`, `test_partial_chunk_data_is_skipped_with_warning`, plus 4–6 disk-round-trip variants — **~10 tests**.
- **Possibly touch:** `tests/test_e2e_pipeline.py` (1–3 tests, depending on whether they exercise `EXPERIENCE_FILE` directly — grep showed no hits, so likely zero).
- **Unchanged:** `tests/test_experience.py` (46 tests, no disk hits), `tests/test_workflow_signature.py` (57 tests, no disk hits), `tests/test_cognitive_pipeline.py` (30+ tests inject the accumulator).
- **Quarantine:** none required.

**Locked-premise conflicts — surfaced honestly, per the mission's pessimism mandate.**

> **Locked premise §1 (per-session Moneta-handle ownership) materially conflicts with Store 3's existing global semantics.** The current `comfy-cozy-experience.jsonl` is **one file across all sessions** in a Cozy installation. The accumulator's "After 30+ runs, the agent starts using your personal history" property — explicitly marketed in the README and CHANGELOG — depends on cross-session pooling. Per-session Moneta handles, with `MonetaResourceLockedError` on shared `storage_uri`, force one of three options:
>
> (a) **Per-session experience pools** — each session has its own substrate URI; cross-session learning is gone. README claim becomes false. Demo viewer who reads marketing copy notices.
> (b) **Cross-session URI namespacing** — `moneta://global-experience/session/{name}` with substrate-side traversal at retrieval time. **Moneta v1.1.0 is fixed (premise §8)** — if the substrate doesn't expose namespace traversal, this option is unavailable. Open Question §E lists this.
> (c) **Demo-narration accommodation** — accept (a), explicitly narrate "session-scoped memory in v0.1, cross-session pooling tracked for v0.2." Honest, downgrades a marketed feature.

The smallest-surface retirement candidate is the one whose retirement is most likely to *visibly change behavior* — because the substrate's design constraint (per-session handles) and the store's design intent (cross-session pool) are misaligned. False optimism would say "Store 3's interface fit is perfect, retire it." Honest pessimism says: it's perfect *if* you accept (a) or (c) above. (b) requires confirming Moneta v1.1.0 capability that this scout cannot verify.

---

## §D — The Honest Alternatives

### [12/13] Tied Stores, Ranked Substitutes, and the Option-2 Fallback

`[12/13] Honest alternatives…`

**Tied stores at 8 — Stores 3 and 6.** Per mission tie-breaker, recommended Store 3 as above for strategic legibility. Store 6 retirement is *not* recommended for three reasons:

1. **No production wiring.** `_handle_save_session` and `_handle_load_session` do not call `save_experience` / `load_experience`. The store exists only for the test_foresight_session integration suite. Retiring it from disk to substrate is invisible to every Cozy production code path. A demo viewer sees nothing.
2. **Wrong substrate shape.** Moneta's value is vector retrieval over high-dimensional embeddings. Store 6 is a flat dump of USD-prim attributes (`initial_state`, `decisions`, `outcome`, `context_signature_hash`). Putting it in Moneta means using a vector store as a key-value cache. The substrate doesn't earn its keep on this workload.
3. **Strategic-weakness pressure-valve fires.** Mission §"Pressure Valve": "The retirement candidate is technically smallest but strategically weakest — i.e., retiring it doesn't visibly demonstrate substrate replacement to a viewer of the demo. Name the trade." Store 6 is exactly that case. Naming it: retiring Store 6 is "deleting orphan code with extra steps" — better handled outside this mission as housekeeping, not as the substrate-bridge first plank.

**Second-cheapest after Store 3 — Store 2.** If the §C premise §1 conflict over Store 3 is unacceptable, Store 2 is the live alternative:

- **Score 11.** Single-class read/write boundary, per-session file naming already aligns with per-session Moneta handle. Aggregations stay consumer-side. No global-pooling claim to re-narrate.
- **Effort:** 3–4 senior eng days. Test blast is 4× Store 3's by disk-state hits (~30 of `test_brain_memory.py`'s 70 need rewrites), plus rotation+backup semantics need a Cozy-side replacement (since substrate.write doesn't have a built-in size-rotate analog under premise §8).
- **Sequence:** sequential, not parallel, with the integration envelope's brain-memory work — same module under edit.

**Recommended fallback if neither Store 3 nor Store 2 is achievable inside the demo cut:** **Option 2 from the mission** — annotate + temporal scoping. Two timing buckets in the benchmark output (substrate latency vs. dual-write tax), README §"Phase 1 / Phase 2" framing with a target date for legacy-store deprecation. Forward-looking narratively without lying. The mission's three-option ladder is honest: Option 2 is real, Option 3 is achievable for Store 3 with a documented behavior change.

**Stores explicitly NOT recommended for retirement.**
- **Store 1** — too widely coupled, schema-migration drag, user-facing system_prompt feed.
- **Store 4** — USD subsystem; rewrite-not-retire; forbidden by mission scope.
- **Store 5** — USD-identity-space coupling; partial retirement leaks debt.
- **Store 6** — strategically weakest despite numerical smallest tie; orphan code.

---

## §E — Open Questions

### [13/13] Open Questions for the Integration Design Pass

`[13/13] Open questions…`

Same shape and rigor as the prior scout's §B, scoped to retirement specifically.

**Substrate capability**
- Does Moneta v1.1.0 expose any cross-namespace traversal (option (b) in §C)? If yes, Store 3 retirement honors the README's cross-session pooling without a behavior change. If no, retirement requires accepting per-session scoping (option (a)) or explicit demo narration (option (c)). This single question gates the recommendation's confidence interval.
- Does Moneta v1.1.0 support any size-bounded eviction or TTL? Stores 2 and 3 today have explicit caps (`OUTCOME_MAX_BYTES`, `ExperienceAccumulator.max_chunks=10000` with lowest-quality eviction). Substrate-side eviction simplifies retirement; consumer-side eviction means Cozy keeps trimming logic on `record()` paths.
- Does Moneta v1.1.0 expose atomic compare-and-swap or a transaction primitive? Store 1's `add_note` RMW under `_NOTE_LOCK` and `save_session`'s lock acquisition pattern need a substrate analog. (Out of scope for the Store 3 recommendation, but if Store 2 becomes the fallback, this matters.)

**Lifecycle & sequencing**
- Where in the 8–13 day envelope does the per-session Moneta-handle infrastructure (the prerequisite for parallel Store 3 retirement) actually land? If it lands on day 7+, the parallel-overlap optimism in §C collapses and the retirement sequences after the integration cut, pushing total wall-clock to days 14–16.
- The pipeline's `accumulator.record(chunk)` is wrapped in a try/except that swallows failures non-fatally (`autonomous.py:530-532`). When the underlying call becomes a network/IPC substrate write, is silent failure still acceptable, or does the retirement need to surface substrate errors more visibly? (The mission forbids interface changes; this is a Cozy-side error-handling decision.)

**Test cutover**
- Should the substrate be mocked in `tests/test_cognitive_experience.py` against an in-memory fake `Moneta`, or against a real local-temporary substrate URI? The prior scout flagged this question generally; for Store 3 specifically, the disk-round-trip tests (`test_save_load_round_trip`, `test_corrupt_jsonl_line_is_skipped`) were *testing the JSONL-corruption recovery property*. If JSONL goes away, those tests are obsolete — but the property they test (substrate-side data corruption tolerance) becomes a Moneta-side test, not a Cozy-side test. Retire the tests, or migrate them to the substrate's test surface?
- Will `pytest -m "not integration"` continue to skip-clean if Moneta is not installed in the dev environment? The integration-test fence currently catches ComfyUI; a similar fence for substrate-availability needs to be added — minor but explicit.

**README + CHANGELOG hygiene**
- The README's "Experience persists across sessions — crash-safe" claim and the CHANGELOG's "Experience persists across sessions" Unreleased entry both predate the Moneta direction. After Store 3 retirement, both need rewording — to what shape? "Experience persists in your session's substrate" (option (a)) reads like a downgrade to existing users. Naming this messaging shift is the demo-narration scope of §C option (c).
- The autonomous-mode doc block in the README explicitly cites `experience.jsonl` as the persistence file. Post-retirement, that filename no longer exists. README-edit scope is non-trivial — call it 0.5d that's currently included in the 2–3d effort estimate, but flag for visibility.

**Strategic legibility**
- Is the *actual demo path* in v0.1 the autonomous pipeline (`pipeline.run(intent)`) or the conversational CLI/MCP loop? The prior scout's "It remembered" demo lives in the conversational loop, fed by `system_prompt.py:225-247` recommendations from `MemoryAgent.get_recommendations()` (Store 2). **If the demo is conversational, retiring Store 3 is invisible to the viewer — Store 3 only powers the autonomous pipeline, which Mike may or may not see.** This is the highest-stakes open question. If the demo is autonomous, Store 3's retirement is maximally visible. If conversational, Store 2's retirement is maximally visible despite its larger surface — that flips the recommendation.

---

## Bottom Line

The numerically smallest retirement surface is **Store 3 (Experience accumulator)**, tied at 8 with **Store 6 (Experience replay USD sidecar)**. The tie-breaker — strategic legibility of substrate replacement — favors Store 3 unambiguously: Store 6 is orphan code with no production callers, the wrong shape for Moneta's vector-retrieval value-add, and invisible to any demo viewer. Store 3 is the canonical retrieval workload Moneta exists to serve, the one whose retirement most cleanly tells the substrate-replacement story, and whose test surface (~10 disk-bound tests in `test_cognitive_experience.py` out of ~145 total experience-related tests) is genuinely modest. **Honest pessimism caveat:** locked premise §1 (per-session Moneta-handle ownership) materially conflicts with Store 3's marketed cross-session pooling. The retirement carries either a documented behavior change (option (a) in §C — per-session experience scoping) or it depends on a Moneta v1.1.0 capability the scout cannot verify (option (b) — cross-namespace traversal). If the demo is the conversational loop rather than the autonomous pipeline, Store 3's retirement is invisible to the viewer and Store 2 becomes the legibility winner despite its larger test surface. **If neither path is acceptable inside the 8–13 day cut, fall back to mission Option 2** (annotate + temporal scoping, Phase 1 / Phase 2 framing) without apology. Option 2 is real; Option 3 for Store 3 is achievable but not free. The single most important pre-design clarification: confirm with Moneta v1.1.0 whether cross-namespace traversal exists, and confirm with the demo plan whether the viewer sees the autonomous pipeline at all.

---

*Scout pass complete. No code modified. No test runs that mutated state. Thirteen marathon markers cleared.*
