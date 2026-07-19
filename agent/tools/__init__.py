"""Tool registry for Comfy Cozy.

Each tool module exports:
  TOOLS: list[dict]    -- Anthropic tool schemas
  handle(name, input)  -- Execute a tool call, return result string

Intelligence layer (84 tools) + Stage layer (22 tools, lazy) + Brain layer (27 tools)
= 133 dispatched tools.
Brain tools are lazily imported to avoid circular dependencies
(brain modules import _util from this package).
"""

import importlib
import inspect
import logging
import threading
import time

log = logging.getLogger(__name__)

# Intelligence-layer tool module names.  Imported individually so a single
# broken module (missing dependency, syntax error) degrades gracefully instead
# of crashing the entire tool registry.
_INTELLIGENCE_MODULE_NAMES = [
    "comfy_api", "comfy_inspect", "workflow_parse", "workflow_patch",
    "comfy_execute", "comfy_discover", "session_tools", "workflow_templates",
    "civitai_api", "model_compat", "verify_execution", "github_releases",
    "pipeline", "image_metadata", "node_replacement", "comfy_provision",
    "auto_wire", "provision_pipeline", "canvas_bridge", "vision_cache",
    "local_assets", "proactive_memory", "ui_api_parser", "exec_profile",
    "output_watcher", "nim_lifecycle", "model_swap", "recipes_tool",
    "diagnose_tool",
]
_STAGE_MODULE_NAMES = [
    "provision_tools", "stage_tools", "foresight_tools",
    "compositor_tools", "hyperagent_tools",
]

# Modules that failed to import, by layer — the capability manifest surfaces
# this so silent registry shrinkage (a dep missing under the ComfyUI python,
# say) is VISIBLE instead of a mystery tool-count drop in a log nobody reads.
_DEGRADED: list[dict] = []

_MODULES: list = []
for _mod_name in _INTELLIGENCE_MODULE_NAMES:
    try:
        _MODULES.append(importlib.import_module(f".{_mod_name}", package=__name__))
    except Exception as _ie:
        log.warning("Tool module %r failed to import — its tools are unavailable: %s", _mod_name, _ie)
        _DEGRADED.append({
            "module": _mod_name, "layer": "intelligence",
            "error": f"{type(_ie).__name__}: {_ie}",
        })

# H2 (ledger C-R13): stage modules are NOT imported here — they pull
# networkx (~294 ms) + pxr (~310 ms) into every cold import. They are
# lazy-registered by _ensure_stage() below (importer-side only; the stage
# package itself is untouched).

# Intelligence layer tool schemas
_LAYER_TOOLS: list[dict] = []
for _mod in _MODULES:
    _LAYER_TOOLS.extend(_mod.TOOLS)

# Map tool name -> handler module (intelligence layers).
# MoE-R7: detect duplicate registrations at import time. Pre-fix, a tool
# defined in two modules would silently have one handler overwrite the
# other, with the order-of-import determining which won. With the
# warning, registration drift is visible in cold-start logs.
_HANDLERS = {}
for _mod in _MODULES:
    for _tool in _mod.TOOLS:
        _name = _tool["name"]
        if _name in _HANDLERS:
            log.warning(
                "tool registration collision: %r registered by %s, "
                "overwriting prior registration from %s",
                _name, _mod.__name__, _HANDLERS[_name].__name__,
            )
        _HANDLERS[_name] = _mod

# MoE-R7: per-layer count diagnostic. Emits at INFO so ops dashboards can
# alert on drift. Brain layer counts are added by `_ensure_brain()` when
# it lazy-loads; the line below is the stage+intelligence subtotal.
log.info(
    "tool dispatch: %d intelligence tools registered (stage + brain lazy)",
    len(_HANDLERS),
)

# C-R12: per-module cache — does mod.handle() accept a `progress` kwarg?
# Computed once via inspect.signature. Replaces the try/except-TypeError
# forwarding, which RE-EXECUTED a handler (without progress) whenever a
# TypeError surfaced from INSIDE a progress-accepting handler.
_PROGRESS_AWARE: dict[str, bool] = {}


