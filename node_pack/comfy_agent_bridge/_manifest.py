"""Capability manifest builder (manifest_schema 1) for GET /agent/capabilities.

The bridge ADVERTISES, the sidebar RENDERS: this payload is the contract that
lets future agent features appear in the ComfyUI UI with zero frontend edits.
Renderers must ignore unknown top-level keys and treat unknown surface_hint
values as 'chat-only'; manifest_schema bumps only on breaking shape changes.

SECURITY INVARIANTS (pinned by tests/test_capabilities_manifest.py):

1. Explicit allowlist construction. Every field in the payload is named
   literally in this module. The builder must NEVER reflect over
   agent.config, os.environ, or module __dict__s — config.py keeps real
   credentials adjacent to the safe flags, and one careless vars() dump
   would ship them to every same-origin page.
2. No auth-posture disclosure. The manifest must not report whether
   MCP_AUTH_TOKEN is set (no auth_enabled/auth_required field) — that tells
   an attacker whether the mutation gate is armed.
3. Raise on agent-package import failure — the route maps it to 503. The
   manifest IS the agent advertisement; an unreachable agent must never
   advertise an empty-but-200 catalog.

First call pays the lazy stage+brain import cost (~600ms of networkx/pxr);
event-loop callers must run build_manifest in an executor.
"""

from __future__ import annotations

MANIFEST_SCHEMA = 1


def build_manifest(include_schemas: bool = False) -> dict:
    """Build the manifest dict from the live registry (never doc counts)."""
    from pathlib import Path

    import agent
    from agent import _build
    from agent.tools import registry_snapshot
    from agent.tools._surfaces import feature_key, surface_hint

    snap = registry_snapshot()
    branch, disk_hash = _build.on_disk_state()
    build_hash = _build.BUILD_HASH
    stale = None
    if build_hash != "unknown" and disk_hash:
        stale = build_hash != disk_hash

    tools = []
    for t in snap["tools"]:
        hint = surface_hint(t["name"])
        if hint == "hidden":
            continue
        entry = {
            "name": t["name"],
            "description": t["description"],
            "layer": t["layer"],
            "module": t["module"],
            "surface_hint": hint,
        }
        fkey = feature_key(t["name"])
        if fkey is not None:
            entry["feature"] = fkey
        # Schemas only where the UI auto-renders from them — payload control.
        if include_schemas or hint in ("action", "panel"):
            entry["input_schema"] = t["input_schema"]
        tools.append(entry)

    return {
        "ok": True,
        "manifest_schema": MANIFEST_SCHEMA,
        "agent": {
            "package_version": agent.__version__,
            "build_hash": build_hash,
            "build_dirty": _build.BUILD_DIRTY,
            "branch": branch,
            "on_disk_hash": disk_hash,
            "stale": stale,
            "loaded_from": str(Path(agent.__file__).resolve().parent.parent),
        },
        "layers": snap["layers"],
        "degraded": snap["degraded"],
        "tools": tools,
        "features": _build_features(),
    }


def _build_features() -> dict:
    """Features block — explicit allowlist of capability state, no secrets.

    Switchboard state is probe=False throughout: configured/selection data
    only, zero network traffic. Live probes are button-only via the widget.
    """
    from agent import config
    from agent.llm import _health, swap
    from agent.llm import _selection

    live = {
        "provider": config.LLM_PROVIDER,
        "model": config.AGENT_MODEL,
        "vision_provider": config.VISION_PROVIDER,
        "vision_model": config.VISION_MODEL,
    }

    saved = None
    try:
        sel = _selection.load_selection()
        if sel:
            # Allowlist the fields — never forward the raw dict.
            saved = {
                "provider": sel.get("provider"),
                "model": sel.get("model"),
                "saved_at": sel.get("saved_at"),
            }
    except Exception:
        saved = None

    try:
        selection_path = str(_selection._selection_path())
    except Exception:
        selection_path = None

    try:
        status = _health.model_status(probe=False)
    except Exception:
        status = None

    return {
        "switchboard": {
            "enabled": True,
            "aliases": swap.list_aliases(),
            "capabilities": swap.list_capabilities(),
            "status": status,
            "live": live,
            "saved": saved,
            # Diagnosable on purpose: differing MODEL_SELECTION_PATH values
            # between processes silently split the "saved as default" promise.
            "selection_path": selection_path,
        },
        "diagnosis": {"enabled": True},
        "verbs": ["find", "intend", "see", "own", "open", "pull"],
        "gate": {"enabled": config.GATE_ENABLED},
        "recipes": {"enabled": config.RECIPES_ENABLED},
        "brain": {"enabled": config.BRAIN_ENABLED},
        "observation": {"enabled": config.OBSERVATION_ENABLED},
    }
