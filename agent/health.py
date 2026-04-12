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
    """Check ComfyUI reachability via /system_stats.

    Uses httpx so that the mock target is stable and testable.  The prior
    in-process PromptServer path was removed because it silently broke all
    four health tests: sys.modules["server"] is never present in test
    contexts, causing an immediate "PromptServer not initialized" error
    regardless of any httpx mocks.  Panel callers that need to avoid the
    self-HTTP deadlock should call a panel-specific health endpoint instead.
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
        hist_data = tool_call_duration_seconds.get()
        all_obs: list[float] = []
        for hinfo in hist_data.values():
            # Reconstruct from count/sum is lossy; read raw observations instead
            pass
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
