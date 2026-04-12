"""Integration tests — session save/load roundtrip."""

import json

import pytest
from unittest.mock import patch as mock_patch

from agent.tools import handle, workflow_patch

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _reset_patch_state_and_disable_gate():
    """Reset workflow_patch state and disable gate between tests."""
    workflow_patch._get_state()["loaded_path"] = None
    workflow_patch._get_state()["base_workflow"] = None
    workflow_patch._get_state()["current_workflow"] = None
    workflow_patch._get_state()["history"] = []
    workflow_patch._get_state()["format"] = None
    workflow_patch._set_engine(None)
    with mock_patch("agent.config.GATE_ENABLED", False):
        yield
    workflow_patch._get_state()["loaded_path"] = None
    workflow_patch._get_state()["base_workflow"] = None
    workflow_patch._get_state()["current_workflow"] = None
    workflow_patch._get_state()["history"] = []
    workflow_patch._get_state()["format"] = None
    workflow_patch._set_engine(None)


class TestSessionPersistence:
    """Save and load sessions, verify state survives roundtrip."""

    def test_save_load_roundtrip(self, tmp_path, sample_workflow_file):
        """Save session to tmp_path, reload, verify workflow state matches."""
        # Load a workflow
        load_result = json.loads(
            handle(
                "apply_workflow_patch",
                {
                    "path": str(sample_workflow_file),
                    "patches": [
                        {"op": "replace", "path": "/2/inputs/steps", "value": 25},
                    ],
                },
            )
        )
        assert "error" not in load_result
        wf_before = workflow_patch.get_current_workflow()
        assert wf_before is not None

        # Save session (mock sessions dir to tmp_path)
        with mock_patch("agent.memory.session.SESSIONS_DIR", tmp_path):
            save_result = json.loads(handle("save_session", {"name": "test-roundtrip"}))
            assert "error" not in save_result, save_result

            # Clear workflow state
            workflow_patch._get_state()["current_workflow"] = None
            workflow_patch._get_state()["base_workflow"] = None

            # Load session back
            load_result = json.loads(
                handle("load_session", {"name": "test-roundtrip"})
            )
            assert "error" not in load_result

        # Verify workflow was restored
        wf_after = workflow_patch.get_current_workflow()
        assert wf_after is not None
        assert wf_after["2"]["inputs"]["steps"] == 25

    def test_notes_persist(self, tmp_path):
        """Add notes, save, reload, verify notes present."""
        session_name = "test-notes"
        with mock_patch("agent.memory.session.SESSIONS_DIR", tmp_path):
            # Add notes (requires session_name + note fields)
            r1 = json.loads(
                handle("add_note", {"session_name": session_name, "note": "First note"})
            )
            assert "error" not in r1, r1
            r2 = json.loads(
                handle("add_note", {"session_name": session_name, "note": "Second note"})
            )
            assert "error" not in r2, r2

            # Load (add_note auto-creates the session file)
            load_result = json.loads(
                handle("load_session", {"name": session_name})
            )
            assert "error" not in load_result

            notes = load_result.get("notes", [])
            note_texts = [
                n.get("text", "") if isinstance(n, dict) else str(n)
                for n in notes
            ]
            assert "First note" in note_texts
            assert "Second note" in note_texts
