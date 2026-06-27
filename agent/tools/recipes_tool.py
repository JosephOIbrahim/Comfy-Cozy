"""apply_recipe / list_recipes — invoke a deterministic zero-LLM recipe as a macro.

These expose the agent/recipes layer to the MCP host (the primary interface). Each
recipe step is dispatched back through ``agent.tools.handle``, so the pre-dispatch
gate vets every operation and every change is reversible (``undo_workflow_patch``).
"""

from __future__ import annotations

from ._util import to_json

TOOLS = [
    {
        "name": "apply_recipe",
        "description": (
            "Apply a deterministic, pre-approved recipe to the loaded workflow in one "
            "shot — e.g. 'dreamier', 'sharper', 'faster', 'upscale_2x_pixel'. Prefer this "
            "over re-deriving the parameter changes yourself for common artist intents. "
            "Pass an exact recipe `name`, or free `text` to trigger-match (e.g. 'make it "
            "dreamier'). Each step is gated like any other tool call and is reversible. "
            "Returns what changed; if nothing matches or the workflow can't satisfy the "
            "recipe, returns matched/applied=false so you can handle it normally."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Exact recipe name (optional if text given)."},
                "text": {"type": "string", "description": "Free text to trigger-match a recipe (optional if name given)."},
            },
            "required": [],
        },
    },
    {
        "name": "list_recipes",
        "description": (
            "List the available zero-LLM recipes (name, description, triggers, category). "
            "Use this to see what one-shot macros exist before falling back to manual edits."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def handle(name: str, tool_input: dict) -> str:
    from agent.recipes import get_registry, run_recipe

    registry = get_registry()

    if name == "list_recipes":
        return to_json({
            "recipes": [
                {
                    "name": r.name,
                    "description": r.description,
                    "triggers": r.triggers,
                    "category": r.category,
                    "requires_workflow": r.requires_workflow,
                }
                for r in registry.all()
            ]
        })

    if name == "apply_recipe":
        tool_input = tool_input or {}
        recipe_name = tool_input.get("name")
        text = tool_input.get("text", "") or ""
        recipe = registry.get(recipe_name) if recipe_name else registry.match(text)
        if recipe is None:
            return to_json({
                "matched": False,
                "message": "No recipe matched — handle this request normally.",
                "available": [r.name for r in registry.all()],
            })
        result = run_recipe(recipe, text or recipe_name or "")
        return to_json({
            "matched": True,
            "recipe": recipe.name,
            "applied": result.applied,
            "steps_run": result.steps_run,
            "fall_through": result.fall_through,
            "message": result.summary,
            "error": result.error,
        })

    return to_json({"error": f"Unknown recipe tool: {name}"})
