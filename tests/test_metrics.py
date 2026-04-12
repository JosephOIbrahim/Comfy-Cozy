"""Tests for agent.metrics module."""

import json
import math
import threading
from unittest.mock import MagicMock, patch

import pytest

from agent.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    get_metrics,
    get_metrics_prometheus,
)


@pytest.fixture(autouse=True)
def _reset_metrics():
    """Reset the global metrics registry between tests."""
    registry = MetricsRegistry()
    registry.reset()
    yield
    registry.reset()


# ---------------------------------------------------------------------------
# Counter tests
# ---------------------------------------------------------------------------


class TestCounter:
    def test_increment_default(self):
        c = Counter("test_counter", labels=["method"])
        c.inc(method="GET")
        c.inc(method="GET")
        c.inc(method="POST")
        vals = c.get()
        assert vals[("GET",)] == 2
        assert vals[("POST",)] == 1

    def test_increment_custom_amount(self):
        c = Counter("test_counter", labels=["method"])
        c.inc(5, method="GET")
        assert c.get()[("GET",)] == 5

    def test_label_isolation(self):
        c = Counter("test_counter", labels=["tool_name", "status"])
        c.inc(tool_name="load_workflow", status="ok")
        c.inc(tool_name="load_workflow", status="error")
        c.inc(tool_name="execute_workflow", status="ok")
        vals = c.get()
        assert vals[("load_workflow", "ok")] == 1
        assert vals[("load_workflow", "error")] == 1
        assert vals[("execute_workflow", "ok")] == 1

    def test_no_labels(self):
        c = Counter("test_counter")
        c.inc()
        c.inc()
        assert c.get()[()] == 2

    def test_reset(self):
        c = Counter("test_counter", labels=["x"])
        c.inc(x="a")
        c.reset()
        assert c.get() == {}


# ---------------------------------------------------------------------------
# Histogram tests
# ---------------------------------------------------------------------------


class TestHistogram:
    def test_observe_and_get(self):
        h = Histogram("test_hist", labels=["tool"])
        h.observe(0.1, tool="a")
        h.observe(0.5, tool="a")
        h.observe(1.0, tool="a")
        data = h.get()
        assert ("a",) in data
        assert data[("a",)]["count"] == 3
        assert abs(data[("a",)]["sum"] - 1.6) < 1e-9

    def test_percentile_p50(self):
        h = Histogram("test_hist")
        for v in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
            h.observe(float(v))
        p50 = h.percentile(50)
        assert abs(p50 - 5.5) < 1e-9

    def test_percentile_p95(self):
        h = Histogram("test_hist")
        for v in range(1, 101):
            h.observe(float(v))
        p95 = h.percentile(95)
        assert p95 >= 95.0

    def test_percentile_p99(self):
        h = Histogram("test_hist")
        for v in range(1, 101):
            h.observe(float(v))
        p99 = h.percentile(99)
        assert p99 >= 99.0

    def test_percentile_empty_returns_nan(self):
        h = Histogram("test_hist")
        assert math.isnan(h.percentile(50))

    def test_bucket_counts(self):
        h = Histogram("test_hist", buckets=[0.1, 0.5, 1.0])
        h.observe(0.05)
        h.observe(0.3)
        h.observe(0.8)
        h.observe(2.0)
        data = h.get()
        buckets = data[()]["buckets"]
        assert buckets["0.1"] == 1
        assert buckets["0.5"] == 2
        assert buckets["1.0"] == 3
        assert buckets["+Inf"] == 4

    def test_reset(self):
        h = Histogram("test_hist")
        h.observe(1.0)
        h.reset()
        assert h.get() == {}


# ---------------------------------------------------------------------------
# Gauge tests
# ---------------------------------------------------------------------------


class TestGauge:
    def test_set(self):
        g = Gauge("test_gauge")
        g.set(42.0)
        assert g.get()[()] == 42.0

    def test_inc(self):
        g = Gauge("test_gauge")
        g.set(10.0)
        g.inc(5.0)
        assert g.get()[()] == 15.0

    def test_dec(self):
        g = Gauge("test_gauge")
        g.set(10.0)
        g.dec(3.0)
        assert g.get()[()] == 7.0

    def test_labels(self):
        g = Gauge("test_gauge", labels=["env"])
        g.set(1.0, env="prod")
        g.set(2.0, env="staging")
        vals = g.get()
        assert vals[("prod",)] == 1.0
        assert vals[("staging",)] == 2.0

    def test_reset(self):
        g = Gauge("test_gauge")
        g.set(5.0)
        g.reset()
        assert g.get() == {}


# ---------------------------------------------------------------------------
# MetricsRegistry tests
# ---------------------------------------------------------------------------


