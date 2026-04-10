"""Tests for agent/stage/arbiter.py — Simulation Arbiter, no real I/O."""

from __future__ import annotations


from agent.stage.arbiter import (
    CALIBRATION_STEP,
    DEFAULT_CONFIDENCE_HIGH,
    DEFAULT_CONFIDENCE_LOW,
    DEFAULT_IMPROVEMENT_LARGE,
    Arbiter,
    ArbiterDecision,
    CalibrationFeedback,
)
from agent.stage.cwm import PredictedOutcome


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prediction(
    confidence: float = 0.5,
    aesthetic: float = 0.6,
    phase: str = "blended",
) -> PredictedOutcome:
    return PredictedOutcome(
        axis_scores={"aesthetic": aesthetic},
        confidence=confidence,
        phase=phase,
        experience_count=50,
        similar_count=10,
    )


# ---------------------------------------------------------------------------
# ArbiterDecision
# ---------------------------------------------------------------------------

class TestArbiterDecision:
    def test_to_dict(self):
        pred = _make_prediction()
        d = ArbiterDecision(
            mode="silent", prediction=pred,
            improvement_estimate=0.05, reasoning="test",
        )
        out = d.to_dict()
        assert out["mode"] == "silent"
        assert "confidence" in out
        assert "reasoning" in out


# ---------------------------------------------------------------------------
# Arbiter.__init__
# ---------------------------------------------------------------------------

class TestArbiterInit:
    def test_defaults(self):
        a = Arbiter()
        assert a.confidence_high == DEFAULT_CONFIDENCE_HIGH
        assert a.confidence_low == DEFAULT_CONFIDENCE_LOW
        assert a.improvement_large == DEFAULT_IMPROVEMENT_LARGE

    def test_custom_thresholds(self):
        a = Arbiter(confidence_high=0.8, confidence_low=0.2, improvement_large=0.2)
        assert a.confidence_high == 0.8
        assert a.confidence_low == 0.2
        assert a.improvement_large == 0.2

    def test_empty_histories(self):
        a = Arbiter()
        assert a.decisions == []
        assert a.feedback_history == []
        assert a.explicit_count == 0


# ---------------------------------------------------------------------------
# Decision tree
# ---------------------------------------------------------------------------

class TestDecisionTree:
    def test_high_conf_small_improvement_silent(self):
        a = Arbiter()
        pred = _make_prediction(confidence=0.8, aesthetic=0.55)
        d = a.prioritize_experiment(pred, current_composite=0.5)
        assert d.mode == "silent"

    def test_high_conf_large_improvement_soft(self):
        a = Arbiter()
        pred = _make_prediction(confidence=0.8, aesthetic=0.75)
        d = a.prioritize_experiment(pred, current_composite=0.5)
        assert d.mode == "soft_surface"

    def test_low_conf_large_improvement_explicit(self):
        a = Arbiter()
        pred = _make_prediction(confidence=0.2, aesthetic=0.75)
        d = a.prioritize_experiment(pred, current_composite=0.5)
        assert d.mode == "explicit"

    def test_low_conf_small_improvement_silent(self):
        a = Arbiter()
        pred = _make_prediction(confidence=0.2, aesthetic=0.55)
        d = a.prioritize_experiment(pred, current_composite=0.5)
        assert d.mode == "silent"

    def test_medium_conf_soft_surface(self):
        a = Arbiter()
        pred = _make_prediction(confidence=0.5, aesthetic=0.6)
        d = a.prioritize_experiment(pred, current_composite=0.5)
        assert d.mode == "soft_surface"

    def test_improvement_estimate_calculated(self):
        a = Arbiter()
        pred = _make_prediction(confidence=0.8, aesthetic=0.75)
        d = a.prioritize_experiment(pred, current_composite=0.5)
        assert abs(d.improvement_estimate - 0.25) < 1e-9

    def test_negative_improvement(self):
        a = Arbiter()
        pred = _make_prediction(confidence=0.8, aesthetic=0.3)
        d = a.prioritize_experiment(pred, current_composite=0.5)
        assert d.improvement_estimate < 0.0
        assert d.mode == "silent"


# ---------------------------------------------------------------------------
# Explicit cap
# ---------------------------------------------------------------------------

class TestExplicitCap:
    def test_max_one_explicit_per_session(self):
        a = Arbiter()
        pred = _make_prediction(confidence=0.2, aesthetic=0.75)

        d1 = a.prioritize_experiment(pred, current_composite=0.5)
        assert d1.mode == "explicit"

        d2 = a.prioritize_experiment(pred, current_composite=0.5)
        assert d2.mode == "soft_surface"
        assert "Downgraded" in d2.reasoning

    def test_explicit_count_increments(self):
        a = Arbiter()
        pred = _make_prediction(confidence=0.2, aesthetic=0.75)
        a.prioritize_experiment(pred, current_composite=0.5)
        assert a.explicit_count == 1

    def test_reset_session_clears_count(self):
        a = Arbiter()
        pred = _make_prediction(confidence=0.2, aesthetic=0.75)
        a.prioritize_experiment(pred, current_composite=0.5)
        a.reset_session()
        assert a.explicit_count == 0

    def test_after_reset_can_explicit_again(self):
        a = Arbiter()
        pred = _make_prediction(confidence=0.2, aesthetic=0.75)
        a.prioritize_experiment(pred, current_composite=0.5)
        a.reset_session()
        d = a.prioritize_experiment(pred, current_composite=0.5)
        assert d.mode == "explicit"


