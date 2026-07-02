"""Unit tests for the zero-LLM recipe layer (agent/recipes).

The engine is exercised with a mocked dispatch + workflow getter, so no tool
layer, gate, or ComfyUI is involved — pure recipe logic.
"""

from __future__ import annotations

import json

from agent.recipes import Recipe, RecipeExecutor, ToolStep
from agent.recipes.builtin import build_default_registry


class FakeBackend:
    """In-memory workflow + dispatch mimicking set_input/add_node/connect_nodes."""

    def __init__(self, workflow=None, fail_on=None):
        self.workflow = workflow if workflow is not None else {}
        self.calls = []
        self._next_id = 100
        self._fail_on = fail_on  # a tool name to return an error for

    def get_workflow(self):
        return self.workflow

    def dispatch(self, name, args):
        self.calls.append((name, args))
        if self._fail_on == name:
            return json.dumps({"error": f"forced failure in {name}"})
        if name == "set_input":
            node = self.workflow.setdefault(args["node_id"], {"inputs": {}})
            node.setdefault("inputs", {})[args["input_name"]] = args["value"]
            return json.dumps({"ok": True})
        if name == "add_node":
            nid = str(self._next_id)
            self._next_id += 1
            self.workflow[nid] = {
                "class_type": args["class_type"],
                "inputs": dict(args.get("inputs", {})),
            }
            return json.dumps({"node_id": nid})
        if name == "connect_nodes":
            return json.dumps({"ok": True})
        return json.dumps({"error": f"unknown tool {name}"})


def _ksampler_wf():
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {"cfg": 8.0, "steps": 20, "sampler_name": "euler", "scheduler": "normal"},
        },
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
    }


def _executor(backend):
    return RecipeExecutor(backend.dispatch, backend.get_workflow)


# ---------------------------------------------------------------------------
# Registry / matching
# ---------------------------------------------------------------------------
def test_registry_has_expected_recipes():
    reg = build_default_registry()
    names = {r.name for r in reg.all()}
    assert {"dreamier", "sharper", "faster", "higher_quality", "upscale_2x_pixel"} <= names
    assert len(reg.all()) == 7


def test_match_dreamier_and_miss():
    reg = build_default_registry()
    assert reg.match("can you make it dreamier please").name == "dreamier"
    assert reg.match("hello, unrelated text") is None
    assert reg.match("") is None


# ---------------------------------------------------------------------------
# ParamMutation recipes
# ---------------------------------------------------------------------------
def test_dreamier_sets_all_ksampler_params():
    backend = FakeBackend(_ksampler_wf())
    recipe = build_default_registry().get("dreamier")
    result = _executor(backend).execute(recipe, "make it dreamier")

    assert result.applied is True
    assert result.fall_through is False
    inputs = backend.workflow["3"]["inputs"]
    assert inputs["cfg"] == 6.0
    assert inputs["steps"] == 28          # 20 + adjust_up 8
    assert inputs["sampler_name"] == "dpmpp_2m"
    assert inputs["scheduler"] == "karras"


def test_adjust_up_reads_current_value():
    backend = FakeBackend(_ksampler_wf())
    recipe = build_default_registry().get("higher_quality")
    _executor(backend).execute(recipe)
    assert backend.workflow["3"]["inputs"]["steps"] == 32  # 20 + 12


def test_faster_sets_absolute_steps():
    backend = FakeBackend(_ksampler_wf())
    recipe = build_default_registry().get("faster")
    _executor(backend).execute(recipe)
    assert backend.workflow["3"]["inputs"]["steps"] == 18


def test_param_applies_to_every_matching_node():
    wf = {
        "3": {"class_type": "KSampler", "inputs": {"cfg": 8.0, "steps": 20,
              "sampler_name": "euler", "scheduler": "normal"}},
        "5": {"class_type": "KSampler", "inputs": {"cfg": 7.0, "steps": 25,
              "sampler_name": "euler", "scheduler": "normal"}},
    }
    backend = FakeBackend(wf)
    _executor(backend).execute(build_default_registry().get("dreamier"))
    assert backend.workflow["3"]["inputs"]["cfg"] == 6.0
    assert backend.workflow["5"]["inputs"]["cfg"] == 6.0


# ---------------------------------------------------------------------------
# Fall-through (never hard-fail a turn)
# ---------------------------------------------------------------------------
def test_no_workflow_falls_through():
    backend = FakeBackend({})
    recipe = build_default_registry().get("dreamier")
    result = _executor(backend).execute(recipe)
    assert result.applied is False
    assert result.fall_through is True
    assert backend.calls == []  # nothing dispatched


