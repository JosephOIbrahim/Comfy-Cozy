# DEADENDS.md — read before EVERY proposal. Never re-pay a logged dead end.

## Pre-seeded (6 known traps)
| Axis | Direction | Why rejected |
|---|---|---|
| API trust | assert ComfyUI/LiteGraph symbols from docs/memory | docs reference APIs absent in a given build — introspect the live install (Leg 0) |
| Parser mapping | positional `widgets_values[i]` → input by index | order not stable across node versions; map via `/object_info` schema |
| Read-back | stream every keystroke to the agent | floods context + transport; debounce + pull instead |
| #3 previews | build before confirming client renders mid-call images | dead code if the runtime can't display them |
| #5 vram | promise `vram_delta_mb` unconditionally | may be absent from the WS stream; ship duration-only |
| Registration | re-register route/extension on every reload | throws / stacks duplicate handlers; guard for idempotency |

## Discovered this run (Leg 0)
| Axis | Direction | Why rejected | evidence |
|---|---|---|---|
| WS vram (#5) | promise per-node `vram_delta_mb` | confirmed ABSENT from the WS stream — executing/executed/cached carry no memory fields → ship duration-only | execution.py:425/487/565/755 |
| Widget ordering (#2) | read input order from `get_node_info` (or any `to_json`'d tool) | agent `to_json` uses `sort_keys=True` → alphabetizes inputs, destroying true widget order; GET raw `/object_info/{class}` instead | KSampler alpha vs raw order (TRACE) |
| Read-back transport (#1) | push server→agent events for canvas edits | MCP is stdio request/response; agent gets no async pushes → use `get_canvas_state()` PULL | mcp_server.py:7,27 |

## Process dead-ends (how the RUN itself went wrong — do not repeat)
| Trap | Why it bit | Rule |
|---|---|---|
| Recording a verifier result before the command returns | During the outage I wrote "109 passed", phantom file fixes, fake commit hash, "4369 passed" — and a fabricated pass hid a REAL 3-test regression inside commit `080cf5b` | Never write a test count / hash / pass into state until the command's final summary line is in hand |
| Adding tools without updating count-contract tests | Registry has hardcoded `len==N` asserts in 2 files + an `expected` name set; any tool add breaks 3 tests | When TOOLS grows, update `test_tools_registry.py` (count + expected set) and `test_mcp_server.py` count in the SAME commit |

## Falsified features (gate failed → do NOT build)
| Feature | Gate | Why falsified | Evidence |
|---|---|---|---|
| #3 streaming previews to the AGENT (P4.1) | client-render mid-tool-call | ComfyUI sends previews as BINARY WS frames; the MCP agent is stdio request/response and is blocked awaiting the tool return mid-call — it cannot receive streamed frames for steering. "Show the user" sub-mode is already native ComfyUI behavior (nothing to build). Building an agent-facing preview tool = dead code. | server.py:1169 (PREVIEW_IMAGE binary); mcp_server.py:7,27 (stdio); HALT per DISPATCH Leg-0 #3 |
