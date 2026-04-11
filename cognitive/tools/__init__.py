"""Consolidated macro-tools for the cognitive layer.

Live macro-tools that compose existing granular tools into
higher-level operations. The granular tools remain available
via MCP for LLM consumers.
"""

from .analyze import analyze_workflow
from .execute import execute_workflow
from .compose import compose_workflow

__all__ = [
    "analyze_workflow",
    "execute_workflow",
    "compose_workflow",
]
