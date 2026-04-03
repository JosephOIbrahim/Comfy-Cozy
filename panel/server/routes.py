"""Server routes for the Comfy Cozy Panel.

Thin REST wrappers mounted on ComfyUI's PromptServer via aiohttp.
Each route translates HTTP requests into agent tool calls.
Covers the full tool surface: load, edit, execute, discover.
"""

import json
import logging

from aiohttp import web

log = logging.getLogger("superduper-panel")

_MAX_REQUEST_BYTES = 10 * 1024 * 1024  # 10 MB


def _too_large(request):
    """Return a 413 response if the request body exceeds _MAX_REQUEST_BYTES, else None."""
    if request.content_length and request.content_length > _MAX_REQUEST_BYTES:
        return web.json_response({"error": "Payload too large"}, status=413)
    return None


def _tool_call(tool_name, tool_input):
    """Call an agent tool and return the JSON string result."""
    from agent.tools import handle
    return handle(tool_name, tool_input)


def setup_routes():
    """Mount panel routes on PromptServer."""
    try:
        from server import PromptServer
        routes = PromptServer.instance.routes
    except Exception:
        log.debug("PromptServer not available — routes not mounted")
        return

    # ── Health ─────────────────────────────────────────────────────

    @routes.get("/superduper-panel/health")
    async def health(request):
        return web.json_response({"status": "ok", "panel": "superduper-panel"})

    # ── Graph State (CognitiveGraphEngine) ─────────────────────────

    @routes.get("/superduper-panel/graph-state")
    async def graph_state(request):
        """Read CognitiveGraphEngine state."""
        try:
            from agent.tools.workflow_patch import get_current_workflow, get_engine
            workflow = get_current_workflow()
            engine = get_engine()

            result = {
                "has_workflow": workflow is not None,
                "node_count": len(workflow) if workflow else 0,
                "has_engine": engine is not None,
                "delta_count": len(engine.delta_stack) if engine else 0,
                "integrity": None,
                "deltas": [],
                "nodes": {},
            }

            if engine:
                ok, errors = engine.verify_stack_integrity()
                result["integrity"] = {"intact": ok, "errors": errors}
                for delta in engine.delta_stack:
                    result["deltas"].append({
                        "layer_id": delta.layer_id,
                        "opinion": delta.opinion,
                        "description": delta.description,
                        "timestamp": delta.timestamp,
                        "mutations": delta.mutations,
                    })

            if workflow:
                for nid, ndata in sorted(workflow.items()):
                    if isinstance(ndata, dict) and "class_type" in ndata:
                        result["nodes"][nid] = {
                            "class_type": ndata["class_type"],
                            "inputs": ndata.get("inputs", {}),
                        }

            return web.json_response(result)
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    # ── Workflow Loading ───────────────────────────────────────────

    @routes.post("/superduper-panel/load-workflow")
    async def load_workflow(request):
        """Load a workflow from a file path."""
        try:
            rejected = _too_large(request)
            if rejected:
                return rejected
            body = await request.json()
            result = _tool_call("load_workflow", body)
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.post("/superduper-panel/load-workflow-data")
    async def load_workflow_data(request):
        """Load a workflow from raw JSON data (canvas injection).

        This is the critical bridge: the frontend sends the live canvas
        graph here on every change. The agent can then repair, modify,
        and execute the workflow.
        """
        try:
            rejected = _too_large(request)
            if rejected:
                return rejected
            body = await request.json()
            workflow_data = body.get("data", {})
            source = body.get("source", "<panel>")

            from agent.tools.workflow_patch import load_workflow_from_data
            err = load_workflow_from_data(workflow_data, source=source)
            if err:
                return web.json_response({"error": err}, status=400)

            result = {"loaded": True}

            # Count nodes for context
            nodes = {
                k: v for k, v in workflow_data.items()
                if isinstance(v, dict) and "class_type" in v
            }
            result["node_count"] = len(nodes)

            # Check for missing nodes (best-effort, non-blocking)
            try:
                missing_json = _tool_call("find_missing_nodes", {})
                import json as _json
                missing_data = _json.loads(missing_json)
                missing = missing_data.get("missing", [])
                if missing:
                    result["missing_nodes"] = [
                        {"class_type": m.get("class_type", "?"), "pack": m.get("pack", "")}
                        for m in missing
                    ]
            except Exception:
                pass  # Missing node check is best-effort

            return web.json_response(result)
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    # ── Workflow Mutation ──────────────────────────────────────────

    @routes.post("/superduper-panel/set-input")
    async def set_input(request):
        """Push a delta layer via set_input tool."""
        try:
            rejected = _too_large(request)
            if rejected:
                return rejected
            body = await request.json()
            result = _tool_call("set_input", body)
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.post("/superduper-panel/add-node")
    async def add_node(request):
        """Add a new node to the workflow."""
        try:
            rejected = _too_large(request)
            if rejected:
                return rejected
            body = await request.json()
            result = _tool_call("add_node", body)
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.post("/superduper-panel/connect-nodes")
    async def connect_nodes(request):
        """Connect two nodes in the workflow."""
        try:
            rejected = _too_large(request)
            if rejected:
                return rejected
            body = await request.json()
            result = _tool_call("connect_nodes", body)
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.post("/superduper-panel/apply-patch")
    async def apply_patch(request):
        """Apply RFC6902 patches to the workflow."""
        try:
            rejected = _too_large(request)
            if rejected:
                return rejected
            body = await request.json()
            result = _tool_call("apply_workflow_patch", body)
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.post("/superduper-panel/rollback")
    async def rollback(request):
        """Undo the last delta layer."""
        try:
            result = _tool_call("undo_workflow_patch", {})
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.post("/superduper-panel/reset")
    async def reset(request):
        """Reset workflow to base state."""
        try:
            result = _tool_call("reset_workflow", {})
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.get("/superduper-panel/diff")
    async def diff(request):
        """Get diff from base workflow."""
        try:
            result = _tool_call("get_workflow_diff", {})
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.get("/superduper-panel/editable-fields")
    async def editable_fields(request):
        """Get editable fields of the loaded workflow."""
        try:
            result = _tool_call("get_editable_fields", {})
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    # ── Execution ─────────────────────────────────────────────────

    @routes.post("/superduper-panel/validate")
    async def validate(request):
        """Pre-execution validation."""
        try:
            result = _tool_call("validate_before_execute", {})
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.post("/superduper-panel/execute")
    async def execute(request):
        """Execute the loaded workflow on ComfyUI."""
        try:
            rejected = _too_large(request)
            if rejected:
                return rejected
            body = await request.json() if request.content_length else {}
            result = _tool_call("execute_workflow", body)
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.get("/superduper-panel/execution-status")
    async def execution_status(request):
        """Check execution status."""
        try:
            prompt_id = request.query.get("prompt_id", "")
            result = _tool_call("get_execution_status", {"prompt_id": prompt_id})
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    # ── Discovery ─────────────────────────────────────────────────

    @routes.get("/superduper-panel/node-info")
    async def node_info(request):
        """Get info for a specific node type."""
        try:
            node_type = request.query.get("node_type", "")
            result = _tool_call("get_node_info", {"node_type": node_type})
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.get("/superduper-panel/models")
    async def models(request):
        """List models by type."""
        try:
            model_type = request.query.get("model_type", "checkpoints")
            result = _tool_call("list_models", {"model_type": model_type, "format": "summary"})
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.get("/superduper-panel/system-stats")
    async def system_stats(request):
        """Get ComfyUI system stats."""
        try:
            result = _tool_call("get_system_stats", {})
            return web.Response(text=result, content_type="application/json")
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    # ── Cognitive Layer ────────────────────────────────────────────

    @routes.get("/superduper-panel/experience")
    async def experience(request):
        """Read ExperienceAccumulator stats."""
        try:
            from src.cognitive.experience.accumulator import ExperienceAccumulator
            acc = ExperienceAccumulator()
            return web.json_response(acc.get_stats())
        except ImportError:
            return web.json_response({
                "total_generations": 0,
                "learning_phase": "prior",
                "experience_weight": 0,
                "message": "Cognitive module not available",
            })
        except Exception as e:
            log.error("Route %s error: %s", request.path, e, exc_info=True)
            return web.json_response({"error": "Internal server error"}, status=500)

    @routes.get("/superduper-panel/autoresearch")
    async def autoresearch(request):
        """Read autoresearch results."""
        return web.json_response({
            "status": "idle",
            "message": "No autoresearch run active",
        })

    log.info("Comfy Cozy Panel routes mounted (%d routes)", 20)
