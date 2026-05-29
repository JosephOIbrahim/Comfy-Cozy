"""Provision-hardening crucible (harness items s2-s6).

Closure-proof tests for the prompt->RCE / autonomous-fetch hardening. Each item has
a NEGATIVE (bad input now rejected) and a POSITIVE (legit input still works) test.
No network / no subprocess: positives use SSRF/scheme/host-rejected inputs so handlers
run but perform no real fetch/install.
"""

import pytest

from agent.tools import handle


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

    def test_hf_xet_cdn_accepted(self):  # HF Xet backend — resolve/main 302s to cas-bridge.xethub.hf.co
        from agent.tools.comfy_provision import _validate_download_url
        assert _validate_download_url(
            "https://cas-bridge.xethub.hf.co/xet-bridge-us/deadbeef/blob.safetensors"
        ) is None

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


# ---------------------------------------------------------------------------
# s4 — repair_workflow(auto_install) gates the inner install behind confirm
# ---------------------------------------------------------------------------
class TestS4RepairInstallGate:
    @staticmethod
    def _wire(monkeypatch, calls):
        """Fake find_missing_nodes (1 pack) + spy on the installer (no git/pip)."""
        import json
        import agent.tools.comfy_discover as disc
        import agent.tools.comfy_provision as cp
        monkeypatch.setattr(disc, "handle", lambda name, ti: json.dumps(
            {"missing": [{"class_type": "Foo", "pack_url": "https://github.com/x/foo", "pack_name": "foo"}]}
        ) if name == "find_missing_nodes" else json.dumps({}))
        monkeypatch.setattr(cp, "_handle_install_node_pack",
                            lambda ti: (calls.append(ti), json.dumps({"installed": True, "message": "ok"}))[1])

    def test_auto_install_without_confirm_blocks(self, monkeypatch):  # NEGATIVE
        import json
        import agent.tools.comfy_provision as cp
        calls = []
        self._wire(monkeypatch, calls)
        r = json.loads(cp._handle_repair_workflow({"auto_install": True}))
        assert r["status"] == "needs_confirmation", r
        assert calls == [], "install must NOT run without confirm"

    def test_auto_install_with_confirm_proceeds(self, monkeypatch):  # POSITIVE
        import json
        import agent.tools.comfy_provision as cp
        calls = []
        self._wire(monkeypatch, calls)
        r = json.loads(cp._handle_repair_workflow({"auto_install": True, "confirm": True}))
        assert r["status"] != "needs_confirmation", r
        assert len(calls) == 1, "confirmed install should run exactly once"

    def test_report_only_not_gated(self, monkeypatch):  # POSITIVE (fluid report path)
        import json
        import agent.tools.comfy_provision as cp
        calls = []
        self._wire(monkeypatch, calls)
        r = json.loads(cp._handle_repair_workflow({"auto_install": False}))
        assert r["status"] != "needs_confirmation", r
        assert calls == [], "report-only must not install"


# ---------------------------------------------------------------------------
# s5 — provision_model is gated at entry by the keystone (cross-module bypass closed)
# ---------------------------------------------------------------------------
class TestS5ProvisionModelGatedAtEntry:
    def test_provision_model_is_provision_risk(self):
        from agent.gate.risk_levels import get_risk_level, RiskLevel
        assert get_risk_level("provision_model") == RiskLevel.PROVISION

    def test_provision_model_blocked_without_confirm(self):  # NEGATIVE — no dispatch, no discover/network
        r = handle("provision_model", {"query": "some model", "auto_download": True})
        assert "auto-blocked" in r.lower(), r
        # POSITIVE (confirmed dispatch) is covered transitively by the keystone crucible:
        # any PROVISION op with confirm=true falls through to dispatch (test_*_confirmed_dispatches).


# ---------------------------------------------------------------------------
# s6 — gate-level https-only on url keys + fix misleading "available immediately" message
# ---------------------------------------------------------------------------
class TestS6UrlScopeAndMessage:
    def test_check_scope_rejects_non_https_url(self):  # NEGATIVE
        from agent.gate.checks import check_scope
        ok, reason = check_scope("download_model", {"url": "http://github.com/x/y"})
        assert ok is False and "https" in reason.lower(), reason

    def test_check_scope_allows_https_url(self):  # POSITIVE
        from agent.gate.checks import check_scope
        ok, _ = check_scope("download_model", {"url": "https://huggingface.co/x/y"})
        assert ok is True

    def test_download_message_not_misleading(self):  # message fix (source-level guard)
        import inspect
        import agent.tools.comfy_provision as cp
        src = inspect.getsource(cp._handle_download_model)
        assert "available immediately" not in src, "misleading 'available immediately' still present"
        assert "estart" in src.lower(), "download success should mention restart/refresh"
