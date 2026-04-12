"""Tests for CWMRecalibrator rolling-window accuracy + threshold adjustment.

Validates:
- confidence_high increases with high accuracy
- confidence_high decreases with low accuracy
- Bounds are respected
- Rolling window behavior
- Serialization round-trip
"""

import json

import pytest

from agent.stage.cwm import CWMRecalibrator, CALIBRATION_STEP


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def recalibrator():
    return CWMRecalibrator()


# ---------------------------------------------------------------------------
# Basic accuracy recording
# ---------------------------------------------------------------------------

class TestAccuracyRecording:

    def test_empty_window_initially(self, recalibrator):
        assert recalibrator.accuracy_window == []
        assert recalibrator.rolling_accuracy is None

    def test_record_populates_window(self, recalibrator):
        recalibrator.record_accuracy(0.7, 0.7)
        assert len(recalibrator.accuracy_window) == 1
        assert recalibrator.rolling_accuracy == pytest.approx(1.0)

    def test_window_size_respected(self):
        r = CWMRecalibrator(window_size=3)
        for i in range(5):
            r.record_accuracy(0.5, 0.5)
        assert len(r.accuracy_window) == 3

    def test_accuracy_computed_correctly(self, recalibrator):
        # Predicted 0.8, actual 0.6 → accuracy = 1 - |0.8-0.6| = 0.8
        recalibrator.record_accuracy(0.8, 0.6)
        assert recalibrator.accuracy_window[0] == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Threshold increases with high accuracy
# ---------------------------------------------------------------------------

class TestHighAccuracyIncrease:

    def test_confidence_high_increases(self):
        r = CWMRecalibrator(confidence_high=0.7, window_size=5)
        # Record 5 perfect predictions → accuracy > 0.8
        for _ in range(5):
            r.record_accuracy(0.7, 0.7)  # accuracy = 1.0
        assert r.confidence_high > 0.7

    def test_increase_step_matches_calibration_step(self):
        r = CWMRecalibrator(confidence_high=0.7, window_size=5)
        for _ in range(5):
            r.record_accuracy(0.7, 0.7)
        assert r.confidence_high == pytest.approx(0.7 + CALIBRATION_STEP)


# ---------------------------------------------------------------------------
# Threshold decreases with low accuracy
# ---------------------------------------------------------------------------

class TestLowAccuracyDecrease:

    def test_confidence_high_decreases(self):
        r = CWMRecalibrator(confidence_high=0.7, window_size=5)
        # Record 5 bad predictions → accuracy < 0.4
        for _ in range(5):
            r.record_accuracy(0.9, 0.1)  # accuracy = 1 - 0.8 = 0.2
        assert r.confidence_high < 0.7

    def test_decrease_step_matches_calibration_step(self):
        r = CWMRecalibrator(confidence_high=0.7, window_size=5)
        for _ in range(5):
            r.record_accuracy(0.9, 0.1)
        assert r.confidence_high == pytest.approx(0.7 - CALIBRATION_STEP)


# ---------------------------------------------------------------------------
# Bounds respected
# ---------------------------------------------------------------------------

class TestBounds:

    def test_confidence_high_capped_at_095(self):
        r = CWMRecalibrator(confidence_high=0.94, window_size=3)
        for _ in range(30):
            r.record_accuracy(0.7, 0.7)  # perfect → keeps increasing
        assert r.confidence_high <= 0.95

    def test_confidence_high_floor_at_050(self):
        r = CWMRecalibrator(confidence_high=0.52, window_size=3)
        for _ in range(30):
            r.record_accuracy(0.9, 0.1)  # bad → keeps decreasing
        assert r.confidence_high >= 0.5

    def test_confidence_low_bounded(self, recalibrator):
        assert recalibrator.confidence_low >= 0.1
        assert recalibrator.confidence_low <= 0.5

    def test_no_recalibration_before_window_full(self):
        r = CWMRecalibrator(confidence_high=0.7, window_size=10)
        for _ in range(9):
            r.record_accuracy(0.7, 0.7)
        # Window not full yet — no recalibration
        assert r.confidence_high == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Rolling window
# ---------------------------------------------------------------------------

class TestRollingWindow:

    def test_old_entries_evicted(self):
        r = CWMRecalibrator(window_size=3)
        r.record_accuracy(0.5, 0.5)
        r.record_accuracy(0.6, 0.6)
        r.record_accuracy(0.7, 0.7)
        r.record_accuracy(0.8, 0.8)
        window = r.accuracy_window
        assert len(window) == 3
        # First entry (0.5, 0.5) should have been evicted
        # All remaining should be accuracy=1.0 (perfect predictions)
        assert all(v == pytest.approx(1.0) for v in window)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

class TestSerialization:

    def test_round_trip_dict(self, recalibrator):
        recalibrator.record_accuracy(0.8, 0.7)
        recalibrator.record_accuracy(0.6, 0.6)
        data = recalibrator.to_dict()
        restored = CWMRecalibrator.from_dict(data)
        assert restored.confidence_high == recalibrator.confidence_high
        assert restored.confidence_low == recalibrator.confidence_low
        assert restored.accuracy_window == recalibrator.accuracy_window

    def test_round_trip_json_file(self, recalibrator, tmp_path):
        recalibrator.record_accuracy(0.5, 0.5)
        path = str(tmp_path / "calibration.json")
        recalibrator.save_json(path)
        restored = CWMRecalibrator.load_json(path)
        assert restored.accuracy_window == recalibrator.accuracy_window

    def test_load_missing_file_returns_default(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        restored = CWMRecalibrator.load_json(path)
        assert restored.confidence_high == pytest.approx(0.7)

    def test_json_serialization_uses_sort_keys(self, recalibrator, tmp_path):
        """JSON file must use sort_keys=True per project convention."""
        path = str(tmp_path / "test.json")
        recalibrator.save_json(path)
        with open(path) as f:
            raw = f.read()
        data = json.loads(raw)
        # json.dumps with sort_keys=True produces alphabetical order
        re_serialized = json.dumps(data, sort_keys=True)
        assert raw == re_serialized

    def test_from_dict_clamps_window_values(self):
        data = {
            "accuracy_window": [1.5, -0.3, 0.5],
        }
        r = CWMRecalibrator.from_dict(data)
        for v in r.accuracy_window:
            assert 0.0 <= v <= 1.0
