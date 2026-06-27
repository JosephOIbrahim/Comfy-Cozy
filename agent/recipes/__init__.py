"""Zero-LLM recipe layer (B1) — public surface.

``get_registry()`` returns the process-wide registry; ``run_recipe()`` /
``match_and_run()`` execute a recipe in PRODUCTION, dispatching each step through
``agent.tools.handle`` (so the pre-dispatch gate vets every operation) and reading
workflow state from the live per-connection ``WorkflowSession``.

Tests build their own ``RecipeExecutor`` with mocked dispatch/getter — see
``tests/test_recipes.py`` — so the engine is exercised without the tool layer.
"""

from __future__ import annotations

from .base import (
    ParamMutation,
    Recipe,
    RecipeExecutor,
    RecipeRegistry,
    RecipeResult,
    ToolStep,
)
from .builtin import build_default_registry

__all__ = [
    "ParamMutation",
    "Recipe",
    "RecipeExecutor",
    "RecipeRegistry",
    "RecipeResult",
    "ToolStep",
    "get_registry",
    "run_recipe",
    "match_and_run",
]

_registry: "RecipeRegistry | None" = None


def get_registry() -> RecipeRegistry:
    """Return the lazily-built, process-wide recipe registry."""
    global _registry
    if _registry is None:
        _registry = build_default_registry()
    return _registry


def _prod_dispatch(name: str, args: dict) -> str:
    # Lazy import avoids an import cycle (agent.tools imports widely at load time).
    from agent.tools import handle
    return handle(name, args)


def _prod_workflow() -> "dict | None":
    try:
        from agent.tools.workflow_patch import _get_state
        return _get_state()["current_workflow"]
    except Exception:
        return None


def run_recipe(recipe: Recipe, text: str = "") -> RecipeResult:
    """Execute ``recipe`` in production (gated dispatch, live workflow state)."""
    executor = RecipeExecutor(_prod_dispatch, _prod_workflow)
    return executor.execute(recipe, text)


def match_and_run(text: str) -> "RecipeResult | None":
    """Trigger-match ``text`` to a recipe and run it; None if nothing matches."""
    recipe = get_registry().match(text)
    if recipe is None:
        return None
    return run_recipe(recipe, text)
