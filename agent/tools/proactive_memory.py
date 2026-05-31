"""Proactive memory (#10 / P4.3) — Home B.

surface_relevant_memory(workflow) — relevance-filtered recall of learned
patterns at conversation start, like the workflow context already injected, so
continuity stops being cosmetic. Relevance = current-workflow class_type overlap
+ recency. Irrelevant memory is NOT injected; output stays within a small token
budget (the #4 disclosure invariant carried forward). Fork-C resolved:
class_type-overlap + recency scorer (simple, budget-safe).
"""

from ._util import to_json

# Keep injected memory small — the #4 context-cost guard applies to every tool
# built after it. Cap the snippet aggressively.
_MAX_HITS = 5
_MAX_CHARS = 1200


TOOLS: list[dict] = [
    {
        "name": "surface_relevant_memory",
        "description": (
            "Surface prior learned patterns relevant to the current workflow, "
            "ranked by node-type overlap and recency. Returns a small, "
            "budget-bounded snippet — nothing is surfaced when no memory is "
            "relevant (no noise). Provide 'class_types' (list) or 'workflow' "
            "(API-format dict) to score against."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "class_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Node class_types in the current workflow.",
                },
                "workflow": {
                    "type": "object",
                    "description": "API-format workflow dict (class_types extracted automatically).",
                },
            },
            "required": [],
        },
    },
]


def _extract_class_types(tool_input: dict) -> set[str]:
    cts = set()
    for c in tool_input.get("class_types", []) or []:
        if isinstance(c, str):
            cts.add(c)
    wf = tool_input.get("workflow")
    if isinstance(wf, dict):
        for node in wf.values():
            if isinstance(node, dict) and isinstance(node.get("class_type"), str):
                cts.add(node["class_type"])
    return cts


def _score(pattern: dict, current: set[str], idx: int, total: int) -> float:
    """class_type overlap (primary) + recency (tiebreak). idx 0 = most recent."""
    p_types = set()
    for key in ("class_types", "node_types", "workflow_class_types"):
        v = pattern.get(key)
        if isinstance(v, list):
            p_types.update(x for x in v if isinstance(x, str))
    # Also try to read class_types out of a nested workflow/parameters blob.
    overlap = len(p_types & current)
    recency = (total - idx) / total if total else 0.0
    return overlap + 0.25 * recency


def _handle_surface_relevant_memory(tool_input: dict) -> str:
    current = _extract_class_types(tool_input)
    if not current:
        return to_json({"surfaced": [], "note": "No class_types provided to score against."})

    # Pull learned patterns via the existing memory tool.
    from . import handle as _dispatch
    import json
    raw = _dispatch("get_learned_patterns", {})
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return to_json({"surfaced": [], "note": "Memory unavailable."})

    patterns = data.get("patterns") if isinstance(data, dict) else None
    if not isinstance(patterns, list) or not patterns:
        return to_json({"surfaced": [], "note": "No learned patterns recorded yet."})

    total = len(patterns)
    scored = [
        (_score(p, current, i, total), p)
        for i, p in enumerate(patterns)
        if isinstance(p, dict)
    ]
    # Only surface patterns with real overlap — irrelevant memory is NOT injected.
    relevant = [(s, p) for s, p in scored if s >= 1.0]
    relevant.sort(key=lambda sp: sp[0], reverse=True)
    hits = [p for _s, p in relevant[:_MAX_HITS]]

    if not hits:
        return to_json({"surfaced": [], "note": "No relevant memory for this workflow (nothing injected)."})

    # Budget guard (#4 invariant): trim to _MAX_CHARS.
    out = to_json({"surfaced": hits, "count": len(hits)})
    if len(out) > _MAX_CHARS:
        out = to_json({
            "surfaced": hits[: max(1, _MAX_HITS // 2)],
            "count": len(hits),
            "note": "Trimmed to stay within the memory injection budget.",
        })
    return out


def handle(name: str, tool_input: dict) -> str:
    try:
        if name == "surface_relevant_memory":
            return _handle_surface_relevant_memory(tool_input)
        return to_json({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return to_json({"error": str(e)})
