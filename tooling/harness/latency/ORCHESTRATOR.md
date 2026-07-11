# LATENCY PASS — ORCHESTRATOR

Boot document for running one latency-and-refinement pass. Constitution:
`tooling/harness/latency/CONSTITUTION.md` (binding). First pass ran 2026-07-11
(offline regime, ComfyUI down); results in `docs/LATENCY_MAP.md` and
`tooling/bench/benchmark_log.jsonl`.

## The loop

```
SCOUT (agent team, read-only, adversarially verified)
  └─ 5 layer censuses (dispatch · coldstart · instrumentation · surface ·
     repeat-work) + prior-art miner → ranked hypotheses, each tagged
     offline-now / needs-live-comfyui / needs-real-llm
MEASURE (tooling/bench — the only source of numbers)
  └─ .venv312/Scripts/python.exe tooling/bench/bench_offline.py --all --mode baseline
ADJUDICATE (conductor)
  └─ a hypothesis the bench refutes PARKS with its curve as evidence;
     only measured, low-risk refinements forge
FORGE (agent team, disjoint file ownership, no git authority)
RATCHET (conductor)
  └─ bench --mode champion + full suite; >2 % regression on any tracked
     scenario reverts (Article III)
SCRIBE
  └─ LATENCY_MAP update, atomic commits, benchmark_log entries
```

## Scenario registry (bench_offline.py)

| # | Scenario | Regime | Status |
|---|----------|--------|--------|
| B1 | edit-path per-call cost vs workflow size + within-sequence growth | offline | run 2026-07-11 |
| B2 | apply_recipe wall-clock vs history depth | offline | run 2026-07-11 |
| B3 | dispatch floor (gate bypassed vs included; observation on/off) | offline | run 2026-07-11 |
| B4 | cold import per boot stage | offline | run 2026-07-11 |
| B5 | boot→initialize→tools/list→ping handshake, refused + blackhole | offline | run 2026-07-11 |
| B7 | metrics/health cost vs observation count | offline | run 2026-07-11 |
| B6 | fs-walk storms (models tree scans, lock-sidecar rglob) | offline | designed, not run |
| B8 | L1 round-trip count: recipe vs LLM-mediated edit | offline | designed, not run |
| L-1 | six blueprint scenarios end-to-end (recipe edit · LLM edit · validate→run · intent→image · model swap · cold start), cold + warm | **needs live ComfyUI** | deferred — run with ComfyUI on :8188 |
| L-2 | L2 schema tax: parity-vs-full profile prompt-size + turn-latency delta | **needs real LLM host** | deferred — pairs with WP-2.2 |

Live-run procedure (when ComfyUI is up): start ComfyUI, verify
`http://127.0.0.1:8188/system_stats`, then extend `bench_offline.py` with the
L-1 scenarios using the `_Blackhole`-style timers against the real endpoint —
vary the seed per run (prompt-cache trap) and poll `/history/{prompt_id}` for
completion (ws detection is unreliable — see prior-art DEADENDS in
`harness/DEADENDS.md`).

## Standing DEADENDS (do not re-litigate without new evidence)

Measured and parked 2026-07-11 (curves in benchmark_log.jsonl @ 2c15b2c):

- **Edit-path O(N) triple tax** (undo deepcopy · engine recompose · make_patch):
  0.08–1.3 ms/edit at 10–200 nodes, growth_x ≈ 1.0 over 200 sequential edits.
  Three orders of magnitude under the L1/L2 cost of any real interaction.
- **Gate + observation dispatch preamble**: gate ≈ 0.007 ms, observation ≈ 0.
- **apply_recipe depth growth**: none. The 258 ms depth-1 reading is a one-time
  first-mutation lazy-import tax per process, by design.
- **list_tools rebuild**: 33 ms first (lazy burst), 2 ms after — not worth
  memoizing.

## Known deferred refinements (evidence exists, risk gates them)

- Inverse-record undo + incremental LIVRPS resolve — parked; only justified if
  a live scenario shows edit-path cost at real workflow sizes matters.
- MCP tool-surface profile (77,286 B / 134 tools measured static) — **WP-2.2's
  designed surface**; do not fork a quick version here.
- Gate-preamble reorder / READ_ONLY short-circuit — touches the safety gate;
  needs its own crucible if ever justified (currently 0.007 ms — it isn't).
- object_info disk cache (WP-4.4) + per-class fan-out — needs-live to measure.
- validate lock-drift TTL memo — needs-live.
