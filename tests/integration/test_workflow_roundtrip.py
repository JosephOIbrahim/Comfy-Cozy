"""Integration tests — workflow load, patch, undo roundtrip.

Uses real workflow parsing but mocks execution (no ComfyUI queue).
"""

import json

import pytest

from agent.tools import handle, workflow_patch

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_patch_state():
    """Reset workflow_patch module state between tests."""
    workflow_patch._get_state()["loaded_path"] = None
    workflow_patch._get_state()["base_workflow"] = None
    workflow_patch._get_state()["current_workflow"] = None
    workflow_patch._get_state()["history"] = []
    workflow_patch._get_state()["format"] = None
    workflow_patch._set_engine(None)
    yield
    workflow_patch._get_state()["loaded_path"] = None
    workflow_patch._get_state()["base_workflow"] = None
    workflow_patch._get_state()["current_workflow"] = None
    workflow_patch._get_state()["history"] = []
    workflow_patch._get_state()["format"] = None
    workflow_patch._set_engine(None)


class TestWorkflowRoundtrip:
    """Load, patch, validate, undo — all with real parsing."""

    def test_load_patch_validate(
        self, comfyui_available, clean_session, sample_workflow_file
    ):
        """Load workflow, patch steps, validate structure."""
        # Load and patch
        result = json.loads(
            handle(
                "apply_workflow_patch",
                {
                    "path": str(sample_workflow_file),
                    "patches": [
                        {"op": "replace", "path": "/2/inputs/steps", "value": 30},
                    ],
                },
            )
        )
        assert "error" not in result
        assert result.get("applied") == 1

        # Verify steps changed
        wf = workflow_patch.get_current_workflow()
        assert wf is not None
        assert wf["2"]["inputs"]["steps"] == 30

    def test_load_patch_undo_verify(
        self, comfyui_available, clean_session, sample_workflow_file
    ):
        """Load, patch, undo, verify state matches original."""
        # Load
        handle(
            "apply_workflow_patch",
            {
                "path": str(sample_workflow_file),
                "patches": [
                    {"op": "replace", "path": "/2/inputs/steps", "value": 20},
                ],
            },
        )
        original_steps = workflow_patch.get_current_workflow()["2"]["inputs"]["steps"]

        # Patch to change steps
        handle(
            "set_input",
            {"node_id": "2", "input_name": "steps", "value": 50},
        )
        assert workflow_patch.get_current_workflow()["2"]["inputs"]["steps"] == 50

        # Undo
        undo = json.loads(handle("undo_workflow_patch", {}))
        assert undo.get("undone") is True

        # Verify restored
        assert (
            workflow_patch.get_current_workflow()["2"]["inputs"]["steps"]
            == original_steps
        )
