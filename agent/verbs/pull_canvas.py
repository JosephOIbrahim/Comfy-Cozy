"""OPEN-IN verb engine — ``cozy pull``: artist canvas edits back into the session.

The inbound half of the canvas round-trip (WP-OPEN, Mile 6). The artist edits
the graph in their browser; this engine ingests those edits under ORCH.L8:

1. Acquire the artist's graph — the live canvas buffer (``get_canvas_state``,
   loopback only) or a saved workflow file (UI-format files convert through
   ``_ui_to_api``, which needs live ``/object_info``).
2. If a session workflow is loaded, re-enter the edits ONLY as
   ``jsonpatch.make_patch(current, artist_graph)`` applied through the
   ``apply_workflow_patch`` handler — validated, one undo step, diff
   continuity intact. ``load_workflow_from_data`` is never called on a live
   session: it would wipe the undo history, the base workflow, and the
   validated-since-mutation consent flag.
3. If NO session workflow is loaded, there is no history to destroy — initial
   ingest routes through ``load_workflow_from_data`` and the canvas graph
   becomes the session baseline.

Artist node adds, deletes, and rewires are ACCEPTED as validated patch
operations — freedom, not violations. The only refusal is a graph that breaks
the DAG (a connection pointing at a node that isn't there), and the refusal
carries the validation message in artist words. Nothing here opens a
non-loopback socket (ORCH.L7): all network traffic goes through the existing
``canvas_bridge`` / ``comfy_api`` seams aimed at ``COMFYUI_URL``.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import jsonpatch

from ..tools import canvas_bridge, ui_api_parser, workflow_patch
from ..tools._util import validate_path
from ..tools.workflow_parse import _extract_api_format, _trace_connections


def _is_link(value: object) -> bool:
    """True when an input value is a connection ``[source_node_id, output_index]``."""
    return isinstance(value, list) and len(value) == 2


def _normalize_graph(graph: dict) -> dict:
    """Keep only well-formed API-format node entries, with string node ids."""
    return {
        str(nid): node
        for nid, node in graph.items()
        if isinstance(node, dict) and "class_type" in node
    }


def _broken_links(graph: dict) -> list[str]:
    """Return human-worded descriptions of connections that break the DAG.

    A connection whose source node id is absent from the graph is a dangling
    link — executing it would fail, so ingest refuses and explains. Uses the
    same connection tracer the validator uses; output order is deterministic.
    """
    problems: list[str] = []
    for conn in _trace_connections(graph):
        if str(conn["from_node"]) not in graph:
            problems.append(
                f"{conn['to_class']} (node {conn['to_node']}) input "
                f"'{conn['to_input']}' points at node {conn['from_node']}, "
                "which is not in the graph"
            )
    return problems


def _summarize_changes(current: dict, artist: dict) -> dict:
    """Structured change summary between the session graph and the artist graph.

    Returns nodes added/removed (id + class_type), literal parameter changes
    (node/param/old -> new), and a count of rewired connections. A node whose
    class_type changed under the same id is reported as removed + added.
    """
    added: list[dict] = []
    removed: list[dict] = []
    params_changed: list[dict] = []
    links_rewired = 0

    cur_ids, art_ids = set(current), set(artist)
    for nid in sorted(art_ids - cur_ids):
        added.append({"id": nid, "class_type": artist[nid].get("class_type", "?")})
    for nid in sorted(cur_ids - art_ids):
        removed.append({"id": nid, "class_type": current[nid].get("class_type", "?")})

    for nid in sorted(cur_ids & art_ids):
        cur_node, art_node = current[nid], artist[nid]
        if cur_node.get("class_type") != art_node.get("class_type"):
            removed.append({"id": nid, "class_type": cur_node.get("class_type", "?")})
            added.append({"id": nid, "class_type": art_node.get("class_type", "?")})
            continue
        cur_in = cur_node.get("inputs", {}) or {}
        art_in = art_node.get("inputs", {}) or {}
        for key in sorted(set(cur_in) | set(art_in)):
            old, new = cur_in.get(key), art_in.get(key)
            if old == new:
                continue
            if _is_link(old) or _is_link(new):
                links_rewired += 1
            else:
                params_changed.append({"node": nid, "param": key, "old": old, "new": new})

    return {
        "nodes_added": added,
        "nodes_removed": removed,
        "params_changed": params_changed,
        "links_rewired": links_rewired,
    }


def _summary_phrase(summary: dict) -> str:
    """One human sentence fragment out of a change summary, deterministic order."""
    parts: list[str] = []
    n_add = len(summary["nodes_added"])
    n_rem = len(summary["nodes_removed"])
    n_par = len(summary["params_changed"])
    n_rew = summary["links_rewired"]
    if n_add:
        parts.append(f"{n_add} node{'s' if n_add != 1 else ''} added")
    if n_rem:
        parts.append(f"{n_rem} node{'s' if n_rem != 1 else ''} removed")
    if n_par:
        parts.append(f"{n_par} parameter{'s' if n_par != 1 else ''} changed")
    if n_rew:
        parts.append(f"{n_rew} connection{'s' if n_rew != 1 else ''} rewired")
    return ", ".join(parts) if parts else "no visible changes"


def _result(
    *,
    ok: bool,
    pulled: bool,
    applied: bool,
    message: str,
    source: str,
    initial_load: bool = False,
    refused: bool = False,
    node_count: int = 0,
    changes: int = 0,
    summary: dict | None = None,
) -> dict:
    """Assemble the uniform pull_canvas result dict."""
    return {
        "ok": ok,
        "pulled": pulled,
        "applied": applied,
        "initial_load": initial_load,
        "refused": refused,
        "source": source,
        "node_count": node_count,
        "changes": changes,
        "summary": summary,
        "message": message,
    }


def _acquire_from_canvas() -> tuple[dict | None, str | None]:
    """Fetch the artist-edited graph from the live canvas buffer.

    Returns ``(graph, error_message)`` — exactly one is non-None, except the
    empty-buffer case which returns ``(None, <plain 'nothing to pull' note>)``.
    """
    state = json.loads(canvas_bridge.handle("get_canvas_state", {}))
    if "error" in state:
        return None, (
            f"Couldn't read the canvas: {state['error']} Your session workflow is untouched."
        )
    workflow = state.get("workflow")
    if not workflow:
        note = state.get("note", "")
        return None, (
            "There's nothing to pull yet — the canvas hasn't reported an artist edit. "
            f"{note} Make a change in the browser, then run `cozy pull` again."
        ).strip()
    if not isinstance(workflow, dict):
        return None, (
            "The canvas buffer didn't look like a workflow graph. "
            "Your session workflow is untouched."
        )
    return workflow, None


def _acquire_from_file(file: str | None) -> tuple[dict | None, str | None]:
    """Load an artist graph from a saved workflow JSON file (UI or API format).

    UI-format files convert through ``_ui_to_api``, which needs live ComfyUI
    for ``/object_info`` — when ComfyUI is down the conversion degrades to a
    clear message instead of a crash.
    """
    if not file:
        return None, "Pulling from a file needs a path: `cozy pull --file your_workflow.json`."
    err = validate_path(file, must_exist=True)
    if err:
        return None, err
    try:
        data = json.loads(Path(file).read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, (
            f"{file} isn't valid JSON — it may be truncated. "
            "Re-save the workflow from ComfyUI and try again."
        )
    if not isinstance(data, dict):
        return None, f"{file} doesn't contain a workflow (expected a JSON object)."

    nodes, fmt = _extract_api_format(data)
    if fmt != "ui_only":
        if not nodes:
            return None, f"No nodes found in {file}."
        return nodes, None

    # UI-only: convert via the live /object_info schema (never guessed).
    try:
        object_info = ui_api_parser._get_object_info()
    except (httpx.ConnectError, httpx.TimeoutException):
        return None, (
            f"{file} is a UI-format workflow, and converting it needs ComfyUI running "
            "(the node schemas come from /object_info). Start ComfyUI and try again, "
            "or re-export the file with Save (API Format)."
        )
    api_graph, unmapped = ui_api_parser._ui_to_api(data, object_info)
    if unmapped:
        names = ", ".join(f"{u['class_type']} (node {u['node_id']})" for u in unmapped)
        return None, (
            f"Couldn't convert {file}: these nodes aren't installed in this ComfyUI, "
            f"so their settings can't be mapped honestly: {names}. "
            "Install the missing node packs, or re-export with Save (API Format)."
        )
    if not api_graph:
        return None, f"No convertible nodes found in {file}."
    return api_graph, None


def pull_canvas(source: str = "canvas", file: str | None = None) -> dict:
    """Ingest the artist's edited graph into the session as a validated, undoable patch.

    Args:
        source: ``"canvas"`` (default) pulls the live browser buffer through the
            canvas bridge; ``"file"`` loads a saved workflow JSON (UI-format
            files convert via ``/object_info``, so ComfyUI must be running).
        file: Path to the workflow JSON when ``source="file"``.

    Returns:
        A structured result dict with keys ``ok``, ``pulled`` (a graph was
        acquired), ``applied`` (the session changed), ``initial_load``,
        ``refused`` (DAG-breaking graph rejected), ``source``, ``node_count``,
        ``changes`` (RFC6902 op count), ``summary`` (nodes added/removed,
        params changed, links rewired), and ``message`` in artist words.
    """
    if source not in ("canvas", "file"):
        return _result(
            ok=False,
            pulled=False,
            applied=False,
            source=source,
            message=f"Unknown source '{source}' — use 'canvas' (live browser) or 'file'.",
        )

    if source == "canvas":
        raw_graph, err = _acquire_from_canvas()
    else:
        raw_graph, err = _acquire_from_file(file)
    if err is not None:
        return _result(ok=False, pulled=False, applied=False, source=source, message=err)

    artist_graph = _normalize_graph(raw_graph)
    if not artist_graph:
        return _result(
            ok=False,
            pulled=False,
            applied=False,
            source=source,
            message=(
                "The pulled graph had no usable nodes — it may be empty or stale. "
                "Your session workflow is untouched."
            ),
        )
    node_count = len(artist_graph)

    # ORCH.L8: refuse only what breaks the DAG — and say exactly what broke.
    broken = _broken_links(artist_graph)
    if broken:
        listing = "; ".join(broken)
        return _result(
            ok=False,
            pulled=True,
            applied=False,
            refused=True,
            source=source,
            node_count=node_count,
            message=(
                "This graph has a connection going nowhere, so running it would fail: "
                f"{listing}. Fix the wiring on the canvas (or delete the dangling link) "
                "and pull again. Your session workflow is untouched."
            ),
        )

    current = workflow_patch._get_state()["current_workflow"]

    # No session workflow: initial ingest. There is no undo history, base, or
    # consent flag to destroy — loading here is legitimate (and the only path).
    if current is None:
        origin = "<canvas pull>" if source == "canvas" else str(file)
        load_err = workflow_patch.load_workflow_from_data(artist_graph, source=origin)
        if load_err:
            return _result(
                ok=False,
                pulled=True,
                applied=False,
                source=source,
                node_count=node_count,
                message=f"Couldn't start a session from the pulled graph: {load_err}",
            )
        return _result(
            ok=True,
            pulled=True,
            applied=True,
            initial_load=True,
            source=source,
            node_count=node_count,
            message=(
                f"No session workflow was loaded, so your graph ({node_count} nodes) "
                "just became the session baseline. Nothing was overwritten — the "
                "session simply starts from what you built."
            ),
        )

    # Live session: edits re-enter ONLY as a validated patch (ORCH.L8).
    patch_ops = jsonpatch.make_patch(current, artist_graph).patch
    if not patch_ops:
        return _result(
            ok=True,
            pulled=True,
            applied=False,
            source=source,
            node_count=node_count,
            message="Canvas and session already match — nothing to pull.",
        )

    summary = _summarize_changes(current, artist_graph)
    apply_result = json.loads(
        workflow_patch.handle("apply_workflow_patch", {"patches": patch_ops})
    )
    if "error" in apply_result:
        return _result(
            ok=False,
            pulled=True,
            applied=False,
            refused=True,
            source=source,
            node_count=node_count,
            summary=summary,
            message=(
                f"The edits couldn't be applied: {apply_result['error']} "
                "Your session workflow is untouched — nothing was half-applied."
            ),
        )

    phrase = _summary_phrase(summary)
    return _result(
        ok=True,
        pulled=True,
        applied=True,
        source=source,
        node_count=node_count,
        changes=len(patch_ops),
        summary=summary,
        message=(
            f"Pulled your canvas edits into the session: {phrase}. It all landed as "
            "one validated patch, so the whole pull is one undo away — tell the agent "
            '"undo" (undo_workflow_patch) and the session steps back to before it.'
        ),
    )


def render_pull_result(result: dict) -> str:
    """Render a pull_canvas result for the terminal, in artist words.

    Node adds and deletes read as accepted creative decisions, not warnings.
    Returns a plain multi-line string; the caller prints it.
    """
    lines: list[str] = [result["message"]]
    summary = result.get("summary")
    if result.get("applied") and summary:
        for node in summary["nodes_added"]:
            lines.append(f"  + {node['class_type']} joined as node {node['id']}")
        for node in summary["nodes_removed"]:
            lines.append(f"  - {node['class_type']} (node {node['id']}) is out — your call")
        for change in summary["params_changed"]:
            lines.append(
                f"  ~ {change['param']} on node {change['node']}: "
                f"{change['old']} -> {change['new']}"
            )
        if summary["links_rewired"]:
            n = summary["links_rewired"]
            lines.append(f"  ~ {n} connection{'s' if n != 1 else ''} rewired")
    return "\n".join(lines)
