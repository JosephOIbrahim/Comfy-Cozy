"""Tests for counterfactual validation feedback (ExperienceChunk generation).

Validates that:
- validate() returns an ExperienceChunk alongside the bool
- The chunk has source="counterfactual"
- None returned when validation fails (ID not found)
"""

import pytest

from cognitive.prediction.counterfactual import (
    Counterfactual,
    CounterfactualGenerator,
    _build_experience_chunk,
)
from cognitive.experience.chunk import ExperienceChunk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def generator():
    return CounterfactualGenerator()


# ---------------------------------------------------------------------------
# validate() returns ExperienceChunk
# ---------------------------------------------------------------------------

class TestValidateReturnsChunk:

    def test_validate_returns_tuple(self, generator):
        cf = generator.generate({"cfg": 7.0, "steps": 20}, 0.7)
        assert cf is not None
        result = generator.validate(cf.cf_id, 0.05)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_validate_found_returns_chunk(self, generator):
        cf = generator.generate({"cfg": 7.0, "steps": 20}, 0.7)
        assert cf is not None
        ok, chunk = generator.validate(cf.cf_id, 0.05)
        assert ok is True
        assert isinstance(chunk, ExperienceChunk)

    def test_validate_not_found_returns_none(self, generator):
        ok, chunk = generator.validate("nonexistent_id", 0.1)
        assert ok is False
        assert chunk is None


# ---------------------------------------------------------------------------
# Chunk has source="counterfactual"
# ---------------------------------------------------------------------------

class TestChunkSource:

    def test_chunk_quality_source_is_counterfactual(self, generator):
        cf = generator.generate({"cfg": 7.0, "steps": 20}, 0.7)
        assert cf is not None
        _, chunk = generator.validate(cf.cf_id, 0.05)
        assert chunk.quality.source == "counterfactual"

    def test_chunk_tags_contain_counterfactual(self, generator):
        cf = generator.generate({"cfg": 7.0, "steps": 20}, 0.7)
        assert cf is not None
        _, chunk = generator.validate(cf.cf_id, 0.05)
        assert "counterfactual" in chunk.tags

    def test_chunk_tags_contain_changed_parameter(self, generator):
        cf = generator.generate({"cfg": 7.0, "steps": 20}, 0.7)
        assert cf is not None
        _, chunk = generator.validate(cf.cf_id, 0.05)
        assert cf.changed_parameter in chunk.tags

    def test_chunk_prompt_mentions_parameter(self, generator):
        cf = generator.generate({"cfg": 7.0, "steps": 20}, 0.7)
        assert cf is not None
        _, chunk = generator.validate(cf.cf_id, 0.1)
        assert "counterfactual" in chunk.prompt
        assert cf.changed_parameter in chunk.prompt


# ---------------------------------------------------------------------------
# Quality score mapping
# ---------------------------------------------------------------------------

class TestQualityMapping:

    def test_positive_delta_above_baseline(self, generator):
        cf = generator.generate({"cfg": 7.0}, 0.7)
        assert cf is not None
        _, chunk = generator.validate(cf.cf_id, 0.3)
        # delta=0.3, overall = 0.5 + 0.3 = 0.8
        assert chunk.quality.overall == pytest.approx(0.8)

    def test_negative_delta_below_baseline(self, generator):
        cf = generator.generate({"cfg": 7.0}, 0.7)
        assert cf is not None
        _, chunk = generator.validate(cf.cf_id, -0.3)
        assert chunk.quality.overall == pytest.approx(0.2)

    def test_quality_clamped_to_zero(self, generator):
        cf = generator.generate({"cfg": 7.0}, 0.7)
        assert cf is not None
        _, chunk = generator.validate(cf.cf_id, -0.9)
        assert chunk.quality.overall >= 0.0

    def test_quality_clamped_to_one(self, generator):
        cf = generator.generate({"cfg": 7.0}, 0.7)
        assert cf is not None
        _, chunk = generator.validate(cf.cf_id, 0.9)
        assert chunk.quality.overall <= 1.0


# ---------------------------------------------------------------------------
# _build_experience_chunk helper
# ---------------------------------------------------------------------------

class TestBuildExperienceChunk:

    def test_builds_chunk_from_counterfactual(self):
        cf = Counterfactual(
            alternative_params={"cfg": 8.0, "steps": 30},
            changed_parameter="cfg",
            actual_quality_delta=0.1,
            validated=True,
        )
        chunk = _build_experience_chunk(cf)
        assert isinstance(chunk, ExperienceChunk)
        assert chunk.parameters == {"cfg": 8.0, "steps": 30}

    def test_chunk_uses_alternative_params(self):
        cf = Counterfactual(
            original_params={"cfg": 7.0},
            alternative_params={"cfg": 9.0},
            changed_parameter="cfg",
            actual_quality_delta=0.0,
            validated=True,
        )
        chunk = _build_experience_chunk(cf)
        assert chunk.parameters == {"cfg": 9.0}

    def test_none_delta_treated_as_zero(self):
        cf = Counterfactual(
            alternative_params={},
            changed_parameter="steps",
            actual_quality_delta=None,
            validated=True,
        )
        chunk = _build_experience_chunk(cf)
        assert chunk.quality.overall == pytest.approx(0.5)
