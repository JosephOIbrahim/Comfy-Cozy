"""MCP surface for run diagnosis — ONE read-only tool (Cherny cut #5).

Everything richer than a query is the model reading the diagnosis documents
on disk — that is the point of files.
"""

from ._util import to_json

TOOLS: list[dict] = [
    {
        "name": "diagnose",
        "description": (
            "Read the latest run report (deterministic, keyless diagnosis document): "
            "environment fingerprint, per-node stage timings, fired triggers, and an "
            "explained finding for every trigger. query: 'latest' (default) for the "
            "newest document, 'env' for the environment fingerprint plus open "
            "warn/critical findings, or a diagnosisId/promptId for a specific run."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "'latest' | 'env' | <diagnosisId> | <promptId>",
                },
            },
        },
    },
]


def handle(name: str, tool_input: dict) -> str:
    try:
        if name == "diagnose":
            from ..diagnosis.cli import query
            return query(str(tool_input.get("query") or "latest"))
        return to_json({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return to_json({"error": f"diagnosis query failed: {e}"})
