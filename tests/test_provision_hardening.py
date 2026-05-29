"""Provision-hardening crucible (harness items s2-s6).

Closure-proof tests for the prompt->RCE / autonomous-fetch hardening. Each item has
a NEGATIVE (bad input now rejected) and a POSITIVE (legit input still works) test.
No network / no subprocess: positives use SSRF/scheme/host-rejected inputs so handlers
run but perform no real fetch/install.
"""

import copy
from collections import deque

import pytest

from agent.tools import handle, workflow_patch


@pytest.fixture(autouse=True)
def _gate_on(monkeypatch):
    monkeypatch.setattr("agent.config.GATE_ENABLED", True, raising=False)


# ---------------------------------------------------------------------------
# s2 — download host allowlist (was dead code)
# ---------------------------------------------------------------------------
class TestS2HostAllowlist:
    def test_offlist_host_rejected(self):
        from agent.tools.comfy_provision import _validate_download_url
        err = _validate_download_url("https://evil.example.com/model.safetensors")
        assert err is not None and "allowlist" in err.lower(), err

    def test_allowlisted_hosts_accepted(self):
        from agent.tools.comfy_provision import _validate_download_url
        assert _validate_download_url("https://huggingface.co/x/model.safetensors") is None
        assert _validate_download_url("https://civitai.com/api/download/123") is None

    def test_allowlisted_subdomain_accepted(self):  # CDN, e.g. cdn-lfs.huggingface.co
        from agent.tools.comfy_provision import _validate_download_url
        assert _validate_download_url("https://cdn-lfs.huggingface.co/repo/blob") is None

    def test_offlist_download_rejected_even_when_confirmed(self):
        # confirm=true passes the keystone; the handler must still reject the off-allowlist host
        r = handle("download_model", {
            "url": "https://evil.example.com/m.safetensors",
            "model_type": "checkpoints", "filename": "m.safetensors", "confirm": True,
        })
        assert "allowlist" in r.lower(), r
