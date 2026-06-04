"""Route-auth audit 4.6 — handler-level confirm defense-in-depth.

The keystone pre-dispatch gate ESCALATEs install_node_pack / download_model and
blocks them without confirm. These tests assert the *handler* enforces the same
confirm requirement independently — so even a caller that bypasses the central
gate (the bug fixed in fix #1) cannot run git clone + pip install or a network
fetch unattended. Validation still runs first (so invalid input still errors).
"""

from __future__ import annotations

import json
from unittest.mock import patch

from agent.tools import comfy_provision


def test_install_requires_confirm_at_handler_level():
    """A valid install without confirm -> needs_confirmation; git clone never runs."""
    with patch("agent.tools.comfy_provision.subprocess.run") as run:
        result = json.loads(
            comfy_provision.handle("install_node_pack", {"url": "https://github.com/example/pack"})
        )
    assert result.get("status") == "needs_confirmation", result
    run.assert_not_called()


def test_download_requires_confirm_at_handler_level():
    """A valid download without confirm -> needs_confirmation; httpx never runs."""
    with patch("agent.tools.comfy_provision.httpx.stream") as stream:
        result = json.loads(
            comfy_provision.handle(
                "download_model",
                {
                    "url": "https://huggingface.co/example.safetensors",
                    "model_type": "checkpoints",
                    "filename": "example.safetensors",
                },
            )
        )
    assert result.get("status") == "needs_confirmation", result
    stream.assert_not_called()


def test_install_invalid_url_still_errors_without_confirm():
    """Validation runs before the confirm gate -- a bad url still errors, not needs_confirmation."""
    result = json.loads(comfy_provision.handle("install_node_pack", {"url": ""}))
    assert "error" in result and result.get("status") != "needs_confirmation"