def _handle_accepts_progress(mod) -> bool:
    """True if `mod.handle` accepts a `progress` keyword (cached per module).

    Test doubles registered as handler modules may lack ``__name__`` —
    those are computed per call instead of cached (real modules always
    have a name, so the hot path stays cached).
    """
    key = getattr(mod, "__name__", None)
    cached = _PROGRESS_AWARE.get(key) if key is not None else None
    if cached is None:
        try:
            params = inspect.signature(mod.handle).parameters
            cached = "progress" in params or any(
                p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
            )
        except (TypeError, ValueError, AttributeError):
            cached = False
        if key is not None:
            _PROGRESS_AWARE[key] = cached
    return cached

# Brain tools are loaded lazily to break the circular import
_brain_loaded = False
_brain_lock = threading.Lock()
_BRAIN_TOOL_NAMES: set[str] = set()


def _ensure_brain():
    """Lazily load brain layer tools (thread-safe)."""
    from ..config import BRAIN_ENABLED
    if not BRAIN_ENABLED:
        return
    global _brain_loaded, _BRAIN_TOOL_NAMES
    if _brain_loaded:
        return
    with _brain_lock:
        if _brain_loaded:  # double-check after acquiring lock
            return
        try:
            from ..brain import ALL_BRAIN_TOOLS
            _BRAIN_TOOL_NAMES.update(t["name"] for t in ALL_BRAIN_TOOLS)
            _brain_loaded = True
        except Exception as _be:
            log.warning(
                "Brain layer unavailable — brain tools will not be registered: %s", _be
            )
            _DEGRADED.append({
                "module": "brain", "layer": "brain",
                "error": f"{type(_be).__name__}: {_be}",
            })


# Stage tools are loaded lazily (H2 / C-R13): same pattern as the brain
# layer. Loaded on first full-tool-list access or on dispatch of a name the
# eager layers don't know.
_stage_loaded = False
_stage_lock = threading.Lock()
_STAGE_TOOL_NAMES: set[str] = set()


def _ensure_stage():
    """Lazily import + register stage-layer tools (thread-safe)."""
    global _stage_loaded
    if _stage_loaded:
        return
    with _stage_lock:
        if _stage_loaded:
            return
        for _mod_name in _STAGE_MODULE_NAMES:
            try:
                _mod = importlib.import_module(f"..stage.{_mod_name}", package=__name__)
            except Exception as _ie:
                log.warning(
                    "Stage module %r failed to import — its tools are unavailable: %s",
                    _mod_name, _ie,
                )
                _DEGRADED.append({
                    "module": _mod_name, "layer": "stage",
                    "error": f"{type(_ie).__name__}: {_ie}",
                })
                continue
            _MODULES.append(_mod)
            for _tool in _mod.TOOLS:
                _name = _tool["name"]
                if _name in _HANDLERS:
                    log.warning(
                        "tool registration collision: %r registered by %s, "
                        "overwriting prior registration from %s",
                        _name, _mod.__name__, _HANDLERS[_name].__name__,
                    )
                _HANDLERS[_name] = _mod
                _STAGE_TOOL_NAMES.add(_name)
            _LAYER_TOOLS.extend(_mod.TOOLS)
        _stage_loaded = True
        log.info("tool dispatch: stage layer loaded (+%d tools)", len(_STAGE_TOOL_NAMES))


def _record_metric(name: str, status: str, elapsed: float) -> None:
    """Record tool call metrics. Lazy import so metrics failure doesn't break tools."""
    try:
        from ..metrics import tool_call_total, tool_call_duration_seconds
        tool_call_total.inc(tool_name=name, status=status)
        tool_call_duration_seconds.observe(elapsed, tool_name=name)
    except Exception:
        pass  # Metrics failure must never break tool dispatch


