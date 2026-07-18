"""Tests for the OPEN-OUT verb engine (``agent/verbs/open_canvas.py``).

All collaborators are mocked: the liveness check (``comfy_api.handle``), the
canvas push (``canvas_bridge.handle``), and the browser launch
(``webbrowser.open``). Session workflow state is set directly through
``workflow_patch._get_state()``; the autouse ``reset_workflow_state`` fixture
in conftest restores it between tests.
"""

import json
from unittest.mock import patch

import pytest

from agent import config
from agent.tools.workflow_patch import _get_state
from agent.verbs.open_canvas import open_canvas


RUNNING = json.dumps({"running": True, "url": config.COMFYUI_URL, "gpu": "RTX 4090"})
DOWN = json.dumps(
    {
        "running": False,
        "url": config.COMFYUI_URL,
        "error": "ComfyUI is not running.",
    }
)
PUSH_OK = json.dumps({"pushed": True, "reason": "cozy open", "note": "tabs reloaded"})
PUSH_FAIL = json.dumps(
    {
        "error": (
            "Push route not found (404). The comfy_agent_bridge node pack is "
            "not installed or ComfyUI needs a restart to load it."
        ),
    }
)


@pytest.fixture
def loaded_workflow(sample_workflow: dict) -> dict:
    """Put a workflow into the current session, mirroring load_workflow."""
    _get_state()["current_workflow"] = sample_workflow
    return sample_workflow


class TestOpenCanvasHappyPath:
    def test_push_and_open(self, loaded_workflow: dict) -> None:
        with (
            patch("agent.verbs.open_canvas.comfy_api.handle", return_value=RUNNING),
            patch(
                "agent.verbs.open_canvas.canvas_bridge.handle", return_value=PUSH_OK
            ) as mock_push,
            patch("agent.verbs.open_canvas.webbrowser.open", return_value=True) as mock_open,
        ):
            result = open_canvas()

        assert result["opened"] is True
        assert result["pushed"] is True
        assert result["node_count"] == len(loaded_workflow)
        assert result["url"] == config.COMFYUI_URL
        mock_open.assert_called_once_with(config.COMFYUI_URL)
        name, tool_input = mock_push.call_args[0]
        assert name == "push_workflow_to_canvas"
        assert tool_input["workflow"] == loaded_workflow
        # v1 realities surfaced in artist words: fresh layout + every-tab broadcast.
        assert "every" in result["message"] and "tab" in result["message"]
        assert "positions" in result["message"]

    def test_url_derives_from_config_only(self, loaded_workflow: dict) -> None:
        with (
            patch("agent.verbs.open_canvas.config.COMFYUI_URL", "http://127.0.0.1:9999"),
            patch("agent.verbs.open_canvas.comfy_api.handle", return_value=RUNNING),
            patch("agent.verbs.open_canvas.canvas_bridge.handle", return_value=PUSH_OK),
            patch("agent.verbs.open_canvas.webbrowser.open", return_value=True) as mock_open,
        ):
            result = open_canvas()

        assert result["url"] == "http://127.0.0.1:9999"
        mock_open.assert_called_once_with("http://127.0.0.1:9999")


class TestOpenCanvasNoWorkflow:
    def test_opens_without_push(self) -> None:
        assert _get_state()["current_workflow"] is None  # fresh session
        with (
            patch("agent.verbs.open_canvas.comfy_api.handle", return_value=RUNNING),
            patch("agent.verbs.open_canvas.canvas_bridge.handle") as mock_push,
            patch("agent.verbs.open_canvas.webbrowser.open", return_value=True),
        ):
            result = open_canvas()

        assert result["opened"] is True
        assert result["pushed"] is False
        assert result["node_count"] == 0
        mock_push.assert_not_called()
        assert "No session workflow" in result["message"]

    def test_push_false_skips_bridge(self, loaded_workflow: dict) -> None:
        with (
            patch("agent.verbs.open_canvas.comfy_api.handle", return_value=RUNNING),
            patch("agent.verbs.open_canvas.canvas_bridge.handle") as mock_push,
            patch("agent.verbs.open_canvas.webbrowser.open", return_value=True),
        ):
            result = open_canvas(push=False)

        assert result["opened"] is True
        assert result["pushed"] is False
        mock_push.assert_not_called()
        assert "skipped" in result["message"]


class TestOpenCanvasComfyDown:
    def test_no_dead_tab(self, loaded_workflow: dict) -> None:
        with (
            patch("agent.verbs.open_canvas.comfy_api.handle", return_value=DOWN),
            patch("agent.verbs.open_canvas.canvas_bridge.handle") as mock_push,
            patch("agent.verbs.open_canvas.webbrowser.open") as mock_open,
        ):
            result = open_canvas()

        assert result["opened"] is False
        assert result["pushed"] is False
        assert result["node_count"] == 0
        mock_open.assert_not_called()
        mock_push.assert_not_called()
        assert "not running" in result["message"]
        assert "Start ComfyUI" in result["message"]


class TestOpenCanvasDegradedPaths:
    def test_push_failure_still_opens(self, loaded_workflow: dict) -> None:
        with (
            patch("agent.verbs.open_canvas.comfy_api.handle", return_value=RUNNING),
            patch("agent.verbs.open_canvas.canvas_bridge.handle", return_value=PUSH_FAIL),
            patch("agent.verbs.open_canvas.webbrowser.open", return_value=True) as mock_open,
        ):
            result = open_canvas()

        assert result["opened"] is True
        assert result["pushed"] is False
        mock_open.assert_called_once_with(config.COMFYUI_URL)
        assert "push didn't land" in result["message"]
        assert "comfy_agent_bridge" in result["message"]  # bridge's own reason carried through
        assert "untouched" in result["message"]

    def test_browser_launch_failure_reports_url(self, loaded_workflow: dict) -> None:
        with (
            patch("agent.verbs.open_canvas.comfy_api.handle", return_value=RUNNING),
            patch("agent.verbs.open_canvas.canvas_bridge.handle", return_value=PUSH_OK),
            patch("agent.verbs.open_canvas.webbrowser.open", return_value=False),
        ):
            result = open_canvas()

        assert result["opened"] is False
        assert result["pushed"] is True  # push landed even though launch failed
        assert config.COMFYUI_URL in result["message"]
        assert "yourself" in result["message"]
