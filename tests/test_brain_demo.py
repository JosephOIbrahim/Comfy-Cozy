"""Tests for brain/demo.py — guided demo walkthroughs."""

import json

import pytest

from agent.brain import handle
from agent.brain._sdk import BrainAgent
from agent.brain.demo import DemoAgent, DEMO_SCENARIOS


# Get the auto-registered DemoAgent instance from the registry
def _get_demo_instance() -> DemoAgent:
    BrainAgent._register_all()
    agent = BrainAgent._registry.get("start_demo")
    assert isinstance(agent, DemoAgent)
    return agent


@pytest.fixture(autouse=True)
def reset_demo_state():
    """Reset demo state between tests."""
    agent = _get_demo_instance()
    agent._demo_state.update({
        "active": False,
        "scenario": None,
        "current_step_idx": 0,
        "started_at": None,
        "checkpoints": [],
    })
    yield


class TestStartDemo:
    def test_list_scenarios(self):
        result = json.loads(handle("start_demo", {"scenario": "list"}))
        assert result["count"] >= 4
        names = [s["name"] for s in result["available_scenarios"]]
        assert "model_swap" in names
        assert "speed_run" in names
        assert "controlnet_add" in names
        assert "full_pipeline" in names

    def test_start_model_swap(self):
        result = json.loads(handle("start_demo", {"scenario": "model_swap"}))
        assert result["demo_started"] is True
        assert result["scenario"] == "model_swap"
        assert result["total_steps"] == 4
        assert result["first_step"]["id"] == "analyze"

    def test_start_speed_run(self):
        result = json.loads(handle("start_demo", {"scenario": "speed_run"}))
        assert result["demo_started"] is True
        assert result["title"] == "Making It Fast"

    def test_start_unknown(self):
        result = json.loads(handle("start_demo", {"scenario": "nonexistent"}))
        assert "error" in result
        assert "available" in result

    def test_demo_state_activated(self):
        handle("start_demo", {"scenario": "model_swap"})
        agent = _get_demo_instance()
        assert agent._demo_state["active"] is True
        assert agent._demo_state["scenario"] == "model_swap"


class TestDemoCheckpoint:
    def test_checkpoint_no_demo(self):
        result = json.loads(handle("demo_checkpoint", {"step_completed": "test"}))
        assert "error" in result

    def test_checkpoint_advances(self):
        handle("start_demo", {"scenario": "model_swap"})
        result = json.loads(handle("demo_checkpoint", {
            "step_completed": "analyze",
            "notes": "Found SD 1.5 workflow with 30 steps",
        }))
        assert result["checkpoint"] == "analyze"
        assert result["next_step"]["id"] == "find_upgrade"
        assert "1/4" in result["progress"]

    def test_checkpoint_completes_demo(self):
        handle("start_demo", {"scenario": "model_swap"})
        # Complete all 4 steps
        steps = ["analyze", "find_upgrade", "apply_swap", "compare"]
        for i, step in enumerate(steps):
            result = json.loads(handle("demo_checkpoint", {
                "step_completed": step,
            }))

        assert result["demo_complete"] is True
        assert result["steps_completed"] == 4
        assert "elapsed_human" in result

    def test_checkpoint_records_history(self):
        handle("start_demo", {"scenario": "model_swap"})
        handle("demo_checkpoint", {
            "step_completed": "analyze",
            "notes": "test note",
        })
        agent = _get_demo_instance()
        assert len(agent._demo_state["checkpoints"]) == 1
        assert agent._demo_state["checkpoints"][0]["notes"] == "test note"


class TestDemoScenarios:
    """Verify all scenarios have valid structure."""

    def test_all_scenarios_have_required_fields(self):
        for name, scenario in DEMO_SCENARIOS.items():
            assert "title" in scenario, f"{name} missing title"
            assert "description" in scenario, f"{name} missing description"
            assert "steps" in scenario, f"{name} missing steps"
            assert len(scenario["steps"]) >= 3, f"{name} has too few steps"

    def test_all_steps_have_required_fields(self):
        for name, scenario in DEMO_SCENARIOS.items():
            for step in scenario["steps"]:
                assert "id" in step, f"{name}/{step} missing id"
                assert "label" in step, f"{name}/{step} missing label"
                assert "narration" in step, f"{name}/{step} missing narration"
                assert "suggested_tools" in step, f"{name}/{step} missing suggested_tools"

    def test_scenario_durations_present(self):
        for name, scenario in DEMO_SCENARIOS.items():
            assert "duration_estimate" in scenario, f"{name} missing duration_estimate"


# ---------------------------------------------------------------------------
# Cycle 46 — Demo handler required field guards
# ---------------------------------------------------------------------------

class TestStartDemoRequiredField:
    """start_demo must return structured error when scenario is missing or invalid."""

    def test_missing_scenario_returns_error(self):
        result = json.loads(handle("start_demo", {}))
        assert "error" in result
        assert "scenario" in result["error"].lower()

    def test_empty_scenario_returns_error(self):
        result = json.loads(handle("start_demo", {"scenario": ""}))
        assert "error" in result

    def test_none_scenario_returns_error(self):
        result = json.loads(handle("start_demo", {"scenario": None}))
        assert "error" in result

    def test_valid_scenario_not_blocked(self):
        """The guard must not block the 'list' scenario value."""
        result = json.loads(handle("start_demo", {"scenario": "list"}))
        assert "error" not in result or "scenario" not in result.get("error", "").lower()


class TestDemoCheckpointRequiredField:
    """demo_checkpoint must return structured error when step_completed is missing."""

    def test_missing_step_completed_returns_error(self):
        result = json.loads(handle("demo_checkpoint", {}))
        assert "error" in result
        assert "step_completed" in result["error"].lower()
