# DIGEST.md — cycle boundary snapshot (replaced each cycle)

## Cycle FINAL — all 4 tracks done + escalation actioned
- **MODE:** SIMULATED · ComfyUI 0.22.0 / comfy3d_env / RTX 4090 · MCP v3.0.0
- **Branch:** `feat/agent-tooling` — `234e2bc` (P1.1) · `d4e922a` (P1.2) · `f16b5e5` (Tracks 2-4) ·
  + pending node_pack/#5 commit. Remote `origin` exists; no upstream yet (first push pending user-OK=yes).

## Predicate status (11)
| Pred | Gap | Status |
|---|---|---|
| P1.1 | #4 disclosure | ✅ shipped `234e2bc` |
| P1.2 | #6 surgery | ✅ shipped `d4e922a` |
| P2.1 | #1 push | ✅ shipped `f16b5e5` + node pack |
| P2.2 | #1 read-back | ✅ shipped `f16b5e5` + node pack (PULL) |
| P2.3 | #5 profiling | ✅ shipped — tool `f16b5e5` + node-pack route/TimingCapture (escalation); live-render confirm pending |
| P2.4 | #8 watcher | ✅ shipped `f16b5e5` |
| P3.1 | #2 parser | ✅ shipped `f16b5e5` |
| P3.2 | #7 assets | ✅ shipped `f16b5e5` |
| P4.1 | #3 previews | 🛑 HALT (falsified — binary WS frames, stdio agent can't consume) |
| P4.2 | #9 vision cache | ✅ shipped `f16b5e5` |
| P4.3 | #10 memory | ✅ shipped `f16b5e5` |

**10/11 shipped · 1 documented HALT.**

## Home A (node pack)
- Canonical source vendored to repo `node_pack/comfy_agent_bridge/` (README + deploy steps).
- Deployed copy at `G:\COMFY\ComfyUI\custom_nodes\comfy_agent_bridge\` (diff-identical). Needs
  ComfyUI restart to load the new #5 route.

## Verifier state
- Registry 125 tools. Per-feature L1/L2/L3 + node-pack TimingCapture (9 tests) all green.
- INTEGRATE full suite (pre-#5): 4409 passed / 1 pre-existing (Windows SIGKILL). Re-running with
  #5 test added (expect ~4418 / 1).
- STRESS: 96 hostile + 5/5 gate probes green.

## Remaining (post-run)
- Live-render end-to-end confirm of #5 timing against a real generation.
- Live-ComfyUI `@pytest.mark.integration` tests for bridge routes (all current tests mocked).
- Push `feat/agent-tooling` (authorized) → then PR-or-branch decision.
