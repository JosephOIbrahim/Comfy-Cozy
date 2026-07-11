"""Tests for panel/server/touched.py — write-back v1 (L-1)."""

import sys
from pathlib import Path

import pytest

# Ensure the checkout-only panel package is importable when the suite runs
# against an installed wheel (repo root is not on sys.path in importlib mode).
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from panel.server.touched import (  # noqa: E402
    record_last_pushed,
    compute_touched,
    clear_session,
)


@pytest.fixture(autouse=True)
def _reset_touched_state():
    """Clear all sessions between tests to prevent cross-test leakage."""
    from panel.server import touched

    touched._snapshots.clear()
    yield
    touched._snapshots.clear()


def _wf(nodes):
    """Build a workflow dict from an iterable of (node_id, class_type, inputs)."""
    return {
        node_id: {"class_type": class_type, "inputs": dict(inputs)}
        for node_id, class_type, inputs in nodes
    }


# ── record_last_pushed ────────────────────────────────────────────────────


class TestRecordLastPushed:
    def test_snapshot_is_deep_copy(self):
        wf = _wf([("5", "KSampler", {"seed": 42})])
        record_last_pushed("s1", wf)
        # Mutate the original after snapshotting
        wf["5"]["inputs"]["seed"] = 999
        # The snapshot should still see 42 — no change against unchanged wf
        unchanged = _wf([("5", "KSampler", {"seed": 42})])
        assert compute_touched("s1", unchanged) == []

    def test_none_workflow_is_noop(self):
        record_last_pushed("s1", None)
        # No snapshot recorded; compute_touched lazily initializes from current
        result = compute_touched("s1", _wf([("5", "KSampler", {})]))
        assert result == []


# ── compute_touched ───────────────────────────────────────────────────────


class TestComputeTouched:
    def test_first_call_lazily_initializes_returns_empty(self):
        wf = _wf([("5", "KSampler", {"seed": 42})])
        result = compute_touched("s1", wf)
        assert result == []
        # Subsequent call with same workflow → still empty (snapshot established)
        assert compute_touched("s1", wf) == []

    def test_widget_change_detected(self):
        wf_before = _wf([("5", "KSampler", {"seed": 42, "cfg": 7.0})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("5", "KSampler", {"seed": 99, "cfg": 7.0})])
        result = compute_touched("s1", wf_after)
        assert result == [
            {
                "node_id": "5",
                "input_name": "seed",
                "kind": "widget",
                "old_value": 42,
                "new_value": 99,
            }
        ]

    def test_link_change_detected(self):
        wf_before = _wf([("9", "VAEDecode", {"samples": ["7", 0]})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("9", "VAEDecode", {"samples": ["8", 0]})])
        result = compute_touched("s1", wf_after)
        assert result == [
            {
                "node_id": "9",
                "input_name": "samples",
                "kind": "link",
                "old_value": ["7", 0],
                "new_value": ["8", 0],
            }
        ]

    def test_link_added(self):
        wf_before = _wf([("9", "VAEDecode", {})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("9", "VAEDecode", {"samples": ["7", 0]})])
        result = compute_touched("s1", wf_after)
        assert len(result) == 1
        assert result[0]["kind"] == "link"
        assert result[0]["old_value"] is None
        assert result[0]["new_value"] == ["7", 0]

    def test_link_removed(self):
        wf_before = _wf([("9", "VAEDecode", {"samples": ["7", 0]})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("9", "VAEDecode", {})])
        result = compute_touched("s1", wf_after)
        assert len(result) == 1
        assert result[0]["old_value"] == ["7", 0]
        assert result[0]["new_value"] is None
        # Kind classified from old_value since new is None
        assert result[0]["kind"] == "link"

    def test_unchanged_inputs_not_in_touched(self):
        wf_before = _wf([("5", "KSampler", {"seed": 42, "cfg": 7.0, "steps": 20})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("5", "KSampler", {"seed": 99, "cfg": 7.0, "steps": 20})])
        result = compute_touched("s1", wf_after)
        names = [e["input_name"] for e in result]
        assert names == ["seed"]

    def test_multiple_nodes_multiple_changes_sorted(self):
        wf_before = _wf(
            [
                ("5", "KSampler", {"seed": 42}),
                ("7", "CLIPTextEncode", {"text": "a cat"}),
                ("9", "VAEDecode", {"samples": ["5", 0]}),
            ]
        )
        record_last_pushed("s1", wf_before)
        wf_after = _wf(
            [
                ("5", "KSampler", {"seed": 99}),
                ("7", "CLIPTextEncode", {"text": "a dog"}),
                ("9", "VAEDecode", {"samples": ["5", 0]}),
            ]
        )
        result = compute_touched("s1", wf_after)
        assert len(result) == 2
        # Determinism: sorted by (node_id, input_name)
        assert (result[0]["node_id"], result[0]["input_name"]) == ("5", "seed")
        assert (result[1]["node_id"], result[1]["input_name"]) == ("7", "text")

    def test_F1_clobber_scenario(self):
        """F-1: director edits node 5, agent edits node 9.

        Touched should contain only node 9's change. Iterating only touched
        in the push means node 5 is never read or written — the director's
        cfg=8.0 edit survives.
        """
        wf_initial = _wf(
            [
                ("5", "KSampler", {"cfg": 7.0}),
                ("9", "VAEDecode", {"samples": ["7", 0]}),
            ]
        )
        record_last_pushed("s1", wf_initial)

        # Director hand-edits the canvas → does not touch the agent cache.
        # Agent mutates node 9: rewires samples from 7 → 8. Agent cache:
        wf_after_agent = _wf(
            [
                ("5", "KSampler", {"cfg": 7.0}),  # untouched in cache
                ("9", "VAEDecode", {"samples": ["8", 0]}),
            ]
        )
        result = compute_touched("s1", wf_after_agent)

        assert len(result) == 1
        assert result[0]["node_id"] == "9"
        assert result[0]["input_name"] == "samples"

    def test_none_current_returns_empty(self):
        assert compute_touched("s1", None) == []


