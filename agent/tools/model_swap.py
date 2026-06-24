"""swap_model / list_models_available — the artist-facing easy-swap tools.

TOOLS + handle() pattern; registered in agent/tools/__init__.py via
_INTELLIGENCE_MODULE_NAMES. swap_model changes the reasoning model for the CLI
agent loop (and out-of-band brain calls). Under `agent mcp` the HOST (Claude
Code / Desktop) owns the conversational model and is NOT changed — the tool
says so explicitly rather than reporting a swap the user can't see.
"""
from __future__ import annotations

import os

from ._util import to_json

TOOLS: list[dict] = [
    {
        "name": "list_models_available",
        "description": (
            "List the LLM model aliases you can swap the agent to (e.g. 'claude', "
            "'nemotron'). Returns each alias with its provider and model id."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "swap_model",
        "description": (
            "Switch the agent's reasoning model for this session. Pass an alias "
            "('claude', 'nemotron'), a 'provider:model' string, or a bare model id. "
            "Affects the CLI agent loop and brain/vision out-of-band calls. Under "
            "`agent mcp` the host (Claude Code) owns this chat model and is unchanged. "
            "Does NOT move image analysis (analyze_image stays on VISION_PROVIDER)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "alias": {"type": "string", "description": "Friendly alias or bare model id"},
                "provider": {"type": "string", "description": "Optional explicit provider"},
                "model": {"type": "string", "description": "Optional explicit model id"},
            },
        },
    },
]


def _mcp_mode() -> bool:
    """True when running under `agent mcp` (the host owns the chat model)."""
    return os.getenv("COMFY_COZY_MCP", "") == "1"


def handle(name: str, tool_input: dict) -> str:
    from ..llm.swap import list_aliases, swap

    if name == "list_models_available":
        return to_json({"aliases": list_aliases()})

    if name == "swap_model":
        try:
            result = swap(
                alias=tool_input.get("alias"),
                provider=tool_input.get("provider"),
                model=tool_input.get("model"),
                probe=True,  # live-check the key so a bad one rolls back, not mid-chat
            )
        except Exception as e:
            return to_json({"error": str(e)})
        if _mcp_mode():
            return to_json({
                "swapped": False,
                "applies_to": "cli_loop_and_vision_calls",
                **result,
                "note": (
                    "Under MCP the host (Claude Code) owns this chat model and is "
                    "unchanged. This repointed the CLI agent loop + brain/vision calls."
                ),
            })
        return to_json({"swapped": True, **result})

    return to_json({"error": f"unknown tool {name}"})
