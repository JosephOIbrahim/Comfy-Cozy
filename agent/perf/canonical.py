"""Canonical operation set for the latency baseline.

PRD §5.3 lists 8 canonical operations. Several require a running
ComfyUI; those are gated behind ``profile='full'`` and skipped if
ComfyUI is offline. ``profile='quick'`` runs only the stdlib-bound
operations.

Each canonical op is a (name, callable_factory) pair where the factory
returns a zero-arg callable. Factories let us:
  - sample fresh inputs per benchmark run (Article VI worst-case)
  - skip ComfyUI-dependent ops cleanly when the server is offline
"""

from __future__ import annotations

import json
from typing import Callable


def _factory_validate_path_allowed() -> Callable[[], object]:
    from agent.tools._util import validate_path
    from agent.config import PROJECT_DIR
    p = str(PROJECT_DIR)

    def call() -> object:
        return validate_path(p)

    return call


def _factory_validate_path_blocked() -> Callable[[], object]:
    from agent.tools._util import validate_path

    def call() -> object:
        return validate_path("/etc/passwd")

    return call


def _factory_to_json_small() -> Callable[[], object]:
    from agent.tools._util import to_json
    payload = {"foo": "bar", "n": 42, "list": [1, 2, 3]}

    def call() -> object:
        return to_json(payload)

    return call


def _factory_to_json_large() -> Callable[[], object]:
    from agent.tools._util import to_json
    payload = {f"key_{i}": {"v": i, "nested": list(range(20))} for i in range(200)}

    def call() -> object:
        return to_json(payload)

    return call


_SAMPLE_WORKFLOW = {
    "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd15.safetensors"}},
    "2": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["1", 0], "seed": 42, "steps": 20, "cfg": 7.0,
            "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            "positive": ["3", 0], "negative": ["4", 0], "latent_image": ["5", 0],
        },
    },
    "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "a cat"}},
    "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": ""}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
    "6": {"class_type": "VAEDecode", "inputs": {"samples": ["2", 0], "vae": ["1", 2]}},
    "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "out"}},
}


def _factory_workflow_parse() -> Callable[[], object]:
    """Serialize-roundtrip a sample workflow — pure stdlib, no ComfyUI needed."""

    def call() -> object:
        s = json.dumps(_SAMPLE_WORKFLOW, sort_keys=True)
        return json.loads(s)

    return call


def _factory_get_node_info_offline() -> Callable[[], object] | None:
    """Try to build a get_node_info benchmark; skip if ComfyUI offline."""
    try:
        import httpx
        from agent.config import COMFYUI_URL
        with httpx.Client(timeout=0.5) as client:
            r = client.get(f"{COMFYUI_URL}/system_stats")
            if r.status_code >= 500:
                return None
    except Exception:
        return None

    from agent.tools import handle as tool_handle

    def call() -> object:
        return tool_handle("get_node_info", {"node_type": "KSampler"})

    return call


CANONICAL_QUICK: list[tuple[str, Callable[[], Callable[[], object] | None]]] = [
    ("perf.validate_path.allowed", _factory_validate_path_allowed),
    ("perf.validate_path.blocked", _factory_validate_path_blocked),
    ("perf.to_json.small", _factory_to_json_small),
    ("perf.to_json.large", _factory_to_json_large),
    ("perf.workflow.parse_roundtrip", _factory_workflow_parse),
]

CANONICAL_FULL: list[tuple[str, Callable[[], Callable[[], object] | None]]] = (
    CANONICAL_QUICK + [
        ("tool.get_node_info", _factory_get_node_info_offline),
    ]
)


def get_canonical(profile: str = "quick") -> list[tuple[str, Callable[[], object] | None]]:
    """Return realized (operation_name, callable) pairs for the chosen profile.

    Callables may be None if the underlying tool requires ComfyUI and
    ComfyUI is offline — the caller should skip those operations.
    """
    if profile == "quick":
        entries = CANONICAL_QUICK
    elif profile == "full":
        entries = CANONICAL_FULL
    else:
        raise ValueError(f"unknown profile: {profile!r} (expected 'quick' or 'full')")
    return [(name, factory()) for name, factory in entries]
