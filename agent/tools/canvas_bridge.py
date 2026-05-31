"""Canvas bridge tools (Home B) — agent ↔ ComfyUI canvas.

Phase 0 (#1 push):  push_workflow_to_canvas — POST a workflow to the
comfy_agent_bridge node pack's /agent/push_workflow route, which broadcasts
`agent.load_workflow` so every connected browser tab reloads the graph.

Phase 1B (#1 read-back):  get_canvas_state — PULL the most recent artist-edited
canvas state the node pack has buffered (transport gate resolved to PULL: MCP is
stdio request/response, so the agent cannot receive server-pushed events).

Both tools are path/endpoint safe and fail cleanly (structured error, no hang).
"""

import httpx

from ..config import COMFYUI_URL
from ._util import to_json, validate_path

TOOLS: list[dict] = [
    {
        "name": "push_workflow_to_canvas",
        "description": (
            "Push a workflow onto the live ComfyUI canvas so the artist sees it "
            "load in their browser. Provide either a 'workflow' dict (API format) "
            "or a 'path' to a workflow JSON file. Optional 'reason' is recorded in "
            "the provenance envelope. Requires the comfy_agent_bridge node pack "
            "installed and at least one browser tab connected."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow": {
                    "type": "object",
                    "description": "Workflow graph (API format) to push. Use this OR path.",
                },
                "path": {
                    "type": "string",
                    "description": "Path to a workflow JSON file to push. Use this OR workflow.",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional human-readable reason (provenance envelope meta).",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_canvas_state",
        "description": (
            "Pull the current workflow state from the live ComfyUI canvas, "
            "including any edits the artist made by hand. Returns the buffered "
            "graph the comfy_agent_bridge node pack last captured, or a note if "
            "no edit has been seen yet. Agent-originated loads (pushes) are not "
            "reported as artist edits."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def _handle_push_workflow_to_canvas(tool_input: dict) -> str:
    workflow = tool_input.get("workflow")
    path = tool_input.get("path")
    reason = tool_input.get("reason", "")

    if workflow is None and not path:
        return to_json({"error": "Provide either 'workflow' (dict) or 'path' (file)."})
    if workflow is not None and not isinstance(workflow, dict):
        return to_json({"error": "'workflow' must be an object (API-format graph)."})

    if path:
        err = validate_path(path, must_exist=True)
        if err:
            return to_json({"error": err})
        if not path.lower().endswith(".json"):
            return to_json({"error": "Workflow path must be a .json file."})
        import json
        from pathlib import Path
        try:
            workflow = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return to_json({"error": "Workflow file is not valid JSON."})
        if not isinstance(workflow, dict):
            return to_json({"error": "Workflow file must contain a JSON object."})

    envelope = {"workflow": workflow, "meta": {"source": "agent", "reason": reason}}

    try:
        resp = httpx.post(
            f"{COMFYUI_URL}/agent/push_workflow", json=envelope, timeout=10.0
        )
    except httpx.ConnectError:
        return to_json({
            "error": "ComfyUI is not reachable. Start ComfyUI, then try again.",
        })
    except httpx.TimeoutException:
        return to_json({"error": "Push timed out after 10s. Is ComfyUI responsive?"})

    if resp.status_code == 404:
        return to_json({
            "error": (
                "Push route not found (404). The comfy_agent_bridge node pack is "
                "not installed or ComfyUI needs a restart to load it."
            ),
        })
    if resp.status_code != 200:
        return to_json({
            "error": f"Push failed (HTTP {resp.status_code}).",
            "detail": resp.text[:200],
        })

    return to_json({
        "pushed": True,
        "reason": reason,
        "note": "Every connected browser tab reloaded the pushed workflow.",
    })


def _handle_get_canvas_state(tool_input: dict) -> str:
    try:
        resp = httpx.get(f"{COMFYUI_URL}/agent/canvas_state", timeout=10.0)
    except httpx.ConnectError:
        return to_json({"error": "ComfyUI is not reachable. Start ComfyUI, then try again."})
    except httpx.TimeoutException:
        return to_json({"error": "Canvas read timed out after 10s."})

    if resp.status_code == 404:
        return to_json({
            "error": (
                "Canvas read-back route not found (404). Update the "
                "comfy_agent_bridge node pack and restart ComfyUI."
            ),
        })
    if resp.status_code != 200:
        return to_json({"error": f"Canvas read failed (HTTP {resp.status_code})."})

    try:
        data = resp.json()
    except Exception:
        return to_json({"error": "Canvas read returned non-JSON."})

    return to_json(data)


def handle(name: str, tool_input: dict) -> str:
    try:
        if name == "push_workflow_to_canvas":
            return _handle_push_workflow_to_canvas(tool_input)
        if name == "get_canvas_state":
            return _handle_get_canvas_state(tool_input)
        return to_json({"error": f"Unknown tool: {name}"})
    except Exception as e:  # no stack vomit — structured error
        return to_json({"error": str(e)})
