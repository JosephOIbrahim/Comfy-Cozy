"""Tests for the OPEN-IN verb engine (``agent/verbs/pull_canvas.py``).

All collaborators are mocked: the canvas buffer (``canvas_bridge.handle``)
and ``/object_info`` (``ui_api_parser._get_object_info``). Session workflow
state is set directly through ``workflow_patch._get_state()``; the autouse
``reset_workflow_state`` fixture in conftest restores it between tests.

The load-bearing assertions follow ORCH.L8: artist edits (including node
adds and deletes) land as validated patch operations with the undo stack
GROWN, never via ``load_workflow_from_data`` on a live session.
"""

import copy
import json
from unittest.mock import patch

import httpx
import pytest

from agent.tools.workflow_patch import _get_state
from agent.verbs.pull_canvas import pull_canvas, render_pull_result


def canvas_reply(workflow) -> str:
    """Build a get_canvas_state JSON reply with the given buffered workflow."""
    return json.dumps({"workflow": workflow})


CANVAS_DOWN = json.dumps({"error": "ComfyUI is not reachable. Start ComfyUI, then try again."})
CANVAS_EMPTY = json.dumps({"workflow": None, "note": "No artist edit captured yet."})


@pytest.fixture
def loaded_session(sample_workflow: dict) -> dict:
    """Put a workflow into the current session, mirroring load_workflow."""
    state = _get_state()
    state["base_workflow"] = copy.deepcopy(sample_workflow)
    state["current_workflow"] = copy.deepcopy(sample_workflow)
    state["loaded_path"] = "<test>"
    return sample_workflow


def _pull_with_canvas(reply: str) -> dict:
    with patch("agent.verbs.pull_canvas.canvas_bridge.handle", return_value=reply):
        return pull_canvas()


class TestDiffAndApplyHappyPath:
    def test_artist_add_delete_param_rewire_land_as_undoable_patch(
        self, loaded_session: dict
    ) -> None:
        """An artist node-add AND node-delete survive as patch ops, undo intact."""
        artist = copy.deepcopy(loaded_session)
        # Artist freedom: delete the negative-prompt encoder...
        removed_class = artist.pop("4")["class_type"]
        # ...add a brand-new node...
        artist["9"] = {"class_type": "LoraLoader", "inputs": {"strength_model": 0.8}}
        # ...turn up the steps...
        artist["2"]["inputs"]["steps"] = 30
        # ...and rewire the negative input at the sampler to the positive encoder.
        artist["2"]["inputs"]["negative"] = ["3", 0]

        undo_before = len(_get_state()["history"])
        result = _pull_with_canvas(canvas_reply(artist))

        assert result["ok"] is True
        assert result["pulled"] is True
        assert result["applied"] is True
        assert result["refused"] is False
        assert result["initial_load"] is False
        assert result["changes"] > 0

        # The session now holds the artist's graph...
        assert _get_state()["current_workflow"] == artist
        # ...and the undo stack GREW by exactly one step (never wiped).
        assert len(_get_state()["history"]) == undo_before + 1
        assert _get_state()["history"][-1] == loaded_session

        summary = result["summary"]
        assert summary["nodes_added"] == [{"id": "9", "class_type": "LoraLoader"}]
        assert summary["nodes_removed"] == [{"id": "4", "class_type": removed_class}]
        assert {"node": "2", "param": "steps", "old": 20, "new": 30} in summary["params_changed"]
        assert summary["links_rewired"] == 1

        # The message names the honest undo path.
        assert "undo" in result["message"]
        assert "one undo away" in result["message"]

    def test_render_celebrates_adds_and_deletes(self, loaded_session: dict) -> None:
        """Adds/deletes render as accepted freedom, not warnings."""
        artist = copy.deepcopy(loaded_session)
        artist.pop("4")
        artist["2"]["inputs"]["negative"] = ["3", 0]  # keep the DAG whole
        artist["9"] = {"class_type": "LoraLoader", "inputs": {"strength_model": 0.8}}

        result = _pull_with_canvas(canvas_reply(artist))
        text = render_pull_result(result)

        assert "+ LoraLoader joined as node 9" in text
        assert "node 4" in text and "your call" in text
        assert "warning" not in text.lower()

    def test_undo_actually_restores_pre_pull_graph(self, loaded_session: dict) -> None:
        """The ingest is genuinely one undo away — undo restores the old graph."""
        from agent.tools import workflow_patch

        artist = copy.deepcopy(loaded_session)
        artist["9"] = {"class_type": "LoraLoader", "inputs": {"strength_model": 0.8}}
        result = _pull_with_canvas(canvas_reply(artist))
        assert result["applied"] is True

        undone = json.loads(workflow_patch.handle("undo_workflow_patch", {}))
        assert undone.get("undone") is True
        assert _get_state()["current_workflow"] == loaded_session


