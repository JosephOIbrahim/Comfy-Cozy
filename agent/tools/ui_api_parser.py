"""UI→API workflow parser (#2 / P3.1) — Home B.

Convert a UI-format ComfyUI workflow (nodes[] with widgets_values) into API
format ({node_id: {class_type, inputs}}) so any community-shared workflow is
legible without a browser round-trip.

WIDGET-ORDERING GATE (resolved at Leg 0): widgets_values order is NOT stable
across node versions and must be mapped via the live /object_info input schema
order — never by positional index. A node absent from /object_info is SURFACED,
not guessed (the unmappable rule). seed + control_after_generate is handled as
the known 2-values-1-logical-input edge case.
"""

import json
from pathlib import Path

import httpx

from ..config import COMFYUI_URL
from ._util import to_json, validate_path

TOOLS: list[dict] = [
    {
        "name": "parse_ui_workflow",
        "description": (
            "Convert a UI-format ComfyUI workflow into executable API format. "
            "Provide 'path' to a UI workflow JSON file or 'workflow' as a dict. "
            "Maps widget values to inputs using the live /object_info schema order "
            "(not positional index). Nodes missing from /object_info are reported "
            "as unmappable rather than guessed. Returns API-format graph plus a "
            "report of any unmapped nodes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to a UI-format workflow JSON file."},
                "workflow": {"type": "object", "description": "UI-format workflow dict (use this OR path)."},
            },
            "required": [],
        },
    },
]

# Widgets that exist in the UI but are not /object_info inputs — they ride
# alongside a real widget and must be consumed without advancing the schema
# cursor incorrectly. control_after_generate trails seed/noise_seed.
_CONTROL_WIDGETS = {"control_after_generate"}


def _get_object_info() -> dict:
    resp = httpx.get(f"{COMFYUI_URL}/object_info", timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def _required_input_order(node_schema: dict) -> list[tuple[str, object]]:
    """Return [(input_name, spec), ...] in /object_info declared order for inputs
    that are widget-backed (i.e. have a default/config, not pure connections)."""
    inp = node_schema.get("input", {}) or {}
    ordered: list[tuple[str, object]] = []
    for section in ("required", "optional"):
        for name, spec in (inp.get(section, {}) or {}).items():
            ordered.append((name, spec))
    return ordered


def _is_widget_spec(spec) -> bool:
    """A widget input has a primitive type (INT/FLOAT/STRING/BOOLEAN) or a combo
    (list of choices). Pure connection inputs (MODEL/CLIP/LATENT/...) are not
    driven by widgets_values."""
    if not isinstance(spec, (list, tuple)) or not spec:
        return False
    t = spec[0]
    if isinstance(t, list):  # combo
        return True
    return t in ("INT", "FLOAT", "STRING", "BOOLEAN")


def _map_widgets(node_schema: dict, widgets_values: list) -> dict:
    """Map a node's widgets_values onto named inputs using schema order.

    Handles the seed+control_after_generate case: an INT seed widget is often
    followed by an extra control value in widgets_values that has no /object_info
    input — we consume it without mapping.
    """
    inputs: dict = {}
    order = [(n, s) for n, s in _required_input_order(node_schema) if _is_widget_spec(s)]
    vi = 0
    for name, spec in order:
        if vi >= len(widgets_values):
            break
        inputs[name] = widgets_values[vi]
        vi += 1
        # seed-like INT widgets carry a trailing control_after_generate value.
        if spec and spec[0] == "INT" and vi < len(widgets_values):
            nxt = widgets_values[vi]
            if isinstance(nxt, str) and nxt in ("fixed", "increment", "decrement", "randomize"):
                vi += 1  # consume control value, do not map
    return inputs


def _ui_to_api(ui: dict, object_info: dict) -> tuple[dict, list]:
    """Return (api_graph, unmapped_nodes)."""
    nodes = ui.get("nodes", [])
    links = ui.get("links", [])

    # link id -> (from_node_id, from_slot)
    link_src: dict = {}
    for lk in links:
        # UI link format: [link_id, from_node, from_slot, to_node, to_slot, type]
        if isinstance(lk, (list, tuple)) and len(lk) >= 5:
            link_src[lk[0]] = (str(lk[1]), lk[2])

    api: dict = {}
    unmapped: list = []
    for node in nodes:
        nid = str(node.get("id"))
        ctype = node.get("type")
        if not ctype:
            continue
        schema = object_info.get(ctype)
        if schema is None:
            unmapped.append({"node_id": nid, "class_type": ctype,
                             "reason": "not in /object_info (custom node not installed?)"})
            continue
        inputs = _map_widgets(schema, node.get("widgets_values", []) or [])
        # Connection inputs from the node's input slots
        for slot in node.get("inputs", []) or []:
            link_id = slot.get("link")
            sname = slot.get("name")
            if link_id is not None and link_id in link_src and sname:
                src_node, src_slot = link_src[link_id]
                inputs[sname] = [src_node, src_slot]
        api[nid] = {"class_type": ctype, "inputs": inputs}
    return api, unmapped


def _handle_parse_ui_workflow(tool_input: dict) -> str:
    path = tool_input.get("path")
    workflow = tool_input.get("workflow")
    if not path and workflow is None:
        return to_json({"error": "Provide either 'path' or 'workflow'."})

    if path:
        err = validate_path(path, must_exist=True)
        if err:
            return to_json({"error": err})
        try:
            workflow = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return to_json({"error": "Workflow file is not valid JSON."})

    if not isinstance(workflow, dict) or "nodes" not in workflow:
        return to_json({"error": "Not a UI-format workflow (expected a 'nodes' list)."})

    try:
        object_info = _get_object_info()
    except httpx.ConnectError:
        return to_json({"error": "ComfyUI not reachable — /object_info needed for parsing."})
    except Exception as e:
        return to_json({"error": f"Could not fetch /object_info: {e}"})

    api, unmapped = _ui_to_api(workflow, object_info)
    result = {"api_workflow": api, "node_count": len(api), "unmapped": unmapped}
    if unmapped:
        result["note"] = (
            f"{len(unmapped)} node(s) could not be mapped (missing from /object_info). "
            "Surfaced, not guessed — install the missing custom nodes and re-parse."
        )
    return to_json(result)


def handle(name: str, tool_input: dict) -> str:
    try:
        if name == "parse_ui_workflow":
            return _handle_parse_ui_workflow(tool_input)
        return to_json({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return to_json({"error": str(e)})
