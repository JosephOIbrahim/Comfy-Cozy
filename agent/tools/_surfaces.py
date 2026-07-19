"""Surface-hint overlay for the capability manifest (v1, closed vocabulary).

Maps tool name -> how the ComfyUI sidebar should present it. Anything not
listed defaults to 'chat-only'. The vocabulary is CLOSED per manifest_schema
version; renderers treat unknown values as 'chat-only' (forward-compat rule).

  chat-only  reachable via sidebar chat; no dedicated UI (the default)
  action     safe one-click / simple-args; sidebar may auto-render a form
  panel      deserves a dedicated server-built panel (e.g. diagnose report)
  bespoke    custom UI ships separately; feature_key() names the
             features-block entry the widget binds to
  hidden     canvas/internal plumbing; never rendered as a capability row
             (still fully reachable via chat and tool dispatch)

Keep this curated and SMALL (<20 non-default entries): every 'action'/'panel'
hint ships its input_schema in the default manifest payload, and hint
inflation is how the ~100KB payload budget dies.
"""

from __future__ import annotations

SURFACE_HINT_VALUES = frozenset({"chat-only", "action", "panel", "bespoke", "hidden"})

_HINTS: dict[str, str] = {
    # Switchboard — bespoke widget, binds to features.switchboard
    "swap_model": "bespoke",
    "list_models_available": "bespoke",
    # Diagnosis — structured report; a capability row can't render it
    "diagnose": "panel",
    # Safe zero/simple-arg one-clicks
    "get_system_stats": "action",
    "get_queue_status": "action",
    "get_models_summary": "action",
    "list_custom_nodes": "action",
    "list_recipes": "action",
    # Canvas plumbing — the canvas itself is the UI for these
    "push_workflow_to_canvas": "hidden",
    "get_canvas_state": "hidden",
}

_FEATURE_KEYS: dict[str, str] = {
    "swap_model": "switchboard",
    "list_models_available": "switchboard",
    "diagnose": "diagnosis",
}


def surface_hint(name: str) -> str:
    """The v1 surface hint for a tool name ('chat-only' when unlisted)."""
    return _HINTS.get(name, "chat-only")


def feature_key(name: str) -> "str | None":
    """The features-block key a bespoke/panel tool belongs to, if any."""
    return _FEATURE_KEYS.get(name)
