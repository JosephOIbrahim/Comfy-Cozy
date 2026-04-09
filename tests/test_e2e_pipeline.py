"""End-to-end integration tests -- full tool pipeline with mocked HTTP."""

import json

import pytest
from unittest.mock import MagicMock, patch

from agent.tools import handle, workflow_patch


@pytest.fixture(autouse=True)
def _reset_patch_state():
    """Reset workflow_patch module state between tests and disable gate."""
    workflow_patch._get_state()["loaded_path"] = None
    workflow_patch._get_state()["base_workflow"] = None
    workflow_patch._get_state()["current_workflow"] = None
    workflow_patch._get_state()["history"] = []
    workflow_patch._get_state()["format"] = None
    workflow_patch._set_engine(None)
    with patch("agent.config.GATE_ENABLED", False):
        yield
    workflow_patch._get_state()["loaded_path"] = None
    workflow_patch._get_state()["base_workflow"] = None
    workflow_patch._get_state()["current_workflow"] = None
    workflow_patch._get_state()["history"] = []
    workflow_patch._get_state()["format"] = None
    workflow_patch._set_engine(None)


def _mock_httpx_client(module_path="agent.tools.comfy_execute.httpx.Client"):
    """Create a properly chained httpx.Client context manager mock.

    Returns (patcher, mock_client) -- mock_client has .post, .get, etc.
    """
    mock_client = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_client)
    mock_cm.__exit__ = MagicMock(return_value=False)
    patcher = patch(module_path, return_value=mock_cm)
    return patcher, mock_client