def _observe(name: str, tool_input: dict, ctx: "object | None") -> None:
    """Record observation after tool dispatch. Never raises."""
    try:
        if ctx is not None and hasattr(ctx, 'workflow'):
            ctx.workflow.observe(name, tool_input)
    except Exception:
        log.debug("Observation failed for tool %s", name, exc_info=True)


def _get_all_tools() -> list[dict]:
    """Get all tool schemas (intelligence + stage + brain layers)."""
    _ensure_stage()
    _ensure_brain()
    if not _brain_loaded:
        return list(_LAYER_TOOLS)
    from ..brain import ALL_BRAIN_TOOLS
    return _LAYER_TOOLS + list(ALL_BRAIN_TOOLS)


# Public API — ALL_TOOLS is a property-like accessor
class _ToolList(list):
    """Lazy tool list that includes brain tools on first access.

    Uses instance-level lock and initialized flag (not class-level) so that
    multiple instances don't share state. Class-level attributes would leave
    the class attribute False after the first instance sets its own instance
    attribute True, causing any second instance to re-initialize. (Cycle 30 fix)
    """

    def __init__(self):
        super().__init__()
        self._initialized = False
        self._lock = threading.Lock()

    def _init_once(self):
        if self._initialized:
            return
        with self._lock:
            if self._initialized:  # Double-check after acquiring lock
                return
            _ensure_stage()
            self.extend(_LAYER_TOOLS)
            _ensure_brain()
            if _brain_loaded:
                try:
                    from ..brain import ALL_BRAIN_TOOLS
                    self.extend(ALL_BRAIN_TOOLS)
                except ImportError:
                    log.warning("Brain layer not available")
            self._initialized = True

    def __iter__(self):
        self._init_once()
        return super().__iter__()

    def __len__(self):
        self._init_once()
        return super().__len__()

    def __getitem__(self, idx):
        self._init_once()
        return super().__getitem__(idx)


ALL_TOOLS = _ToolList()


def registry_snapshot() -> dict:
    """Live-registry snapshot for the capability manifest.

    Always derived from the registry as loaded in THIS process — never from
    documented counts. First call pays the lazy stage+brain import cost via
    len(ALL_TOOLS); event-loop callers must offload to an executor.

    Layer attribution: brain tools are absent from _HANDLERS (the brain
    package dispatches its own), so module falls back to the layer name;
    intelligence count is total - brain - stage (tool_count()'s first
    element lumps intelligence WITH stage).
    """
    total = len(ALL_TOOLS)  # triggers _ensure_stage() + _ensure_brain()
    brain = len(_BRAIN_TOOL_NAMES)
    stage = len(_STAGE_TOOL_NAMES)
    tools = []
    for t in ALL_TOOLS:
        name = t["name"]
        if name in _BRAIN_TOOL_NAMES:
            layer = "brain"
        elif name in _STAGE_TOOL_NAMES:
            layer = "stage"
        else:
            layer = "intelligence"
        mod = _HANDLERS.get(name)
        mod_name = getattr(mod, "__name__", "")
        tools.append({
            "name": name,
            "description": t.get("description", ""),
            "layer": layer,
            "module": mod_name.rsplit(".", 1)[-1] if mod_name else layer,
            "input_schema": t.get("input_schema"),
        })
    return {
        "layers": {
            "intelligence": total - brain - stage,
            "stage": stage,
            "brain": brain,
            "total": total,
        },
        "tools": tools,
        "degraded": list(_DEGRADED),
    }


