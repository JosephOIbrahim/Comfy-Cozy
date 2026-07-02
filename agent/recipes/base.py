"""Zero-LLM recipe layer — deterministic, pre-approved multi-step macros.

A Recipe is a trigger-matched sequence of workflow operations the agent applies
WITHOUT an LLM round-trip. Every step is dispatched through ``agent.tools.handle``,
so the existing pre-dispatch gate vets each operation — recipes inherit safety,
they do not bypass it. Every change is reversible (``undo_workflow_patch``).

Two step kinds:
  * ``ParamMutation`` — set/nudge a literal input on every node of a class. Source:
    the CLAUDE.md "Artistic Intent Translation" table ("dreamier", "sharper", ...).
  * ``ToolStep`` — a raw semantic-build call (``add_node`` / ``connect_nodes`` /
    ``set_input``) with ``$var.field`` dataflow and ``@find:<class>`` node resolution.
    Source: the agent/knowledge/common_recipes.md graphs.

Recipes NEVER hard-fail a turn: if the current workflow can't satisfy a recipe
(no workflow loaded, target node absent before the first change), the executor
returns ``applied=False`` with ``fall_through=True`` so the caller defers to the LLM.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

# (tool_name, tool_input) -> JSON string result. Injected so the engine is testable
# and so production runs route through the gated tool layer.
Dispatch = Callable[[str, dict], str]
# () -> current API-format workflow dict (or None). Injected for the same reasons.
WorkflowGetter = Callable[[], "dict | None"]


# ---------------------------------------------------------------------------
# Step + recipe data structures
# ---------------------------------------------------------------------------
@dataclass
class ParamMutation:
    """Set or nudge a literal input on every node of ``target_class``."""

    target_class: str
    input_name: str
    action: str = "set"            # "set" | "adjust_up" | "adjust_down"
    value: Any = None              # absolute (set) or delta (adjust_*)


@dataclass
class ToolStep:
    """A raw semantic-build tool call with ``$var`` / ``@find`` resolution."""

    tool: str
    args: dict
    out: str = ""                  # store json.loads(result) under this $name


@dataclass
class Recipe:
    name: str
    description: str
    triggers: list[str]                       # regex, matched case-insensitively
    steps: list                               # list[ParamMutation | ToolStep]
    requires_workflow: bool = False
    category: str = "general"

    def matches(self, text: str) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in self.triggers)


@dataclass
class RecipeResult:
    applied: bool
    summary: str
    steps_run: int = 0
    fall_through: bool = False     # True => caller should defer to the LLM
    error: str | None = None


# ---------------------------------------------------------------------------
# Resolution helpers ($var.field, @find:<class>)
# ---------------------------------------------------------------------------
class _ResolveError(Exception):
    """A step argument referenced something that isn't present."""


def _find_nodes(workflow: "dict | None", class_type: str) -> list[str]:
    """Return the ids of every node whose class_type matches (sorted, deterministic)."""
    if not workflow:
        return []
    return sorted(
        nid for nid, node in workflow.items()
        if isinstance(node, dict) and node.get("class_type") == class_type
    )


def _current_input(workflow: "dict | None", node_id: str, input_name: str) -> Any:
    node = (workflow or {}).get(node_id, {})
    if not isinstance(node, dict):
        return None
    return node.get("inputs", {}).get(input_name)


def _result_error(result: str) -> "str | None":
    """Extract an ``{"error": ...}`` from a tool result, else None (success)."""
    try:
        data = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return None  # non-JSON tool output is treated as success text
    if isinstance(data, dict) and "error" in data:
        return str(data["error"])
    return None


def _resolve_value(value: Any, vars_: dict, workflow: "dict | None") -> Any:
    if isinstance(value, str):
        if value.startswith("$"):
            name, _, field_path = value[1:].partition(".")
            if name not in vars_:
                raise _ResolveError(f"unknown step output ${name}")
            cur = vars_[name]
            for part in (field_path.split(".") if field_path else []):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    raise _ResolveError(f"{value} not found in a prior step's output")
            return cur
        if value.startswith("@find:"):
            cls = value[len("@find:"):]
            ids = _find_nodes(workflow, cls)
            if not ids:
                raise _ResolveError(f"no {cls} node to reference")
            return ids[0]
        return value
    if isinstance(value, dict):
        return {k: _resolve_value(v, vars_, workflow) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_value(v, vars_, workflow) for v in value]
    return value