class TestEmptyDiff:
    def test_matching_graphs_report_already_match(self, loaded_session: dict) -> None:
        undo_before = len(_get_state()["history"])
        result = _pull_with_canvas(canvas_reply(copy.deepcopy(loaded_session)))

        assert result["ok"] is True  # exit-worthy 0
        assert result["pulled"] is True
        assert result["applied"] is False
        assert result["changes"] == 0
        assert "already match" in result["message"]
        # No phantom undo step for a no-op.
        assert len(_get_state()["history"]) == undo_before


class TestNoSessionInitialLoad:
    def test_canvas_graph_becomes_session_baseline(self, sample_workflow: dict) -> None:
        assert _get_state()["current_workflow"] is None  # fresh session
        result = _pull_with_canvas(canvas_reply(sample_workflow))

        assert result["ok"] is True
        assert result["applied"] is True
        assert result["initial_load"] is True
        assert result["node_count"] == len(sample_workflow)
        assert _get_state()["current_workflow"] == sample_workflow
        assert _get_state()["base_workflow"] == sample_workflow
        assert "baseline" in result["message"]

    def test_initial_load_resets_consent_flag(self, sample_workflow: dict) -> None:
        """The load path clears validated_since_mutation — no stale consent."""
        _pull_with_canvas(canvas_reply(sample_workflow))
        assert _get_state()["validated_since_mutation"] is False


class TestComfyUIDown:
    def test_bridge_error_is_human_worded_and_harmless(self, loaded_session: dict) -> None:
        result = _pull_with_canvas(CANVAS_DOWN)

        assert result["ok"] is False
        assert result["pulled"] is False
        assert result["applied"] is False
        assert "not reachable" in result["message"]
        assert "untouched" in result["message"]
        assert _get_state()["current_workflow"] == loaded_session  # untouched

    def test_empty_buffer_says_so_plainly(self, loaded_session: dict) -> None:
        result = _pull_with_canvas(CANVAS_EMPTY)

        assert result["ok"] is False
        assert result["applied"] is False
        assert "nothing to pull" in result["message"].lower()
        assert "cozy pull" in result["message"]

    def test_ui_file_degrades_clearly_when_object_info_unreachable(self, tmp_path) -> None:
        ui_file = tmp_path / "artist_ui.json"
        ui_file.write_text(
            json.dumps({"nodes": [{"id": 1, "type": "KSampler"}], "links": []}),
            encoding="utf-8",
        )
        with patch(
            "agent.verbs.pull_canvas.ui_api_parser._get_object_info",
            side_effect=httpx.ConnectError("refused"),
        ):
            result = pull_canvas(source="file", file=str(ui_file))

        assert result["ok"] is False
        assert result["pulled"] is False
        assert "ComfyUI running" in result["message"]
        assert "Save (API Format)" in result["message"]