# ── classification ────────────────────────────────────────────────────────


class TestClassification:
    def test_int_widget(self):
        wf_before = _wf([("5", "KSampler", {"seed": 0})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("5", "KSampler", {"seed": 42})])
        assert compute_touched("s1", wf_after)[0]["kind"] == "widget"

    def test_float_widget(self):
        wf_before = _wf([("5", "KSampler", {"cfg": 7.0})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("5", "KSampler", {"cfg": 8.5})])
        assert compute_touched("s1", wf_after)[0]["kind"] == "widget"

    def test_string_widget(self):
        wf_before = _wf([("7", "CLIPTextEncode", {"text": "cat"})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("7", "CLIPTextEncode", {"text": "dog"})])
        assert compute_touched("s1", wf_after)[0]["kind"] == "widget"

    def test_bool_widget(self):
        wf_before = _wf([("3", "LoadImage", {"upload": True})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("3", "LoadImage", {"upload": False})])
        # bool is widget, not link (despite being int subclass)
        assert compute_touched("s1", wf_after)[0]["kind"] == "widget"

    def test_link_well_formed(self):
        wf_before = _wf([("9", "VAEDecode", {"samples": ["7", 0]})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("9", "VAEDecode", {"samples": ["8", 1]})])
        assert compute_touched("s1", wf_after)[0]["kind"] == "link"

    def test_malformed_array_classified_as_unknown(self):
        # length-1 array is not a well-formed link
        wf_before = _wf([("9", "VAEDecode", {"samples": ["7"]})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("9", "VAEDecode", {"samples": ["8"]})])
        assert compute_touched("s1", wf_after)[0]["kind"] == "unknown"


# ── session isolation ────────────────────────────────────────────────────


class TestSessionIsolation:
    def test_sessions_independent(self):
        wf_s1 = _wf([("5", "KSampler", {"seed": 42})])
        wf_s2 = _wf([("5", "KSampler", {"seed": 99})])
        record_last_pushed("s1", wf_s1)
        record_last_pushed("s2", wf_s2)
        assert compute_touched("s1", wf_s1) == []
        assert compute_touched("s2", wf_s2) == []
        # s1 with s2's workflow → sees a diff
        assert len(compute_touched("s1", wf_s2)) == 1

    def test_clear_session_drops_snapshot(self):
        wf = _wf([("5", "KSampler", {"seed": 42})])
        record_last_pushed("s1", wf)
        clear_session("s1")
        # Next compute_touched lazily initializes again
        wf_changed = _wf([("5", "KSampler", {"seed": 99})])
        assert compute_touched("s1", wf_changed) == []

    def test_clear_unknown_session_is_safe(self):
        clear_session("nonexistent")  # Should not raise


# ── ack-push flow ────────────────────────────────────────────────────────


class TestAckPushFlow:
    def test_ack_clears_touched(self):
        wf_before = _wf([("5", "KSampler", {"seed": 42})])
        record_last_pushed("s1", wf_before)
        wf_after = _wf([("5", "KSampler", {"seed": 99})])
        touched_pre = compute_touched("s1", wf_after)
        assert len(touched_pre) == 1
        # Frontend pushes successfully → calls ack-push → snapshot updated
        record_last_pushed("s1", wf_after)
        # Next compute_touched against same workflow → empty
        assert compute_touched("s1", wf_after) == []

    def test_double_mutation_only_latest_in_touched(self):
        wf_initial = _wf([("5", "KSampler", {"seed": 42})])
        record_last_pushed("s1", wf_initial)
        # First mutation
        wf_first = _wf([("5", "KSampler", {"seed": 99})])
        # Push acks → snapshot updates
        record_last_pushed("s1", wf_first)
        # Second mutation
        wf_second = _wf([("5", "KSampler", {"seed": 100})])
        touched = compute_touched("s1", wf_second)
        # Old value should be 99 (last pushed), not 42 (original baseline)
        assert touched == [
            {
                "node_id": "5",
                "input_name": "seed",
                "kind": "widget",
                "old_value": 99,
                "new_value": 100,
            }
        ]


# ── malformed workflow shapes ────────────────────────────────────────────


class TestMalformedShapes:
    def test_missing_inputs_field_treated_as_empty(self):
        # Node without "inputs" key
        wf_before = {"5": {"class_type": "KSampler"}}
        record_last_pushed("s1", wf_before)
        wf_after = {"5": {"class_type": "KSampler", "inputs": {"seed": 42}}}
        result = compute_touched("s1", wf_after)
        assert len(result) == 1
        assert result[0]["old_value"] is None
        assert result[0]["new_value"] == 42

    def test_non_dict_node_skipped(self):
        wf_before = {"5": "not-a-dict"}
        record_last_pushed("s1", wf_before)
        wf_after = {"5": {"class_type": "KSampler", "inputs": {"seed": 42}}}
        # Should not crash; the non-dict before is skipped
        result = compute_touched("s1", wf_after)
        # Returns empty because before-node isn't a dict and is bypassed
        assert result == []
