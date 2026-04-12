"""Tests for adaptive alpha blending in agent/stage/cwm.py.

Verifies SNR-weighted alpha adjustment: low variance → high trust
in experience, high variance → lower trust (prior preserved).
"""

from __future__ import annotations

from agent.stage.cwm import (
    _blend_scores,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PRIOR = {"aesthetic": 0.5, "lighting": 0.5}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAdaptiveAlpha:

    def test_low_variance_high_trust(self):
        """When experience scores have near-zero variance, effective_alpha
        should be approximately equal to base_alpha (full trust)."""
        experience = {"aesthetic": 0.8, "lighting": 0.9}
        # All scores are identical → variance = 0 → snr_factor = 1.0
        exp_scores = {
            "aesthetic": [0.8, 0.8, 0.8, 0.8],
            "lighting": [0.9, 0.9, 0.9, 0.9],
        }

        blended_with_snr, _ = _blend_scores(
            PRIOR, experience, 150,
            experience_scores=exp_scores,
        )
        blended_without, _ = _blend_scores(
            PRIOR, experience, 150,
            experience_scores=None,
        )

        # With zero variance, SNR should not change the result
        assert abs(blended_with_snr["aesthetic"] - blended_without["aesthetic"]) < 0.01
        assert abs(blended_with_snr["lighting"] - blended_without["lighting"]) < 0.01

    def test_high_variance_low_trust(self):
        """When experience scores have high variance, effective_alpha
        should be lower than base_alpha (more prior influence)."""
        experience = {"aesthetic": 0.7}
        # Highly inconsistent scores → high variance
        exp_scores = {"aesthetic": [0.1, 0.9, 0.2, 0.8, 0.1, 0.95]}

        blended_with_snr, _ = _blend_scores(
            {"aesthetic": 0.5}, experience, 150,
            experience_scores=exp_scores,
        )
        blended_without, _ = _blend_scores(
            {"aesthetic": 0.5}, experience, 150,
            experience_scores=None,
        )

        # With high variance, SNR reduces alpha → result closer to prior (0.5)
        dist_snr = abs(blended_with_snr["aesthetic"] - 0.5)
        dist_no_snr = abs(blended_without["aesthetic"] - 0.5)
        assert dist_snr < dist_no_snr

    def test_none_scores_falls_back(self):
        """When experience_scores is None, behavior matches the original
        fixed alpha path exactly."""
        experience = {"aesthetic": 0.8, "lighting": 0.7}

        blended_none, phase_none = _blend_scores(
            PRIOR, experience, 60,
            experience_scores=None,
        )
        blended_default, phase_default = _blend_scores(
            PRIOR, experience, 60,
        )

        assert phase_none == phase_default
        assert blended_none == blended_default

    def test_mixed_variance_per_axis(self):
        """Different variance per axis should produce different alpha
        adjustments per axis."""
        experience = {"aesthetic": 0.8, "lighting": 0.8}
        # aesthetic: consistent; lighting: noisy
        exp_scores = {
            "aesthetic": [0.8, 0.8, 0.8, 0.8],
            "lighting": [0.2, 0.9, 0.3, 0.95, 0.1],
        }

        blended, _ = _blend_scores(
            PRIOR, experience, 150,
            experience_scores=exp_scores,
        )
        blended_no_snr, _ = _blend_scores(
            PRIOR, experience, 150,
        )

        # aesthetic should be close to no-SNR (low variance)
        assert abs(blended["aesthetic"] - blended_no_snr["aesthetic"]) < 0.01

        # lighting should differ (high variance → reduced alpha)
        assert abs(blended["lighting"] - blended_no_snr["lighting"]) > 0.01

    def test_zero_experience_count(self):
        """When experience_count is 0, alpha is 0 regardless of SNR."""
        experience = {"aesthetic": 0.9}
        exp_scores = {"aesthetic": [0.9, 0.9]}

        blended, phase = _blend_scores(
            {"aesthetic": 0.5}, experience, 0,
            experience_scores=exp_scores,
        )

        assert phase == "prior_only"
        # alpha=0 * anything = 0, so result = prior
        assert blended["aesthetic"] == 0.5
