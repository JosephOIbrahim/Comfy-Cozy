"""Autonomous generation pipeline.

End-to-end: creative intent → composed workflow → predicted outcome
→ execution → evaluation → learning. Zero human intervention.

The pipeline orchestrates all cognitive components:
- Composer: intent → workflow
- CWM: predict quality before executing
- Arbiter: decide whether to surface predictions
- Engine: non-destructive mutations
- Experience: capture and learn from outcomes
- Ratchet: iterative optimization
"""

from __future__ import annotations

import copy
import json
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from ..core.graph import CognitiveGraphEngine
from ..experience.chunk import ExperienceChunk, QualityScore
from ..experience.accumulator import ExperienceAccumulator
from ..experience.signature import GenerationContextSignature
from ..prediction.cwm import CognitiveWorldModel, Prediction
from ..prediction.arbiter import SimulationArbiter, DeliveryMode
from ..prediction.counterfactual import CounterfactualGenerator
from ..tools.analyze import analyze_workflow
from ..tools.compose import compose_workflow
from ..tools.execute import execute_workflow as _execute_workflow_default
import os

EXPERIENCE_FILE = (
    Path(os.getenv("COMFYUI_DATABASE") or str(Path.home() / ".comfy-cozy"))
    / "comfy-cozy-experience.jsonl"
)

log = logging.getLogger(__name__)

_FALLBACK_WORKFLOW_SD15: dict = {
    "1": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"},
    },
    "2": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "a beautiful image", "clip": ["1", 1]},
    },
    "3": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "ugly, blurry, low quality", "clip": ["1", 1]},
    },
    "4": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 512, "height": 512, "batch_size": 1},
    },
    "5": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 42,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler_ancestral",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["1", 0],
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
        },
    },
    "6": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
    },
    "7": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "ComfyUI", "images": ["6", 0]},
    },
}

# NOTE: This path reads from agent/templates/ but does NOT import from agent/.
# Option A-compliant — filesystem read, not a Python import. If agent/ is ever
# removed, SDXL silently falls back to SD1.5 (the hardcoded fallback only
# contains SD1.5). Follow-up session: copy templates to cognitive/templates/
# to eliminate this cross-layer dependency.
_AGENT_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "agent" / "templates"

_STEM_TO_FAMILY = {
    "txt2img_sd15": "SD1.5",
    "txt2img_sdxl": "SDXL",
    "img2img": "SDXL",
    "txt2img_lora": "SDXL",
}


def _load_available_templates() -> list[dict]:
    """Load workflow templates from agent/templates/ dir.

    Returns a list of template metadata dicts in the shape expected by
    compose_workflow: [{"name": str, "family": str, "data": dict}].

    Falls back to the hardcoded SD1.5 template if the directory is missing
    or all files fail to parse.
    """
    templates: list[dict] = []
    if _AGENT_TEMPLATES_DIR.exists():
        for json_path in sorted(_AGENT_TEMPLATES_DIR.glob("*.json")):
            name = json_path.stem
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                templates.append({
                    "name": name,
                    "family": _STEM_TO_FAMILY.get(name, "SD1.5"),
                    "data": data,
                })
            except (json.JSONDecodeError, OSError):
                continue

    if not templates:
        templates = [
            {
                "name": "txt2img_sd15_fallback",
                "family": "SD1.5",
                "data": copy.deepcopy(_FALLBACK_WORKFLOW_SD15),
            }
        ]
    return templates


class PipelineStage(Enum):
    """Stages of the autonomous pipeline."""

    INTENT = "intent"
    COMPOSE = "compose"
    PREDICT = "predict"
    GATE = "gate"  # Arbiter decides whether to proceed
    EXECUTE = "execute"
    EVALUATE = "evaluate"
    RETRY = "retry"
    LEARN = "learn"
    COMPLETE = "complete"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass
class PipelineConfig:
    """Configuration for an autonomous pipeline run."""

    intent: str = ""
    model_family: str | None = None
    quality_threshold: float = 0.6
    max_retries: int = 2  # Max retry attempts when quality < threshold
    executor: Callable | None = None  # Actual execution delegate
    evaluator: Callable | None = None  # Quality evaluation delegate
    vision_analyzer: Callable | None = None  # Injected vision analysis callback


