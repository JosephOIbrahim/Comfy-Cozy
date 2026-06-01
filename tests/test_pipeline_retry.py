"""Tests for the auto-retry loop in the autonomous pipeline.

Validates that:
- Retry fires when quality < threshold
- max_retries is respected
- Parameters adjust between retries
- No retry when quality >= threshold
"""

import copy
from types import SimpleNamespace

import pytest

from cognitive.pipeline.autonomous import (
    AutonomousPipeline,
    PipelineConfig,
    PipelineStage,
)
from cognitive.experience.chunk import QualityScore


# ---------------------------------------------------------------------------
# Mock compose to isolate from template changes
# ---------------------------------------------------------------------------

_KNOWN_WORKFLOW = {
    "1": {"class_type": "CheckpointLoaderSimple",
          "inputs": {"ckpt_name": "test.safetensors"}},
    "2": {"class_type": "KSampler",
          "inputs": {"model": ["1", 0], "seed": 42, "steps": 20, "cfg": 7.0,
                     "sampler_name": "euler", "scheduler": "normal",
                     "denoise": 1.0}},
}


def _mock_compose(*args, **kwargs):
    return SimpleNamespace(
        success=True,
        workflow_data=copy.deepcopy(_KNOWN_WORKFLOW),
        plan=SimpleNamespace(model_family="SD1.5", parameters={"cfg": 7.0, "steps": 20}),
        error=None,
    )


@pytest.fixture(autouse=True)
def _patch_compose(monkeypatch):
    import cognitive.pipeline.autonomous as _mod
    monkeypatch.setattr(_mod, "compose_workflow", _mock_compose)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_exec_result(success: bool = True, filenames: list[str] | None = None):
    fnames = filenames or []
    return type("R", (), {"output_filenames": fnames, "success": success})()


class _CountingExecutor:
    """Executor that counts calls and records workflow snapshots."""

    def __init__(self):
        self.call_count = 0
        self.workflows: list[dict] = []

    def __call__(self, wf):
        self.call_count += 1
        self.workflows.append(copy.deepcopy(wf))
        return _make_exec_result(success=True)


class _EscalatingEvaluator:
    """Evaluator that returns increasing quality on each call.

    Starts at *start* and increases by *step* each call, clamped to 1.0.
    """

    def __init__(self, start: float = 0.2, step: float = 0.3):
        self._current = start
        self._step = step
        self.call_count = 0

    def __call__(self, _exec_result) -> QualityScore:
        score = min(1.0, self._current)
        self._current += self._step
        self.call_count += 1
        return QualityScore(overall=score, source="test")


# ---------------------------------------------------------------------------
# Retry fires when quality < threshold
# ---------------------------------------------------------------------------

class TestRetryFires:

    def test_retry_fires_on_low_quality(self):
        executor = _CountingExecutor()
        # First eval returns 0.2, second returns 0.5, third returns 0.8
        evaluator = _EscalatingEvaluator(start=0.2, step=0.3)

        pipeline = AutonomousPipeline()
        result = pipeline.run(PipelineConfig(
            intent="test retry",
            executor=executor,
            evaluator=evaluator,
            quality_threshold=0.6,
            max_retries=2,
        ))

        assert result.stage == PipelineStage.COMPLETE
        assert result.retry_count >= 1
        assert executor.call_count >= 2
        # Final quality should be above threshold
        assert result.quality.overall >= 0.6

    def test_retry_count_tracked_on_result(self):
        call_count = 0

        def always_bad(_):
            nonlocal call_count
            call_count += 1
            return QualityScore(overall=0.1, source="test")

        pipeline = AutonomousPipeline()
        result = pipeline.run(PipelineConfig(
            intent="test",
            executor=lambda wf: _make_exec_result(),
            evaluator=always_bad,
            quality_threshold=0.6,
            max_retries=2,
        ))

        assert result.retry_count == 2
        # 1 initial + 2 retries = 3 evaluator calls
        assert call_count == 3


