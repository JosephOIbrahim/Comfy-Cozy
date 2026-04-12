"""Integration test fixtures.

All tests in this directory require a running ComfyUI instance
and/or an ANTHROPIC_API_KEY.  Fixtures skip cleanly when
prerequisites are missing.
"""

import os
import uuid

import httpx
import pytest

from agent._conn_ctx import _conn_session


# ---------------------------------------------------------------------------
# Session-scoped: external service availability
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def comfyui_available() -> str:
    """Return the ComfyUI base URL if reachable, else skip.

    Checks ``http://127.0.0.1:8188/system_stats`` once per session.
    """
    url = "http://127.0.0.1:8188"
    try:
        resp = httpx.get(f"{url}/system_stats", timeout=5.0)
        resp.raise_for_status()
    except Exception:
        pytest.skip("ComfyUI not running at 127.0.0.1:8188")
    return url


@pytest.fixture(scope="session")
def api_key_available() -> str:
    """Return the Anthropic API key if set, else skip."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


# ---------------------------------------------------------------------------
# Function-scoped: isolated session per test
# ---------------------------------------------------------------------------


@pytest.fixture()
def clean_session():
    """Create a unique session ID, set the ContextVar, yield, then clean up."""
    session_id = f"test_{uuid.uuid4().hex[:8]}"
    token = _conn_session.set(session_id)
    try:
        yield session_id
    finally:
        try:
            _conn_session.reset(token)
        except (ValueError, LookupError):
            pass