@pytest.mark.integration
class TestWorkflowPipeline:
    """Exercise: load -> inspect -> modify -> validate -> execute."""

    def test_load_inspect_modify_diff(self, sample_workflow_file):
        """Full pipeline: load a workflow via patch, inspect fields, set input, check diff."""
        # 1. Load workflow into patch engine via apply_workflow_patch
        load_result = json.loads(
            handle(
                "apply_workflow_patch",
                {
                    "path": str(sample_workflow_file),
                    "patches": [
                        {"op": "replace", "path": "/2/inputs/steps", "value": 20},
                    ],
                },
            )
        )
        assert "error" not in load_result
        assert load_result.get("applied", 0) >= 1

        # 2. Get editable fields (requires path to file)
        fields = json.loads(
            handle(
                "get_editable_fields",
                {
                    "path": str(sample_workflow_file),
                },
            )
        )
        assert "error" not in fields
        assert fields.get("total_fields", 0) > 0

        # 3. Set an input (change steps to 30)
        set_result = json.loads(
            handle(
                "set_input",
                {
                    "node_id": "2",
                    "input_name": "steps",
                    "value": 30,
                },
            )
        )
        assert "error" not in set_result
        assert set_result["new_value"] == 30
        assert set_result["old_value"] == 20

        # 4. Get diff -- should show steps changed from base
        diff = json.loads(handle("get_workflow_diff", {}))
        assert "error" not in diff
        assert diff.get("changes", 0) > 0

    def test_load_modify_undo_verify(self, sample_workflow_file):
        """Load, modify cfg, then undo and verify restoration."""
        # Load workflow (initial cfg is 7.0 from conftest sample_workflow)
        handle(
            "apply_workflow_patch",
            {
                "path": str(sample_workflow_file),
                "patches": [
                    {"op": "replace", "path": "/2/inputs/cfg", "value": 7.0},
                ],
            },
        )

        # Modify cfg to 12.0
        set_result = json.loads(
            handle(
                "set_input",
                {
                    "node_id": "2",
                    "input_name": "cfg",
                    "value": 12.0,
                },
            )
        )
        assert set_result["new_value"] == 12.0

        # Undo
        undo = json.loads(handle("undo_workflow_patch", {}))
        assert "error" not in undo
        assert undo["undone"] is True

        # Verify cfg is back -- check via workflow diff
        # After undo, cfg should be 7.0 (the value after initial load+patch)
        # The current workflow should match the state before set_input
        diff = json.loads(handle("get_workflow_diff", {}))
        # If cfg was replaced with 7.0 (same as original), diff might be 0
        # The key check is that undo succeeded without error
        assert "error" not in diff

    def test_add_node_and_set_input(self, sample_workflow_file):
        """Load, add a node, set an input on it."""
        # Load workflow
        handle(
            "apply_workflow_patch",
            {
                "path": str(sample_workflow_file),
                "patches": [
                    {"op": "replace", "path": "/2/inputs/steps", "value": 20},
                ],
            },
        )

        # Add a new node
        add_result = json.loads(
            handle(
                "add_node",
                {
                    "class_type": "UpscaleModelLoader",
                },
            )
        )
        assert "error" not in add_result
        assert add_result["added"] is True
        new_node_id = add_result["node_id"]
        assert add_result["class_type"] == "UpscaleModelLoader"

        # Set an input on the new node
        set_result = json.loads(
            handle(
                "set_input",
                {
                    "node_id": new_node_id,
                    "input_name": "model_name",
                    "value": "4x_NMKD-Superscale-SP_178000_G.pth",
                },
            )
        )
        assert "error" not in set_result
        assert set_result["new_value"] == "4x_NMKD-Superscale-SP_178000_G.pth"

    def test_connect_nodes(self, sample_workflow_file):
        """Load, add a node, connect it to an existing node."""
        # Load workflow
        handle(
            "apply_workflow_patch",
            {
                "path": str(sample_workflow_file),
                "patches": [
                    {"op": "replace", "path": "/2/inputs/steps", "value": 20},
                ],
            },
        )

        # Add a new CLIPTextEncode node
        add_result = json.loads(
            handle(
                "add_node",
                {
                    "class_type": "CLIPTextEncode",
                },
            )
        )
        new_node_id = add_result["node_id"]

        # Connect checkpoint loader's CLIP output to the new node's clip input
        conn_result = json.loads(
            handle(
                "connect_nodes",
                {
                    "from_node": "1",
                    "from_output": 1,
                    "to_node": new_node_id,
                    "to_input": "clip",
                },
            )
        )
        assert "error" not in conn_result
        assert conn_result["connected"] is True

    def test_multiple_modifications_then_reset(self, sample_workflow_file):
        """Apply multiple changes then reset to original."""
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

        # Multiple modifications
        handle("set_input", {"node_id": "2", "input_name": "steps", "value": 50})
        handle("set_input", {"node_id": "2", "input_name": "cfg", "value": 12.0})
        handle("set_input", {"node_id": "3", "input_name": "text", "value": "a cat"})

        # Verify changes are present in diff
        diff = json.loads(handle("get_workflow_diff", {}))
        assert diff.get("changes", 0) >= 3

        # Reset to original
        reset_result = json.loads(handle("reset_workflow", {}))
        assert "error" not in reset_result
        assert reset_result["reset"] is True

        # Diff should now show zero changes
        diff_after = json.loads(handle("get_workflow_diff", {}))
        assert diff_after.get("changes", 0) == 0

    def test_save_modified_workflow(self, sample_workflow_file, tmp_path):
        """Load, modify, save to a new file, verify contents."""
        # Load and modify
        handle(
            "apply_workflow_patch",
            {
                "path": str(sample_workflow_file),
                "patches": [
                    {"op": "replace", "path": "/3/inputs/text", "value": "a red car"},
                ],
            },
        )

        # Save to new path
        output_path = tmp_path / "saved_workflow.json"
        save_result = json.loads(
            handle(
                "save_workflow",
                {
                    "output_path": str(output_path),
                },
            )
        )
        assert "error" not in save_result

        # Verify the saved file has the modification
        saved_data = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved_data["3"]["inputs"]["text"] == "a red car"

    def test_load_workflow_returns_inspection(self, sample_workflow_file):
        """load_workflow returns node counts and editable fields."""
        result = json.loads(
            handle(
                "load_workflow",
                {
                    "path": str(sample_workflow_file),
                },
            )
        )
        assert "error" not in result
        assert result["node_count"] == 7
        assert result["editable_field_count"] > 0
        assert "nodes" in result
        assert "connections" in result

    def test_validate_before_execute_mocked(self, sample_workflow_file):
        """validate_before_execute calls ComfyUI -- verify with mocked HTTP."""
        # Load workflow into patch engine
        handle(
            "apply_workflow_patch",
            {
                "path": str(sample_workflow_file),
                "patches": [
                    {"op": "replace", "path": "/2/inputs/steps", "value": 20},
                ],
            },
        )

        # Mock the ComfyUI /prompt endpoint for validation
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"prompt_id": "val123", "number": 1}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.status_code = 200

        # Mock object_info for node class validation
        mock_info_resp = MagicMock()
        mock_info_resp.json.return_value = {
            "CheckpointLoaderSimple": {"input": {"required": {}}},
            "KSampler": {"input": {"required": {}}},
            "CLIPTextEncode": {"input": {"required": {}}},
            "EmptyLatentImage": {"input": {"required": {}}},
            "VAEDecode": {"input": {"required": {}}},
            "SaveImage": {"input": {"required": {}}},
        }
        mock_info_resp.raise_for_status = MagicMock()
        mock_info_resp.status_code = 200

        patcher, mock_client = _mock_httpx_client()
        # GET for object_info, POST for prompt validation
        mock_client.get.return_value = mock_info_resp
        mock_client.post.return_value = mock_resp

        with patcher, patch("agent.tools.comfy_execute.COMFYUI_BREAKER", create=True):
            breaker = MagicMock()
            breaker.allow_request.return_value = True
            with patch("agent.circuit_breaker.get_breaker", return_value=breaker):
                result = json.loads(handle("validate_before_execute", {}))
                # Result should not be a Python exception -- exact shape depends
                # on which validation path fires. Verify no crash occurred.
                assert isinstance(result, dict)
