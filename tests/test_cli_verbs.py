"""CLI wiring tests for the Mile-2 verbs: models/nodes (FIND), open (OPEN-OUT), see (SEE).

The engine layers (agent/verbs/{find,see,open_canvas}.py) carry their own test
files; these tests pin the CLI layer only — command registration, help text,
happy-path rendering with the engines mocked, ComfyUI-down degradation, and
exit codes. All mocked: no ComfyUI server, no network, no API key.
"""

import json
import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import agent.config as config
from agent.cli import app

runner = CliRunner(env={"NO_COLOR": "1"})


@pytest.fixture(autouse=True)
def _isolated_sessions_dir(tmp_path, monkeypatch):
    """The open/see verbs now restore the CLI session sidecar (defect B1) —
    keep every test's sidecar reads out of the real sessions directory."""
    monkeypatch.setattr(config, "SESSIONS_DIR", tmp_path / "sessions")


# ---------------------------------------------------------------------------
# Fixture-shaped reports (match the engine contracts' structured dict shapes)
# ---------------------------------------------------------------------------


def _models_report(note: str | None = None) -> dict:
    return {
        "source": "X:/COMFYUI_Database/models",
        "groups": [
            {
                "model_type": "checkpoints",
                "count": 1,
                "models": [
                    {
                        "name": "sd15_base.safetensors",
                        "size": "2.0 GB",
                        "size_bytes": 2147483648,
                        "family": "sd15",
                        "family_label": "SD 1.5",
                        "status": "ok",
                        "glyph": "✓",
                        "note": None,
                    }
                ],
            }
        ],
        "workflow": {"checked": False, "references": [], "note": "No workflow loaded"},
        "note": note,
    }


def _nodes_report(wf_note: str | None = None) -> dict:
    return {
        "source": "X:/COMFYUI_Database/Custom_Nodes",
        "packs": [
            {
                "name": "ComfyUI-Manager",
                "status": "ok",
                "glyph": "✓",
                "registers_nodes": True,
                "has_requirements": True,
            }
        ],
        "count": 1,
        "workflow": {"checked": False, "missing": [], "note": wf_note},
        "note": None,
    }


# ---------------------------------------------------------------------------
# Help surfaces — every new command registers and self-describes
# ---------------------------------------------------------------------------


def _plain(output: str) -> str:
    """Strip ANSI styles so flag assertions survive color-rendering CI envs
    (rich splits option names into styled spans, breaking substring checks)."""
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


