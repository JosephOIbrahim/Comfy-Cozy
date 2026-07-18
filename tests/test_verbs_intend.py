"""Tests for the INTEND verb engine (agent/verbs/intend.py).

The recipe registry is real and offline. The tool-dispatch and session-workflow
seams are mocked, so the tests exercise the REAL ``recipes_tool.handle`` +
``RecipeExecutor`` path without loading the full tool dispatcher or ComfyUI.
"""

import json
from unittest.mock import patch

import pytest

from agent.recipes import RecipeRegistry, get_registry
from agent.verbs import intend

ALL_RECIPE_NAMES = [
    "dreamier",
    "sharper",
    "faster",
    "higher_quality",
    "more_variation",
    "less_variation",
    "upscale_2x_pixel",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ksampler_workflow():
    """Minimal API-format workflow with one KSampler (recipe target)."""
    return {
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "cfg": 8.0,
                "steps": 20,
                "sampler_name": "euler",
                "scheduler": "normal",
                "seed": 42,
                "model": ["1", 0],
            },
        },
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd15.safetensors"}},
    }


@pytest.fixture
def live_session(ksampler_workflow):
    """Wire a fake live session: dispatch mutates the dict, getters read it.

    Patches the production seams so the REAL recipes_tool.handle → run_recipe →
    RecipeExecutor path runs against this in-memory workflow.
    """
    workflow = ksampler_workflow

    def fake_dispatch(name, args):
        assert name == "set_input", f"unexpected tool in param recipe: {name}"
        workflow[args["node_id"]]["inputs"][args["input_name"]] = args["value"]
        return json.dumps({"success": True})

    def get_workflow():
        return workflow

    def snapshot():
        return json.loads(json.dumps(workflow))

    with (
        patch("agent.recipes._prod_dispatch", fake_dispatch),
        patch("agent.recipes._prod_workflow", get_workflow),
        patch("agent.verbs.intend._session_workflow", snapshot),
    ):
        yield workflow


@pytest.fixture
def partial_session(ksampler_workflow):
    """Live session whose dispatch REJECTS the scheduler step.

    dreamier's 4th step (KSampler.scheduler) fails, so the REAL executor
    returns a partial result: applied=True, steps_run=3, error set. This
    un-mocks what the old tests never exercised — a mid-recipe failure.
    """
    workflow = ksampler_workflow

    def fake_dispatch(name, args):
        assert name == "set_input", f"unexpected tool in param recipe: {name}"
        if args["input_name"] == "scheduler":
            return json.dumps({"error": "that scheduler isn't available on this sampler"})
        workflow[args["node_id"]]["inputs"][args["input_name"]] = args["value"]
        return json.dumps({"success": True})

    def get_workflow():
        return workflow

    def snapshot():
        return json.loads(json.dumps(workflow))

    with (
        patch("agent.recipes._prod_dispatch", fake_dispatch),
        patch("agent.recipes._prod_workflow", get_workflow),
        patch("agent.verbs.intend._session_workflow", snapshot),
    ):
        yield workflow


# ---------------------------------------------------------------------------
# resolve_recipe — hits
# ---------------------------------------------------------------------------


class TestResolveRecipe:
    def test_exact_name(self):
        result = intend.resolve_recipe("dreamier")
        assert result["matched"] is True
        assert result["recipe"]["name"] == "dreamier"
        assert result["available"] == ALL_RECIPE_NAMES

    def test_name_is_case_and_space_tolerant(self):
        result = intend.resolve_recipe("  Higher Quality ")
        assert result["matched"] is True
        assert result["recipe"]["name"] == "higher_quality"

    def test_free_text_trigger_match(self):
        result = intend.resolve_recipe("make it dreamier please")
        assert result["matched"] is True
        assert result["recipe"]["name"] == "dreamier"

    def test_registry_is_real_and_complete(self):
        assert [r.name for r in get_registry().all()] == ALL_RECIPE_NAMES


# ---------------------------------------------------------------------------
# resolve_recipe — misses (never raise)
# ---------------------------------------------------------------------------


