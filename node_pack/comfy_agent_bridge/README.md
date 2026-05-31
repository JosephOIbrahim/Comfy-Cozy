# comfy_agent_bridge — ComfyUI custom node pack (Home A)

Canonical, version-controlled source for the ComfyUI side of the comfy-Cozy
agent bridge. The agent's MCP tools (Home B, in `agent/tools/`) call the HTTP
routes this pack registers inside the running ComfyUI server.

## What it provides

Server routes (registered on `PromptServer.instance`):

| Route | Method | Agent tool (Home B) | Gap |
|-------|--------|---------------------|-----|
| `/agent/push_workflow` | POST | `push_workflow_to_canvas` | #1 push |
| `/agent/canvas_changed` | POST | (frontend → buffer) | #1 read-back |
| `/agent/canvas_state` | GET | `get_canvas_state` | #1 read-back |
| `/agent/exec_profile/{prompt_id}` | GET | `get_execution_profile` | #5 profiling |

Frontend extension (`web/agent_bridge.js`): loads agent-pushed workflows onto
the canvas (tagging them via `window.__agentLoad` for loop-prevention) and
reports debounced artist edits back to `/agent/canvas_changed`.

`profiling.py` (`TimingCapture`): pure, ComfyUI-free per-node duration capture
fed by an idempotent `send_sync` observer. Duration-only — the WS stream carries
no vram data (Leg-0 gate).

## Deploy

This directory is the source of truth. To run it, place a copy (or symlink) in
your ComfyUI `custom_nodes/`:

```bash
# Windows (symlink, run as admin) — keeps repo + runtime in sync:
mklink /D "G:\COMFY\ComfyUI\custom_nodes\comfy_agent_bridge" ^
          "G:\Comfy-Cozy\node_pack\comfy_agent_bridge"

# Or a plain copy (re-copy after changes):
xcopy /E /I /Y "G:\Comfy-Cozy\node_pack\comfy_agent_bridge" ^
               "G:\COMFY\ComfyUI\custom_nodes\comfy_agent_bridge"
```

Restart ComfyUI after first install or after changing `__init__.py` / routes.

## Notes

- **Idempotent**: routes and the `send_sync` observer register exactly once and
  survive hot-reload without stacking handlers.
- **Safe degradation**: if `server`/`PromptServer.instance` is unavailable
  (e.g. imported outside ComfyUI), route registration is skipped with a warning;
  the module still imports cleanly.
- `TimingCapture` is unit-tested in `tests/test_node_pack_profiling.py`.
- `class_type` is not present in ComfyUI's `executing` events, so profiled nodes
  report `class_type: null`; node_id + duration_ms are the reliable signal.