class TestMetricsRegistry:
    def test_get_all_returns_all_registered(self):
        reg = MetricsRegistry()
        # Pre-registered metrics should be present
        all_data = reg.get_all()
        assert "tool_call_total" in all_data
        assert "tool_call_duration_seconds" in all_data
        assert "llm_call_total" in all_data
        assert "session_active" in all_data
        assert "pipeline_runs_total" in all_data

    def test_get_all_types(self):
        reg = MetricsRegistry()
        all_data = reg.get_all()
        assert all_data["tool_call_total"]["type"] == "counter"
        assert all_data["tool_call_duration_seconds"]["type"] == "histogram"
        assert all_data["session_active"]["type"] == "gauge"

    def test_reset_clears_all(self):
        from agent.metrics import tool_call_total
        tool_call_total.inc(tool_name="test", status="ok")
        reg = MetricsRegistry()
        reg.reset()
        assert tool_call_total.get() == {}


# ---------------------------------------------------------------------------
# Thread safety test
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_concurrent_counter_increments(self):
        c = Counter("thread_test", labels=["worker"])
        n_per_thread = 1000
        n_threads = 8
        barrier = threading.Barrier(n_threads)

        def worker():
            barrier.wait()
            for _ in range(n_per_thread):
                c.inc(worker="shared")

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert c.get()[("shared",)] == n_threads * n_per_thread


# ---------------------------------------------------------------------------
# Export function tests
# ---------------------------------------------------------------------------


class TestGetMetrics:
    def test_returns_json_serializable(self):
        from agent.metrics import tool_call_total
        tool_call_total.inc(tool_name="test_tool", status="ok")
        data = get_metrics()
        # Must be JSON-serializable
        serialized = json.dumps(data, sort_keys=True)
        parsed = json.loads(serialized)
        assert isinstance(parsed, dict)
        assert "tool_call_total" in parsed


class TestGetMetricsPrometheus:
    def test_valid_format(self):
        from agent.metrics import tool_call_total, tool_call_duration_seconds
        tool_call_total.inc(tool_name="load", status="ok")
        tool_call_total.inc(tool_name="load", status="ok")
        tool_call_duration_seconds.observe(0.15, tool_name="load")

        text = get_metrics_prometheus()
        assert "# TYPE tool_call_total counter" in text
        assert "# TYPE tool_call_duration_seconds histogram" in text
        assert "tool_call_total{tool_name=" in text
        assert "tool_call_duration_seconds_bucket{" in text
        assert 'le="' in text

    def test_empty_metrics(self):
        text = get_metrics_prometheus()
        # Even with no data, should not crash. May be empty or have headers.
        assert isinstance(text, str)


# ---------------------------------------------------------------------------
# Tool dispatch instrumentation test
# ---------------------------------------------------------------------------


class TestToolDispatchInstrumentation:
    def test_metrics_recorded_on_tool_call(self):
        """Mock a tool module and verify metrics are recorded after dispatch."""
        from agent.metrics import tool_call_total, tool_call_duration_seconds

        mock_mod = MagicMock()
        mock_mod.handle.return_value = '{"status": "ok"}'
        mock_mod.TOOLS = [{"name": "mock_tool"}]

        with (
            patch.dict(
                "agent.tools._HANDLERS", {"mock_tool": mock_mod}, clear=False
            ),
            patch("agent.config.GATE_ENABLED", False),
        ):
            from agent.tools import handle
            result = handle("mock_tool", {})

        assert result == '{"status": "ok"}'
        counts = tool_call_total.get()
        assert counts.get(("mock_tool", "ok"), 0) >= 1
        hist_data = tool_call_duration_seconds.get()
        assert ("mock_tool",) in hist_data

    def test_metrics_recorded_on_tool_error(self):
        """Verify error metrics are recorded when a tool raises."""
        from agent.metrics import tool_call_total

        mock_mod = MagicMock()
        mock_mod.handle.side_effect = RuntimeError("boom")
        mock_mod.TOOLS = [{"name": "broken_tool"}]

        with (
            patch.dict(
                "agent.tools._HANDLERS", {"broken_tool": mock_mod}, clear=False
            ),
            patch("agent.config.GATE_ENABLED", False),
        ):
            from agent.tools import handle
            result = handle("broken_tool", {})

        # Should return error JSON, not crash
        assert "Something went wrong" in result
        counts = tool_call_total.get()
        assert counts.get(("broken_tool", "error"), 0) >= 1


# ---------------------------------------------------------------------------
# Health endpoint metrics test
# ---------------------------------------------------------------------------


class TestHealthMetrics:
    def test_health_includes_metrics(self):
        """check_health() includes a metrics summary."""
        from agent.metrics import tool_call_total, tool_call_duration_seconds

        tool_call_total.inc(tool_name="t1", status="ok")
        tool_call_total.inc(tool_name="t2", status="ok")
        tool_call_total.inc(tool_name="t3", status="error")
        tool_call_duration_seconds.observe(0.1, tool_name="t1")
        tool_call_duration_seconds.observe(0.5, tool_name="t2")

        with (
            patch("agent.health._check_comfyui") as mock_comfy,
            patch("agent.health._check_llm") as mock_llm,
        ):
            mock_comfy.return_value = {"status": "ok"}
            mock_llm.return_value = {"status": "ok"}

            from agent.health import check_health
            result = check_health()

        assert "metrics" in result
        m = result["metrics"]
        assert m["total_tool_calls"] == 3
        assert m["error_rate"] > 0
        assert m["tool_latency_p50"] is not None
        assert m["tool_latency_p99"] is not None