def test_missing_target_node_falls_through():
    # Workflow exists but has no KSampler.
    backend = FakeBackend({"4": {"class_type": "CheckpointLoaderSimple", "inputs": {}}})
    recipe = build_default_registry().get("dreamier")
    result = _executor(backend).execute(recipe)
    assert result.applied is False
    assert result.fall_through is True
    assert "KSampler" in (result.error or "")


# ---------------------------------------------------------------------------
# ToolStep build recipes ($var + @find dataflow)
# ---------------------------------------------------------------------------
def test_upscale_resolves_var_and_find():
    backend = FakeBackend({"8": {"class_type": "VAEDecode", "inputs": {}}})
    recipe = build_default_registry().get("upscale_2x_pixel")
    result = _executor(backend).execute(recipe, "upscale it 2x")

    assert result.applied is True
    assert result.steps_run == 4
    connects = [args for (name, args) in backend.calls if name == "connect_nodes"]
    assert len(connects) == 2
    # First connect: loader ($loader.node_id -> "100") into the upscaler ("101").
    assert connects[0]["from_node"] == "100"
    assert connects[0]["from_output"] == 0
    assert connects[0]["to_node"] == "101"
    assert connects[0]["to_input"] == "upscale_model"
    # Second connect: @find:VAEDecode resolved to the existing node "8".
    assert connects[1]["from_node"] == "8"
    assert connects[1]["to_input"] == "image"


def test_find_missing_node_stops_honestly():
    # No VAEDecode -> the @find step fails; the two add_nodes already ran.
    backend = FakeBackend({})
    # bypass requires_workflow by injecting a non-empty workflow with no VAEDecode
    backend.workflow = {"1": {"class_type": "EmptyLatentImage", "inputs": {}}}
    recipe = build_default_registry().get("upscale_2x_pixel")
    result = _executor(backend).execute(recipe, "make it 2x bigger")
    assert result.error is not None
    assert "VAEDecode" in result.error
    assert result.steps_run == 3          # two add_nodes + one connect succeeded
    assert result.fall_through is False    # partial work happened; don't re-run via LLM


def test_tool_error_stops_and_reports():
    backend = FakeBackend(_ksampler_wf(), fail_on="set_input")
    recipe = build_default_registry().get("faster")
    result = _executor(backend).execute(recipe)
    assert result.applied is False         # nothing committed
    assert result.fall_through is True
    assert "set_input" in (result.error or "")


def test_custom_recipe_partial_failure_does_not_fall_through():
    # A two-step build where the second call fails after the first succeeds.
    backend = FakeBackend({}, fail_on="connect_nodes")
    backend.workflow = {}
    recipe = Recipe(
        name="t", description="t", triggers=[r"t"], requires_workflow=False,
        steps=[
            ToolStep("add_node", {"class_type": "Foo"}, out="a"),
            ToolStep("connect_nodes", {"from_node": "$a.node_id", "from_output": 0,
                                       "to_node": "$a.node_id", "to_input": "x"}),
        ],
    )
    result = RecipeExecutor(backend.dispatch, backend.get_workflow).execute(recipe)
    assert result.steps_run == 1
    assert result.applied is True          # partial work happened
    assert result.fall_through is False
    assert "connect_nodes" in (result.error or "")


# ---------------------------------------------------------------------------
# MCP tool surface (apply_recipe / list_recipes via the gated dispatcher)
# ---------------------------------------------------------------------------
def test_list_recipes_tool():
    from agent.tools import handle
    data = json.loads(handle("list_recipes", {}))
    names = {r["name"] for r in data["recipes"]}
    assert "dreamier" in names and "upscale_2x_pixel" in names
    assert len(data["recipes"]) == 7


def test_apply_recipe_tool_no_match():
    from agent.tools import handle
    data = json.loads(handle("apply_recipe", {"text": "completely unrelated request"}))
    assert data["matched"] is False
    assert "dreamier" in data["available"]


def test_apply_recipe_tool_no_workflow_falls_through():
    # No workflow loaded (conftest resets state) -> a requires_workflow recipe
    # matches but cannot apply, and asks the caller to handle it normally.
    from agent.tools import handle
    data = json.loads(handle("apply_recipe", {"name": "dreamier"}))
    assert data["matched"] is True
    assert data["applied"] is False
    assert data["fall_through"] is True
