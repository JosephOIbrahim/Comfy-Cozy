# CHAMPION.md — per-track best *verified* state

> Promote only on a passed predicate. Replicate stochastic gains (#5 timing, #9 vision) on a
> fresh run before promoting (noise-aware).

## Track 1 — Tool Layer  ✅ COMPLETE (P1.1 + P1.2 both committed)
- **Seed (the bar = current pain):** verbose ~3,500-tok introspection responses; "rewrite the
  whole graph" for any edit.
- **P1.2 ✅ PASSED — committed `d4e922a`:** graph surgery `delete_node` / `replace_node` /
  `rewire_around` in `workflow_patch.py`. Delete removes node + all incident links (no dangling);
  replace keeps node id (incoming links intact) + rename map; rewire bridges single-upstream
  passthrough, drops+reports zero/multi-upstream (honest — no slot-type guess offline). Reversible
  via existing undo. Registry 113→116 (+3 count-contract test fixes folded in). +17
  TestGraphSurgery; full suite **4369 passed, 1 failed** (the failure is the pre-existing
  Windows-only `test_cozy_persistence` SIGKILL issue — unrelated).
- **Current champion (P1.1 ✅ PASSED — committed `234e2bc`):**
  `get_node_info` `detail` tier (`summary` default / `signature` / `full`). KSampler live: full
  ~2853 B (~713 tok) → **summary ~341 B (~85 tok), ~8.4×**; signature ~366 B (≤1KB budget).
  Required inputs **never dropped** at any tier (emitted as ordered lists → also preserves true
  widget order). Code: `comfy_api.py:293 _spec_type`, `:304 _node_info_tier`, `:356` default,
  `:380` full-branch + schema. Sole runtime consumer pinned to `detail='full'`:
  `iterative_refine.py:739`.
  Verified: L0 ruff/imports ✓ · L1 live tiers ✓ · L3 fidelity (heaviest node *LoRA Stacker*, 202
  required, all kept) ✓ · hostile (invalid detail→summary, empty/not-found errors) ✓ · comfy_api
  39✓ · **regression: full mocked suite 4352 passed / 2 skipped / 40 deselected, 1 failed**. The
  lone failure (`test_cozy_persistence.py::test_kill_after_flush_resumes_cleanly`) is **pre-existing
  & unrelated** — proven: fails identically with these 3 files git-stashed out. Files (3):
  `comfy_api.py`, `brain/iterative_refine.py`, `tests/test_comfy_api.py`.
- **Next leg:** P1.2 `#6` surgery (delete/replace/rewire) on `workflow_patch.py`.

## Track 2 — Bridge → WS  ✅ COMMITTED `f16b5e5` (INTEGRATE 4409✓ / 1 pre-existing fail · STRESS✓)
- **Seed:** the Phase-0 push bridge is its own seed; read-back/profiling/watcher extend it.
- **P2.1 #1 push** — Home A `comfy_agent_bridge` (POST /agent/push_workflow → send_sync; web JS loads
  + tags `__agentLoad`); Home B `push_workflow_to_canvas` (path-safe, 404/timeout/connect clean).
- **P2.2 #1 read-back** — PULL: FE debounced onAfterChange→POST /agent/canvas_changed (buffered);
  agent `get_canvas_state` GET; loop-prevented via `__agentLoad`.
- **P2.3 #5** — `get_execution_profile` DURATION-ONLY (vram gate); ordered, cached not flagged,
  regression vs baseline. **LIVE-CONFIRMED 2026-05-31** against a real LTX-2 t2v render
  (prompt_id 7b8a97ee…): node-pack observer captured **41 nodes with real per-node duration_ms**
  (e.g. 267:236=1050ms, 267:221=366ms), enriched via the agent tool (node_count=41, total_ms growing
  as the render proceeds), `vram: "unavailable (not in WS stream)"` exactly as designed. End-to-end
  proven on real hardware — not just unit-mocked.
- **P2.4 #8** — `watch_outputs_begin/diff` snapshot-diff (no watchdog dep); catches off-output writes
  when root watched; no false-positive.

## Track 3 — Comprehension  ✅ COMMITTED `f16b5e5`
- **Seed:** "re-export in browser" / "give me the path".
- **P3.1 #2** — `parse_ui_workflow`: schema-order mapping via raw /object_info (NOT positional);
  seed+control_after_generate handled; unmappable nodes surfaced not guessed.
- **P3.2 #7** — `list_assets`: input/+outputs scan, search, recent cap, pHash dedup (reuses vision
  aHash — no new dep).

## Track 4 — Gated / Dependent  ✅ COMMITTED `f16b5e5` (#9,#10) · 🛑 #3 HALT (falsified)
- **Seed:** blind renders; re-analyze every image; cosmetic memory.
- **P4.1 #3** — HALT: agent-facing streaming previews are dead code (binary WS frames; stdio MCP
  agent can't consume mid-tool-call). Built nothing. (DEADENDS.)
- **P4.2 #9** — `analyze_image_cached`: pHash cache (hamming≤2), boundary-safe (5-bit→miss),
  eviction, delegates miss to analyze_image.
- **P4.3 #10** — `surface_relevant_memory`: class_type-overlap+recency scorer, irrelevant→nothing
  injected, budget-capped (#4 invariant).