class TestResolveMiss:
    def test_miss_returns_available_names(self):
        result = intend.resolve_recipe("cinematic bokeh explosion")
        assert result["matched"] is False
        assert result["recipe"] is None
        assert result["available"] == ALL_RECIPE_NAMES
        for name in ALL_RECIPE_NAMES:
            assert name in result["message"]

    def test_near_miss_suggests_closest(self):
        result = intend.resolve_recipe("dreamir")
        assert result["matched"] is False
        assert "dreamier" in result["message"]

    def test_empty_text(self):
        result = intend.resolve_recipe("   ")
        assert result["matched"] is False
        assert result["available"] == ALL_RECIPE_NAMES

    def test_custom_registry_injection(self):
        result = intend.resolve_recipe("dreamier", registry=RecipeRegistry([]))
        assert result["matched"] is False
        assert result["available"] == []


# ---------------------------------------------------------------------------
# apply_recipe_to_session
# ---------------------------------------------------------------------------


class TestApplyRecipeToSession:
    def test_happy_path_reports_old_to_new(self, live_session):
        result = intend.apply_recipe_to_session("dreamier")
        assert result["applied"] is True
        assert result["matched"] is True
        assert result["recipe"]["name"] == "dreamier"
        assert result["steps_run"] == 4
        assert result["error"] is None
        changed = {(c["param"]): (c["old"], c["new"]) for c in result["changes"]}
        assert changed["cfg"] == (8.0, 6.0)
        assert changed["steps"] == (20, 28)  # adjust_up 8 from 20
        assert changed["sampler_name"] == ("euler", "dpmpp_2m")
        assert changed["scheduler"] == ("normal", "karras")
        assert result["nodes_added"] == []
        assert "dreamier" in result["message"]
        assert "**" not in result["message"]

    def test_happy_path_mutates_the_session_workflow(self, live_session):
        intend.apply_recipe_to_session("sharper")
        assert live_session["3"]["inputs"]["cfg"] == 9.0
        assert live_session["3"]["inputs"]["sampler_name"] == "euler"

    def test_free_text_routes_through_same_path(self, live_session):
        result = intend.apply_recipe_to_session("speed it up")
        assert result["applied"] is True
        assert result["recipe"]["name"] == "faster"
        assert live_session["3"]["inputs"]["steps"] == 18

    def test_no_workflow_loaded_degrades_in_human_words(self):
        with (
            patch("agent.recipes._prod_workflow", lambda: None),
            patch("agent.verbs.intend._session_workflow", lambda: None),
        ):
            result = intend.apply_recipe_to_session("dreamier")
        assert result["applied"] is False
        assert result["fall_through"] is True
        assert result["changes"] == []
        assert "no workflow" in result["message"].lower()

    def test_unknown_recipe_short_circuits(self):
        # Miss path must not touch the engine at all.
        with patch("agent.tools.recipes_tool.handle") as handler:
            result = intend.apply_recipe_to_session("nope not a recipe")
        handler.assert_not_called()
        assert result["matched"] is False
        assert result["applied"] is False
        assert result["fall_through"] is True
        assert result["available"] == ALL_RECIPE_NAMES

    def test_engine_exception_never_escapes(self, live_session):
        with patch("agent.tools.recipes_tool.handle", side_effect=RuntimeError("boom")):
            result = intend.apply_recipe_to_session("dreamier")
        assert result["applied"] is False
        assert result["error"] == "recipe engine failure"
        assert "unexpected problem" in result["message"]


# ---------------------------------------------------------------------------
# Partial failure honesty (defects D2 + D3)
# ---------------------------------------------------------------------------


