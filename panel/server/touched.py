"""Per-session touched-set tracking for write-back v1 (Tier 1+2).

The agent mutates the server-side ``current_workflow`` via
``_handle_apply_patch`` / ``_handle_connect_nodes`` / ``_handle_set_input``.
Without this module, the panel's ``pushAgentToCanvas`` would iterate every
node in the cached workflow and write every widget/link that differs from
the live canvas — including slots the director just hand-edited (F-1
stale-cache clobber race; see ``harness/CAPSULE.md``).

This module records a per-session snapshot of "the last workflow successfully
pushed to the canvas." ``compute_touched()`` diffs the current cache against
that snapshot and returns only the slots the agent has changed since the
last push. The frontend push iterates those slots only, never touching
director-edited neighbours.

Lifecycle hooks:

  * ``/comfy-cozy/load-workflow-data`` → ``record_last_pushed`` after a
    successful canvas-sync POST (snapshot = the freshly-loaded workflow).
  * ``/comfy-cozy/get-workflow-api-with-touched`` → ``compute_touched``
    reads against the snapshot.
  * ``/comfy-cozy/ack-push`` → ``record_last_pushed`` after the panel
    confirms it applied the previous touched-set.
  * ``/comfy-cozy/reset`` → ``record_last_pushed`` against the post-reset
    state.
  * Chat WebSocket disconnect → ``clear_session`` drops the snapshot.

Thread-safe via a single module-level RLock. Storage is in-memory; lifetime
is the panel server process.
"""

from __future__ import annotations

import copy
import logging
import threading
from typing import Any

log = logging.getLogger("comfy-cozy.touched")

# Internal storage: session_id -> snapshot of last-pushed workflow
_snapshots: dict[str, dict[str, Any]] = {}
_lock = threading.RLock()


def record_last_pushed(session_id: str, workflow: dict[str, Any] | None) -> None:
    """Snapshot ``workflow`` as the last-pushed state for ``session_id``.

    The snapshot is a deep copy — callers may continue to mutate the
    original without affecting the touched-set baseline.

    ``None`` is a no-op (no snapshot recorded, no error raised).
    """
    if workflow is None:
        return
    with _lock:
        _snapshots[session_id] = copy.deepcopy(workflow)


def compute_touched(
    session_id: str, current_workflow: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Return the list of slots the agent has changed since the last push.

    Each entry has shape::

        {"node_id":    str,
         "input_name": str,
         "kind":       "widget" | "link" | "unknown",
         "old_value":  <prior value or None if added>,
         "new_value":  <current value or None if removed>}

    ``kind`` is determined by classifying ``new_value`` (or ``old_value``
    if new is ``None`` — i.e. a disconnect).

    First call for a session with no recorded snapshot lazily initializes
    the snapshot to ``current_workflow`` and returns ``[]``. This is the
    safe-default for cases where the lifecycle hooks haven't fired yet
    (e.g. chat WebSocket opened but no workflow load has occurred). It
    avoids accidentally treating a brand-new session as having every slot
    "touched."
    """
    if current_workflow is None:
        return []

    with _lock:
        snapshot = _snapshots.get(session_id)
        if snapshot is None:
            _snapshots[session_id] = copy.deepcopy(current_workflow)
            return []

        return _diff(snapshot, current_workflow)


def clear_session(session_id: str) -> None:
    """Drop the snapshot for ``session_id`` (safe if absent)."""
    with _lock:
        _snapshots.pop(session_id, None)


def _diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Compute the touched-set as the input-level diff of ``before -> after``.

    Only ``workflow[node_id]["inputs"][input_name]`` is compared. Node
    adds, deletes, and class-type changes are NOT touched-set entries —
    they're Tier-3 deltas handled by L-4 detection on the frontend.
    """
    entries: list[dict[str, Any]] = []
    all_node_ids = set(before.keys()) | set(after.keys())

    for node_id in all_node_ids:
        before_node = before.get(node_id) or {}
        after_node = after.get(node_id) or {}
        if not isinstance(before_node, dict) or not isinstance(after_node, dict):
            continue
        before_inputs = before_node.get("inputs", {}) or {}
        after_inputs = after_node.get("inputs", {}) or {}
        if not isinstance(before_inputs, dict) or not isinstance(after_inputs, dict):
            continue

        all_input_names = set(before_inputs.keys()) | set(after_inputs.keys())
        for input_name in all_input_names:
            old_value = before_inputs.get(input_name)
            new_value = after_inputs.get(input_name)
            if old_value == new_value:
                continue
            # Classify by new_value; fall back to old_value when new is None
            # (e.g., a disconnect — new is None but the kind is "link").
            kind = _classify(new_value)
            if kind == "unknown":
                kind = _classify(old_value)
            entries.append(
                {
                    "node_id": node_id,
                    "input_name": input_name,
                    "kind": kind,
                    "old_value": old_value,
                    "new_value": new_value,
                }
            )

    # Sort for determinism (helps tests + debugging).
    entries.sort(key=lambda e: (str(e["node_id"]), str(e["input_name"])))
    return entries


def _classify(value: Any) -> str:
    """Classify ``value`` as ``"link"``, ``"widget"``, or ``"unknown"``.

    A link is a 2-element list of the form ``[from_node_id_str,
    from_output_int]`` — the API representation written by
    ``connect_nodes``.
    """
    if value is None:
        return "unknown"
    if (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str)
        and isinstance(value[1], int)
        and not isinstance(value[1], bool)  # bool subclasses int — exclude
    ):
        return "link"
    if isinstance(value, (str, int, float, bool)):
        return "widget"
    return "unknown"
