"""Vision analysis cache (#9 / P4.2) — Home B.

Exact-key cache for analyze_image so "verify every output" becomes affordable.
C-R8c: the key is SHA-256 over (image bytes || prompt) — the old 64-bit aHash
keyed on the image alone, so asking a DIFFERENT question about the same image
served the stale previous answer. Same image + same prompt hits instantly; a
changed image or a different prompt re-analyzes. In-memory only; old-format
entries are simply never hit again (it is a cache — no migration).
"""

import hashlib
import threading
from pathlib import Path

from ._util import to_json

_CACHE_MAX = 256

_lock = threading.Lock()
# list of (key:str, analysis:str) — small LRU-ish, newest appended.
_cache: list[tuple[str, str]] = []

TOOLS: list[dict] = [
    {
        "name": "analyze_image_cached",
        "description": (
            "Analyze an image, reusing a cached result when the same image "
            "was analyzed with the same prompt before (instant, no API call). "
            "A changed image or a different prompt is re-analyzed. Use instead "
            "of analyze_image when verifying many similar outputs. Pass "
            "'image_path' (+ optional 'prompt_used'); pass 'invalidate': true "
            "to clear the cache."
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


def _cache_key(image_bytes: bytes, prompt: str) -> str:
    """SHA-256 over (image bytes || prompt) — prompt-sensitive keying (C-R8c)."""
    h = hashlib.sha256()
    h.update(image_bytes)
    h.update(prompt.encode("utf-8"))
    return h.hexdigest()


def _lookup(key: str) -> str | None:
    for ck, analysis in reversed(_cache):
        if ck == key:
            return analysis
    return None


def _store(key: str, analysis: str) -> None:
    _cache.append((key, analysis))
    if len(_cache) > _CACHE_MAX:
        del _cache[0]


def _handle_analyze_image_cached(tool_input: dict) -> str:
    image_path = tool_input.get("image_path")
    if not image_path or not isinstance(image_path, str):
        return to_json({"error": "image_path is required and must be a non-empty string."})

    if tool_input.get("invalidate"):
        with _lock:
            _cache.clear()

    # Compute the cache key; if we can't, fall through to a live analysis.
    prompt_used = tool_input.get("prompt_used")
    prompt_used = prompt_used if isinstance(prompt_used, str) else ""
    key = None
    try:
        key = _cache_key(Path(image_path).read_bytes(), prompt_used)
    except FileNotFoundError:
        return to_json({"error": f"Image not found: {image_path}"})
    except Exception:
        key = None

    if key is not None:
        with _lock:
            hit = _lookup(key)
        if hit is not None:
            return to_json({"cached": True, "analysis": _safe_load(hit)})

    # Cache miss → delegate to the real analyze_image tool.
    from . import handle as _dispatch
    analysis = _dispatch("analyze_image", {
        k: v for k, v in tool_input.items() if k in ("image_path", "prompt_used", "workflow_context")
    })

    if key is not None and isinstance(analysis, str) and '"error"' not in analysis:
        with _lock:
            _store(key, analysis)

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
