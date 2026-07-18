"""Regression tests for defect B1: the CLI-session sidecar (agent/verbs/_cli_state.py).

Every ``cozy`` invocation is a fresh process, so before the sidecar existed
the in-memory workflow session died between commands — the open→pull
round-trip, ``see`` with no argument, and ``run --recipe`` without ``-w``
were all non-functional across invocations, and pull's "one undo away —
survives between commands" promise died with the process.

These tests simulate two processes by wiping the in-memory session between
CliRunner invocations while the sidecar file survives — exactly what a real
process exit does. All offline: no ComfyUI server, no network, no API key.
"""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import agent.config as config
from agent.cli import app
from agent.tools import workflow_patch
from agent.verbs import _cli_state

runner = CliRunner()


CANVAS_GRAPH = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd15.safetensors"}},
    "2": {
        "class_type": "KSampler",
        "inputs": {"model": ["1", 0], "seed": 42, "steps": 20, "cfg": 8.0},
    },
}

_VALIDATION_OK = json.dumps(
    {
        "valid": True,
        "node_count": 7,
        "errors": [],
        "warnings": [],
        "message": "Workflow looks ready to execute.",
    }
)

_EXEC_COMPLETE = json.dumps(
    {
        "status": "complete",
        "prompt_id": "abc-123",
        "total_time_s": 3.0,
        "outputs": [{"type": "image", "filename": "out_00001.png", "subfolder": ""}],
        "node_timing": [{"node_id": "2", "class_type": "KSampler", "duration_s": 2.1}],
        "slowest_node": {"node_id": "2", "class_type": "KSampler", "duration_s": 2.1},
        "progress_events": 0,
        "progress_log": [],
        "monitoring": "websocket",
    }
)

_API_DOWN = json.dumps({"error": "ComfyUI is not reachable at http://127.0.0.1:8188"})


@pytest.fixture(autouse=True)
def _isolated_sessions_dir(tmp_path, monkeypatch):
    """Point the sidecar at a per-test directory — never the real sessions dir."""
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path / "sessions")


def _wipe_in_memory_session() -> None:
    """Simulate a process exit: the in-memory session dies, the sidecar survives."""
    assert workflow_patch.import_session_state({"current_workflow": None, "schema": 1}) is None
    assert workflow_patch.get_current_workflow() is None


def _flat(output: str) -> str:
    """Collapse console line-wrapping so phrase assertions survive any width."""
    return " ".join(output.split())


# ---------------------------------------------------------------------------
# Sidecar seam — persist() / restore() unit behavior
# ---------------------------------------------------------------------------


