"""Output watcher (#8 / P2.4) — Home B.

Report the files actually written by an execution, robust against custom nodes
saving to nonstandard paths. Implemented as a snapshot-diff (no watchdog
dependency — Home A env lacks it): snapshot configured roots before a run, diff
after, return exactly the new files. A write outside output/ is still caught if
its root is in the watch list; unrelated pre-existing files don't false-positive.
"""

import threading
from pathlib import Path

from ..config import COMFYUI_INSTALL_DIR, COMFYUI_OUTPUT_DIR
from ._util import to_json

_lock = threading.Lock()
_snapshots: dict[str, set] = {}  # label -> set of file paths

_DEFAULT_ROOTS_NOTE = "output/, plus any extra roots you pass"


def _default_roots() -> list[Path]:
    roots = [Path(COMFYUI_OUTPUT_DIR)]
    temp = Path(COMFYUI_INSTALL_DIR) / "temp"
    if temp.exists():
        roots.append(temp)
    return [r for r in roots if r.exists()]


def _snapshot(roots: list[Path]) -> set:
    seen = set()
    for r in roots:
        for p in r.rglob("*"):
            if p.is_file():
                seen.add(str(p))
    return seen


TOOLS: list[dict] = [
    {
        "name": "watch_outputs_begin",
        "description": (
            "Snapshot output directories before running a workflow, so the files "
            "it writes can be detected afterward — even if a custom node saves to "
            "a nonstandard path. Pass a 'label' to correlate with watch_outputs_diff, "
            "and optional 'extra_roots' (list of dirs) to watch beyond output/."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Correlation label (e.g. prompt_id)."},
                "extra_roots": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Additional directories to watch.",
                },
            },
            "required": ["label"],
        },
    },
    {
        "name": "watch_outputs_diff",
        "description": (
            "After a workflow runs, return exactly the new files written since "
            "watch_outputs_begin for the same 'label'. Reports files even outside "
            "output/ if their root was watched; does not false-positive on "
            "pre-existing files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "label": {"type": "string", "description": "Same label used in watch_outputs_begin."},
            },
            "required": ["label"],
        },
    },
]


def _resolve_roots(extra_roots) -> list[Path]:
    roots = _default_roots()
    for r in extra_roots or []:
        if isinstance(r, str):
            p = Path(r)
            if p.exists():
                roots.append(p)
    return roots


def _handle_begin(tool_input: dict) -> str:
    label = tool_input.get("label")
    if not label or not isinstance(label, str):
        return to_json({"error": "label is required and must be a non-empty string."})
    roots = _resolve_roots(tool_input.get("extra_roots"))
    if not roots:
        return to_json({"error": "No watchable output roots exist.", "watched": []})
    with _lock:
        _snapshots[label] = _snapshot(roots)
        # Stash the roots alongside the snapshot for the diff.
        _snapshots[f"{label}::roots"] = {str(r) for r in roots}
    return to_json({"watching": True, "label": label, "roots": [str(r) for r in roots]})


def _handle_diff(tool_input: dict) -> str:
    label = tool_input.get("label")
    if not label or not isinstance(label, str):
        return to_json({"error": "label is required and must be a non-empty string."})
    with _lock:
        before = _snapshots.get(label)
        root_strs = _snapshots.get(f"{label}::roots")
    if before is None:
        return to_json({"error": f"No snapshot for label '{label}'. Call watch_outputs_begin first."})
    roots = [Path(r) for r in (root_strs or set())]
    after = _snapshot(roots)
    new_files = sorted(after - before)
    with _lock:
        _snapshots.pop(label, None)
        _snapshots.pop(f"{label}::roots", None)
    return to_json({"label": label, "new_files": new_files, "count": len(new_files)})


def handle(name: str, tool_input: dict) -> str:
    try:
        if name == "watch_outputs_begin":
            return _handle_begin(tool_input)
        if name == "watch_outputs_diff":
            return _handle_diff(tool_input)
        return to_json({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return to_json({"error": str(e)})