# ---------------------------------------------------------------------------
# History tracking
# ---------------------------------------------------------------------------

class TestHistory:
    def test_decisions_recorded(self):
        a = Arbiter()
        pred = _make_prediction()
        a.prioritize_experiment(pred, current_composite=0.5)
        assert len(a.decisions) == 1

    def test_multiple_decisions(self):
        a = Arbiter()
        for _ in range(5):
            a.prioritize_experiment(
                _make_prediction(), current_composite=0.5,
            )
        assert len(a.decisions) == 5

    def test_decisions_returns_copy(self):
        a = Arbiter()
        a.prioritize_experiment(_make_prediction(), current_composite=0.5)
        d = a.decisions
        d.append(None)
        assert len(a.decisions) == 1


# ---------------------------------------------------------------------------
# Feedback & calibration
# ---------------------------------------------------------------------------

class TestCalibration:
    def test_accepted_soft_lowers_improvement_threshold(self):
        a = Arbiter()
        before = a.improvement_large
        a.record_feedback(CalibrationFeedback(
            decision_mode="soft_surface", accepted=True,
        ))
        assert a.improvement_large < before

    def test_rejected_soft_raises_improvement_threshold(self):
        a = Arbiter()
        before = a.improvement_large
        a.record_feedback(CalibrationFeedback(
            decision_mode="soft_surface", accepted=False,
        ))
        assert a.improvement_large > before

    def test_accepted_explicit_lowers_confidence_low(self):
        a = Arbiter()
        before = a.confidence_low
        a.record_feedback(CalibrationFeedback(
            decision_mode="explicit", accepted=True,
        ))
        assert a.confidence_low < before

    def test_rejected_explicit_raises_confidence_low(self):
        a = Arbiter()
        before = a.confidence_low
        a.record_feedback(CalibrationFeedback(
            decision_mode="explicit", accepted=False,
        ))
        assert a.confidence_low > before

    def test_improvement_threshold_floor(self):
        a = Arbiter(improvement_large=0.06)
        a.record_feedback(CalibrationFeedback(
            decision_mode="soft_surface", accepted=True,
        ))
        assert a.improvement_large >= 0.05

    def test_improvement_threshold_ceiling(self):
        a = Arbiter(improvement_large=0.49)
        a.record_feedback(CalibrationFeedback(
            decision_mode="soft_surface", accepted=False,
        ))
        assert a.improvement_large <= 0.5

    def test_confidence_low_floor(self):
        a = Arbiter(confidence_low=0.11)
        a.record_feedback(CalibrationFeedback(
            decision_mode="explicit", accepted=True,
        ))
        assert a.confidence_low >= 0.1

    def test_confidence_low_ceiling(self):
        a = Arbiter(confidence_low=0.59)
        a.record_feedback(CalibrationFeedback(
            decision_mode="explicit", accepted=False,
        ))
        assert a.confidence_low <= 0.6

    def test_feedback_recorded(self):
        a = Arbiter()
        a.record_feedback(CalibrationFeedback(
            decision_mode="soft_surface", accepted=True,
        ))
        assert len(a.feedback_history) == 1

    def test_silent_feedback_no_calibration(self):
        a = Arbiter()
        before_imp = a.improvement_large
        before_conf = a.confidence_low
        a.record_feedback(CalibrationFeedback(
            decision_mode="silent", accepted=True,
        ))
        assert a.improvement_large == before_imp
        assert a.confidence_low == before_conf

    def test_calibration_step_size(self):
        a = Arbiter()
        before = a.improvement_large
        a.record_feedback(CalibrationFeedback(
            decision_mode="soft_surface", accepted=True,
        ))
        assert abs((before - a.improvement_large) - CALIBRATION_STEP) < 1e-9


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_empty_summary(self):
        a = Arbiter()
        s = a.summary()
        assert s["total_decisions"] == 0
        assert s["feedback_total"] == 0
        assert s["feedback_acceptance_rate"] == 0.0

    def test_summary_with_decisions(self):
        a = Arbiter()
        a.prioritize_experiment(
            _make_prediction(confidence=0.8, aesthetic=0.55),
            current_composite=0.5,
        )
        a.prioritize_experiment(
            _make_prediction(confidence=0.5, aesthetic=0.6),
            current_composite=0.5,
        )
        s = a.summary()
        assert s["total_decisions"] == 2
        assert s["mode_counts"]["silent"] == 1
        assert s["mode_counts"]["soft_surface"] == 1

    def test_summary_thresholds(self):
        a = Arbiter(confidence_high=0.8)
        s = a.summary()
        assert s["current_thresholds"]["confidence_high"] == 0.8

    def test_acceptance_rate(self):
        a = Arbiter()
        a.record_feedback(CalibrationFeedback("soft_surface", True))
        a.record_feedback(CalibrationFeedback("soft_surface", False))
        s = a.summary()
        assert abs(s["feedback_acceptance_rate"] - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# Cycle 39: _decisions and _feedback FIFO cap
# ---------------------------------------------------------------------------

class TestArbiterHistoryCap:
    """Cycle 39: _decisions and _feedback must not grow unbounded."""

    def test_decisions_capped_at_max(self):
        """_decisions list must not exceed _max_decisions."""
        a = Arbiter()
        a._max_decisions = 5
        pred = _make_prediction(confidence=0.8, aesthetic=0.55)
        for _ in range(10):
            a.prioritize_experiment(pred, current_composite=0.5)
        assert len(a._decisions) <= 5

    def test_decisions_oldest_evicted_first(self):
        """Oldest decisions are evicted when cap is reached (FIFO)."""
        a = Arbiter()
        a._max_decisions = 3
        pred_lo = _make_prediction(confidence=0.3, aesthetic=0.55)
        pred_hi = _make_prediction(confidence=0.9, aesthetic=0.55)
        a.prioritize_experiment(pred_lo, current_composite=0.5)  # 1 — evicted
        a.prioritize_experiment(pred_lo, current_composite=0.5)  # 2 — evicted
        a.prioritize_experiment(pred_hi, current_composite=0.5)  # 3 — kept
        a.prioritize_experiment(pred_hi, current_composite=0.5)  # 4 — kept
        a.prioritize_experiment(pred_hi, current_composite=0.5)  # 5 — kept (evicts 1, 2)
        assert len(a._decisions) == 3

    def test_feedback_capped_at_max(self):
        """_feedback list must not exceed _max_feedback."""
        a = Arbiter()
        a._max_feedback = 4
        fb = CalibrationFeedback("soft_surface", True)
        for _ in range(10):
            a.record_feedback(fb)
        assert len(a._feedback) <= 4

    def test_default_cap_constants_exist(self):
        """_MAX_DECISIONS and _MAX_FEEDBACK module constants must exist."""
        from agent.stage.arbiter import _MAX_DECISIONS, _MAX_FEEDBACK
        assert _MAX_DECISIONS >= 1_000
        assert _MAX_FEEDBACK >= 1_000


# ---------------------------------------------------------------------------
# Cycle 40: Arbiter thread-safety
# ---------------------------------------------------------------------------

class TestArbiterThreadSafety:
    """Cycle 40: Arbiter must be thread-safe for concurrent access."""

    def test_lock_exists(self):
        """Arbiter must have a _lock attribute."""
        import threading
        a = Arbiter()
        assert hasattr(a, "_lock")
        assert isinstance(a._lock, type(threading.Lock()))

    def test_concurrent_prioritize_no_corruption(self):
        """Multiple threads calling prioritize_experiment() must not corrupt _decisions."""
        import threading
        a = Arbiter()
        errors = []
        n = 40

        def _prioritize(i):
            try:
                pred = _make_prediction(confidence=0.5 + (i % 5) * 0.05, aesthetic=0.55)
                a.prioritize_experiment(pred, current_composite=0.5)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=_prioritize, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent prioritize raised: {errors}"
        assert len(a.decisions) == n

    def test_concurrent_summary_and_prioritize_no_crash(self):
        """summary() called concurrently with prioritize_experiment() must not crash."""
        import threading
        a = Arbiter()
        errors = []

        def _prioritize():
            pred = _make_prediction(confidence=0.6, aesthetic=0.55)
            for _ in range(30):
                try:
                    a.prioritize_experiment(pred, current_composite=0.5)
                except Exception as exc:
                    errors.append(f"prioritize: {exc}")

        def _summarize():
            for _ in range(20):
                try:
                    s = a.summary()
                    assert isinstance(s, dict)
                    assert "total_decisions" in s
                except Exception as exc:
                    errors.append(f"summary: {exc}")

        t1 = threading.Thread(target=_prioritize)
        t2 = threading.Thread(target=_summarize)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors, f"Concurrent summary/prioritize raised: {errors}"

    def test_concurrent_record_feedback_no_corruption(self):
        """Multiple threads calling record_feedback() must not corrupt _feedback."""
        import threading
        a = Arbiter()
        errors = []
        n = 30

        def _feedback(i):
            try:
                a.record_feedback(CalibrationFeedback("soft_surface", i % 2 == 0))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=_feedback, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent record_feedback raised: {errors}"
        assert len(a.feedback_history) == n
