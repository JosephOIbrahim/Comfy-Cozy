"""Typed handoff artifacts for MoE agent coordination.

Each agent phase produces a structured artifact that the next phase consumes.
This replaces ad-hoc dict passing with typed contracts (Commandment 6:
Explicit Handoffs).

Existing artifacts (kept in their original locations):
  - IntentSpecification (agents/intent_agent.py)
  - VerificationResult (agents/verify_agent.py)

New artifacts defined here:
  - ExecutionResult: what execution produces for verify
  - PipelineEnvelope: carries all artifacts through the pipeline
  - EscalationReport: structured failure escalation (Commandment 3)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ExecutionResult:
    """Handoff artifact from the Execution phase to the Verify phase.

    Contains everything the Verify agent needs to judge the output:
    the prompt ID, output paths, execution timing, and the exact
    workflow state that was executed.
    """

    prompt_id: str
    status: Literal["success", "error", "timeout", "cancelled"]
    output_paths: list[str] = field(default_factory=list)
    execution_time_ms: int = 0
    node_timings: dict[str, float] = field(default_factory=dict)
    workflow_snapshot: dict[str, Any] = field(default_factory=dict)
    patches_applied: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON transport."""
        return {
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "node_timings": self.node_timings,
            "output_paths": self.output_paths,
            "patches_applied": self.patches_applied,
            "prompt_id": self.prompt_id,
            "status": self.status,
            "workflow_snapshot": self.workflow_snapshot,
        }


@dataclass
class EscalationReport:
    """Structured failure report when an agent exhausts its retry budget.

    Commandment 3: Bounded Failure -> Escalate. After N retries, the agent
    produces this instead of silently degrading.
    """

    agent: str  # "intent", "execution", "verify"
    error_type: str  # e.g. "circuit_open", "timeout", "validation_failed"
    attempts: int
    max_attempts: int
    last_error: str
    tried: list[str] = field(default_factory=list)  # what approaches were tried
    suggestion: str = ""  # what the agent thinks should happen next

    def to_dict(self) -> dict[str, Any]:
        """Serialize for JSON transport."""
        return {
            "agent": self.agent,
            "attempts": self.attempts,
            "error_type": self.error_type,
            "last_error": self.last_error,
            "max_attempts": self.max_attempts,
            "suggestion": self.suggestion,
            "tried": self.tried,
        }


@dataclass
class PipelineEnvelope:
    """Carries artifacts between pipeline phases.

    The Router creates an envelope at pipeline start and passes it through
    Intent -> Execution -> Verify. Each phase writes its artifact into the
    envelope. The envelope is the single source of truth for pipeline state.

    Commandment 6: the handoff IS the envelope, not ambient context.
    Commandment 8: human_gate_pending pauses the pipeline for user approval.
    """

    correlation_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id: str = "default"
    phase: Literal[
        "created", "intent", "execution", "verify",
        "complete", "escalated",
    ] = "created"
    intent: Any = None  # IntentSpecification (circular import avoidance)
    execution: ExecutionResult | None = None
    verification: Any = None  # VerificationResult
    escalation: EscalationReport | None = None
    human_gate_pending: bool = False
    human_gate_reason: str = ""
    iteration: int = 0
    max_iterations: int = 3
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def advance_phase(self, new_phase: str) -> None:
        """Advance to the next phase, updating timestamp."""
        self.phase = new_phase
        self.updated_at = time.time()

    def request_human_gate(self, reason: str) -> None:
        """Pause the pipeline for human approval."""
        self.human_gate_pending = True
        self.human_gate_reason = reason
        self.updated_at = time.time()

    def clear_human_gate(self) -> None:
        """Resume pipeline after human approval."""
        self.human_gate_pending = False
        self.human_gate_reason = ""
        self.updated_at = time.time()

    def escalate(self, report: EscalationReport) -> None:
        """Terminate pipeline with an escalation report."""
        self.escalation = report
        self.phase = "escalated"
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the full envelope for JSON transport."""
        result: dict[str, Any] = {
            "correlation_id": self.correlation_id,
            "created_at": self.created_at,
            "human_gate_pending": self.human_gate_pending,
            "human_gate_reason": self.human_gate_reason,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "phase": self.phase,
            "session_id": self.session_id,
            "updated_at": self.updated_at,
        }
        if self.intent and hasattr(self.intent, "to_dict"):
            result["intent"] = self.intent.to_dict()
        if self.execution:
            result["execution"] = self.execution.to_dict()
        if self.verification and hasattr(self.verification, "to_dict"):
            result["verification"] = self.verification.to_dict()
        if self.escalation:
            result["escalation"] = self.escalation.to_dict()
        return result


# ---------------------------------------------------------------------------
# Circuit breaker presets for external services
# ---------------------------------------------------------------------------

def get_service_breakers() -> dict[str, dict[str, Any]]:
    """Return circuit breaker configurations for external services.

    Uses the existing circuit_breaker.get_breaker() factory.
    """
    from .circuit_breaker import get_breaker
    return {
        "comfyui_api": get_breaker("comfyui", failure_threshold=3, recovery_timeout=30),
        "civitai_api": get_breaker("civitai", failure_threshold=3, recovery_timeout=120),
        "vision_api": get_breaker("vision", failure_threshold=2, recovery_timeout=60),
        "github_api": get_breaker("github", failure_threshold=3, recovery_timeout=300),
        "huggingface": get_breaker("huggingface", failure_threshold=3, recovery_timeout=120),
    }
