"""Tests for agent.perf.benchmark — stats math + run_benchmark loop."""

import time

import pytest

from agent.perf.benchmark import BenchmarkResult, compute_stats, run_benchmark


class TestComputeStats:
    def test_empty(self):
        s = compute_stats([])
        assert s["n_samples"] == 0
        assert s["p50_ms"] == 0.0
        assert s["mean_ms"] == 0.0

    def test_single_sample(self):
        s = compute_stats([5_000_000])  # 5 ms
        assert s["n_samples"] == 1
        assert s["p50_ms"] == pytest.approx(5.0)
        assert s["p95_ms"] == pytest.approx(5.0)
        assert s["p99_ms"] == pytest.approx(5.0)
        assert s["mean_ms"] == pytest.approx(5.0)
        assert s["std_ms"] == 0.0

    def test_known_distribution(self):
        samples_ns = [i * 1_000_000 for i in range(1, 101)]  # 1..100 ms
        s = compute_stats(samples_ns)
        assert s["n_samples"] == 100
        assert s["p50_ms"] == pytest.approx(50.5, abs=0.5)
        assert s["p95_ms"] == pytest.approx(95.05, abs=0.5)
        assert s["p99_ms"] == pytest.approx(99.01, abs=0.5)
        assert s["min_ms"] == pytest.approx(1.0)
        assert s["max_ms"] == pytest.approx(100.0)
        # CV > 0 for a wide distribution
        assert s["coefficient_of_variation"] > 0


class TestRunBenchmark:
    def test_basic(self):
        result = run_benchmark(lambda: None, operation="noop", n=20, warmup=2)
        assert isinstance(result, BenchmarkResult)
        assert result.n_samples == 20
        assert result.warmup == 2
        assert result.p50_ms >= 0.0
        assert result.mem_peak_mb > 0.0

    def test_sleep_call_is_measurable(self):
        result = run_benchmark(
            lambda: time.sleep(0.005), operation="sleep_5ms", n=10, warmup=1
        )
        # Sleep of 5ms — measured p50 should be at least 4ms (allow OS jitter)
        assert result.p50_ms >= 4.0
        assert result.p50_ms < 50.0  # not absurdly high

    def test_n_zero_rejected(self):
        with pytest.raises(ValueError):
            run_benchmark(lambda: None, operation="x", n=0)

    def test_negative_warmup_rejected(self):
        with pytest.raises(ValueError):
            run_benchmark(lambda: None, operation="x", warmup=-1)

    def test_keep_raw_samples_flag(self):
        r_keep = run_benchmark(
            lambda: None, operation="x", n=5, warmup=0, keep_raw_samples=True
        )
        assert len(r_keep.raw_samples_ns) == 5
        r_drop = run_benchmark(lambda: None, operation="x", n=5, warmup=0)
        assert r_drop.raw_samples_ns == []

    def test_callable_invoked_correct_times(self):
        counter = [0]

        def fn():
            counter[0] += 1

        run_benchmark(fn, operation="x", n=7, warmup=3)
        assert counter[0] == 10  # warmup + n

    def test_gc_disable_restored(self):
        import gc

        was = gc.isenabled()
        try:
            gc.enable()
            run_benchmark(lambda: None, operation="x", n=5, warmup=0, gc_disable=True)
            assert gc.isenabled() is True
        finally:
            if was:
                gc.enable()
            else:
                gc.disable()