@dataclass
class PipelineResult:
    """Result of an autonomous pipeline run."""

    stage: PipelineStage = PipelineStage.INTENT
    intent: str = ""
    workflow_data: dict[str, Any] = field(default_factory=dict)
    prediction: Prediction | None = None
    arbiter_decision: Any | None = None
    execution_result: Any | None = None
    quality: QualityScore = field(default_factory=QualityScore)
    experience_chunk: ExperienceChunk | None = None
    error: str = ""
    stage_log: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    retry_count: int = 0

    @property
    def success(self) -> bool:
        return self.stage == PipelineStage.COMPLETE and not self.error

    def log(self, message: str) -> None:
        self.stage_log.append(f"[{self.stage.value}] {message}")


class AutonomousPipeline:
    """Orchestrates the full autonomous generation pipeline.

    Components are injected at construction time. Missing components
    degrade gracefully — the pipeline adapts to what's available.
    """

    def __init__(
        self,
        accumulator: ExperienceAccumulator | None = None,
        cwm: CognitiveWorldModel | None = None,
        arbiter: SimulationArbiter | None = None,
        counterfactual_gen: CounterfactualGenerator | None = None,
    ):
        self._accumulator = accumulator or ExperienceAccumulator()
        self._cwm = cwm or CognitiveWorldModel()
        self._arbiter = arbiter or SimulationArbiter()
        self._cf_gen = counterfactual_gen or CounterfactualGenerator()
        self._run_lock = threading.Lock()  # Serialise concurrent run() calls

    def run(self, config: PipelineConfig) -> PipelineResult:
        """Execute the full autonomous pipeline.

        Stages:
        1. INTENT: Parse the creative intent
        2. COMPOSE: Build a workflow from intent + experience
        3. PREDICT: Predict quality before executing
        4. GATE: Arbiter decides whether to proceed
        5. EXECUTE: Run the workflow (via delegate)
        6. EVALUATE: Assess output quality
        7. LEARN: Store experience + counterfactual

        Returns:
            PipelineResult with full execution details. If a pipeline run is
            already in progress, returns immediately with result.error set
            rather than blocking indefinitely.
        """
        if not self._run_lock.acquire(blocking=False):
            result = PipelineResult(intent=config.intent)
            result.error = "Pipeline already running — concurrent run rejected. Wait for the current run to complete."
            return result
        try:
            return self._run_locked(config)
        finally:
            self._run_lock.release()

    def _run_locked(self, config: PipelineConfig) -> PipelineResult:
        """Internal run body — called under self._run_lock."""
        result = PipelineResult(intent=config.intent)

        # Stage 1: INTENT
        result.stage = PipelineStage.INTENT
        if not config.intent.strip():
            result.error = "Empty intent"
            result.stage = PipelineStage.FAILED
            return result
        result.log(f"Intent: {config.intent}")

        # Stage 2: COMPOSE
        result.stage = PipelineStage.COMPOSE
        experience_patterns = self._get_experience_patterns(config)
        available_templates = _load_available_templates()
        composition = compose_workflow(
            config.intent,
            model_family=config.model_family,
            experience_patterns=experience_patterns,
            available_templates=available_templates,
        )
        if not composition.success:
            result.error = f"Composition failed: {composition.error}"
            result.stage = PipelineStage.FAILED
            return result

        result.workflow_data = composition.workflow_data

        # Post-COMPOSE diagnostic (§17): warn if workflow is empty or malformed.
        # Warn-only — does not halt the pipeline. The fallback guard below
        # ensures we proceed with a valid workflow even if the warning fires.
        _analysis = analyze_workflow(result.workflow_data)
        if _analysis.node_count == 0:
            result.log(
                "COMPOSE warning: workflow has 0 nodes — "
                "falling back to SD1.5 template"
            )

        # Last-resort fallback if compose still returned empty workflow_data
        # (e.g., no template matched the detected model family)
        if not result.workflow_data:
            result.log(
                f"No template matched family={composition.plan.model_family if composition.plan else 'unknown'}"
                " — using SD1.5 fallback"
            )
            result.workflow_data = copy.deepcopy(_FALLBACK_WORKFLOW_SD15)
            result.warnings.append(
                f"No template found for family '{config.model_family}'; fell back to SD1.5 default"
            )

        model_family = composition.plan.model_family if composition.plan else ""
        params = composition.plan.parameters if composition.plan else {}

        # Guard: if model_family is empty (compose step returned no plan or
        # reported an unknown family), fall back to SD1.5 explicitly so that
        # predict() uses an intentional baseline rather than an empty-string
        # lookup that silently matches nothing. (Cycle 28 fix)
        if not model_family:
            log.warning("model_family is empty after compose — defaulting to SD1.5")
            model_family = "SD1.5"

        result.log(f"Composed workflow: family={model_family}, params={len(params)}")

        # Stage 3: PREDICT
        result.stage = PipelineStage.PREDICT
        exp_weight = self._accumulator.experience_weight
        cf_adjustment = self._cf_gen.get_adjustment()

        try:
            prediction = self._cwm.predict(
                model_family=model_family,
                parameters=params,
                experience_quality=self._get_avg_experience_quality(config),
                experience_weight=exp_weight,
                counterfactual_adjustment=cf_adjustment,
            )
        except Exception as e:
            log.error("CWM predict failed: %s", e)
            result.stage = PipelineStage.FAILED
            result.error = f"CWM prediction failed: {e}"
            result.log(result.error)
            return result
        result.prediction = prediction
        result.log(
            f"Predicted quality: {prediction.quality_estimate:.1%} "
            f"(confidence: {prediction.confidence:.1%})"
        )

        # Stage 4: GATE (Arbiter)
        result.stage = PipelineStage.GATE
        decision = self._arbiter.decide(
            prediction.quality_estimate,
            prediction.confidence,
            prediction.risk_factors,
        )
        result.arbiter_decision = decision

        if decision.should_interrupt:
            result.log(f"Arbiter interrupted: {decision.message}")
            result.error = f"Arbiter: {decision.message}"
            result.stage = PipelineStage.INTERRUPTED
            return result

        if decision.mode != DeliveryMode.SILENT:
            result.log(f"Arbiter ({decision.mode.value}): {decision.message}")

        # Resolve evaluator once (used by execute-evaluate-retry loop)
        if config.evaluator is not None:
            _evaluator = config.evaluator
        elif config.vision_analyzer is not None:
            _evaluator = self._vision_evaluator(config.vision_analyzer)
        else:
            _evaluator = self._default_evaluator

        _executor = (
            config.executor
            if config.executor is not None
            else _execute_workflow_default
        )

        # Execute → Evaluate → Retry loop
        while True:
            # Stage 5: EXECUTE
            result.stage = PipelineStage.EXECUTE
            try:
                exec_result = _executor(result.workflow_data)
                result.execution_result = exec_result
                if result.retry_count == 0:
                    result.log("Execution complete")
                else:
                    result.log(
                        f"Retry execution complete "
                        f"(attempt {result.retry_count})"
                    )
            except Exception as e:
                label = "Retry execution" if result.retry_count else "Execution"
                result.error = f"{label} failed: {e}"
                result.stage = PipelineStage.FAILED
                return result

            # Stage 6: EVALUATE
            result.stage = PipelineStage.EVALUATE
            try:
                quality = _evaluator(result.execution_result)
                if isinstance(quality, QualityScore):
                    result.quality = quality
                elif isinstance(quality, (int, float)):
                    result.quality = QualityScore(overall=float(quality))
                result.log(f"Quality: {result.quality.overall:.1%}")
            except Exception as e:
                result.log(f"Evaluation failed: {e}")
                result.error = f"Evaluation failed: {e}"
                result.stage = PipelineStage.FAILED
                return result

            # Check if retry needed
            if (
                result.quality.overall < config.quality_threshold
                and result.retry_count < config.max_retries
            ):
                result.retry_count += 1
                result.stage = PipelineStage.RETRY
                result.log(
                    f"Quality {result.quality.overall:.1%} below threshold "
                    f"{config.quality_threshold:.1%}, retry "
                    f"{result.retry_count}/{config.max_retries}"
                )

                # Adjust parameters for retry: increase steps, nudge CFG
                self._adjust_params_for_retry(result.workflow_data)
                continue  # loop back to EXECUTE

            break  # quality OK or retries exhausted

        # Stage 7: LEARN
        result.stage = PipelineStage.LEARN
        chunk = ExperienceChunk(
            model_family=model_family,
            prompt=config.intent,
            parameters=params,
            quality=result.quality,
            output_filenames=[],
        )
        if result.execution_result is not None:
            chunk.output_filenames = getattr(
                result.execution_result, "output_filenames", [],
            )

        try:
            self._accumulator.record(chunk)
            result.experience_chunk = chunk
            result.log(f"Recorded experience (total: {self._accumulator.generation_count})")
        except Exception as e:
            log.warning("Experience record failed (non-fatal): %s", e)
            result.log(f"Experience record failed (non-fatal): {e}")

        # Persist accumulated experience so it survives between sessions
        try:
            saved = self._accumulator.save(str(EXPERIENCE_FILE))
            result.log(f"Experience persisted ({saved} chunks → {EXPERIENCE_FILE.name})")
        except Exception as e:
            log.warning("Experience save failed (%s: %s)", type(e).__name__, e)
            result.log(f"Experience save failed (non-fatal): {e}")

        # Record prediction accuracy
        if result.quality.is_scored and result.prediction is not None:
            self._cwm.record_accuracy(
                result.prediction.quality_estimate,
                result.quality.overall,
            )

        # Generate counterfactual
        cf = self._cf_gen.generate(params, prediction.quality_estimate)
        if cf is not None:
            result.log(f"Counterfactual: vary {cf.changed_parameter}")

        result.stage = PipelineStage.COMPLETE
        result.log("Pipeline complete")
        return result

    def _get_experience_patterns(self, config: PipelineConfig) -> list[dict]:
        """Get relevant experience patterns for composition."""
        if self._accumulator.generation_count == 0:
            return []

        # Build a rough signature from intent keywords
        sig = GenerationContextSignature()
        if config.model_family:
            sig.model_family = config.model_family

        retrieval = self._accumulator.retrieve(sig, top_k=5, min_similarity=0.0)
        return [
            {
                "confidence": chunk.quality.overall * chunk.decay_weight,
                "parameters": chunk.parameters,
            }
            for chunk in retrieval.matches
        ]

    def _get_avg_experience_quality(self, config: PipelineConfig) -> float | None:
        """Get average quality from relevant experience."""
        successful = self._accumulator.get_successful_chunks(min_quality=0.3)
        if not successful:
            return None
        return sum(c.quality.overall for c in successful) / len(successful)

    def _default_evaluator(self, execution_result: Any) -> QualityScore:
        """Rule-based quality evaluation for when no evaluator is provided.

        PLACEHOLDER VALUES (Session N+1): 0.7 on success, 0.1 on failure.
        These are deliberately chosen so auto-retry (threshold=0.6) fires only
        on execution failure, not on "mediocre success." Calibration deferred
        to Session N+2 when the vision evaluator replaces this rule-based path.
        """
        if execution_result is not None and getattr(execution_result, "success", False):
            return QualityScore(overall=0.7, source="rule")
        return QualityScore(overall=0.1, source="rule")

    @staticmethod
    def _vision_evaluator(
        vision_analyzer: Callable,
    ) -> Callable[[Any], QualityScore]:
        """Build an evaluator that delegates to an injected vision analyzer.

        The *vision_analyzer* callable receives an image path (str) and
        returns a dict with keys: ``quality_score``, ``prompt_adherence``,
        and optionally ``technical_score``, ``aesthetic_score``.

        When the analyzer returns unusable data the evaluator degrades
        to a rule-based 0.5 score so the pipeline never crashes.
        """

        def _evaluate(execution_result: Any) -> QualityScore:
            # Extract output image path from execution result
            filenames: list[str] = getattr(
                execution_result, "output_filenames", [],
            )
            if not filenames:
                return QualityScore(overall=0.5, source="vision_fallback")

            image_path = filenames[0]

            try:
                raw = vision_analyzer(image_path)
            except Exception as exc:
                log.warning("Vision analyzer failed: %s", exc)
                return QualityScore(overall=0.5, source="vision_error")

            if not isinstance(raw, dict):
                # Try JSON parse if string
                if isinstance(raw, str):
                    try:
                        raw = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        return QualityScore(
                            overall=0.5, source="vision_parse_error",
                        )
                else:
                    return QualityScore(
                        overall=0.5, source="vision_type_error",
                    )

            overall = float(raw.get("quality_score", 0.5))
            technical = float(raw.get("technical_score", 0.0))
            aesthetic = float(raw.get("aesthetic_score", 0.0))
            adherence = float(raw.get("prompt_adherence", 0.0))

            return QualityScore(
                overall=overall,
                technical=technical,
                aesthetic=aesthetic,
                prompt_adherence=adherence,
                source="vision",
            )

        return _evaluate

    @staticmethod
    def _adjust_params_for_retry(workflow_data: dict[str, Any]) -> None:
        """Adjust workflow parameters between retry attempts.

        Increases steps by 10 and nudges CFG toward 7.0 (the general
        sweet spot across model families).
        """
        for _node_id, node_data in workflow_data.items():
            if not isinstance(node_data, dict):
                continue
            inputs = node_data.get("inputs", {})
            if not isinstance(inputs, dict):
                continue
            if "steps" in inputs:
                try:
                    inputs["steps"] = int(inputs["steps"]) + 10
                except (ValueError, TypeError):
                    pass
            if "cfg" in inputs:
                try:
                    cfg_val = float(inputs["cfg"])
                    if cfg_val < 7.0:
                        inputs["cfg"] = round(cfg_val + 0.5, 1)
                    elif cfg_val > 7.0:
                        inputs["cfg"] = round(cfg_val - 0.5, 1)
                except (ValueError, TypeError):
                    pass
