"""Tests for agent.perf.baseline — hardware fingerprint, JSONL round-trip, compare."""


import pytest

from agent.perf.baseline import (
    HardwareFingerprint,
    append_baseline,
    capture_hardware,
    compare,
    load_baseline,
    record_from_benchmark,
)
from agent.perf.benchmark import run_benchmark


class TestCaptureHardware:
    def test_returns_fingerprint(self):
        hw = capture_hardware()
        assert isinstance(hw, HardwareFingerprint)
        assert hw.platform
        assert hw.python
        assert hw.cpu_count >= 1
        # Hash is 16-char hex
        assert len(hw.fingerprint_hash) == 16
        int(hw.fingerprint_hash, 16)  # raises if not hex

    def test_is_stable(self):
        h1 = capture_hardware()
        h2 = capture_hardware()
        assert h1.fingerprint_hash == h2.fingerprint_hash


class TestRecordRoundTrip:
    def test_append_and_load(self, tmp_path):
        bench = run_benchmark(lambda: None, operation="op.x", n=5, warmup=1)
        rec = record_from_benchmark(bench, tag="smoke")
        path = append_baseline(rec, baselines_dir=tmp_path)
        assert path.exists()
        records = load_baseline(path)
        assert len(records) == 1
        assert records[0]["operation"] == "op.x"
        assert records[0]["tag"] == "smoke"
        assert "hardware" in records[0]
        assert "fingerprint_hash" in records[0]["hardware"]

    def test_multiple_appends(self, tmp_path):
        bench = run_benchmark(lambda: None, operation="op.x", n=3, warmup=0)
        for tag in ("smoke", "baseline", "after"):
            rec = record_from_benchmark(bench, tag=tag)
            append_baseline(rec, baselines_dir=tmp_path)
        path = tmp_path / "op.x.jsonl"
        records = load_baseline(path)
        assert len(records) == 3
        assert [r["tag"] for r in records] == ["smoke", "baseline", "after"]

    def test_safe_filename_for_pathy_op_name(self, tmp_path):
        bench = run_benchmark(lambda: None, operation="tool/get:node", n=3, warmup=0)
        rec = record_from_benchmark(bench, tag="smoke")
        path = append_baseline(rec, baselines_dir=tmp_path)
        # No slashes or colons in the actual filename
        assert "/" not in path.name
        assert ":" not in path.name


class TestCompare:
    def _make_record(self, p50: float, p95: float, p99: float, mem: float, hw_hash: str) -> dict:
        return {
            "operation": "op.x",
            "tag": "x",
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "mem_peak_mb": mem,
            "hardware": {"fingerprint_hash": hw_hash},
        }

    def test_accept_when_improvement_above_threshold(self):
        before = self._make_record(100.0, 150.0, 200.0, 100.0, "hw1")
        after = self._make_record(85.0, 140.0, 195.0, 100.0, "hw1")
        result = compare(before, after)
        assert result["verdict"] == "accept"
        assert result["p50_pct_change"] == pytest.approx(15.0, abs=0.01)

    def test_refine_when_improvement_below_threshold(self):
        before = self._make_record(100.0, 150.0, 200.0, 100.0, "hw1")
        after = self._make_record(95.0, 148.0, 199.0, 100.0, "hw1")
        result = compare(before, after)
        assert result["verdict"] == "refine"

    def test_reject_on_regression(self):
        before = self._make_record(100.0, 150.0, 200.0, 100.0, "hw1")
        after = self._make_record(85.0, 200.0, 250.0, 100.0, "hw1")
        result = compare(before, after)
        assert result["verdict"] == "reject"
        assert "regressed" in result["reason"]

    def test_reject_on_memory_bloat(self):
        before = self._make_record(100.0, 150.0, 200.0, 100.0, "hw1")
        after = self._make_record(50.0, 100.0, 150.0, 200.0, "hw1")
        result = compare(before, after)
        assert result["verdict"] == "reject"
        assert "mem" in result["reason"]

    def test_reject_cross_hardware(self):
        before = self._make_record(100.0, 150.0, 200.0, 100.0, "hw1")
        after = self._make_record(50.0, 100.0, 150.0, 100.0, "hw2")
        result = compare(before, after)
        assert result["verdict"] == "reject"
        assert "hardware" in result["reason"].lower()
