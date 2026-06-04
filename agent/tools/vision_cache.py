"""Vision analysis cache (#9 / P4.2) — Home B.

pHash-based cache for analyze_image so "verify every output" becomes affordable.
A perceptually-identical image returns the cached analysis instantly; a changed
image re-analyzes; a near-threshold pHash does NOT false-dedup two different
images (boundary-safe). Reuses the average-hash from agent.brain.vision.
"""

import threading

from ._util import to_json

# aHash hamming distance <= this -> treat as same image (cache hit).
# Kept tight so two genuinely different images near the boundary do NOT collide.
_CACHE_HAMMING = 2
_CACHE_MAX = 256

_lock = threading.Lock()
# list of (hash:int, analysis:str) — small LRU-ish, newest appended.
_cache: list[tuple[int, str]] = []

TOOLS: list[dict] = [
    {
        "name": "analyze_image_cached",
        "description": (
            "Analyze an image, reusing a cached result when a perceptually "
            "identical image was analyzed before (instant, no API call). A "
            "changed image is re-analyzed. Use instead of analyze_image when "
            "verifying many similar outputs. Pass 'image_path' (+ optional "
            "'prompt_used'); pass 'invalidate': true to clear the cache."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Absolute path to the image."},
                "prompt_used": {"type": "string", "description": "Prompt used (forwarded to analyze_image)."},
                "invalidate": {"type": "boolean", "description": "Clear the cache before running."},
            },
            "required": ["image_path"],
        },
    },
]


def _hamming(a: int, b: int) -> int:
    """Hamming distance between two integer perceptual hashes (matches vision.py)."""
    return bin(a ^ b).count("1")


def _lookup(h: int) -> str | None:
    for ch, analysis in reversed(_cache):
        if _hamming(h, ch) <= _CACHE_HAMMING:
            return analysis
    return None


def _store(h: int, analysis: str) -> None:
    _cache.append((h, analysis))
    if len(_cache) > _CACHE_MAX:
        del _cache[0]


def _handle_analyze_image_cached(tool_input: dict) -> str:
    image_path = tool_input.get("image_path")
    if not image_path or not isinstance(image_path, str):
        return to_json({"error": "image_path is required and must be a non-empty string."})

    if tool_input.get("invalidate"):
        with _lock:
            _cache.clear()

    # Compute pHash; if we can't, fall through to a live analysis (no cache).
    img_hash = None
    try:
        from PIL import Image
        from ..brain.vision import _compute_average_hash
        with Image.open(image_path) as _img:
            img_hash = _compute_average_hash(_img)
    except FileNotFoundError:
        return to_json({"error": f"Image not found: {image_path}"})
    except Exception:
        img_hash = None

    if img_hash is not None:
        with _lock:
            hit = _lookup(img_hash)
        if hit is not None:
            return to_json({"cached": True, "analysis": _safe_load(hit)})

    # Cache miss → delegate to the real analyze_image tool.
    from . import handle as _dispatch
    analysis = _dispatch("analyze_image", {
        k: v for k, v in tool_input.items() if k in ("image_path", "prompt_used", "workflow_context")
    })

    if img_hash is not None and isinstance(analysis, str) and '"error"' not in analysis:
        with _lock:
            _store(img_hash, analysis)

    return to_json({"cached": False, "analysis": _safe_load(analysis)})


def _safe_load(s):
    import json
    try:
        return json.loads(s) if isinstance(s, str) else s
    except Exception:
        return s


def handle(name: str, tool_input: dict) -> str:
    try:
        if name == "analyze_image_cached":
            return _handle_analyze_image_cached(tool_input)
        return to_json({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return to_json({"error": str(e)})