# ---------------------------------------------------------------------------
# max_retries respected
# ---------------------------------------------------------------------------

class TestMaxRetries:

    def test_max_retries_zero_means_no_retry(self):
        executor = _CountingExecutor()

        pipeline = AutonomousPipeline()
        result = pipeline.run(PipelineConfig(
            intent="test",
            executor=executor,
            evaluator=lambda _: QualityScore(overall=0.1),
            quality_threshold=0.6,
            max_retries=0,
        ))

        assert result.stage == PipelineStage.COMPLETE
        assert result.retry_count == 0
        assert executor.call_count == 1

    def test_max_retries_caps_attempts(self):
        executor = _CountingExecutor()

        pipeline = AutonomousPipeline()
        result = pipeline.run(PipelineConfig(
            intent="test",
            executor=executor,
            evaluator=lambda _: QualityScore(overall=0.1),
            quality_threshold=0.9,
            max_retries=3,
        ))

        assert result.retry_count == 3
        # 1 initial + 3 retries = 4 executor calls
        assert executor.call_count == 4


# ---------------------------------------------------------------------------
# Parameters adjust between retries
# ---------------------------------------------------------------------------

class TestParameterAdjustment:

    def test_steps_increase_on_retry(self):
        executor = _CountingExecutor()

        pipeline = AutonomousPipeline()
        pipeline.run(PipelineConfig(
            intent="test",
            executor=executor,
            evaluator=lambda _: QualityScore(overall=0.1),
            quality_threshold=0.6,
            max_retries=1,
        ))

        assert len(executor.workflows) == 2
        wf1 = executor.workflows[0]
        wf2 = executor.workflows[1]

        # Find KSampler node and check steps increased
        for node_id in wf1:
            inputs1 = wf1[node_id].get("inputs", {})
            inputs2 = wf2[node_id].get("inputs", {})
            if "steps" in inputs1 and "steps" in inputs2:
                assert int(inputs2["steps"]) > int(inputs1["steps"])

    def test_cfg_nudges_toward_seven(self):
        """CFG should move toward 7.0 on each retry."""
        pipeline = AutonomousPipeline()

        # Build a workflow with high CFG
        from cognitive.pipeline.autonomous import _FALLBACK_WORKFLOW_SD15
        wf = copy.deepcopy(_FALLBACK_WORKFLOW_SD15)
        # Set CFG to 12.0 (above 7.0, should decrease)
        for node in wf.values():
            if "cfg" in node.get("inputs", {}):
                node["inputs"]["cfg"] = 12.0

        pipeline._adjust_params_for_retry(wf)
        for node in wf.values():
            if "cfg" in node.get("inputs", {}):
                assert node["inputs"]["cfg"] < 12.0


# ---------------------------------------------------------------------------
# No retry when quality >= threshold
# ---------------------------------------------------------------------------

class TestNoRetryAboveThreshold:

    def test_no_retry_when_quality_good(self):
        executor = _CountingExecutor()

        pipeline = AutonomousPipeline()
        result = pipeline.run(PipelineConfig(
            intent="test",
            executor=executor,
            evaluator=lambda _: QualityScore(overall=0.9),
            quality_threshold=0.6,
            max_retries=2,
        ))

        assert result.stage == PipelineStage.COMPLETE
        assert result.retry_count == 0
        assert executor.call_count == 1

    def test_no_retry_at_exact_threshold(self):
        executor = _CountingExecutor()

        pipeline = AutonomousPipeline()
        result = pipeline.run(PipelineConfig(
            intent="test",
            executor=executor,
            evaluator=lambda _: QualityScore(overall=0.6),
            quality_threshold=0.6,
            max_retries=2,
        ))

        assert result.retry_count == 0
        assert executor.call_count == 1

    def test_stage_log_contains_retry_entries(self):
        pipeline = AutonomousPipeline()
        result = pipeline.run(PipelineConfig(
            intent="test",
            executor=lambda wf: _make_exec_result(),
            evaluator=lambda _: QualityScore(overall=0.1),
            quality_threshold=0.6,
            max_retries=1,
        ))

        retry_logs = [s for s in result.stage_log if "retry" in s.lower()]
        assert len(retry_logs) >= 1

    def test_default_max_retries_is_two(self):
        cfg = PipelineConfig()
        assert cfg.max_retries == 2


