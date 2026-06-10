"""Tests for agent.perf.contention — concurrent runner + Article IV verdict."""


import pytest

from agent.perf.contention import ContentionResult, run_contention


class TestRunContention:
    def test_basic_low_contention(self):
        # No shared state, fn is trivial — degradation should be low.
        result = run_contention(
            lambda: None,
            operation="noop",
            threads=2,
            calls_per_thread=50,
            warmup=2,
            single_thread_samples=10,
        )
        assert isinstance(result, ContentionResult)
        assert result.threads == 2
        assert result.calls_per_thread == 50
        assert result.errors == 0
        # 4 thread degradation budget is < 2x; trivial noop should easily clear it
        assert result.verdict in ("accept", "refine")

    def test_per_thread_p50_populated(self):
        result = run_contention(
            lambda: None,
            operation="noop",
            threads=3,
            calls_per_thread=20,
            warmup=1,
            single_thread_samples=5,
        )
        assert len(result.per_thread_p50_ms) == 3
        assert all(p >= 0.0 for p in result.per_thread_p50_ms)

    def test_errors_counted(self):
        counter = [0]

        def flaky():
            counter[0] += 1
            if counter[0] % 5 == 0:
                raise RuntimeError("synthetic")

        result = run_contention(
            flaky,
            operation="flaky",
            threads=2,
            calls_per_thread=10,
            warmup=0,
            single_thread_samples=3,
        )
        # Single-thread warmup + 20 concurrent calls should produce several errors
        assert result.errors > 0

    def test_invalid_thread_count(self):
        with pytest.raises(ValueError):
            run_contention(lambda: None, operation="x", threads=0)

    def test_invalid_calls_per_thread(self):
        with pytest.raises(ValueError):
            run_contention(lambda: None, operation="x", calls_per_thread=0)

    def test_verdict_set(self):
        result = run_contention(
            lambda: None,
            operation="noop",
            threads=2,
            calls_per_thread=30,
            warmup=1,
            single_thread_samples=5,
        )
        assert result.verdict in ("accept", "refine", "reject")
        assert result.reason