class TestSidecarSeam:
    def test_persist_restore_round_trip(self, sample_workflow_file):
        assert workflow_patch._load_workflow(str(sample_workflow_file)) is None
        before = workflow_patch.get_current_workflow()
        assert _cli_state.persist() is None
        assert _cli_state.sidecar_path().exists()

        _wipe_in_memory_session()
        assert _cli_state.restore() is None
        assert workflow_patch.get_current_workflow() == before

    def test_sidecar_is_deterministic_sorted_json(self, sample_workflow_file):
        assert workflow_patch._load_workflow(str(sample_workflow_file)) is None
        assert _cli_state.persist() is None
        raw = _cli_state.sidecar_path().read_text(encoding="utf-8")
        data = json.loads(raw)
        assert data["schema"] == 1
        assert raw == json.dumps(data, indent=2, sort_keys=True, allow_nan=False)

    def test_undo_history_survives_the_round_trip(self, sample_workflow_file):
        """The pull promise: history saved through the seam keeps undo working."""
        assert workflow_patch._load_workflow(str(sample_workflow_file)) is None
        result = json.loads(
            workflow_patch.handle("set_input", {"node_id": "2", "input_name": "cfg", "value": 3.5})
        )
        assert "error" not in result
        assert _cli_state.persist() is None

        _wipe_in_memory_session()
        assert _cli_state.restore() is None
        assert workflow_patch.get_current_workflow()["2"]["inputs"]["cfg"] == 3.5
        undo = json.loads(workflow_patch.handle("undo_workflow_patch", {}))
        assert "error" not in undo
        assert workflow_patch.get_current_workflow()["2"]["inputs"]["cfg"] == 7.0

    def test_restore_missing_file_is_quiet(self):
        assert _cli_state.restore() is None
        assert workflow_patch.get_current_workflow() is None

    def test_restore_corrupt_file_degrades_with_note(self):
        path = _cli_state.sidecar_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{this is not json", encoding="utf-8")
        note = _cli_state.restore()
        assert note is not None
        assert "damaged" in note
        assert workflow_patch.get_current_workflow() is None

    def test_restore_unknown_schema_leaves_live_session_untouched(self, sample_workflow_file):
        assert workflow_patch._load_workflow(str(sample_workflow_file)) is None
        live = json.loads(json.dumps(workflow_patch.get_current_workflow()))
        path = _cli_state.sidecar_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema": 99, "current_workflow": {}}), encoding="utf-8")
        note = _cli_state.restore()
        assert note is not None
        assert workflow_patch.get_current_workflow() == live


# ---------------------------------------------------------------------------
# Two-process simulation through the real CLI commands
# ---------------------------------------------------------------------------


class TestTwoProcessRoundTrip:
    def test_pull_then_open_across_processes(self):
        """The B1 live repro: pull in one process, open in the next.

        Process one pulls the (mocked) canvas graph — the real pull_canvas
        engine runs, the session baseline loads, and the CLI persists the
        sidecar. The in-memory session is then wiped (process exit). Process
        two runs ``cozy open`` and its push branch must see the workflow.
        """
        canvas_state = json.dumps({"workflow": CANVAS_GRAPH})

        def canvas_handle(name, tool_input):
            assert name == "get_canvas_state"
            return canvas_state

        with patch("agent.tools.canvas_bridge.handle", side_effect=canvas_handle):
            result = runner.invoke(app, ["pull"])
        assert result.exit_code == 0
        assert "session baseline" in _flat(result.output)
        assert _cli_state.sidecar_path().exists()

        _wipe_in_memory_session()

        pushes: list[dict] = []

        def bridge_handle(name, tool_input):
            assert name == "push_workflow_to_canvas"
            pushes.append(tool_input)
            return json.dumps({"pushed": True})

        with (
            patch("agent.tools.comfy_api.handle", return_value=json.dumps({"running": True})),
            patch("agent.tools.canvas_bridge.handle", side_effect=bridge_handle),
            patch("agent.verbs.open_canvas.webbrowser.open", return_value=True),
        ):
            result = CliRunner().invoke(app, ["open"])
        assert result.exit_code == 0
        assert len(pushes) == 1
        assert pushes[0]["workflow"] == CANVAS_GRAPH
        assert "now on the canvas" in _flat(result.output)

    def test_recipe_rail_restores_across_processes(self, sample_workflow_file):
        """``cozy run --recipe`` without -w must run on the persisted session."""
        assert workflow_patch._load_workflow(str(sample_workflow_file)) is None
        assert _cli_state.persist() is None
        _wipe_in_memory_session()

        with (
            patch(
                "agent.tools.comfy_execute.handle",
                side_effect=[_VALIDATION_OK, _EXEC_COMPLETE],
            ),
            patch("agent.tools.comfy_api.handle", return_value=_API_DOWN),
        ):
            result = CliRunner().invoke(app, ["run", "--recipe", "dreamier"])
        assert result.exit_code == 0
        assert "dreamier" in result.output
        workflow = workflow_patch.get_current_workflow()
        assert workflow is not None
        assert workflow["2"]["inputs"]["cfg"] == 6.0  # the real recipe landed

    def test_corrupt_sidecar_degrades_gracefully_at_the_cli(self):
        """A damaged sidecar is a note and a fresh start — never a traceback."""
        path = _cli_state.sidecar_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json at all", encoding="utf-8")

        with (
            patch("agent.tools.comfy_api.handle", return_value=json.dumps({"running": True})),
            patch("agent.verbs.open_canvas.webbrowser.open", return_value=True),
        ):
            result = runner.invoke(app, ["open"])
        assert result.exit_code == 0
        assert "Traceback" not in result.output
        flat = _flat(result.output)
        assert "damaged" in flat
        assert "No session workflow is loaded" in flat
