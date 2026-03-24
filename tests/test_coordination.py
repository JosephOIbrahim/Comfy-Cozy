"""Tests for agent coordination — typed handoff artifacts and pipeline envelope."""

import time

from agent.artifacts import (
    EscalationReport,
    ExecutionResult,
    PipelineEnvelope,
    get_service_breakers,
)
from agent.circuit_breaker import get_breaker, reset_all


class TestExecutionResult:
    """Tests for the ExecutionResult handoff artifact."""

    def test_create_success(self):
        result = ExecutionResult(
            prompt_id="abc123",
            status="success",
            output_paths=["/output/img_001.png"],
            execution_time_ms=2500,
        )
        assert result.status == "success"
        assert result.error is None

    def test_create_error(self):
        result = ExecutionResult(
            prompt_id="def456",
            status="error",
            error="Node KSampler not found",
        )
        assert result.status == "error"
        assert result.error == "Node KSampler not found"

    def test_to_dict(self):
        result = ExecutionResult(
            prompt_id="abc",
            status="success",
            output_paths=["/a.png"],
            execution_time_ms=1000,
        )
        d = result.to_dict()
        assert d["prompt_id"] == "abc"
        assert d["status"] == "success"
        assert d["execution_time_ms"] == 1000
        assert d["output_paths"] == ["/a.png"]
        # Keys are sorted (He2025 pattern via to_dict order)
        assert "error" in d

    def test_default_empty_collections(self):
        result = ExecutionResult(prompt_id="x", status="success")
        assert result.output_paths == []
        assert result.node_timings == {}
        assert result.workflow_snapshot == {}
        assert result.patches_applied == []


class TestEscalationReport:
    """Tests for bounded failure escalation (Commandment 3)."""

    def test_create(self):
        report = EscalationReport(
            agent="execution",
            error_type="circuit_open",
            attempts=3,
            max_attempts=3,
            last_error="ComfyUI API unreachable",
            tried=["retry 1", "retry 2", "retry 3"],
            suggestion="Check if ComfyUI is running on port 8188",
        )
        assert report.agent == "execution"
        assert report.attempts == 3

    def test_to_dict(self):
        report = EscalationReport(
            agent="verify",
            error_type="timeout",
            attempts=2,
            max_attempts=3,
            last_error="Vision API timeout after 120s",
        )
        d = report.to_dict()
        assert d["agent"] == "verify"
        assert d["error_type"] == "timeout"
        assert d["attempts"] == 2


class TestPipelineEnvelope:
    """Tests for the pipeline coordination envelope."""

    def test_create_defaults(self):
        env = PipelineEnvelope()
        assert env.phase == "created"
        assert env.correlation_id  # auto-generated
        assert len(env.correlation_id) == 12
        assert env.iteration == 0
        assert env.human_gate_pending is False

    def test_advance_phase(self):
        env = PipelineEnvelope()
        old_time = env.updated_at
        time.sleep(0.01)
        env.advance_phase("intent")
        assert env.phase == "intent"
        assert env.updated_at > old_time

    def test_human_gate_request_and_clear(self):
        env = PipelineEnvelope()
        env.request_human_gate("Workflow will be modified. Review changes?")
        assert env.human_gate_pending is True
        assert "modified" in env.human_gate_reason
        env.clear_human_gate()
        assert env.human_gate_pending is False
        assert env.human_gate_reason == ""

    def test_escalate(self):
        env = PipelineEnvelope()
        report = EscalationReport(
            agent="intent",
            error_type="low_confidence",
            attempts=1,
            max_attempts=1,
            last_error="Confidence 0.3 below threshold 0.5",
        )
        env.escalate(report)
        assert env.phase == "escalated"
        assert env.escalation is not None
        assert env.escalation.agent == "intent"

    def test_to_dict_minimal(self):
        env = PipelineEnvelope(session_id="test")
        d = env.to_dict()
        assert d["phase"] == "created"
        assert d["session_id"] == "test"
        assert "intent" not in d  # not set
        assert "execution" not in d
        assert "verification" not in d
        assert "escalation" not in d

    def test_to_dict_with_execution(self):
        env = PipelineEnvelope()
        env.execution = ExecutionResult(
            prompt_id="abc",
            status="success",
            output_paths=["/out.png"],
        )
        d = env.to_dict()
        assert "execution" in d
        assert d["execution"]["prompt_id"] == "abc"

    def test_to_dict_with_escalation(self):
        env = PipelineEnvelope()
        report = EscalationReport(
            agent="verify",
            error_type="timeout",
            attempts=3,
            max_attempts=3,
            last_error="Timeout",
        )
        env.escalate(report)
        d = env.to_dict()
        assert "escalation" in d
        assert d["escalation"]["agent"] == "verify"

    def test_full_pipeline_flow(self):
        """Simulate a complete pipeline: create -> intent -> exec -> verify -> complete."""
        env = PipelineEnvelope(session_id="sim")

        # Phase 1: Intent
        env.advance_phase("intent")
        assert env.phase == "intent"

        # Human gate before execution
        env.request_human_gate("Apply 3 parameter changes?")
        assert env.human_gate_pending is True

        # User approves
        env.clear_human_gate()

        # Phase 2: Execution
        env.advance_phase("execution")
        env.execution = ExecutionResult(
            prompt_id="sim-001",
            status="success",
            output_paths=["/sim.png"],
            execution_time_ms=3000,
        )

        # Phase 3: Verify
        env.advance_phase("verify")

        # Phase 4: Complete
        env.advance_phase("complete")
        assert env.phase == "complete"

        # Serialize full envelope
        d = env.to_dict()
        assert d["phase"] == "complete"
        assert d["execution"]["status"] == "success"

    def test_escalated_pipeline_flow(self):
        """Pipeline that fails and escalates properly."""
        env = PipelineEnvelope(session_id="fail")
        env.advance_phase("execution")

        # Execution fails after 3 retries
        env.escalate(EscalationReport(
            agent="execution",
            error_type="circuit_open",
            attempts=3,
            max_attempts=3,
            last_error="ComfyUI unreachable",
            tried=["attempt 1", "attempt 2", "attempt 3"],
            suggestion="Verify ComfyUI is running",
        ))
        assert env.phase == "escalated"
        d = env.to_dict()
        assert d["escalation"]["attempts"] == 3


class TestServiceBreakers:
    """Tests for pre-configured service circuit breakers."""

    def setup_method(self):
        reset_all()

    def test_get_service_breakers(self):
        breakers = get_service_breakers()
        assert "comfyui_api" in breakers
        assert "civitai_api" in breakers
        assert "vision_api" in breakers
        assert "github_api" in breakers
        assert "huggingface" in breakers

    def test_comfyui_breaker_config(self):
        breaker = get_breaker("comfyui", failure_threshold=3, recovery_timeout=30)
        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 30.0

    def test_breaker_trips_after_threshold(self):
        breaker = get_breaker("test_trip", failure_threshold=3, recovery_timeout=60)
        assert breaker.allow_request() is True
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.allow_request() is True  # only 2 failures
        breaker.record_failure()
        assert breaker.allow_request() is False  # circuit open

    def test_breaker_resets_on_success(self):
        breaker = get_breaker("test_reset", failure_threshold=2, recovery_timeout=60)
        breaker.record_failure()
        breaker.record_success()
        breaker.record_failure()
        assert breaker.allow_request() is True  # success reset the count
