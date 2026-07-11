# LATENCY MAP — offline pass, 2026-07-11

Deliverable of the latency-and-refinement harness (`tooling/harness/latency/`,
WP-4.0 lineage). **Regime: ComfyUI DOWN** — every number below is offline-real
(median of N on this machine, Windows 11 / Python 3.12, git `2c15b2c` working
tree); the six live end-to-end scenarios are deferred to a live pass (see
`tooling/harness/latency/ORCHESTRATOR.md`). Raw runs:
`tooling/bench/benchmark_log.jsonl`. C6: these numbers are internal evidence,
not publishable benchmarks — WP-4.1 owns publication.

## Where the milliseconds actually live (measured)

| Layer | Term | Baseline | After this pass |
|---|---|---|---|
| L6 | MCP `initialize` (ComfyUI refused / hung) | 3,023 / 6,006 ms | **584 / 587 ms** |
| L6 | boot → tools listed (composite) | 3,056 / 6,039 ms | **836 / 841 ms** |
| L4 | `ping` re-probe (hung, cold / warm-TTL) | 5,188 ms / n-a | 3,027 ms / **≈0 ms** |
| L4 | cold import `agent.mcp_server` | 491 ms | 494 ms (see deferred) |
| L4 | cold import `agent.cli` | 229 ms | **121 ms** |
| L4 | per-edit `set_input` @10/50/200 nodes | 0.08 / 0.34 / 1.33 ms | unchanged (parked) |
| L4 | dispatch floor (gate incl. / bypassed) | 0.017 / 0.011 ms | unchanged (parked) |
| L4 | health summary @100k observations | 3.79 ms + unbounded RAM | **0.012 ms, bounded** |
| L4 | first mutation in a process (lazy-import tax) | ~258 ms once | unchanged (by design) |
| L2 | tool schemas advertised (static) | 77,286 B / 134 tools | unchanged (WP-2.2's lane) |

Honest accounting on the composite: `tools/list #1` rose 33 → 252 ms because the
lazy brain/stage burst moved out of the now-fast `initialize`; the composite the
user feels dropped 73–86 %. Warm `ping` ≈ 0 ms measured over real stdio JSON-RPC.

## What landed (this pass)

1. **Handshake de-serialized** (`agent/mcp_server.py`): stdio opens first; the
   boot reachability probe is a background task; probe verdict cached with a
   20 s TTL and served by `ping`; probe routed through the pooled keepalive
   client, timeout 5 s → 3 s.
2. **`tool_count` honors `BRAIN_ENABLED`** (`agent/__init__.py`): counts come
   from the dispatcher's lazy registry; no eager `agent.brain` import in `ping`.
3. **Boot laziness** (`agent/cli.py`, `agent/_build.py`): tool-layer imports are
   function-level (`agent --help` no longer imports 28 tool modules); git build
   identity is PEP-562 lazy with cache.
4. **Bounded metrics + dead code** (`agent/metrics.py`, `agent/health.py`):
   histogram raw storage capped at last-1000 per label (reservoir semantics —
   `count`/`sum` are windowed, not cumulative); dead `Histogram.get()` block
   removed from the health path.
5. **Dark-layer L3/L4 lit** (`agent/mcp_server.py`): correlation IDs now attach
   on MCP worker threads; one INFO span per dispatched tool (name + seconds) —
   riding existing rails, no new frameworks.

## Parked on evidence (do not re-litigate without new numbers)

| Hypothesis (scout rank) | Measured verdict |
|---|---|
| O(n²) delta-stack growth per edit (#1) | growth_x ≈ 1.0 over 200 edits; 0.08–1.3 ms/edit at 10–200 nodes |
| Inverse-record undo vs deepcopy snapshots (#2) | inside the same 1.3 ms envelope; undo fidelity risk ≫ benefit |
| Decorative `make_patch` per mutation (#3) | same envelope |
| Gate-preamble reorder (#8) | gate costs 0.007 ms/call |
| Observation tax (#9) | unmeasurable at floor scale |
| `list_tools` memoization (#6c) | 33 ms once + 2 ms/rebuild |
| `apply_recipe` depth growth (B2) | none; depth-1 reading is the one-time lazy-import tax |

## Deferred (evidence exists, needs its lane or a live pass)

- **MCP tool-surface profile** — 77,286 B static is real L2 evidence, but the
  profile set is WP-2.2's designed surface (D2 binding). Do not fork it here.
- **`mcp_server` still pays the ~35 ms git probe at import** (module-level
  `from ._build import BUILD_HASH` fires the lazy hook) — make the ping payload
  read build identity lazily in a later pass.
- **object_info disk cache (WP-4.4)** — confirmed memory-only (TTL 300 s,
  ~4.6 MB first fetch) but sizing needs live ComfyUI.
- **Lock-drift validate memo, fs-walk storms (B6), session-lock narrowing
  (#14)** — needs-live / tail-latency; specs in the scout journal.

## Binding recommendation — Track-4 ordering (per WP-4.0's mandate)

1. **WP-4.2 (`run_intent`)** first — its L1 round-trip math is structural and
   needs no map (blueprint already says so); nothing measured tonight argues
   otherwise.
2. **Live L-1 pass next** (ComfyUI up): runs the six blueprint scenarios,
   sizes WP-4.3 (progress notifications, L6) vs WP-4.4 (schema warm start, L4
   cold) with real execution in the loop.
3. **WP-4.3 vs WP-4.4 in the order the live pass ranks them** — tonight's
   offline evidence leans WP-4.4 (the object_info gap is confirmed-real and
   cold-start dominates offline), but execution-heavy sessions may flip it.
4. **WP-2.2 profiles** carry independent L2 evidence (77 KB) — reinforces the
   Week-2 slot; measure the prompt-tax delta with a real host when it lands.
