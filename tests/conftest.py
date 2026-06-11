"""Shared test fixtures for the Comfy Cozy test suite."""

import copy
import json

import pytest


@pytest.fixture(autouse=True)
def _reset_conn_session():
    """Snapshot ``_conn_session`` ContextVar and restore after each test.

    Without this, a test that calls ``_conn_session.set('foo')`` leaks the
    value into the next test, causing order-dependent flakiness. The
    ``LookupError`` branch handles the common case where the var has no
    prior value — we install a ``"default"`` sentinel so there is always
    a token to reset to.
    """
    from agent._conn_ctx import _conn_session

    try:
        token = _conn_session.set(_conn_session.get())
    except LookupError:
        token = _conn_session.set("default")
    try:
        yield
    finally:
        try:
            _conn_session.reset(token)
        except (ValueError, LookupError):
            pass  # Token was already reset by the test itself


@pytest.fixture(autouse=True)
def _reset_circuit_breakers():
    """Reset circuit breakers between tests.

    The COMFYUI_BREAKER is a module-level singleton. Tests that call
    record_failure() can leave it OPEN, poisoning subsequent pipeline tests.
    """
    yield
    try:
        from agent.circuit_breaker import COMFYUI_BREAKER, _breakers, _registry_lock
        breaker = COMFYUI_BREAKER()
        breaker._state = "closed"
        breaker._failure_count = 0
        # Per-endpoint breakers (hardening 3.5) reset in place — identity
        # preserved for any test holding a reference.
        with _registry_lock:
            for name, b in _breakers.items():
                if name.startswith("comfyui:"):
                    b._state = "closed"
                    b._failure_count = 0
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _isolate_experience_file(tmp_path, monkeypatch):
    """Redirect the cognitive experience JSONL to a per-test temp file.

    Without this, every ``pipeline.run()`` in the suite (~56 call sites)
    persists test chunks into the developer's REAL experience store
    (``COMFYUI_DATABASE/comfy-cozy-experience.jsonl``) — real-store
    pollution. Patching the call-time resolver keeps every
    AutonomousPipeline constructed inside a test pointed at tmp_path.

    The CANON-EXPFILE drift-stopper test in test_cognitive_pipeline.py
    opts out by holding an import-time reference to the real resolver,
    which this setattr does not touch.
    """
    try:
        import cognitive.pipeline.autonomous as _auto
    except ImportError:
        yield
        return
    monkeypatch.setattr(
        _auto,
        "_default_experience_file",
        lambda: str(tmp_path / "experience.jsonl"),
    )
    yield


@pytest.fixture(autouse=True)
def _reset_shared_caches():
    """Reset cross-call cached state between tests (ledger A-CACHE-RESET).

    The engine adapter singleton and the /object_info TTL cache are
    module-level state; a warm entry leaking across the mocked suite would
    mask regressions (H0.2 named this the Wave-2 merge blocker).
    """
    yield
    try:
        from agent.engine import _reset_cache_for_tests
        _reset_cache_for_tests()
    except Exception:
        pass
    try:
        from agent.tools.comfy_api import invalidate_object_info_cache
        invalidate_object_info_cache()
    except Exception:
        pass
    try:
        from agent.tools.comfy_discover import _reset_discover_memo_for_tests
        _reset_discover_memo_for_tests()
    except Exception:
        pass
    try:
        from agent.tools.workflow_lock import _hash_cache
        _hash_cache.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_workflow_state():
    """Deep-snapshot and restore ``workflow_patch`` state between tests.

    Consolidated from four duplicate implementations across test_session,
    test_sidebar_workflow, test_new_features, and test_brain_optimizer.
    Uses deepcopy + ``.update()`` so mutable containers (history list,
    current_workflow dict) are fully restored, not aliased.
    """
    from agent.tools import workflow_patch

    original = copy.deepcopy(workflow_patch._get_state())
    yield
    workflow_patch._get_state().update(original)


@pytest.fixture
def sample_workflow():
    """Minimal SD1.5 API-format workflow dict."""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sd15.safetensors"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["5", 0],
                "denoise": 1.0,
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a beautiful landscape", "clip": ["1", 1]},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "ugly, blurry", "clip": ["1", 1]},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["2", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"images": ["6", 0], "filename_prefix": "test"},
        },
    }


@pytest.fixture
def sample_workflow_file(tmp_path, sample_workflow):
    """Write sample_workflow to a JSON file and return the path."""
    path = tmp_path / "workflow.json"
    path.write_text(json.dumps(sample_workflow), encoding="utf-8")
    return path


@pytest.fixture
def fake_image(tmp_path):
    """Create a tiny valid PNG file and return its path as string."""
    png_data = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
        b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
        b"\xd8N\x00\x00\x00\x00IEND\xaeB\x60\x82"
    )
    img_path = tmp_path / "test_output.png"
    img_path.write_bytes(png_data)
    return str(img_path)