class TestBrokenDagRefusal:
    def test_dangling_link_refused_with_validations_message(self, loaded_session: dict) -> None:
        artist = copy.deepcopy(loaded_session)
        # Artist deleted node "3" but the sampler still points at it.
        artist.pop("3")

        undo_before = len(_get_state()["history"])
        result = _pull_with_canvas(canvas_reply(artist))

        assert result["ok"] is False
        assert result["pulled"] is True  # we DID get the graph — the refusal is the DAG
        assert result["applied"] is False
        assert result["refused"] is True
        # Validation's finding surfaces, in artist words: which input, which node.
        assert "node 3" in result["message"]
        assert "going nowhere" in result["message"]
        assert "untouched" in result["message"]
        # Session state fully intact: graph unchanged, no undo step burned.
        assert _get_state()["current_workflow"] == loaded_session
        assert len(_get_state()["history"]) == undo_before

    def test_new_node_with_dangling_wire_is_refused_not_the_add_itself(
        self, loaded_session: dict
    ) -> None:
        """The refusal is about the broken wire — a clean add is accepted."""
        artist = copy.deepcopy(loaded_session)
        artist["9"] = {"class_type": "LoraLoader", "inputs": {"model": ["77", 0]}}

        result = _pull_with_canvas(canvas_reply(artist))
        assert result["refused"] is True
        assert "node 77" in result["message"]

        # Same add, wired correctly -> accepted.
        artist["9"]["inputs"]["model"] = ["1", 0]
        result = _pull_with_canvas(canvas_reply(artist))
        assert result["ok"] is True
        assert result["applied"] is True


class TestFileSource:
    def test_api_format_file_diffs_into_session(self, loaded_session: dict, tmp_path) -> None:
        artist = copy.deepcopy(loaded_session)
        artist["2"]["inputs"]["cfg"] = 4.5
        wf_file = tmp_path / "artist_edit.json"
        wf_file.write_text(json.dumps(artist), encoding="utf-8")

        result = pull_canvas(source="file", file=str(wf_file))

        assert result["ok"] is True
        assert result["applied"] is True
        assert result["source"] == "file"
        assert _get_state()["current_workflow"]["2"]["inputs"]["cfg"] == 4.5
        assert {"node": "2", "param": "cfg", "old": 7.0, "new": 4.5} in result["summary"][
            "params_changed"
        ]

    def test_ui_format_file_converts_then_initial_loads(self, tmp_path) -> None:
        assert _get_state()["current_workflow"] is None  # fresh session
        ui = {
            "nodes": [
                {
                    "id": 1,
                    "type": "KSampler",
                    "widgets_values": [42, "fixed", 30],
                    "inputs": [],
                }
            ],
            "links": [],
        }
        object_info = {
            "KSampler": {
                "input": {
                    "required": {
                        "seed": ["INT", {"default": 0}],
                        "steps": ["INT", {"default": 20}],
                    }
                }
            }
        }
        ui_file = tmp_path / "artist_ui.json"
        ui_file.write_text(json.dumps(ui), encoding="utf-8")

        with patch(
            "agent.verbs.pull_canvas.ui_api_parser._get_object_info",
            return_value=object_info,
        ):
            result = pull_canvas(source="file", file=str(ui_file))

        assert result["ok"] is True
        assert result["initial_load"] is True
        current = _get_state()["current_workflow"]
        # seed=42, "fixed" consumed as control_after_generate, steps=30.
        assert current["1"]["inputs"] == {"seed": 42, "steps": 30}

    def test_file_source_without_path_asks_for_one(self) -> None:
        result = pull_canvas(source="file")
        assert result["ok"] is False
        assert "--file" in result["message"]


class TestGuardRails:
    def test_unknown_source_is_named(self) -> None:
        result = pull_canvas(source="telepathy")
        assert result["ok"] is False
        assert "telepathy" in result["message"]

    def test_non_graph_buffer_is_rejected_plainly(self, loaded_session: dict) -> None:
        result = _pull_with_canvas(canvas_reply({"not_a_node": "just a string"}))
        assert result["ok"] is False
        assert "no usable nodes" in result["message"]
        assert _get_state()["current_workflow"] == loaded_session