def handle(
    name: str,
    tool_input: dict,
    *,
    session_id: str | None = None,
    progress: "object | None" = None,
    ctx: "object | None" = None,
) -> str:
    """Dispatch a tool call to the right handler.

    Args:
        name: Tool name to dispatch.
        tool_input: Tool arguments dict.
        session_id: Optional session ID for workflow state isolation.
                    When ctx is not provided, this is used to look up
                    the SessionContext from the global registry.
        progress: Optional progress reporter for long-running tools.
                  Passed through to handlers that support it.
        ctx: Optional SessionContext for session-scoped state.
             When None, falls back to the default session (v1 behavior).
    """
    # Resolve session context if not provided
    if ctx is None and session_id:
        from ..session_context import get_session_context
        ctx = get_session_context(session_id)

    # Ensure brain is loaded BEFORE the gate check — _BRAIN_TOOL_NAMES is
    # populated by _ensure_brain(). Without this, brain tools on their first
    # call are not present in _BRAIN_TOOL_NAMES, so _is_known=False and the
    # gate is silently skipped for high-risk brain tools. (Cycle 28 fix)
    _ensure_brain()

    # H2 (C-R13): stage tools register lazily — only pay the stage import
    # when the requested name isn't known to the eager layers.
    if name not in _HANDLERS and name not in _BRAIN_TOOL_NAMES:
        _ensure_stage()

    # Pre-dispatch gate (guarded by kill switch, only for known tools)
    _is_known = name in _HANDLERS or name in _BRAIN_TOOL_NAMES
    try:
        from ..config import GATE_ENABLED
        if GATE_ENABLED and _is_known:
            from ..gate import pre_dispatch_check, GateDecision, RiskLevel

            # Determine session_active: either explicit ctx (MCP path with
            # SessionContext), or a workflow loaded in this connection's
            # WorkflowSession.  _get_state() reads the _conn_session
            # ContextVar, which is set per-connection by routes.py and
            # mcp_server.py — so the sidebar's injected workflow lives in
            # its own session and the gate sees it correctly.
            # session_active + has_undo feed the gate's consent + reversibility
            # checks.  Workflow state can live in TWO stores that DIVERGE:
            #   - ctx.workflow : the SessionContext's own WorkflowSession
            #   - _get_state() : this connection's REGISTRY WorkflowSession,
            #                    which the loaders (load_workflow_from_data /
            #                    _load_workflow) actually write to.
            # The sidebar/MCP path passes a session_id (ctx present), but the
            # injected graph lands in the REGISTRY session — a different object
            # from ctx.workflow.  Consult BOTH so a loaded workflow is seen
            # regardless of which store holds it (fixes the dual-store wedge).
            _session_active = ctx is not None
            _wf_loaded = False
            _has_undo = False
            if ctx is not None and hasattr(ctx, 'workflow'):
                try:
                    if ctx.workflow.get("current_workflow") is not None:
                        _wf_loaded = True
                    if ctx.workflow.get("history"):
                        _has_undo = True
                except Exception:
                    pass
            try:
                from .workflow_patch import _get_state
                _reg = _get_state()
                if _reg.get("current_workflow") is not None:
                    _wf_loaded = True
                if _reg.get("history"):
                    _has_undo = True
            except Exception:
                pass
            # Fail open SAFELY: a LOADED-but-unmutated workflow is reversible via
            # reset_workflow, which restores base_workflow (set once at load,
            # never touched by writes) — so "a workflow is loaded" is itself a
            # legitimate undo baseline, even before the first mutation seeds
            # history.  A genuinely UNLOADED session (no current_workflow in
            # either store) still fails CLOSED: _wf_loaded stays False so
            # _has_undo stays False and REVERSIBLE writes are denied.
            if _wf_loaded:
                _session_active = True
                _has_undo = True

            # load_session is self-baselining (audit 3.4): it restores a saved
            # base_workflow (reset_workflow can restore it) and the on-disk session is
            # recoverable, so it is reversible even on a fresh load. Without this, the
            # REVERSIBLE reclassification would DENY a fresh load (no prior undo state).
            if name == "load_session":
                _session_active = True
                _has_undo = True

            # Stage-state fallback for stage_* tools.  The workflow-state
            # fallback above misses the case where a CognitiveWorkflowStage
            # exists but no workflow is loaded — stage tools operate on USD
            # stage prims, which can exist independently of workflow_patch
            # state.  Without this, a REVERSIBLE stage tool like stage_write
            # would be incorrectly DENIED by check_consent (no session) or
            # check_reversibility (no workflow_patch undo history) even
            # though the stage itself has its own delta-rollback mechanism.
            if name.startswith("stage_") and not _session_active:
                try:
                    from ..session_context import get_session_context
                    from .._conn_ctx import current_conn_session
                    _stage_ctx = get_session_context(current_conn_session())
                    if _stage_ctx.stage is not None:
                        _session_active = True
                        # Stage delta sublayers provide undo capability
                        _has_undo = True
                except Exception:
                    pass

            # C-P0-3: wire the REAL circuit-breaker state into the gate's
            # system-health check (it previously ran on the "closed" default).
            from ..circuit_breaker import COMFYUI_BREAKER
            _breaker_state = COMFYUI_BREAKER().state

            # C-P0-3: per-session action history (stored in the registry
            # WorkflowSession) feeds the constitution checks. Behavior-neutral
            # today by design — scout_before_act treats empty history as "not
            # tracked — skipped" and passes non-empty history unconditionally,
            # and verify_after_mutation only fires when
            # verified_since_mutation=False is passed (it is not) — but the
            # wiring makes the substrate real instead of always-default.
            # H1.4: validated_since_mutation is set by validate_before_execute
            # (session validations only) and cleared below when a mutation
            # dispatches — it feeds the gate's consent check, which requires
            # it True before execute_workflow / execute_with_progress run the
            # session workflow. Defensive read, default False (deny-side).
            _history: list = []
            _validated = False
            try:
                from .workflow_patch import _get_state
                _st = _get_state()
                _history = list(_st.get("action_history") or [])
                _validated = bool(_st.get("validated_since_mutation", False))
            except Exception:
                pass

            gate_result = pre_dispatch_check(
                name, tool_input,
                breaker_state=_breaker_state,
                session_active=_session_active,
                validated=_validated,
                has_undo=_has_undo,
                action_history=_history,
            )
            if gate_result.decision == GateDecision.DENY:
                from ..errors import error_json
                return error_json(
                    f"Gate denied '{name}': {gate_result.reason}",
                    hint="Check prerequisites or try a different approach.",
                )
            elif gate_result.decision == GateDecision.LOCKED:
                from ..errors import error_json
                return error_json(
                    f"'{name}' is a destructive operation and requires "
                    f"explicit confirmation.",
                    hint="This tool cannot be auto-executed.",
                )
            elif gate_result.decision == GateDecision.ESCALATE:
                # ESCALATE = a PROVISION-class op (download_model, install_node_pack,
                # provision_*) — a NETWORK fetch / CODE-EXECUTING install. It is NO
                # LONGER auto-allowed: it now requires an explicit confirmation token
                # in the call (`"confirm": true`), supplied after the escalation is
                # surfaced to a human. Without it we BLOCK (do NOT dispatch), closing
                # the prompt->autonomous-fetch / prompt->RCE hole. A genuinely
                # confirmed call falls through to dispatch unchanged.
                if isinstance(tool_input, dict):
                    _raw_confirm = tool_input.get("confirm", False)
                    _confirmed = (
                        _raw_confirm
                        if isinstance(_raw_confirm, bool)
                        else str(_raw_confirm).lower() in ("true", "1", "yes")
                    )
                else:
                    _confirmed = False
                if not _confirmed:
                    log.info("Gate ESCALATE-blocked '%s' (risk %d) — needs confirm",
                             name, gate_result.risk_level)
                    from ..errors import error_json
                    # C-R12: echo SAFE identifying inputs (url/filename/name) so
                    # the human approves an IDENTIFIED action, not a blind one.
                    _ident = ""
                    if isinstance(tool_input, dict):
                        _parts = [
                            f"{_k}={str(tool_input[_k])[:120]}"
                            for _k in ("url", "filename", "name")
                            if isinstance(tool_input.get(_k), str) and tool_input.get(_k)
                        ]
                        if _parts:
                            _ident = " Target: " + ", ".join(_parts) + "."
                    return error_json(
                        f"'{name}' is a network/code-executing operation and needs "
                        f"explicit confirmation before it runs — auto-blocked to "
                        f"prevent unattended download/install.{_ident}",
                        hint="A human must approve; re-call with \"confirm\": true "
                             "to proceed.",
                    )
                log.info("Gate ESCALATE-confirmed '%s' (risk %d) — proceeding",
                         name, gate_result.risk_level)
                # confirmed -> fall through to dispatch

            # C-P0-3: the call WILL dispatch (ALLOW fell through, or ESCALATE
            # with confirm=true) — record it in the per-session action history
            # (capped at the last 50) so the constitution checks see real
            # history on the next call. DENY/LOCKED/blocked returned early.
            try:
                from .workflow_patch import _get_state
                _st = _get_state()
                _st["action_history"] = (
                    list(_st.get("action_history") or []) + [name]
                )[-50:]
                # H1.4: a mutation-class (REVERSIBLE) dispatch invalidates any
                # prior validate_before_execute verdict — the session workflow
                # is about to change, so execution must re-validate first.
                if gate_result.risk_level == RiskLevel.REVERSIBLE:
                    _st["validated_since_mutation"] = False
            except Exception:
                pass
    except ImportError:
        # Gate not available — FAIL CLOSED (C-P0-3). A broken agent.gate import
        # previously degraded silently, letting even DESTRUCTIVE tools dispatch
        # ungated. Closed means closed: deny every tool until the gate imports.
        log.error("Gate import failed for '%s' — denying dispatch for safety",
                  name, exc_info=True)
        from ..errors import error_json
        return error_json(
            f"Gate unavailable for '{name}' — denied for safety (gate import "
            f"failed). Check the agent.gate package and logs."
        )
    except Exception:
        log.warning("Gate check failed for '%s' — denying for safety", name,
                    exc_info=True)
        from ..errors import error_json
        return error_json(
            f"Gate unavailable for '{name}' — denied for safety. Check logs."
        )

    # Check brain tools (_ensure_brain already called above before gate check)
    if name in _BRAIN_TOOL_NAMES:
        from ..brain import handle as handle_brain
        _t0 = time.monotonic()
        try:
            result = handle_brain(name, tool_input)
            _observe(name, tool_input, ctx)
            _record_metric(name, "ok", time.monotonic() - _t0)
            return result
        except Exception:
            _record_metric(name, "error", time.monotonic() - _t0)
            log.error("Unhandled error in brain tool %s", name, exc_info=True)
            from ..errors import error_json
            return error_json(
                f"Something went wrong with {name}.",
                hint="Check the logs or try again.",
            )

    # Intelligence layer tools
    mod = _HANDLERS.get(name)
    if mod is None:
        log.warning("Unknown tool called: %s", name)
        from ..errors import error_json
        return error_json(f"Unknown tool: {name}", hint="Check the tool name and try again.")
    _t0 = time.monotonic()
    try:
        # C-R12: signature-aware progress forwarding — pass progress= only when
        # the module's handle() accepts it. The old try/except-TypeError fallback
        # re-ran the handler whenever a TypeError escaped from inside it.
        if _handle_accepts_progress(mod):
            result = mod.handle(name, tool_input, progress=progress)
        else:
            result = mod.handle(name, tool_input)
        _observe(name, tool_input, ctx)
        _record_metric(name, "ok", time.monotonic() - _t0)
        return result
    except Exception:
        _record_metric(name, "error", time.monotonic() - _t0)
        log.error("Unhandled error in tool %s", name, exc_info=True)
        from ..errors import error_json
        return error_json(
            f"Something went wrong with {name}.",
            hint="Check the logs or try again.",
        )
