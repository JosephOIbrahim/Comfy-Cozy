# FORUM.md — adversarial critique of forks BEFORE any build cost.

## Fork A — Read-back transport (Track 2, #1-readback) — ✅ RESOLVED at Leg 0
- **Winner: PULL.** MCP is stdio request/response (`mcp_server.py:7,27`) — the agent cannot receive
  server-pushed events mid-turn, so push is infeasible *to the agent*. FE change hooks exist, so the
  feasible design is debounced FE→backend buffer + `get_canvas_state()` pull tool. Not a HALT.

## Fork B — Parser widget-mapping (Track 3, #2) — PENDING
- Candidates: schema-order (`/object_info`) vs heuristic vs hybrid.
- Leg-0 input: positional-index is already a DEADEND; **and** the existing `get_node_info` is unusable for
  ordering (to_json sort). Critique schema-order-from-raw-`/object_info` vs hybrid before build.

## Fork C — Memory relevance scorer (Track 4, #10) — PENDING
- Candidates: class_type-overlap+recency vs richer scoring. Must stay within P1.1 context budget.
