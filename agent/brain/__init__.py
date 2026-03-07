"""Brain layer for the ComfyUI SUPER DUPER Agent.

Adds higher-order capabilities on top of the intelligence layers:
  Vision    — see and critique generated images
  Planner   — decompose goals into tracked sub-tasks
  Memory    — learn from outcomes, recommend what works
  Orchestrator — coordinate parallel sub-tasks
  Optimizer — GPU-aware performance engineering
  Demo      — guided walkthroughs for streams/podcasts
  IterativeRefine — autonomous quality iteration loop
  IntentCollector — capture artistic intent for metadata embedding
  IterationAccumulator — track refinement journey across iterations

SDK classes (for standalone/testing use):
  BrainConfig  — dependency injection container
  BrainAgent   — base class for all brain agents
  VisionAgent, PlannerAgent, MemoryAgent, OrchestratorAgent, OptimizerAgent,
  DemoAgent, IterativeRefineAgent, IntentCollectorAgent, IterationAccumulatorAgent
"""

import logging

from . import (  # noqa: F401 — trigger subclass registration
    vision, planner, memory, orchestrator, optimizer,
    demo, iterative_refine, intent_collector, iteration_accumulator,
)
from ._sdk import BrainAgent, BrainConfig  # noqa: F401

# Re-export agent classes (keep ALL existing re-exports)
from .demo import DemoAgent  # noqa: F401
from .intent_collector import IntentCollectorAgent  # noqa: F401
from .iterative_refine import IterativeRefineAgent  # noqa: F401
from .iteration_accumulator import IterationAccumulatorAgent  # noqa: F401
from .memory import MemoryAgent  # noqa: F401
from .optimizer import OptimizerAgent  # noqa: F401
from .orchestrator import OrchestratorAgent  # noqa: F401
from .planner import PlannerAgent  # noqa: F401
from .vision import VisionAgent  # noqa: F401

log = logging.getLogger(__name__)

ALL_BRAIN_TOOLS = BrainAgent.get_all_tools()


def handle(name: str, tool_input: dict) -> str:
    """Dispatch a brain tool call to the right handler."""
    try:
        return BrainAgent.dispatch(name, tool_input)
    except Exception as e:
        log.error("Unhandled error in brain tool %s", name, exc_info=True)
        from ..tools._util import to_json
        return to_json({"error": f"Internal error in {name}: {type(e).__name__}: {e}"})
