"""L-PANEL: /agent/* bridge route auth + client-safe chat errors.

The bridge node pack registers mutating routes (push_workflow replaces the
artist's canvas; canvas_changed seeds the buffer the agent trusts) directly on
ComfyUI's server. They previously had NO auth. These tests pin the Origin-first
gate (browser must be same-origin; non-browser must carry the Bearer token when
one is configured) and the agent-side header that keeps the agent's own calls
working under a token. Pure logic — no live ComfyUI needed.
"""

import pathlib
import sys
import types


_NODE_PACK = pathlib.Path(__file__).resolve().parent.parent / "node_pack"
if str(_NODE_PACK) not in sys.path:
    sys.path.insert(0, str(_NODE_PACK))

import comfy_agent_bridge as bridge  # noqa: E402


def _req(headers: dict):
    return types.SimpleNamespace(headers=headers)


class TestBridgeAuth:
    def test_same_origin_browser_allowed(self):
        from agent.config import COMFYUI_PORT
        origin = f"http://127.0.0.1:{COMFYUI_PORT}"
        assert bridge.bridge_auth_failure(_req({"Origin": origin})) is None

    def test_cross_origin_browser_rejected(self):
        fail = bridge.bridge_auth_failure(_req({"Origin": "http://evil.example:9999"}))
        assert fail == (403, "forbidden origin")

    def test_non_browser_no_token_allowed(self, monkeypatch):
        monkeypatch.setattr("agent.config.MCP_AUTH_TOKEN", None, raising=False)
        assert bridge.bridge_auth_failure(_req({})) is None

    def test_non_browser_with_token_requires_bearer(self, monkeypatch):
        monkeypatch.setattr("agent.config.MCP_AUTH_TOKEN", "s3cret", raising=False)
        # no Authorization header
        assert bridge.bridge_auth_failure(_req({})) == (401, "unauthorized")
        # wrong token
        assert bridge.bridge_auth_failure(
            _req({"Authorization": "Bearer nope"})
        ) == (401, "unauthorized")
        # correct token
        assert bridge.bridge_auth_failure(
            _req({"Authorization": "Bearer s3cret"})
        ) is None

    def test_agent_unavailable_fails_closed(self, monkeypatch):
        """L-PANEL fail-closed: if the agent package cannot import, every
        request is refused — including same-origin browsers. The mutating
        routes must never serve unauthenticated."""
        import builtins
        real_import = builtins.__import__

        def broken(name, *args, **kwargs):
            if name == "agent" or name.startswith("agent."):
                raise ImportError("agent unavailable (simulated)")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", broken)
        assert bridge.bridge_auth_failure(_req({})) == (503, "agent auth unavailable")
        assert bridge.bridge_auth_failure(
            _req({"Origin": "http://127.0.0.1:8188"})
        ) == (503, "agent auth unavailable")

    def test_agent_client_sends_bearer_when_token_set(self, monkeypatch):
        from agent.tools.canvas_bridge import bridge_auth_headers
        monkeypatch.setattr("agent.config.MCP_AUTH_TOKEN", None, raising=False)
        assert bridge_auth_headers() == {}
        monkeypatch.setattr("agent.config.MCP_AUTH_TOKEN", "s3cret", raising=False)
        assert bridge_auth_headers() == {"Authorization": "Bearer s3cret"}


class TestSafeError:
    def test_no_raw_exception_text(self):
        from agent._session_helpers import safe_error_message
        try:
            {}["nonexistent_internal_key"]
        except KeyError as e:
            msg = safe_error_message("agent turn")
            assert "nonexistent_internal_key" not in msg
            assert str(e) not in msg
            assert "agent turn" in msg
            assert "server logs" in msg
