"""INTEND verb engine — recipe glue for ``cozy run --recipe`` (WP-INTEND).

Thin, pure-function layer the CLI can call to expose the EXISTING zero-LLM
recipe engine as a flag: name the goal ("dreamier", "sharper", "faster"), not
the numbers. Per the ratified design (HARNESS_CLI_20260714.md §WP-INTEND,
CLI.L4) everything here routes through the deterministic recipe/patch rail —
``apply_recipe`` → validated ``set_input``/``add_node`` patches on the session
workflow — and NEVER the orchestration/cognitive-stage path. Every change is
reversible with ``undo_workflow_patch``. 0 network; local JSON only.

Reuses (never duplicates):

- ``agent.recipes``             — the registry (7 built-ins) + trigger matching
- ``agent.tools.recipes_tool``  — the existing gated ``apply_recipe`` handler
- ``agent.tools.workflow_patch``— session workflow snapshots for the old→new diff

Nothing in this module raises for artist-input problems: unknown recipe names
and no-workflow-loaded both come back as structured dicts with human words.
"""

from __future__ import annotations

import copy
import difflib
import json
from typing import Any

from ..recipes import RecipeRegistry, get_registry

# ---------------------------------------------------------------------------
# Resolution — exact name or fuzzy match, never raise
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Fold artist spelling into registry-name shape (``Higher Quality`` → ``higher_quality``)."""
    return text.strip().lower().replace("-", "_").replace(" ", "_")


def _recipe_info(recipe: Any) -> dict:
    """Small serializable view of a Recipe for structured results."""
    return {
        "name": recipe.name,
        "description": recipe.description,
        "category": recipe.category,
        "requires_workflow": recipe.requires_workflow,
    }


def resolve_recipe(text: str, registry: RecipeRegistry | None = None) -> dict:
    """Resolve ``text`` to a recipe by exact name or fuzzy trigger match.

    Tries, in order: exact registry name (case/space/hyphen tolerant), then the
    registry's own trigger regexes against the free text ("make it dreamier").
    On a miss, returns the available names in artist words — never raises.

    Returns ``{"matched", "recipe", "available", "message"}`` where ``recipe``
    is a small info dict (or None on miss).
    """
    registry = registry or get_registry()
    names = [r.name for r in registry.all()]
    cleaned = (text or "").strip()

    if not cleaned:
        return {
            "matched": False,
            "recipe": None,
            "available": names,
            "message": (
                "Tell me the look you're after — recipes I know: " + ", ".join(names) + "."
            ),
        }

    recipe = registry.get(_normalize(cleaned)) or registry.get(cleaned)
    if recipe is None:
        recipe = registry.match(cleaned)

    if recipe is None:
        close = difflib.get_close_matches(_normalize(cleaned), names, n=3, cutoff=0.6)
        hint = f" Closest matches: {', '.join(close)}." if close else ""
        return {
            "matched": False,
            "recipe": None,
            "available": names,
            "message": (
                f"I don't have a recipe called '{cleaned}'.{hint} "
                "Recipes I know: " + ", ".join(names) + "."
            ),
        }

    return {
        "matched": True,
        "recipe": _recipe_info(recipe),
        "available": names,
        "message": f"Recipe: {recipe.name} — {recipe.description}.",
    }


# ---------------------------------------------------------------------------
# Session snapshots + old→new diff
# ---------------------------------------------------------------------------


def _session_workflow() -> dict | None:
    """Deep-copied snapshot of the session workflow (None if nothing loaded)."""
    try:
        from ..tools.workflow_patch import get_current_workflow

        workflow = get_current_workflow()
        return copy.deepcopy(workflow) if workflow else None
    except Exception:
        return None


def _diff_workflows(before: dict | None, after: dict | None) -> "tuple[list[dict], list[dict]]":
    """Compare two workflow snapshots: (input changes, nodes added).

    Changes are ``{"node_id", "class_type", "param", "old", "new"}``; added
    nodes are ``{"node_id", "class_type"}``. Deterministic ordering (sorted by
    node id, then param name).
    """
    before = before or {}
    after = after or {}
    changes: list[dict] = []
    added: list[dict] = []

    for node_id in sorted(after, key=str):
        node = after[node_id]
        if not isinstance(node, dict):
            continue
        if node_id not in before:
            added.append({"node_id": str(node_id), "class_type": node.get("class_type", "")})
            continue
        old_node = before[node_id] if isinstance(before[node_id], dict) else {}
        old_inputs = old_node.get("inputs") if isinstance(old_node.get("inputs"), dict) else {}
        new_inputs = node.get("inputs") if isinstance(node.get("inputs"), dict) else {}
        for param in sorted(set(old_inputs) | set(new_inputs)):
            old_value = old_inputs.get(param)
            new_value = new_inputs.get(param)
            if old_value != new_value:
                changes.append(
                    {
                        "node_id": str(node_id),
                        "class_type": node.get("class_type", ""),
                        "param": param,
                        "old": old_value,
                        "new": new_value,
                    }
                )
    return changes, added


# ---------------------------------------------------------------------------
# Apply — route through the EXISTING gated apply_recipe handler
# ---------------------------------------------------------------------------


def apply_recipe_to_session(text: str) -> dict:
    """Apply the recipe named/implied by ``text`` to the session workflow.

    Routes through the existing ``apply_recipe`` tool handler
    (``agent.tools.recipes_tool``), so every step rides the validated patch
    path and stays undoable via ``undo_workflow_patch``. Snapshots the session
    workflow before/after to report what changed in structured old→new form.

    Returns a dict with: ``matched``, ``recipe``, ``available``, ``applied``,
    ``steps_run``, ``fall_through``, ``changes`` (param old→new), ``nodes_added``,
    ``message`` (one human line), ``error``. Never raises.
    """
    resolution = resolve_recipe(text)
    if not resolution["matched"]:
        return {
            **resolution,
            "applied": False,
            "steps_run": 0,
            "fall_through": True,
            "changes": [],
            "nodes_added": [],
            "error": None,
        }

    before = _session_workflow()
    try:
        from ..tools import recipes_tool

        raw = recipes_tool.handle(
            "apply_recipe", {"name": resolution["recipe"]["name"], "text": text}
        )
        result = json.loads(raw)
    except Exception:
        return {
            **resolution,
            "applied": False,
            "steps_run": 0,
            "fall_through": True,
            "changes": [],
            "nodes_added": [],
            "message": (
                f"The recipe engine hit an unexpected problem applying "
                f"'{resolution['recipe']['name']}' — nothing was changed. "
                "Check the workflow is loaded and try again."
            ),
            "error": "recipe engine failure",
        }
    after = _session_workflow()
    changes, nodes_added = _diff_workflows(before, after)

    message = str(result.get("message") or "").replace("**", "")
    return {
        "matched": True,
        "recipe": resolution["recipe"],
        "available": resolution["available"],
        "applied": bool(result.get("applied")),
        "steps_run": int(result.get("steps_run") or 0),
        "fall_through": bool(result.get("fall_through")),
        "changes": changes,
        "nodes_added": nodes_added,
        "message": message,
        "error": result.get("error"),
    }


# ---------------------------------------------------------------------------
# Text renderers — the CLI layer prints these as-is
# ---------------------------------------------------------------------------


def _fmt_value(value: Any) -> str:
    """Render one input value in artist words (connections stay abstract)."""
    if isinstance(value, list):
        return "(rewired)"
    if value is None:
        return "(unset)"
    return str(value)


def render_recipe_result(result: dict) -> str:
    """Render an ``apply_recipe_to_session`` result as plain text, artist words."""
    if not result.get("matched"):
        return result.get("message", "No recipe matched.")

    recipe = result.get("recipe") or {}
    lines: list[str] = []
    if result.get("applied"):
        lines.append(f"Applied '{recipe.get('name', '?')}' — {recipe.get('description', '')}")
        for change in result.get("changes", []):
            lines.append(
                f"  {change['class_type'] or change['node_id']} {change['param']}: "
                f"{_fmt_value(change['old'])} -> {_fmt_value(change['new'])}"
            )
        for node in result.get("nodes_added", []):
            lines.append(f"  + added {node['class_type'] or 'node'} (node {node['node_id']})")
        if not result.get("changes") and not result.get("nodes_added"):
            lines.append("  (parameters were already at the recipe's values)")
        lines.append("Every change is reversible — undo puts it right back.")
    else:
        lines.append(result.get("message") or "The recipe couldn't be applied.")
    return "\n".join(lines)


def render_recipe_list(registry: RecipeRegistry | None = None) -> str:
    """Render the available recipes as plain text, artist words."""
    registry = registry or get_registry()
    recipes = registry.all()
    if not recipes:
        return "No recipes are available."
    width = max(len(r.name) for r in recipes)
    lines = ["Recipes — name the goal, not the numbers:"]
    for recipe in recipes:
        lines.append(f"  {recipe.name:<{width}}  {recipe.description}")
    lines.append("")
    lines.append("Use: cozy run --recipe <name>   (works on the loaded workflow; undoable)")
    return "\n".join(lines)
