"""Tests for the startup auto-initialization module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from agent.startup import (
    run_auto_init,
    _scan_models_to_stage,
    _scan_workflows_to_stage,
    _scan_workflows_from_disk,
    _safe_prim_name,
    MODEL_EXTENSIONS,
)
import agent.startup as startup_mod


@pytest.fixture(autouse=True)
def reset_init_guard():
    """Reset the _initialized guard between tests."""
    startup_mod._initialized = False
    yield
    startup_mod._initialized = False


@pytest.fixture
def mock_ctx():
    """Create a minimal mock SessionContext."""
    ctx = MagicMock()
    ctx.workflow = {"loaded_path": None}
    ctx.ensure_stage.return_value = None
    return ctx


class TestSafePrimName:
    def test_simple(self):
        assert _safe_prim_name("my_workflow.json") == "my_workflow"

    def test_hyphens_replaced(self):
        assert _safe_prim_name("video-ltx-2.3.json") == "video_ltx_2_3"

    def test_leading_digit(self):
        assert _safe_prim_name("123_test.json") == "w_123_test"


class TestRunAutoInit:
    def test_no_config_does_nothing(self, mock_ctx):
        with patch.object(startup_mod, "AUTO_SCAN_MODELS", False), \
             patch.object(startup_mod, "AUTO_SCAN_WORKFLOWS", False), \
             patch.object(startup_mod, "AUTO_LOAD_WORKFLOW", ""), \
             patch.object(startup_mod, "AUTO_LOAD_SESSION", ""):
            result = run_auto_init(mock_ctx)
        assert result == {}

    def test_only_runs_once(self, mock_ctx):
        with patch.object(startup_mod, "AUTO_SCAN_MODELS", False), \
             patch.object(startup_mod, "AUTO_SCAN_WORKFLOWS", False), \
             patch.object(startup_mod, "AUTO_LOAD_WORKFLOW", ""), \
             patch.object(startup_mod, "AUTO_LOAD_SESSION", ""):
            run_auto_init(mock_ctx)
            result = run_auto_init(mock_ctx)
        assert result == {"status": "already_initialized"}

    def test_scan_models_called_when_enabled(self, mock_ctx):
        with patch.object(startup_mod, "AUTO_SCAN_MODELS", True), \
             patch.object(startup_mod, "AUTO_SCAN_WORKFLOWS", False), \
             patch.object(startup_mod, "AUTO_LOAD_WORKFLOW", ""), \
             patch.object(startup_mod, "AUTO_LOAD_SESSION", ""), \
             patch.object(startup_mod, "_scan_models_to_stage",
                          return_value="registered 5 models") as scan:
            result = run_auto_init(mock_ctx)
        scan.assert_called_once_with(mock_ctx)
        assert "models" in result

    def test_scan_workflows_called_when_enabled(self, mock_ctx):
        with patch.object(startup_mod, "AUTO_SCAN_MODELS", False), \
             patch.object(startup_mod, "AUTO_SCAN_WORKFLOWS", True), \
             patch.object(startup_mod, "AUTO_LOAD_WORKFLOW", ""), \
             patch.object(startup_mod, "AUTO_LOAD_SESSION", ""), \
             patch.object(startup_mod, "_scan_workflows_to_stage",
                          return_value="cataloged 10 workflows"), \
             patch.object(startup_mod, "_load_newest_favorite",
                          return_value="loaded foo.json"):
            result = run_auto_init(mock_ctx)
        assert "workflows" in result
        assert "active_workflow" in result

    def test_explicit_workflow_overrides_auto_favorite(self, mock_ctx):
        with patch.object(startup_mod, "AUTO_SCAN_MODELS", False), \
             patch.object(startup_mod, "AUTO_SCAN_WORKFLOWS", True), \
             patch.object(startup_mod, "AUTO_LOAD_WORKFLOW", "/some/wf.json"), \
             patch.object(startup_mod, "AUTO_LOAD_SESSION", ""), \
             patch.object(startup_mod, "_scan_workflows_to_stage",
                          return_value="cataloged 10"), \
             patch.object(startup_mod, "_load_default_workflow",
                          return_value="loaded wf.json") as load, \
             patch.object(startup_mod, "_load_newest_favorite") as fav:
            result = run_auto_init(mock_ctx)
        load.assert_called_once_with(mock_ctx, "/some/wf.json")
        fav.assert_not_called()

    def test_workflow_skipped_if_session_loaded_one(self, mock_ctx):
        mock_ctx.workflow = {"loaded_path": "/already/loaded.json"}
        with patch.object(startup_mod, "AUTO_SCAN_MODELS", False), \
             patch.object(startup_mod, "AUTO_SCAN_WORKFLOWS", False), \
             patch.object(startup_mod, "AUTO_LOAD_WORKFLOW", "/some/wf.json"), \
             patch.object(startup_mod, "AUTO_LOAD_SESSION", "my_session"), \
             patch.object(startup_mod, "_load_session",
                          return_value="loaded 'my_session'"), \
             patch.object(startup_mod, "_load_default_workflow") as load_wf:
            run_auto_init(mock_ctx)
        load_wf.assert_not_called()


class TestScanModels:
    def test_skipped_without_usd(self, mock_ctx):
        mock_ctx.ensure_stage.return_value = None
        result = _scan_models_to_stage(mock_ctx)
        assert "skipped" in result

    def test_scans_model_dirs(self, mock_ctx, tmp_path):
        ckpt_dir = tmp_path / "checkpoints"
        ckpt_dir.mkdir()
        (ckpt_dir / "model.safetensors").write_bytes(b"\x00" * 100)

        stage = MagicMock()
        mock_ctx.ensure_stage.return_value = stage

        with patch("agent.config.MODELS_DIR", tmp_path), \
             patch("agent.stage.model_registry.register_model",
                   return_value="/models/checkpoints/model"):
            result = _scan_models_to_stage(mock_ctx)

        assert "registered 1 models" in result


class TestScanWorkflows:
    def test_skipped_without_usd(self, mock_ctx):
        mock_ctx.ensure_stage.return_value = None
        result = _scan_workflows_to_stage(mock_ctx)
        assert "skipped" in result

    def test_catalogs_from_api(self, mock_ctx):
        stage = MagicMock()
        mock_ctx.ensure_stage.return_value = stage

        api_response = [
            {"path": "my_workflow.json", "size": 1000, "modified": 100.0},
            {"path": "another.json", "size": 2000, "modified": 200.0},
            {"path": "_backups/old.json", "size": 500, "modified": 50.0},
        ]
        favorites_response = {"favorites": ["workflows/another.json"]}

        with patch.object(startup_mod, "_fetch_json") as fetch, \
             patch("agent.config.WORKFLOWS_DIR", Path("/fake")):
            fetch.side_effect = [
                api_response,       # all workflows
                favorites_response, # favorites
                {"queue_running": [], "queue_pending": []},  # queue
                {},                 # history
            ]
            result = _scan_workflows_to_stage(mock_ctx)

        # Should catalog 2 (backup excluded)
        assert "cataloged 2 workflows" in result
        assert "1 favorites" in result

    def test_falls_back_to_disk_scan(self, mock_ctx, tmp_path):
        stage = MagicMock()
        mock_ctx.ensure_stage.return_value = stage

        (tmp_path / "test.json").write_text("{}")
        (tmp_path / "not_json.txt").write_text("hi")

        with patch.object(startup_mod, "_fetch_json", return_value=None), \
             patch("agent.config.WORKFLOWS_DIR", tmp_path):
            result = _scan_workflows_to_stage(mock_ctx)

        assert "cataloged 1 workflows" in result


class TestScanWorkflowsFromDisk:
    def test_empty_dir(self, tmp_path):
        result = _scan_workflows_from_disk(tmp_path)
        assert result == []

    def test_finds_json_files(self, tmp_path):
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "b.json").write_text("{}")
        (tmp_path / "c.txt").write_text("nope")
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "d.json").write_text("{}")

        result = _scan_workflows_from_disk(tmp_path)
        assert len(result) == 3
        assert all(r["path"].endswith(".json") for r in result)

    def test_nonexistent_dir(self):
        result = _scan_workflows_from_disk(Path("/nonexistent"))
        assert result == []
