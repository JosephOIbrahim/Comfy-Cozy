"""OPEN-OUT verb engine — ``cozy open``: session workflow to the live canvas.

One command from session to editable canvas (WP-OPEN, OPEN-OUT half):

1. Check ComfyUI liveness first — if it's down there is no canvas to open,
   so return a human-worded status instead of launching a dead tab.
2. If a session workflow is loaded (and ``push=True``), push it through the
   existing ``push_workflow_to_canvas`` bridge seam — the POST is never
   re-implemented here.
3. Launch (or focus) the artist's browser at ``COMFYUI_URL`` via
   ``webbrowser.open``.

The URL derives ONLY from ``agent.config.COMFYUI_URL`` (loopback by default —
ORCH.L7). Two v1 realities are surfaced in the returned message, in artist
words rather than warning spam: node positions are laid out fresh by the
frontend importer (not preserved), and the push broadcasts to every connected
browser tab. OPEN-IN (ingesting artist edits back) is a separate lane and is
deliberately absent here (ORCH.L8).
"""

from __future__ import annotations

import json
import webbrowser

from .. import config
from ..tools import canvas_bridge, comfy_api
from ..tools.workflow_patch import _get_state


def open_canvas(push: bool = True) -> dict:
    """Open the ComfyUI canvas in the artist's browser, pushing the session workflow first.

    Args:
        push: When True (default) and a session workflow is loaded, push it to
            the canvas through the existing bridge before opening the browser.
            When False, just open the browser at the ComfyUI URL.

    Returns:
        A structured status dict with keys:
            ``opened`` (bool) — a browser launch/focus was triggered,
            ``pushed`` (bool) — the session workflow landed on the canvas,
            ``node_count`` (int) — nodes in the session workflow (0 if none),
            ``url`` (str) — the ComfyUI URL used (from config, loopback-only),
            ``message`` (str) — what happened, in artist words.
    """
    url = config.COMFYUI_URL

    # 1 — liveness first (rule 7): never open a tab onto a dead server.
    liveness = json.loads(comfy_api.handle("is_comfyui_running", {}))
    if not liveness.get("running", False):
        return {
            "opened": False,
            "pushed": False,
            "node_count": 0,
            "url": url,
            "message": (
                f"ComfyUI is not running at {url}, so there is no canvas to open yet. "
                "Start ComfyUI, then run `cozy open` again."
            ),
        }

    # 2 — push the session workflow through the existing bridge seam.
    workflow = _get_state()["current_workflow"]
    node_count = len(workflow) if workflow else 0
    pushed = False
    if push and workflow:
        result = json.loads(
            canvas_bridge.handle(
                "push_workflow_to_canvas",
                {"workflow": workflow, "reason": "cozy open"},
            )
        )
        if result.get("pushed"):
            pushed = True
            push_note = (
                f"Your session workflow ({node_count} nodes) is now on the canvas in every "
                "open ComfyUI tab — the layout is freshly arranged, so node positions from "
                "an earlier canvas session aren't preserved."
            )
        else:
            push_note = (
                "The workflow push didn't land: "
                f"{result.get('error', 'unknown push failure')} "
                "Your session workflow is untouched — fix the above and run `cozy open` again."
            )
    elif not workflow:
        push_note = "No session workflow is loaded, so the canvas opens as-is."
    else:
        push_note = "Push skipped — the canvas opens with whatever it already had."

    # 3 — launch/focus the browser at the config-derived URL.
    opened = bool(webbrowser.open(url))
    if opened:
        message = f"Opened ComfyUI at {url}. {push_note}"
    else:
        message = (
            f"Couldn't launch a browser here — open {url} in your browser yourself. {push_note}"
        )

    return {
        "opened": opened,
        "pushed": pushed,
        "node_count": node_count,
        "url": url,
        "message": message,
    }
