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


def _check_llm() -> dict:
    """Check LLM provider can be constructed (no API call)."""
    try:
        from .llm import get_provider

        provider = get_provider()
        return {"status": "ok", "provider": LLM_PROVIDER, "class": type(provider).__name__}
    except Exception as e:
        return {"status": "error", "provider": LLM_PROVIDER, "error": str(e)}
