"""Autonomous Pipeline — end-to-end generation from intent to learning.

Wires all cognitive components into a single autonomous pipeline:
intent → compose → predict → execute → evaluate → learn
"""

from . import autonomous as _autonomous
from .autonomous import (
    AutonomousPipeline, PipelineConfig, PipelineResult, PipelineStage,
)
from ..experience.accumulator import ExperienceAccumulator
from ..prediction.cwm import CognitiveWorldModel
from ..prediction.arbiter import SimulationArbiter
from ..prediction.counterfactual import CounterfactualGenerator


def create_default_pipeline(experience_path: str | None = None) -> AutonomousPipeline:
    """Construct an AutonomousPipeline with default singleton components.

    Instantiates all four cognitive components fresh, loading any previously
    saved experience from *experience_path* (default: the call-time resolver
    in autonomous.py — CANON-EXPFILE) so learning persists across sessions.
    The same resolved path is passed into the pipeline so LEARN saves where
    load() read — no save/load asymmetry. The caller owns their lifetime —
    for MCP server use, call once at startup and keep the returned pipeline
    alive for the server's lifetime (Option A).

    Two calls return two independent pipelines with independent
    accumulator state. There is no implicit module-level singleton.

    Returns:
        AutonomousPipeline ready to call .run(PipelineConfig(...)).
    """
    # Module-attribute lookup (not a from-import) so test patches of
    # autonomous._default_experience_file take effect here too.
    resolved = experience_path or _autonomous._default_experience_file()
    accumulator = ExperienceAccumulator.load(resolved)
    cwm = CognitiveWorldModel()
    arbiter = SimulationArbiter()
    cf_gen = CounterfactualGenerator()
    return AutonomousPipeline(
        accumulator=accumulator,
        cwm=cwm,
        arbiter=arbiter,
        counterfactual_gen=cf_gen,
        experience_path=resolved,
    )


__all__ = [
    "AutonomousPipeline",
    "PipelineConfig",
    "PipelineResult",
    "PipelineStage",
    "create_default_pipeline",
]