class TestHelp:
    def test_models_group_help(self):
        result = runner.invoke(app, ["models", "--help"])
        assert result.exit_code == 0
        assert "list" in _plain(result.output)

    def test_models_list_help(self):
        result = runner.invoke(app, ["models", "list", "--help"])
        assert result.exit_code == 0
        assert "--workflow" in _plain(result.output)

    def test_nodes_list_help(self):
        result = runner.invoke(app, ["nodes", "list", "--help"])
        assert result.exit_code == 0
        assert "--workflow" in _plain(result.output)

    def test_open_help(self):
        result = runner.invoke(app, ["open", "--help"])
        assert result.exit_code == 0
        assert "--no-push" in _plain(result.output)

    def test_see_help(self):
        result = runner.invoke(app, ["see", "--help"])
        assert result.exit_code == 0
        assert "--timeout" in _plain(result.output)

    def test_find_help(self):
        result = runner.invoke(app, ["find", "--help"])
        assert result.exit_code == 0
        assert "--limit" in _plain(result.output)

    def test_existing_commands_still_registered(self):
        """Additive-only guarantee: the pre-existing commands keep their names."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for name in (
            "run",
            "inspect",
            "diagnose",
            "parse",
            "sessions",
            "search",
            "orchestrate",
            "autoresearch",
            "autonomous",
            "mcp",
        ):
            assert name in result.output


# ---------------------------------------------------------------------------
# cozy models list
# ---------------------------------------------------------------------------


class TestModelsList:
    def test_happy_path(self):
        with patch("agent.verbs.find.build_models_report", return_value=_models_report()) as m:
            result = runner.invoke(app, ["models", "list"])
        assert result.exit_code == 0
        assert "checkpoints (1)" in result.output
        assert "sd15_base.safetensors" in result.output
        m.assert_called_once_with(model_type=None, workflow=None)

    def test_type_filter_passes_through(self):
        with patch("agent.verbs.find.build_models_report", return_value=_models_report()) as m:
            result = runner.invoke(app, ["models", "list", "loras"])
        assert result.exit_code == 0
        m.assert_called_once_with(model_type="loras", workflow=None)

    def test_degrades_with_note_no_models_dir(self):
        note = "No models folder found at X:/COMFYUI_Database/models"
        report = _models_report(note=note)
        report["groups"] = []
        with patch("agent.verbs.find.build_models_report", return_value=report):
            result = runner.invoke(app, ["models", "list"])
        assert result.exit_code == 0
        assert "No models folder found" in result.output

    def test_workflow_flag_loads_and_forwards_json(self, tmp_path):
        wf = {"1": {"class_type": "CheckpointLoaderSimple", "inputs": {}}}
        path = tmp_path / "wf.json"
        path.write_text(json.dumps(wf), encoding="utf-8")
        with patch("agent.verbs.find.build_models_report", return_value=_models_report()) as m:
            result = runner.invoke(app, ["models", "list", "--workflow", str(path)])
        assert result.exit_code == 0
        m.assert_called_once_with(model_type=None, workflow=wf)

    def test_workflow_flag_missing_file_exits_1(self):
        result = runner.invoke(app, ["models", "list", "--workflow", "no_such_file.json"])
        assert result.exit_code == 1
        assert "File not found" in result.output

    def test_workflow_flag_bad_json_exits_1(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        result = runner.invoke(app, ["models", "list", "--workflow", str(path)])
        assert result.exit_code == 1
        assert "JSON" in result.output


# ---------------------------------------------------------------------------
# cozy nodes list
# ---------------------------------------------------------------------------


class TestNodesList:
    def test_happy_path(self):
        with patch("agent.verbs.find.build_nodes_report", return_value=_nodes_report()) as m:
            result = runner.invoke(app, ["nodes", "list"])
        assert result.exit_code == 0
        assert "ComfyUI-Manager" in result.output
        m.assert_called_once_with(workflow_path=None)

    def test_workflow_flag_passes_path(self):
        with patch("agent.verbs.find.build_nodes_report", return_value=_nodes_report()) as m:
            result = runner.invoke(app, ["nodes", "list", "--workflow", "shot.json"])
        assert result.exit_code == 0
        m.assert_called_once_with(workflow_path="shot.json")

    def test_comfyui_down_note_prints_and_exits_0(self):
        wf_note = "ComfyUI is not running, so I skipped the live check for missing workflow nodes."
        with patch("agent.verbs.find.build_nodes_report", return_value=_nodes_report(wf_note)):
            result = runner.invoke(app, ["nodes", "list"])
        assert result.exit_code == 0
        assert "ComfyUI is not running" in result.output
        assert "ComfyUI-Manager" in result.output  # pack list still shown


# ---------------------------------------------------------------------------
# cozy find (palette — pure engine, no mocking needed)
# ---------------------------------------------------------------------------


class TestFindPalette:
    def test_no_query_shows_palette(self):
        result = runner.invoke(app, ["find"])
        assert result.exit_code == 0
        assert "cozy models list" in result.output

    def test_query_ranks_models_verb(self):
        result = runner.invoke(app, ["find", "models"])
        assert result.exit_code == 0
        assert "cozy models list" in result.output


# ---------------------------------------------------------------------------
# cozy open
# ---------------------------------------------------------------------------


def _open_result(opened: bool, pushed: bool, message: str) -> dict:
    return {
        "opened": opened,
        "pushed": pushed,
        "node_count": 7 if pushed else 0,
        "url": "http://127.0.0.1:8188",
        "message": message,
    }


class TestOpen:
    def test_happy_path_pushes_by_default(self):
        ok = _open_result(True, True, "Opened ComfyUI at http://127.0.0.1:8188.")
        with patch("agent.verbs.open_canvas.open_canvas", return_value=ok) as m:
            result = runner.invoke(app, ["open"])
        assert result.exit_code == 0
        assert "Opened ComfyUI" in result.output
        m.assert_called_once_with(push=True)

    def test_no_push_flag(self):
        ok = _open_result(True, False, "Opened ComfyUI at http://127.0.0.1:8188. Push skipped.")
        with patch("agent.verbs.open_canvas.open_canvas", return_value=ok) as m:
            result = runner.invoke(app, ["open", "--no-push"])
        assert result.exit_code == 0
        m.assert_called_once_with(push=False)

    def test_comfyui_down_exits_1_with_message(self):
        down = _open_result(
            False,
            False,
            "ComfyUI is not running at http://127.0.0.1:8188, so there is no canvas to open yet.",
        )
        with patch("agent.verbs.open_canvas.open_canvas", return_value=down):
            result = runner.invoke(app, ["open"])
        assert result.exit_code == 1
        assert "ComfyUI is not running" in result.output


# ---------------------------------------------------------------------------
# cozy see
# ---------------------------------------------------------------------------


_PROGRESS_LOG = [
    {"event": "start", "elapsed_s": 0.0},
    {"event": "progress", "node_id": "3", "value": 1, "max": 4, "pct": 25.0, "elapsed_s": 0.5},
    {"event": "progress", "node_id": "3", "value": 2, "max": 4, "pct": 50.0, "elapsed_s": 1.0},
    {"event": "progress", "node_id": "3", "value": 3, "max": 4, "pct": 75.0, "elapsed_s": 1.6},
    {"event": "progress", "node_id": "3", "value": 4, "max": 4, "pct": 100.0, "elapsed_s": 2.1},
    {"event": "complete", "elapsed_s": 3.0},
]


def _see_success() -> str:
    return json.dumps(
        {
            "status": "complete",
            "prompt_id": "abc-123",
            "total_time_s": 3.0,
            "outputs": [{"type": "image", "filename": "out_00001.png", "subfolder": ""}],
            "node_timing": [
                {"node_id": "3", "class_type": "KSampler", "duration_s": 2.1},
                {"node_id": "8", "class_type": "VAEDecode", "duration_s": 0.4},
            ],
            "slowest_node": {"node_id": "3", "class_type": "KSampler", "duration_s": 2.1},
            "progress_events": len(_PROGRESS_LOG),
            "progress_log": _PROGRESS_LOG,
            "monitoring": "websocket",
        }
    )


_API_DOWN = json.dumps({"error": "ComfyUI is not reachable at http://127.0.0.1:8188"})


class TestSee:
    def test_happy_path_renders_summary(self):
        with (
            patch("agent.tools.comfy_execute.handle", return_value=_see_success()) as m,
            patch("agent.tools.comfy_api.handle", return_value=_API_DOWN),
        ):
            result = runner.invoke(app, ["see"])
        assert result.exit_code == 0
        assert "run    complete" in result.output
        assert "steps" in result.output
        assert "KSampler" in result.output
        assert "vram   unavailable" in result.output  # stats poll mocked to down
        name, tool_input = m.call_args[0]
        assert name == "execute_with_progress"
        # include_progress_log: Lane C contract — see opts in to the capped log.
        assert tool_input == {"timeout": 300.0, "include_progress_log": True}

    def test_workflow_path_forwarded(self):
        with (
            patch("agent.tools.comfy_execute.handle", return_value=_see_success()) as m,
            patch("agent.tools.comfy_api.handle", return_value=_API_DOWN),
        ):
            result = runner.invoke(app, ["see", "shot_020.json", "--timeout", "600"])
        assert result.exit_code == 0
        _name, tool_input = m.call_args[0]
        assert tool_input == {
            "timeout": 600.0,
            "path": "shot_020.json",
            "include_progress_log": True,
        }

    def test_comfyui_down_exits_1_in_human_words(self):
        with patch("agent.tools.comfy_execute.handle", return_value=_API_DOWN):
            result = runner.invoke(app, ["see"])
        assert result.exit_code == 1
        assert "ComfyUI is not reachable" in result.output
        assert "Traceback" not in result.output

    def test_run_error_still_renders_partial_telemetry(self):
        error_result = json.dumps(
            {
                "status": "error",
                "prompt_id": "abc-123",
                "error": "CUDA out of memory",
                "node_id": "3",
                "class_type": "KSampler",
                "progress_log": _PROGRESS_LOG,
                "monitoring": "websocket",
            }
        )
        with (
            patch("agent.tools.comfy_execute.handle", return_value=error_result),
            patch("agent.tools.comfy_api.handle", return_value=_API_DOWN),
        ):
            result = runner.invoke(app, ["see"])
        assert result.exit_code == 1
        assert "CUDA out of memory" in result.output
        assert "steps" in result.output  # telemetry captured up to the failure

    def test_timeout_exits_1_with_message(self):
        timeout_result = json.dumps(
            {
                "status": "timeout",
                "prompt_id": "abc-123",
                "progress_log": _PROGRESS_LOG,
                "monitoring": "websocket",
                "message": "Execution did not complete within 300s.",
            }
        )
        with (
            patch("agent.tools.comfy_execute.handle", return_value=timeout_result),
            patch("agent.tools.comfy_api.handle", return_value=_API_DOWN),
        ):
            result = runner.invoke(app, ["see"])
        assert result.exit_code == 1
        assert "did not complete" in result.output
