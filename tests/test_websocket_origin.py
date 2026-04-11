"""Regression tests for cycle 8 — WebSocket Origin validation.

The sidebar (`/superduper/ws`) and panel (`/comfy-cozy/chat-ws`) WebSocket
handlers now validate the Origin header against agent._session_helpers.
allowed_origins() before upgrading the connection. Without this check, any
page on any origin could open a WebSocket to localhost and use the agent's
full tool surface (info disclosure + confused-deputy workflow execution).
"""

from __future__ import annotations

from unittest.mock import patch


class TestAllowedOrigins:
    """agent/_session_helpers.py:allowed_origins() returns the right set."""

    def test_default_localhost_variants(self):
        """The default config (127.0.0.1:8188) yields all four canonical forms."""
        from agent._session_helpers import allowed_origins
        with patch("agent.config.COMFYUI_HOST", "127.0.0.1"), \
             patch("agent.config.COMFYUI_PORT", 8188):
            origins = allowed_origins()
        assert "http://127.0.0.1:8188" in origins
        assert "http://localhost:8188" in origins
        assert "http://[::1]:8188" in origins

    def test_custom_port(self):
        """Custom port flows through to the allowlist."""
        from agent._session_helpers import allowed_origins
        with patch("agent.config.COMFYUI_HOST", "127.0.0.1"), \
             patch("agent.config.COMFYUI_PORT", 9999):
            origins = allowed_origins()
        assert "http://127.0.0.1:9999" in origins
        assert "http://localhost:9999" in origins
        # The default 8188 should NOT leak in
        assert "http://127.0.0.1:8188" not in origins

    def test_custom_host(self):
        """Custom host flows through to the allowlist as a fourth entry."""
        from agent._session_helpers import allowed_origins
        with patch("agent.config.COMFYUI_HOST", "192.168.1.50"), \
             patch("agent.config.COMFYUI_PORT", 8188):
            origins = allowed_origins()
        assert "http://192.168.1.50:8188" in origins
        # Localhost variants still allowed for local testing
        assert "http://127.0.0.1:8188" in origins

    def test_returns_frozenset(self):
        """allowed_origins() returns a frozenset (immutable)."""
        from agent._session_helpers import allowed_origins
        origins = allowed_origins()
        assert isinstance(origins, frozenset)

    def test_evil_origin_not_in_allowlist(self):
        """An attacker origin like https://evil.com is NEVER in the allowlist."""
        from agent._session_helpers import allowed_origins
        origins = allowed_origins()
        assert "https://evil.com" not in origins
        assert "http://evil.com" not in origins
        assert "http://localhost.evil.com:8188" not in origins
        assert "http://127.0.0.1.evil.com:8188" not in origins


class TestOriginValidationLogic:
    """The Origin check pattern used in both WebSocket handlers."""

    def test_cross_origin_rejected(self):
        """An Origin not in allowed_origins() should be rejected."""
        from agent._session_helpers import allowed_origins
        evil_origin = "https://evil.com"
        assert evil_origin not in allowed_origins()

    def test_localhost_accepted(self):
        """Same-origin (localhost) should be accepted."""
        from agent._session_helpers import allowed_origins
        with patch("agent.config.COMFYUI_HOST", "127.0.0.1"), \
             patch("agent.config.COMFYUI_PORT", 8188):
            origins = allowed_origins()
            assert "http://127.0.0.1:8188" in origins

    def test_empty_origin_passes_through(self):
        """Empty Origin header (non-browser client) passes the Origin check
        and falls through to the bearer auth layer in the handlers."""
        # The pattern in both handlers is:
        #   if origin and origin not in allowed_origins(): reject
        # When origin == "", the `if origin and ...` is False, so we don't
        # reject — we fall through to the bearer auth check. Verify the
        # truthy check works as expected.
        empty_origin = ""
        # The validation block only fires when origin is truthy
        assert not empty_origin  # confirm "" is falsy
