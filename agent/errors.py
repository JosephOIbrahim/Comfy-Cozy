"""Unified error vocabulary for all tools.

Every tool error follows one shape. No exceptions.
"""

import json as _json


def error_json(message: str, *, hint: str | None = None, **context) -> str:
    """Return a standardized error JSON string.

    Args:
        message: What went wrong (human-readable, no jargon).
        hint: Optional suggestion for what to do next.
        **context: Optional structured context (e.g., available=["a","b"]).
    """
    result: dict = {"error": message}
    if hint:
        result["hint"] = hint
    if context:
        result["context"] = context
    return _json.dumps(result, sort_keys=True)
