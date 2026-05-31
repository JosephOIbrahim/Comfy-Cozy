"""comfy_agent_bridge — ComfyUI custom node pack (Home A).

Server-side surface for the agent↔canvas bridge:
  - Phase 0 (#1 push): POST /agent/push_workflow → broadcasts `agent.load_workflow`
    so connected browser tabs reload the pushed graph.

Idempotent: registering the same route twice on hot-reload is guarded so it
does not stack handlers or throw. No third-party imports beyond aiohttp/server
(both ship with ComfyUI).
"""

import logging
import time

from .profiling import TimingCapture

log = logging.getLogger("comfy_agent_bridge")

# Guard so a hot-reload (module re-import) does not re-register the route and
# stack duplicate handlers (Invariant: idempotent registration).
_ROUTES_REGISTERED = False

# #5: per-node execution timing, fed by a send_sync observer (wired below).
_capture = TimingCapture(time.perf_counter)


def _register_routes() -> None:
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return
    try:
        from aiohttp import web
        from server import PromptServer
    except Exception as exc:  # pragma: no cover - only in a live ComfyUI process
        log.warning("comfy_agent_bridge: server not available, routes skipped: %s", exc)
        return

    instance = getattr(PromptServer, "instance", None)
    if instance is None:
        log.warning("comfy_agent_bridge: PromptServer.instance not ready, routes skipped")
        return

    @instance.routes.post("/agent/push_workflow")
    async def push_workflow(request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid json"}, status=400)
        workflow = data.get("workflow") if isinstance(data, dict) else None
        if not isinstance(workflow, dict):
            return web.json_response(
                {"ok": False, "error": "missing or malformed 'workflow'"}, status=400
            )
        # send_sync broadcasts to ALL connected clients — every open tab reloads.
        instance.send_sync("agent.load_workflow", data)
        return web.json_response({"ok": True})

    # Phase 1B (#1 read-back): the frontend POSTs the artist-edited graph here
    # (debounced); we buffer the latest. The agent PULLs it via GET. This is the
    # PULL design — MCP stdio cannot receive server-pushed events.
    _canvas_buffer = {"workflow": None, "seen": False}

    @instance.routes.post("/agent/canvas_changed")
    async def canvas_changed(request):
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "invalid json"}, status=400)
        wf = data.get("workflow") if isinstance(data, dict) else None
        if not isinstance(wf, dict):
            return web.json_response(
                {"ok": False, "error": "missing or malformed 'workflow'"}, status=400
            )
        _canvas_buffer["workflow"] = wf
        _canvas_buffer["seen"] = True
        return web.json_response({"ok": True})

    @instance.routes.get("/agent/canvas_state")
    async def canvas_state(request):
        if not _canvas_buffer["seen"]:
            return web.json_response(
                {"workflow": None, "note": "No artist edit captured yet."}
            )
        return web.json_response({"workflow": _canvas_buffer["workflow"]})

    # Phase 1B (#5 profiling): observe the execution events ComfyUI already
    # broadcasts by wrapping send_sync once (idempotent via the _agent_wrapped
    # flag). The wrapper NEVER swallows the original call and isolates observer
    # errors so it cannot break event delivery.
    if not getattr(instance.send_sync, "_agent_wrapped", False):
        _orig_send_sync = instance.send_sync

        def _send_sync_observed(event, data, sid=None):
            try:
                _capture.observe(event, data)
            except Exception:  # observation must never break the event stream
                pass
            return _orig_send_sync(event, data, sid)

        _send_sync_observed._agent_wrapped = True
        instance.send_sync = _send_sync_observed

    @instance.routes.get("/agent/exec_profile/{prompt_id}")
    async def exec_profile(request):
        pid = request.match_info.get("prompt_id")
        prof = _capture.profile(pid)
        if prof is None:
            return web.json_response(
                {"error": f"No profile for prompt_id '{pid}' (never ran or not captured).",
                 "nodes": []},
                status=404,
            )
        return web.json_response(prof)

    _ROUTES_REGISTERED = True
    log.info("comfy_agent_bridge: routes registered")


_register_routes()

NODE_CLASS_MAPPINGS: dict = {}
NODE_DISPLAY_NAME_MAPPINGS: dict = {}
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
