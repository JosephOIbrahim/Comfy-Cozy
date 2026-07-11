"""Health check for Comfy Cozy subsystems."""

import logging
import time

import httpx

from .config import COMFYUI_URL, LLM_PROVIDER

log = logging.getLogger(__name__)

_start_time = time.monotonic()


def check_health() -> dict:
    """Check health of all subsystems. Returns structured status dict."""
    result = {
        "status": "ok",
        "uptime_seconds": round(time.monotonic() - _start_time),
        "llm_provider": LLM_PROVIDER,
        "comfyui": _check_comfyui(),
        "llm": _check_llm(),
        "metrics": _get_metrics_summary(),
    }

    # Determine overall status
    if result["comfyui"]["status"] == "error" or result["llm"]["status"] == "error":
        result["status"] = "degraded"

    return result


def _check_comfyui() -> dict:
    """Check ComfyUI reachability — in-process when possible, HTTP otherwise.

    Priority is inverted from the previous httpx-only design that
    deadlocked when the /comfy-cozy/health panel route called this from
    inside PromptServer's own aiohttp event loop (the recursive httpx
    GET to /system_stats could not be serviced because the loop was
    blocked on the original health request, so it timed out at 5s and
    returned 503).

    1. **In-process branch (production):** when the ComfyUI ``server``
       module is loaded *and* ``PromptServer.instance`` exists, read
       GPU/VRAM straight from ``comfy.model_management``. No HTTP, no
       event-loop deadlock. Used by panel routes running in-process
       inside PromptServer.

    2. **HTTP fallback (tests, external CLI/MCP callers):** httpx GET
       ``/system_stats``. Tests patch ``agent.health.httpx.Client`` and
       never import ComfyUI's ``server.py``, so ``"server" not in
       sys.modules`` keeps them on this path — preserving every
       existing health test verbatim.

    The ``server`` and ``comfy.model_management`` imports are lazy and
    live inside the in-process branch only, so the test path never
    touches them.
    """
    import sys
    server_mod = sys.modules.get("server")
    if server_mod is not None:
        PromptServer = getattr(server_mod, "PromptServer", None)
        if PromptServer is not None and getattr(PromptServer, "instance", None) is not None:
            return _check_comfyui_in_process()
    return _check_comfyui_via_http()


def _check_comfyui_in_process() -> dict:
    """Read GPU/VRAM directly from comfy.model_management. No HTTP call."""
    try:
        import comfy.model_management as mm
        device = mm.get_torch_device()
        device_name = mm.get_torch_device_name(device)
        total = mm.get_total_memory(device)
        free = mm.get_free_memory(device)
        gpu_info = {
            "name": device_name,
            "vram_total_gb": round(total / 1e9, 1),
            "vram_free_gb": round(free / 1e9, 1),
        }
        return {"status": "ok", "url": COMFYUI_URL, "gpu": gpu_info}
    except Exception as e:
        return {"status": "error", "url": COMFYUI_URL, "error": str(e)}


def _check_comfyui_via_http() -> dict:
    """HTTP fallback: GET /system_stats with a 5s budget.

    Test target — patches against ``agent.health.httpx.Client`` exercise
    this branch.
    """
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{COMFYUI_URL}/system_stats")
            resp.raise_for_status()
            data = resp.json()
            devices = data.get("devices", [])
            gpu_info: dict = {}
            if devices:
                dev = devices[0]
                total = dev.get("vram_total", 0)
                free = dev.get("vram_free", 0)
                gpu_info = {
                    "name": dev.get("name", "unknown"),
                    "vram_total_gb": round(total / 1e9, 1),
                    "vram_free_gb": round(free / 1e9, 1),
                }
            return {"status": "ok", "url": COMFYUI_URL, "gpu": gpu_info}
    except httpx.TimeoutException as e:
        return {"status": "error", "url": COMFYUI_URL, "error": f"Timeout: {e}"}
    except Exception as e:
        return {"status": "error", "url": COMFYUI_URL, "error": str(e)}


def _get_metrics_summary() -> dict:
    """Build a metrics summary for the health endpoint."""
    try:
        from .metrics import tool_call_total, tool_call_duration_seconds
        counts = tool_call_total.get()
        total_ok = sum(v for k, v in counts.items() if len(k) >= 2 and k[1] == "ok")
        total_err = sum(
            v for k, v in counts.items() if len(k) >= 2 and k[1] == "error"
        )
        total_calls = total_ok + total_err
        error_rate = round(total_err / total_calls, 4) if total_calls > 0 else 0.0

        # Aggregate all observations across label keys for percentile calc
        all_obs: list[float] = []
        # Access raw observations thread-safely
        with tool_call_duration_seconds._lock:
            for obs_list in tool_call_duration_seconds._observations.values():
                all_obs.extend(obs_list)

        p50_val: float | None = None
        p99_val: float | None = None
        if all_obs:
            all_obs.sort()
            p50_val = _percentile_from_sorted(all_obs, 50)
            p99_val = _percentile_from_sorted(all_obs, 99)

        return {
            "total_tool_calls": total_calls,
            "error_rate": error_rate,
            "tool_latency_p50": round(p50_val, 6) if p50_val is not None else None,
            "tool_latency_p99": round(p99_val, 6) if p99_val is not None else None,
        }
    except Exception:
        return {"total_tool_calls": 0, "error_rate": 0.0}


def _percentile_from_sorted(sorted_data: list[float], p: float) -> float:
    """Compute p-th percentile from pre-sorted data."""
    import math
    n = len(sorted_data)
    k = (p / 100.0) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_data[int(k)]
    return sorted_data[f] * (c - k) + sorted_data[c] * (k - f)


def _check_llm() -> dict:
    """Check LLM provider can be constructed (no API call)."""
    try:
        from .llm import get_provider

        provider = get_provider()
        return {"status": "ok", "provider": LLM_PROVIDER, "class": type(provider).__name__}
    except Exception as e:
        return {"status": "error", "provider": LLM_PROVIDER, "error": str(e)}
