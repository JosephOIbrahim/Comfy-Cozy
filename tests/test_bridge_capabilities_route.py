"""B4: /agent/capabilities gate logic + bridge build-identity pinning.

The route handler is defined inside _register_routes() and needs a live
PromptServer, so the relaxation decision is factored into the pure helper
capabilities_relaxed() (same pattern as bridge_auth_failure) and tested here
with a stub request — no ComfyUI, no sockets.

The gate's threat model is pinned by these tests: the raw socket peer is NOT
an auth signal (a same-host reverse proxy makes every peer loopback, and a
DNS-rebound page is genuinely same-origin so it carries no Origin either).
The Host header is what actually distinguishes them.
"""

import subprocess
import sys

import pytest

_REPO = __import__("pathlib").Path(__file__).resolve().parent.parent
_NODE_PACK = _REPO / "node_pack"
if str(_NODE_PACK) not in sys.path:
    sys.path.insert(0, str(_NODE_PACK))

from comfy_agent_bridge import bridge_auth_failure, capabilities_relaxed  # noqa: E402


class _Req:
    """Minimal stand-in for aiohttp's Request (headers + transport peer)."""

    def __init__(self, headers=None, remote="127.0.0.1"):
        self.headers = headers or {}
        self.remote = remote


def _good_host() -> str:
    """A host:port the origin allowlist trusts — never hardcoded, so the
    test follows COMFYUI_HOST/COMFYUI_PORT wherever the config points."""
    from agent._session_helpers import allowed_origins

    return sorted(allowed_origins())[0].split("://", 1)[1]


class TestRelaxedGate:
    def test_loopback_no_origin_good_host_relaxes(self):
        """The sidebar's own manifest fetch: same-origin GETs omit Origin."""
        assert capabilities_relaxed(_Req({"Host": _good_host()})) is True

    def test_host_match_is_case_insensitive(self):
        assert capabilities_relaxed(_Req({"Host": _good_host().upper()})) is True

    def test_dns_rebinding_foreign_host_gets_full_gate(self):
        """A rebound page IS same-origin (no Origin) and its peer IS loopback;
        only the Host header it was fetched under gives it away."""
        host = _good_host().split(":")[-1]
        assert capabilities_relaxed(_Req({"Host": f"evil.tld:{host}"})) is False

    def test_missing_host_gets_full_gate(self):
        assert capabilities_relaxed(_Req({})) is False

    def test_proxied_peer_gets_full_gate(self):
        """A same-host reverse proxy forwards a good Host with a loopback peer
        for internet traffic — the peer must not buy any relaxation on its own."""
        assert capabilities_relaxed(_Req({"Host": _good_host()}, remote="203.0.113.7")) is False

    def test_cross_origin_never_relaxes(self):
        req = _Req({"Host": _good_host(), "Origin": "http://evil.tld"})
        assert capabilities_relaxed(req) is False

    def test_cross_origin_is_rejected_403(self):
        assert bridge_auth_failure(_Req({"Origin": "http://evil.tld"})) == (
            403,
            "forbidden origin",
        )

    def test_unix_socket_peer_still_needs_good_host(self):
        assert capabilities_relaxed(_Req({"Host": _good_host()}, remote=None)) is True
        assert capabilities_relaxed(_Req({"Host": "evil.tld:8188"}, remote=None)) is False

    def test_fails_closed_when_agent_unavailable(self):
        """Same doctrine as bridge_auth_failure: an unverifiable gate refuses."""
        import unittest.mock

        req = _Req({"Host": _good_host()})  # resolve BEFORE the import is broken
        with unittest.mock.patch.dict(sys.modules, {"agent._session_helpers": None}):
            assert capabilities_relaxed(req) is False


class TestBuildIdentityPinned:
    def test_bridge_import_pins_build_identity(self):
        """agent._build computes BUILD_HASH lazily and caches on first access.
        If nothing touches it until the first manifest request, an artist who
        pulled new code mid-session gets it computed against the NEW on-disk
        HEAD — reporting "fresh" while the process runs the old code. Fresh
        interpreter so the assertion sees a genuinely untouched module."""
        code = (
            "import sys\n"
            f"sys.path.insert(0, {str(_NODE_PACK)!r})\n"
            "import comfy_agent_bridge\n"
            "from agent import _build\n"
            "assert 'BUILD_HASH' in _build.__dict__, 'BUILD_HASH not pinned at bridge import'\n"
            "assert 'BUILD_DIRTY' in _build.__dict__, 'BUILD_DIRTY not pinned at bridge import'\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=str(_REPO),
            timeout=120,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr

    def test_manifest_reports_the_pinned_hash(self):
        """The manifest must read the captured value, not re-run git."""
        from agent import _build

        from comfy_agent_bridge._manifest import build_manifest

        assert build_manifest()["agent"]["build_hash"] == _build.BUILD_HASH


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