class TestPartialFailureHonesty:
    def test_partial_result_carries_applied_and_error(self, partial_session):
        result = intend.apply_recipe_to_session("dreamier")
        # CONTRACT (Lane B): error set means the CLI exits 1 and does NOT execute.
        assert result["applied"] is True
        assert result["error"] is not None
        assert result["steps_run"] == 3
        assert result["recipe"]["total_steps"] == 4
        assert len(result["changes"]) == 3  # cfg, steps, sampler_name landed

    def test_render_partial_failure_never_shows_success_header(self, partial_session):
        result = intend.apply_recipe_to_session("dreamier")
        text = intend.render_recipe_result(result)
        assert text.startswith("Applied 3 of 4 steps, then stopped:")
        assert "scheduler" in text  # the stop reason is not dropped
        assert "Applied 'dreamier' —" not in text  # never the success header

    def test_render_partial_failure_keeps_landed_changes(self, partial_session):
        result = intend.apply_recipe_to_session("dreamier")
        text = intend.render_recipe_result(result)
        assert "cfg: 8.0 -> 6.0" in text
        assert "steps: 20 -> 28" in text
        assert "sampler_name: euler -> dpmpp_2m" in text
        assert "3 undo steps" in text  # honest undo count for what DID apply

    def test_render_multi_step_success_reports_honest_undo_count(self, live_session):
        result = intend.apply_recipe_to_session("dreamier")
        text = intend.render_recipe_result(result)
        assert "Reversible — this recipe is 4 undo steps." in text
        assert "puts it right back" not in text  # the one-undo claim is false here

    def test_render_single_change_keeps_simple_undo_phrasing(self, live_session):
        result = intend.apply_recipe_to_session("faster")  # 1 step, 1 change
        text = intend.render_recipe_result(result)
        assert "Every change is reversible — undo puts it right back." in text


# ---------------------------------------------------------------------------
# Diff helper
# ---------------------------------------------------------------------------


class TestDiffWorkflows:
    def test_detects_added_nodes(self):
        before = {"1": {"class_type": "A", "inputs": {}}}
        after = {
            "1": {"class_type": "A", "inputs": {}},
            "2": {"class_type": "ImageUpscaleWithModel", "inputs": {}},
        }
        changes, added = intend._diff_workflows(before, after)
        assert changes == []
        assert added == [{"node_id": "2", "class_type": "ImageUpscaleWithModel"}]

    def test_none_snapshots(self):
        changes, added = intend._diff_workflows(None, None)
        assert changes == []
        assert added == []

    def test_deterministic_ordering(self):
        before = {"3": {"class_type": "K", "inputs": {"b": 1, "a": 1}}}
        after = {"3": {"class_type": "K", "inputs": {"b": 2, "a": 2}}}
        changes, _ = intend._diff_workflows(before, after)
        assert [c["param"] for c in changes] == ["a", "b"]


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


class TestRenderers:
    def test_render_applied_result(self, live_session):
        result = intend.apply_recipe_to_session("dreamier")
        text = intend.render_recipe_result(result)
        assert "Applied 'dreamier'" in text
        assert "cfg: 8.0 -> 6.0" in text
        assert "reversible" in text.lower()

    def test_render_miss_lists_names(self):
        result = intend.apply_recipe_to_session("nope not a recipe")
        text = intend.render_recipe_result(result)
        for name in ALL_RECIPE_NAMES:
            assert name in text

    def test_render_no_workflow(self):
        with (
            patch("agent.recipes._prod_workflow", lambda: None),
            patch("agent.verbs.intend._session_workflow", lambda: None),
        ):
            result = intend.apply_recipe_to_session("dreamier")
        text = intend.render_recipe_result(result)
        assert "no workflow" in text.lower()

    def test_render_connection_values_stay_abstract(self):
        assert intend._fmt_value(["1", 0]) == "(rewired)"
        assert intend._fmt_value(None) == "(unset)"
        assert intend._fmt_value(6.0) == "6.0"

    def test_render_recipe_list_has_all_names(self):
        text = intend.render_recipe_list()
        for name in ALL_RECIPE_NAMES:
            assert name in text
        assert "cozy run --recipe" in text

    def test_render_recipe_list_empty_registry(self):
        assert "No recipes" in intend.render_recipe_list(RecipeRegistry([]))
