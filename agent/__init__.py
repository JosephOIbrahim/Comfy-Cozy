"""ComfyUI Agent — AI co-pilot for ComfyUI workflows."""

__version__ = "5.8.2"


def tool_count() -> tuple[int, int, int]:
    """Return (intelligence_tools, brain_tools, total) from live registry.

    Routes through the dispatcher's lazy registry: len(ALL_TOOLS) triggers
    _ensure_brain(), which honors the BRAIN_ENABLED kill switch, so this
    never imports agent.brain eagerly and reports 0 brain tools when the
    brain layer is disabled or unavailable.
    """
    from .tools import ALL_TOOLS, _BRAIN_TOOL_NAMES
    total = len(ALL_TOOLS)
    brain = len(_BRAIN_TOOL_NAMES)
    return total - brain, brain, total
