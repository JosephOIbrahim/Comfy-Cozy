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
        # confirm=true passes the keystone; the handler must still reject the off-allowlist host.
        # (host check is the FIRST handler step — rejects before any mkdir/network.)
        r = handle("download_model", {
            "url": "https://evil.example.com/m.safetensors",
            "model_type": "checkpoints", "filename": "m.safetensors", "confirm": True,
        })
        assert "allowlist" in r.lower(), r


# ---------------------------------------------------------------------------
# s3 — pickle-format block (default-deny) + sha256 verify
# ---------------------------------------------------------------------------
class TestS3PickleAndHash:
    def test_pickle_blocked_by_default(self):  # NEGATIVE
        from agent.tools.comfy_provision import _pickle_blocked
        assert _pickle_blocked(".ckpt", {}) is True
        assert _pickle_blocked(".pt", {}) is True
        assert _pickle_blocked(".bin", {}) is True

    def test_safetensors_not_blocked(self):  # POSITIVE (safe format works)
        from agent.tools.comfy_provision import _pickle_blocked
        assert _pickle_blocked(".safetensors", {}) is False
        assert _pickle_blocked(".gguf", {}) is False

    def test_allow_pickle_override(self):  # POSITIVE (explicit opt-in works)
        from agent.tools.comfy_provision import _pickle_blocked
        assert _pickle_blocked(".ckpt", {"allow_pickle": True}) is False
        assert _pickle_blocked(".ckpt", {"allow_pickle": "true"}) is False

    def test_sha256_verify_helper(self, tmp_path):  # NEGATIVE+POSITIVE
        import hashlib
        from agent.tools.comfy_provision import _verify_sha256
        f = tmp_path / "blob.bin"
        f.write_bytes(b"hello world")
        assert _verify_sha256(f, hashlib.sha256(b"hello world").hexdigest()) is None  # match
        assert _verify_sha256(f, "deadbeef" * 8) is not None                          # mismatch