# ---------------------------------------------------------------------------
# §0b — Blueprint capture: retries become L-tier deltas, captured at LEARN
# ---------------------------------------------------------------------------

class TestBlueprintCapture:
    """The autonomous path now produces and persists a resolved-LIVRPS-stack."""

    def test_retry_deltas_captured_in_chunk(self):
        pipeline = AutonomousPipeline()
        result = pipeline.run(PipelineConfig(
            intent="capture test",
            executor=lambda wf: _make_exec_result(filenames=["o.png"]),
            evaluator=lambda _: QualityScore(overall=0.1, source="test"),
            quality_threshold=0.9,
            max_retries=2,
        ))
        chunk = result.experience_chunk
        assert chunk is not None
        # 2 retries -> 2 L-tier deltas captured as the resolved-LIVRPS-stack
        assert chunk.delta_count == 2
        assert len(chunk.layers) == 2
        assert chunk.delta_count == len(chunk.layers)

    def test_captured_layers_are_all_local_tier(self):
        """Autonomous self-mutation is L-tier only — structurally subordinate to
        S=6 Safety, which the loop can never push or override (§0d/§8)."""
        pipeline = AutonomousPipeline()
        result = pipeline.run(PipelineConfig(
            intent="safety tier test",
            executor=lambda wf: _make_exec_result(),
            evaluator=lambda _: QualityScore(overall=0.1),
            quality_threshold=0.9,
            max_retries=3,
        ))
        layers = result.experience_chunk.layers
        assert layers, "expected captured retry layers"
        assert all(layer["opinion"] == "L" for layer in layers)

    def test_no_retry_means_no_layers(self):
        pipeline = AutonomousPipeline()
        result = pipeline.run(PipelineConfig(
            intent="clean run",
            executor=lambda wf: _make_exec_result(),
            evaluator=lambda _: QualityScore(overall=0.95),
            quality_threshold=0.6,
            max_retries=2,
        ))
        assert result.retry_count == 0
        assert result.experience_chunk.layers == []
        assert result.experience_chunk.delta_count == 0

    def test_captured_layer_round_trips_through_deltalayer(self):
        """The persisted layer dicts are valid DeltaLayer.to_dict() payloads."""
        from cognitive.core.delta import DeltaLayer
        pipeline = AutonomousPipeline()
        result = pipeline.run(PipelineConfig(
            intent="round trip",
            executor=lambda wf: _make_exec_result(),
            evaluator=lambda _: QualityScore(overall=0.1),
            quality_threshold=0.9,
            max_retries=1,
        ))
        layers = result.experience_chunk.layers
        assert len(layers) == 1
        restored = DeltaLayer.from_dict(layers[0])
        assert restored.opinion == "L"
        assert restored.is_intact is True

    def test_engine_absent_direct_call_mutates_in_place_and_returns_dict(self):
        """Backward-compat contract: with no engine (a direct call outside run),
        _adjust_params_for_retry mutates in place AND returns the same dict."""
        pipeline = AutonomousPipeline()
        assert pipeline._engine is None
        wf = {"2": {"class_type": "KSampler", "inputs": {"steps": 20, "cfg": 12.0}}}
        out = pipeline._adjust_params_for_retry(wf)
        assert out is wf  # same object — legacy in-place path
        assert wf["2"]["inputs"]["steps"] == 30
        assert wf["2"]["inputs"]["cfg"] == 11.5
