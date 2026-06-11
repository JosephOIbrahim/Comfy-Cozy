"""ComfyUI HTTP API tools.

Wraps the ComfyUI REST API as Agent SDK tools so the agent can
query the running ComfyUI instance for node info, system stats,
queue status, and execution history.
"""

import threading
import time
from collections.abc import Iterable
from urllib.parse import quote

import httpx

from ..circuit_breaker import COMFYUI_BREAKER
from ..config import COMFYUI_URL
from ._util import to_json

# ---------------------------------------------------------------------------
# Shared HTTP client (connection pool)
# ---------------------------------------------------------------------------

_client_lock = threading.Lock()
_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """Return a shared httpx client for ComfyUI API calls."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = httpx.Client(
                    base_url=COMFYUI_URL,
                    timeout=10.0,
                    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                )
    return _client

# ---------------------------------------------------------------------------
# /object_info cache (H2): TTL + explicit invalidation
# ---------------------------------------------------------------------------
# The full /object_info payload is ~4.6 MB and was re-fetched uncached at
# every call site (ledger C-R3) — seconds per validate. One shared TTL cache
# plus cheap per-class GETs collapse the validate -> fix -> re-validate loop.

_OBJECT_INFO_TTL_S = 300.0

_object_info_lock = threading.Lock()
_object_info_full: dict | None = None
_object_info_full_at = 0.0
_object_info_classes: dict[str, tuple[float, dict | None]] = {}


def invalidate_object_info_cache() -> None:
    """Drop all cached /object_info state.

    Call after anything that changes ComfyUI's node registry
    (node-pack install/uninstall); also wired into the test suite's
    autouse reset fixture so cached state never leaks across tests.
    """
    global _object_info_full, _object_info_full_at
    with _object_info_lock:
        _object_info_full = None
        _object_info_full_at = 0.0
        _object_info_classes.clear()


def get_object_info(timeout: float = 30.0, force_refresh: bool = False) -> dict:
    """Full /object_info payload, served from the TTL cache when warm.

    Raises like _get() (ConnectError / HTTPStatusError). A failed fetch
    leaves the cache untouched; an expired cache is never served.
    The lock is held across the fetch so concurrent callers wait for one
    fetch instead of each paying the multi-second download.
    """
    global _object_info_full, _object_info_full_at
    with _object_info_lock:
        fresh = time.monotonic() - _object_info_full_at < _OBJECT_INFO_TTL_S
        if _object_info_full is not None and fresh and not force_refresh:
            return _object_info_full
        data = _get("/object_info", timeout=timeout)
        _object_info_full = data
        _object_info_full_at = time.monotonic()
        return data


def get_object_info_classes(class_types: Iterable[str], timeout: float = 10.0) -> dict[str, dict]:
    """Schemas for the given node classes only.

    Served from the warm full-payload cache when available; otherwise one
    per-class GET /object_info/{class} (~KB instead of ~4.6 MB) per class,
    each TTL-cached. A class absent from the result is not installed —
    ComfyUI returns an empty body for unknown classes — while an
    unreachable ComfyUI raises, so "missing" is never conflated with "down".
    """
    wanted = sorted(set(class_types))
    out: dict[str, dict] = {}
    now = time.monotonic()
    to_fetch: list[str] = []
    with _object_info_lock:
        if _object_info_full is not None and now - _object_info_full_at < _OBJECT_INFO_TTL_S:
            for cls in wanted:
                schema = _object_info_full.get(cls)
                if schema is not None:
                    out[cls] = schema
            return out
        for cls in wanted:
            hit = _object_info_classes.get(cls)
            if hit is not None and now - hit[0] < _OBJECT_INFO_TTL_S:
                if hit[1] is not None:
                    out[cls] = hit[1]
            else:
                to_fetch.append(cls)
    # Network outside the lock — per-class GETs are small and independent.
    for cls in to_fetch:
        data = _get(f"/object_info/{quote(cls)}", timeout=timeout)
        schema = data.get(cls) if isinstance(data, dict) else None
        with _object_info_lock:
            _object_info_classes[cls] = (time.monotonic(), schema)
        if schema is not None:
            out[cls] = schema
    return out


# ---------------------------------------------------------------------------
# Tool schemas (Anthropic tool-use format)
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "is_comfyui_running",
        "description": (
            "Check if ComfyUI is running and reachable. "
            "Call this first before using other ComfyUI tools."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_all_nodes",
        "description": (
            "Get registered node types in ComfyUI via GET /object_info. "
            "Use format='names_only' (just class_type names) or "
            "'summary' (name+category) to control response size. "
            "Use 'full' for complete input/output schemas. "
            "Prefer get_node_info for a specific node."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category_filter": {
                    "type": "string",
                    "description": (
                        "Optional substring to filter nodes by category "
                        "(e.g. 'sampling', 'loaders', 'image'). "
                        "Case-insensitive."
                    ),
                },
                "name_filter": {
                    "type": "string",
                    "description": (
                        "Optional substring to filter nodes by class_type name "
                        "(e.g. 'KSampler', 'ControlNet'). Case-insensitive."
                    ),
                },
                "format": {
                    "type": "string",
                    "enum": ["names_only", "summary", "full"],
                    "description": (
                        "Response format. 'names_only': just class_type names (smallest). "
                        "'summary': name + category + display_name (default). "
                        "'full': includes input types and output types."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_node_info",
        "description": (
            "Get info for a specific ComfyUI node type: its required/optional "
            "inputs with types and defaults, output types, category, and description. "
            "Use the exact class_type name (e.g. 'KSampler', 'CLIPTextEncode'). "
            "Use 'detail' to control response size: 'summary' (default) is tiny, "
            "'signature' adds required input types, 'full' is the complete schema. "
            "Required inputs are never dropped at any tier."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "node_type": {
                    "type": "string",
                    "description": "Exact class_type name of the node.",
                },
                "detail": {
                    "type": "string",
                    "enum": ["summary", "signature", "full"],
                    "description": (
                        "Disclosure tier (default 'summary'). 'summary' ~200 tok: "
                        "required input names + outputs. 'signature' ~1KB: required "
                        "inputs with types. 'full': complete schema with defaults/tooltips."
                    ),
                },
            },
            "required": ["node_type"],
        },
    },
    {
        "name": "get_system_stats",
        "description": (
            "Get ComfyUI system stats: GPU info, VRAM usage, "
            "Python version, and currently loaded models."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_queue_status",
        "description": (
            "Get the current ComfyUI queue: running prompts and pending items."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_history",
        "description": (
            "Get execution history from ComfyUI. Optionally filter by prompt_id. "
            "Returns outputs (images, videos) and execution status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt_id": {
                    "type": "string",
                    "description": "Specific prompt ID to look up. Omit for recent history.",
                },
                "max_items": {
                    "type": "integer",
                    "description": "Max number of history items to return (default 5).",
                },
            },
            "required": [],
        },
    },
]

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_TIMEOUT = 15.0


def _get(path: str, timeout: float = _TIMEOUT) -> dict:
    """GET request to ComfyUI, returns parsed JSON.

    Raises httpx.ConnectError or httpx.HTTPStatusError on failure.
    Circuit breaker tracks failures and fast-fails when ComfyUI is down.
    """
    breaker = COMFYUI_BREAKER()
    if not breaker.allow_request():
        raise httpx.ConnectError(
            f"ComfyUI has been unreachable. Waiting {breaker.recovery_timeout:.0f}s before retrying. Is ComfyUI still running?"
        )
    try:
        resp = _get_client().get(f"{COMFYUI_URL}{path}", timeout=timeout)
        resp.raise_for_status()
        breaker.record_success()
        try:
            return resp.json()
        except ValueError as e:  # Cycle 43: guard against non-JSON response body
            raise httpx.ConnectError(
                f"ComfyUI returned non-JSON on {path} (HTML error page?): {e}"
            ) from e
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        breaker.record_failure()
        raise httpx.ConnectError(str(e)) from e


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _handle_is_running() -> str:
    try:
        stats = _get("/system_stats", timeout=5.0)
        devices = stats.get("devices", [])
        # Cycle 67: guard non-dict element (malformed API shape)
        gpu = (
            devices[0].get("name", "unknown")
            if devices and isinstance(devices[0], dict)
            else "no GPU detected"
        )
        py_ver = stats.get("system", {}).get("python_version", "unknown")
        return to_json({
            "running": True,
            "url": COMFYUI_URL,
            "gpu": gpu,
            "python": py_ver,
        })
    except httpx.ConnectError:  # Cycle 68: give VFX artist actionable guidance
        return to_json({
            "running": False,
            "url": COMFYUI_URL,
            "error": f"ComfyUI is not running at {COMFYUI_URL}. Start ComfyUI and try again.",
        })
    except Exception as e:
        return to_json({
            "running": False,
            "url": COMFYUI_URL,
            "error": f"Could not reach ComfyUI: {e}",
        })


def _handle_get_all_nodes(tool_input: dict) -> str:
    cat_filter = (tool_input.get("category_filter") or "").lower()
    name_filter = (tool_input.get("name_filter") or "").lower()
    fmt = tool_input.get("format", "summary")

    all_info = _get("/object_info", timeout=30.0)

    # Apply filters
    filtered_names = []
    for name in sorted(all_info.keys()):
        info = all_info[name]
        if not isinstance(info, dict):  # Cycle 42: guard malformed node entries
            continue
        cat = (info.get("category") or "").lower()
        if cat_filter and cat_filter not in cat:
            continue
        if name_filter and name_filter not in name.lower():
            continue
        filtered_names.append(name)

    # Format output based on requested detail level
    if fmt == "names_only":
        return to_json({
            "count": len(filtered_names),
            "nodes": filtered_names,
        })

    if fmt == "full":
        nodes = {}
        for name in filtered_names:
            info = all_info[name]
            nodes[name] = {
                "category": info.get("category", ""),
                "display_name": info.get("display_name", name),
                "description": info.get("description", ""),
                "input_types": sorted((info.get("input", {}).get("required", {})).keys()),
                "output_types": info.get("output", []),
            }
        return to_json({"count": len(nodes), "nodes": nodes})

    # Default: summary (name + category + display_name)
    nodes = {}
    for name in filtered_names:
        info = all_info[name]
        nodes[name] = {
            "category": info.get("category", ""),
            "display_name": info.get("display_name", name),
        }
    return to_json({
        "count": len(nodes),
        "nodes": nodes,
        "hint": "Use format='names_only' for smaller response, or get_node_info for details on a specific node.",
    })


def _spec_type(spec) -> str:
    """Short type label for an /object_info input spec (e.g. 'MODEL', 'INT', 'COMBO')."""
    if isinstance(spec, (list, tuple)) and spec:
        t = spec[0]
        if isinstance(t, str):
            return t
        if isinstance(t, (list, tuple)):
            return "COMBO"
    return "UNKNOWN"


def _node_info_tier(node_type: str, info: dict, detail: str) -> str:
    """Compact disclosure tier for get_node_info (#4 progressive disclosure).

    summary   (~200 tok): required input NAMES + outputs (types/defaults dropped).
    signature (~1KB):      required inputs as [name, type] (defaults/tooltips dropped).

    Required inputs are NEVER dropped at either tier (P1.1 fidelity rule); inputs are
    emitted as ordered lists so they keep /object_info order regardless of to_json sort.
    Oversize responses keep all required inputs and add a 'detail=full' hint.
    """
    req = info.get("input", {}).get("required", {}) or {}
    opt = info.get("input", {}).get("optional", {}) or {}
    outputs = list(info.get("output", []) or [])

    if detail == "signature":
        compact = {
            "class_type": node_type,
            "category": info.get("category", ""),
            "detail": "signature",
            "required": [[n, _spec_type(s)] for n, s in req.items()],
            "optional": list(opt.keys()),
            "outputs": outputs,
        }
        limit = 1024  # P1.1: signature <= 1KB
    else:  # summary
        desc = " ".join((info.get("description") or "").split())
        if len(desc) > 120:
            desc = desc[:117] + "..."
        compact = {
            "class_type": node_type,
            "category": info.get("category", ""),
            "detail": "summary",
            "description": desc,
            "required_inputs": list(req.keys()),
            "outputs": outputs,
        }
        limit = 800  # P1.1: summary ~200 tokens

    out = to_json(compact)
    if len(out) > limit:
        compact["_more"] = (
            f"Compacted to '{detail}'. Call get_node_info with detail='full' "
            "for defaults, tooltips, and optional-input types."
        )
        out = to_json(compact)
    return out


def _handle_get_node_info(tool_input: dict) -> str:
    node_type = tool_input.get("node_type")  # Cycle 46: guard required field
    if not node_type or not isinstance(node_type, str):
        return to_json({"error": "node_type is required and must be a non-empty string."})
    detail = tool_input.get("detail", "summary")  # #4 progressive disclosure
    if detail not in ("summary", "signature", "full"):
        detail = "summary"
    all_info = _get(f"/object_info/{node_type}", timeout=10.0)

    info = all_info.get(node_type)
    if not info:
        # Try case-insensitive search
        all_nodes = _get("/object_info", timeout=30.0)
        matches = [n for n in all_nodes if n.lower() == node_type.lower()]
        if matches:
            info = all_nodes[matches[0]]
            node_type = matches[0]
        else:
            # Suggest similar names
            # He2025: sort for deterministic suggestion order
            similar = sorted(n for n in all_nodes if node_type.lower() in n.lower())[:10]
            return to_json({
                "error": f"Node type '{node_type}' not found.",
                "similar_nodes": similar,
            })

    # #4 progressive disclosure: compact tiers before the full build.
    # Required inputs are never dropped at any tier (P1.1 fidelity rule).
    if detail != "full":
        return _node_info_tier(node_type, info, detail)

    result = {
        "class_type": node_type,
        "display_name": info.get("display_name", node_type),
        "category": info.get("category", ""),
        "description": info.get("description", ""),
        "input": info.get("input", {}),
        "output": info.get("output", []),
        "output_name": info.get("output_name", []),
        "output_is_list": info.get("output_is_list", []),
    }

    # Annotate COMFY_AUTOGROW_V3 inputs with dotted-name hints so the
    # agent knows to use "group.sub" notation (e.g. "values.a") when
    # setting inputs or making connections on these nodes.
    autogrow_hints = {}
    for section in ("required", "optional"):
        for inp_name, spec in info.get("input", {}).get(section, {}).items():
            if (
                isinstance(spec, (list, tuple))
                and len(spec) > 0
                and spec[0] == "COMFY_AUTOGROW_V3"
            ):
                tmpl = spec[1] if len(spec) > 1 else {}
                template_info = tmpl.get("template", {})
                names = tmpl.get("names", [])
                min_count = tmpl.get("min", 0)
                # Extract sub-input type from template
                tmpl_inputs = template_info.get("input", {}).get("required", {})
                sub_type = None
                if tmpl_inputs:
                    first_spec = next(iter(tmpl_inputs.values()))
                    if isinstance(first_spec, (list, tuple)) and first_spec:
                        sub_type = first_spec[0]
                autogrow_hints[inp_name] = {
                    "type": "COMFY_AUTOGROW_V3",
                    "sub_input_type": sub_type,
                    "template_names": names[:10],  # cap for readability
                    "min": min_count,
                    "usage": (
                        f"Use dotted names: '{inp_name}.{names[0]}', "
                        f"'{inp_name}.{names[1]}', etc."
                        if len(names) >= 2
                        else f"Use dotted names: '{inp_name}.<name>'"
                    ),
                }

    if autogrow_hints:
        result["autogrow_inputs"] = autogrow_hints

    return to_json(result)


def _handle_get_system_stats() -> str:
    stats = _get("/system_stats", timeout=5.0)
    return to_json(stats)


def _handle_get_queue() -> str:
    queue = _get("/queue", timeout=5.0)
    running = queue.get("queue_running") or []  # Cycle 54: guard against explicit null from API
    pending = queue.get("queue_pending") or []
    return to_json({
        "running_count": len(running),
        "pending_count": len(pending),
        "running": [{"prompt_id": r[1]} for r in running] if running else [],
        "pending": [{"prompt_id": p[1]} for p in pending] if pending else [],
    })


def _handle_get_history(tool_input: dict) -> str:
    prompt_id = tool_input.get("prompt_id")
    try:
        max_items = int(tool_input.get("max_items", 5))  # Cycle 67: guard string input
    except (TypeError, ValueError):
        return to_json({"error": "max_items must be an integer."})
    if max_items < 1:  # Cycle 72: negative value causes wrong slice [-n:] = [n:]
        return to_json({"error": "max_items must be >= 1."})
    if prompt_id is not None and not isinstance(prompt_id, str):  # Cycle 54: type guard optional field
        return to_json({"error": "prompt_id must be a string if provided."})

    if prompt_id:
        history = _get(f"/history/{prompt_id}", timeout=10.0)
    else:
        history = _get("/history", timeout=10.0)

    # Trim to max_items
    if not prompt_id and len(history) > max_items:
        # History keys are prompt IDs; take most recent
        keys = list(history.keys())[-max_items:]
        history = {k: history[k] for k in keys}

    # Summarize outputs
    result = {}
    # He2025: sort for deterministic output order
    for pid, entry in sorted(history.items()):
        outputs_summary = []
        for node_id, node_out in sorted(entry.get("outputs", {}).items()):
            for img in node_out.get("images", []):
                outputs_summary.append({
                    "type": "image",
                    "filename": img.get("filename"),
                })
            for vid in node_out.get("gifs", []):
                outputs_summary.append({
                    "type": "video",
                    "filename": vid.get("filename"),
                })
        status_info = entry.get("status", {})
        result[pid] = {
            "status": status_info.get("status_str", "unknown"),
            "completed": status_info.get("completed", False),
            "outputs": outputs_summary,
        }

    return to_json(result)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def handle(name: str, tool_input: dict) -> str:
    """Execute a comfy_api tool call."""
    try:
        if name == "is_comfyui_running":
            return _handle_is_running()
        elif name == "get_all_nodes":
            return _handle_get_all_nodes(tool_input)
        elif name == "get_node_info":
            return _handle_get_node_info(tool_input)
        elif name == "get_system_stats":
            return _handle_get_system_stats()
        elif name == "get_queue_status":
            return _handle_get_queue()
        elif name == "get_history":
            return _handle_get_history(tool_input)
        else:
            return to_json({"error": f"Unknown tool: {name}"})
    except httpx.ConnectError:
        return to_json({
            "error": f"Could not connect to ComfyUI at {COMFYUI_URL}. Is it running?",
        })
    except httpx.HTTPStatusError as e:
        return to_json({
            "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
        })
    except Exception as e:
        return to_json({"error": str(e)})