def _resolve_args(args: dict, vars_: dict, workflow: "dict | None") -> dict:
    return {k: _resolve_value(v, vars_, workflow) for k, v in args.items()}


def _make_summary(recipe: Recipe, notes: list[str]) -> str:
    head = f"Applied **{recipe.name}** — {recipe.description}."
    if notes:
        head += " Changes: " + "; ".join(notes) + "."
    head += " (Reversible with undo_workflow_patch.)"
    return head


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------
class RecipeExecutor:
    """Run a recipe's steps through an injected dispatch + workflow getter."""

    def __init__(self, dispatch: Dispatch, workflow_getter: WorkflowGetter) -> None:
        self._dispatch = dispatch
        self._get_workflow = workflow_getter

    def execute(self, recipe: Recipe, text: str = "") -> RecipeResult:
        workflow = self._get_workflow()
        if recipe.requires_workflow and not workflow:
            return RecipeResult(
                applied=False,
                summary=(
                    f"There's no workflow open yet, so I can't apply '{recipe.name}'. "
                    "Load or build one first."
                ),
                fall_through=True,
            )

        vars_: dict[str, Any] = {}
        applied = 0
        notes: list[str] = []

        for step in recipe.steps:
            if isinstance(step, ParamMutation):
                ok, note = self._apply_param(step, workflow, notes)
            elif isinstance(step, ToolStep):
                ok, note = self._apply_tool(step, vars_, notes)
            else:
                return RecipeResult(
                    applied=False,
                    summary=f"Recipe '{recipe.name}' has an unsupported step.",
                    error="unsupported step type",
                )
            if not ok:
                # Honest partial report — never claim silent success.
                return RecipeResult(
                    applied=applied > 0,
                    summary=f"Started '{recipe.name}' but stopped: {note}",
                    steps_run=applied,
                    fall_through=(applied == 0),
                    error=note,
                )
            applied += 1
            # Refresh the snapshot so later @find / adjust_* steps see new nodes/values.
            workflow = self._get_workflow()

        return RecipeResult(
            applied=True,
            summary=_make_summary(recipe, notes),
            steps_run=applied,
        )

    def _apply_param(self, m: ParamMutation, workflow, notes) -> "tuple[bool, str]":
        node_ids = _find_nodes(workflow, m.target_class)
        if not node_ids:
            return False, f"there's no {m.target_class} node in the current workflow"
        for nid in node_ids:
            value = m.value
            if m.action in ("adjust_up", "adjust_down"):
                cur = _current_input(workflow, nid, m.input_name)
                if not isinstance(cur, (int, float)) or isinstance(cur, bool):
                    return False, f"{m.target_class}.{m.input_name} isn't a number to adjust"
                value = cur + (m.value if m.action == "adjust_up" else -m.value)
            result = self._dispatch(
                "set_input",
                {"node_id": nid, "input_name": m.input_name, "value": value},
            )
            err = _result_error(result)
            if err:
                return False, f"set_input {m.target_class}.{m.input_name} failed: {err}"
            notes.append(f"{m.target_class}.{m.input_name} → {value}")
        return True, ""

    def _apply_tool(self, step: ToolStep, vars_, notes) -> "tuple[bool, str]":
        workflow = self._get_workflow()
        try:
            args = _resolve_args(step.args, vars_, workflow)
        except _ResolveError as exc:
            return False, str(exc)
        result = self._dispatch(step.tool, args)
        err = _result_error(result)
        if err:
            return False, f"{step.tool} failed: {err}"
        if step.out:
            try:
                vars_[step.out] = json.loads(result)
            except (json.JSONDecodeError, TypeError):
                vars_[step.out] = {}
        notes.append(step.tool)
        return True, ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class RecipeRegistry:
    def __init__(self, recipes: "list[Recipe] | None" = None) -> None:
        self._recipes: list[Recipe] = list(recipes or [])

    def add(self, recipe: Recipe) -> None:
        self._recipes.append(recipe)

    def all(self) -> list[Recipe]:
        return list(self._recipes)

    def get(self, name: str) -> "Recipe | None":
        return next((r for r in self._recipes if r.name == name), None)

    def match(self, text: str) -> "Recipe | None":
        """Return the first recipe whose triggers match (None if nothing matches)."""
        if not text:
            return None
        for recipe in self._recipes:
            if recipe.matches(text):
                return recipe
        return None
