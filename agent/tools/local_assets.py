"""Local asset awareness (#7 / P3.2) — Home B.

list_assets(type, recent=N, search) — index ComfyUI/input/ + recent outputs so
reference/img2img workflows stop stalling on "give me the path". Reuses the
average-hash (aHash) perceptual hash from agent.brain.vision (pure Pillow — no
new dependency) to collapse perceptual duplicates. Caps/paginates for scale.
"""

from pathlib import Path

from ..config import COMFYUI_INSTALL_DIR, COMFYUI_OUTPUT_DIR
from ._util import to_json

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_DEFAULT_CAP = 200
_DEDUP_HAMMING = 5  # aHash distance <= this -> perceptual duplicate

TOOLS: list[dict] = [
    {
        "name": "list_assets",
        "description": (
            "List local image assets the artist can use: files in ComfyUI/input/ "
            "and recent outputs. Optional 'search' filters by filename substring; "
            "'recent' caps how many of the newest files to return; 'collapse_dupes' "
            "merges perceptually-identical images. Returns paths + metadata, "
            "paginated/capped for large directories."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["input", "output", "both"],
                    "description": "Which roots to scan (default 'both').",
                },
                "search": {"type": "string", "description": "Filename substring filter."},
                "recent": {"type": "integer", "description": f"Cap to N newest (default {_DEFAULT_CAP})."},
                "collapse_dupes": {"type": "boolean", "description": "Merge perceptual duplicates (default false)."},
            },
            "required": [],
        },
    },
]


def _roots(source: str) -> list[Path]:
    roots = []
    if source in ("input", "both"):
        roots.append(Path(COMFYUI_INSTALL_DIR) / "input")
    if source in ("output", "both"):
        roots.append(Path(COMFYUI_OUTPUT_DIR))
    return [r for r in roots if r.exists()]


def _scan(roots: list[Path], search: str | None) -> list[dict]:
    items = []
    for root in roots:
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in _IMAGE_EXTS:
                continue
            if search and search.lower() not in p.name.lower():
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            items.append({"path": str(p), "name": p.name, "size": st.st_size, "_mtime": st.st_mtime})
    items.sort(key=lambda d: d["_mtime"], reverse=True)
    return items


def _hamming(a: int, b: int) -> int:
    """Hamming distance between two integer perceptual hashes (matches vision.py)."""
    return bin(a ^ b).count("1")


def _collapse(items: list[dict]) -> tuple[list[dict], int]:
    """Collapse perceptual duplicates using aHash. Returns (kept, removed_count)."""
    try:
        from PIL import Image
        from ..brain.vision import _compute_average_hash
    except Exception:
        return items, 0  # dedup unavailable — return as-is, no crash

    kept: list[dict] = []
    hashes: list[int] = []
    removed = 0
    for it in items:
        try:
            h = _compute_average_hash(Image.open(it["path"]))
        except Exception:
            kept.append(it)
            continue
        dup = any(_hamming(h, kh) <= _DEDUP_HAMMING for kh in hashes)
        if dup:
            removed += 1
            continue
        hashes.append(h)
        kept.append(it)
    return kept, removed


def _handle_list_assets(tool_input: dict) -> str:
    source = tool_input.get("source", "both")
    if source not in ("input", "output", "both"):
        source = "both"
    search = tool_input.get("search")
    cap = tool_input.get("recent", _DEFAULT_CAP)
    if not isinstance(cap, int) or cap <= 0:
        cap = _DEFAULT_CAP

    roots = _roots(source)
    if not roots:
        return to_json({"assets": [], "note": f"No existing asset roots for source={source}."})

    items = _scan(roots, search)
    total_found = len(items)
    items = items[:cap]

    removed = 0
    if tool_input.get("collapse_dupes"):
        items, removed = _collapse(items)

    for it in items:
        it.pop("_mtime", None)

    result = {
        "assets": items,
        "count": len(items),
        "total_found": total_found,
    }
    if total_found > cap:
        result["note"] = f"Capped to {cap} newest of {total_found}. Use 'search' or raise 'recent'."
    if removed:
        result["deduped"] = removed
    return to_json(result)


def handle(name: str, tool_input: dict) -> str:
    try:
        if name == "list_assets":
            return _handle_list_assets(tool_input)
        return to_json({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return to_json({"error": str(e)})
