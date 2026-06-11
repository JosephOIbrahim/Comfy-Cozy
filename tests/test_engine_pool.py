"""EndpointPool — failover, per-endpoint breakers, affinity (hardening 3.5)."""

from unittest.mock import MagicMock, patch

import pytest

import agent.engine as engine_mod
from agent.circuit_breaker import COMFYUI_BREAKER, get_breaker
from agent.engine import EngineConnectionError, EngineUnavailableError, get_engine
from agent.engine.comfyui_adapter import ComfyUIAdapter
from agent.engine.pool import EndpointPool, _normalize_endpoint

URL_A = "http://10.0.0.1:8188"
URL_B = "http://10.0.0.2:8188"


@pytest.fixture(autouse=True)
def _fresh_engine_cache():
    engine_mod._reset_cache_for_tests()
    yield
    engine_mod._reset_cache_for_tests()


def _pool() -> EndpointPool:
    return EndpointPool([URL_A, URL_B])


def _fail_connect(*a, **k):
    raise EngineConnectionError("refused")


class TestWiring:
    def test_default_mode_is_the_plain_adapter(self):
        eng = get_engine()
        assert isinstance(eng, ComfyUIAdapter)
        assert get_engine() is eng  # identity pin (singleton cache)

    def test_endpoints_config_routes_through_the_pool(self):
        with patch("agent.config.COMFYUI_ENDPOINTS", [URL_A, URL_B]):
            engine_mod._reset_cache_for_tests()
            eng = get_engine()
        assert isinstance(eng, EndpointPool)

    def test_normalization(self):
        assert _normalize_endpoint("10.0.0.5:8190") == "http://10.0.0.5:8190"
        assert _normalize_endpoint("https://farm:9000/") == "https://farm:9000"


class TestBreakers:
    def test_default_adapter_keeps_the_shared_breaker(self):
        adapter = ComfyUIAdapter()
        assert adapter._breaker() is COMFYUI_BREAKER()

    def test_pool_adapters_get_isolated_per_endpoint_breakers(self):
        pool = _pool()
        a, b = pool._adapters
        assert a._breaker() is not b._breaker()
        assert a._breaker() is not COMFYUI_BREAKER()
        for _ in range(3):
            a._breaker().record_failure()
        assert a._breaker().state == "open"
        assert b._breaker().state == "closed"  # sibling unaffected


class TestFailover:
    def test_queue_fails_over_to_the_next_endpoint(self):
        pool = _pool()
        a, b = pool._adapters
        a.queue_prompt = MagicMock(side_effect=_fail_connect)
        b.queue_prompt = MagicMock(return_value="pid-123")
        pid = pool.queue_prompt(workflow={"1": {}}, client_id="c1")
        assert pid == "pid-123"
        a.queue_prompt.assert_called_once()
        b.queue_prompt.assert_called_once()

    def test_affinity_routes_history_to_the_queueing_endpoint(self):
        pool = _pool()
        a, b = pool._adapters
        a.queue_prompt = MagicMock(side_effect=_fail_connect)
        b.queue_prompt = MagicMock(return_value="pid-123")
        a.get_history = MagicMock(return_value={"wrong": "worker"})
        b.get_history = MagicMock(return_value={"pid-123": {"status": {}}})
        pid = pool.queue_prompt(workflow={"1": {}}, client_id="c1")
        hist = pool.get_history(prompt_id=pid)
        assert "pid-123" in hist
        a.get_history.assert_not_called()  # affinity pinned to B

    def test_affinity_routes_ws_by_client_id(self):
        pool = _pool()
        a, b = pool._adapters
        b.queue_prompt = MagicMock(return_value="pid-9")
        a.queue_prompt = MagicMock(side_effect=_fail_connect)
        b.subscribe_ws = MagicMock(return_value="ws-cm-b")
        a.subscribe_ws = MagicMock()
        pool.queue_prompt(workflow={"1": {}}, client_id="client-7")
        assert pool.subscribe_ws(client_id="client-7") == "ws-cm-b"
        a.subscribe_ws.assert_not_called()

    def test_all_endpoints_down_raises_and_mirrors_aggregate(self):
        pool = _pool()
        for ad in pool._adapters:
            ad.get_history = MagicMock(side_effect=_fail_connect)
        before = COMFYUI_BREAKER()._failure_count
        with pytest.raises((EngineConnectionError, EngineUnavailableError)):
            pool.get_history()
        assert COMFYUI_BREAKER()._failure_count == before + 1

    def test_success_mirrors_aggregate_success(self):
        pool = _pool()
        COMFYUI_BREAKER().record_failure()
        pool._adapters[0].get_history = MagicMock(return_value={})
        pool.get_history()
        assert COMFYUI_BREAKER()._failure_count == 0  # success resets

    def test_open_breaker_endpoint_is_skipped_via_fast_fail(self):
        pool = _pool()
        a, b = pool._adapters
        # A's breaker opens after 3 failures; its adapter then fast-fails
        # with EngineUnavailableError without touching the network.
        for _ in range(3):
            a._breaker().record_failure()
        b.get_history = MagicMock(return_value={"ok": True})
        with patch.object(a, "_http") as a_http:  # must never be reached
            result = pool.get_history()
        assert result == {"ok": True}
        a_http.assert_not_called()

    def test_recovery_readmits_after_timeout(self):
        pool = _pool()
        a, b = pool._adapters
        # Pre-create A's breaker with a tiny recovery window (registry
        # returns the existing instance to the adapter afterwards).
        fast = get_breaker(f"comfyui:{URL_A}", recovery_timeout=0.01)
        for _ in range(3):
            fast.record_failure()
        assert fast.state == "open"
        import time
        time.sleep(0.05)
        a.get_history = MagicMock(return_value={"served": "A"})
        b.get_history = MagicMock()
        result = pool.get_history()
        assert result == {"served": "A"}  # HALF_OPEN admitted A again
        b.get_history.assert_not_called()
