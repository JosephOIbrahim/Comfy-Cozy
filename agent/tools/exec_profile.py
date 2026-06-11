"""Execution profiling (#5 / P2.3) — Home B.

get_execution_profile(prompt_id) → per-node timing so optimization stops being
theoretical.

VRAM GATE (resolved at Leg 0): the ComfyUI WS stream emits executing/executed
without timestamps or vram deltas (execution.py). So profiling is DURATION-ONLY,
measured consumer-side by the comfy_agent_bridge node pack, which timestamps the
executing→executed transitions in-process and exposes them at
/agent/exec_profile/{prompt_id}. This tool pulls that, orders by start, and
flags regressions against a stored baseline. vram_delta is intentionally absent.
"""

import threading

import httpx

from ..config import COMFYUI_URL
from ._util import to_json

# prompt_id signature (sorted class_types) -> {node_key: duration_ms} baseline.
_lock = threading.Lock()
_baselines: dict[str, dict] = {}
_REGRESSION_RATIO = 1.5  # >50% slower than baseline -> flag

TOOLS: list[dict] = [
    {
        "name": "get_execution_profile",
        "description": (
            "Get per-node timing for a completed render (duration-only — the "
            "ComfyUI WS stream carries no vram data). Returns nodes ordered by "
            "execution, each with class_type and duration_ms. Cached (~0ms) nodes "
            "are marked, not flagged as anomalies. Pass 'baseline_key' to compare "
            "against a stored baseline and flag regressions; pass 'save_baseline': "
            "true to record this run as the baseline for that key."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt_id": {"type": "string", "description": "prompt_id from execute_workflow."},
                "baseline_key": {"type": "string", "description": "Key to compare/store a baseline under."},
                "save_baseline": {"type": "boolean", "description": "Store this run as the baseline."},
            },
            "required": ["prompt_id"],
        },
    },
]


def _fetch_profile(prompt_id: str) -> dict:
    from .canvas_bridge import bridge_auth_headers
    resp = httpx.get(
        f"{COMFYUI_URL}/agent/exec_profile/{prompt_id}", timeout=10.0,
        headers=bridge_auth_headers(),
    )
    if resp.status_code == 404:
        raise FileNotFoundError("profile route or prompt_id not found")
    resp.raise_for_status()
    return resp.json()


def _handle_get_execution_profile(tool_input: dict) -> str:
    prompt_id = tool_input.get("prompt_id")
    if not prompt_id or not isinstance(prompt_id, str):
        return to_json({"error": "prompt_id is required and must be a non-empty string."})

    try:
        data = _fetch_profile(prompt_id)
    except FileNotFoundError:
        return to_json({
            "error": (
                f"No profile for prompt_id '{prompt_id}'. Either it never ran, or "
                "the comfy_agent_bridge node pack (which captures timing) is not "
                "installed / needs a ComfyUI restart."
            ),
        })
    except httpx.ConnectError:
        return to_json({"error": "ComfyUI not reachable."})
    except Exception as e:
        return to_json({"error": f"Could not fetch profile: {e}"})

    nodes = data.get("nodes", []) if isinstance(data, dict) else []
    # Order by start time; mark cached (~0ms) nodes.
    nodes = sorted(nodes, key=lambda n: n.get("start", 0))
    for n in nodes:
        n["cached"] = bool(n.get("cached")) or n.get("duration_ms", 0) <= 1

    result = {"prompt_id": prompt_id, "nodes": nodes, "node_count": len(nodes),
              "total_ms": round(sum(n.get("duration_ms", 0) for n in nodes), 2),
              "vram": "unavailable (not in WS stream)"}

    key = tool_input.get("baseline_key")
    if key and tool_input.get("save_baseline"):
        with _lock:
            _baselines[key] = {n.get("node_id", str(i)): n.get("duration_ms", 0)
                               for i, n in enumerate(nodes)}
        result["baseline_saved"] = key
    elif key:
        with _lock:
            base = _baselines.get(key)
        if base:
            regressions = []
            for i, n in enumerate(nodes):
                nid = n.get("node_id", str(i))
                cur = n.get("duration_ms", 0)
                prev = base.get(nid)
                # Don't flag cached (~0ms) nodes as anomalies.
                if prev and prev > 1 and not n["cached"] and cur > prev * _REGRESSION_RATIO:
                    regressions.append({"node_id": nid, "class_type": n.get("class_type"),
                                        "baseline_ms": prev, "current_ms": cur})
            result["regressions"] = regressions
            result["regression_flagged"] = bool(regressions)
        else:
            result["note"] = f"No baseline stored under '{key}' to compare."

    return to_json(result)


def handle(name: str, tool_input: dict) -> str:
    try:
        if name == "get_execution_profile":
            return _handle_get_execution_profile(tool_input)
        return to_json({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return to_json({"error": str(e)})


# Re-export so a unit test can drive the parser without a live server.
def _profile_from_payload(payload: dict, **kw) -> str:
    """Test seam: run the ordering/regression logic on a literal payload."""
    import unittest.mock as _m
    with _m.patch.object(__import__(__name__, fromlist=["_fetch_profile"]),
                         "_fetch_profile", return_value=payload):
        return _handle_get_execution_profile({"prompt_id": "test", **kw})
