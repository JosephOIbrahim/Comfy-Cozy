"""Tests for agent.tools.perf_tools — MCP tool wrappers."""

import json
from pathlib import Path


from agent.tools import handle as tool_handle


class TestBenchmarkTool:
    def test_against_fast_synthetic_tool(self, tmp_path, monkeypatch):
        # Redirect baselines to tmp so we don't write into the repo.
        from agent.perf import baseline as baseline_mod
        monkeypatch.setattr(baseline_mod, "BASELINES_DIR", tmp_path)

        # Stub-tool: register a fake handler into the dispatch map for the
        # duration of the test so benchmark_tool has something cheap to call.
        from agent.tools import _HANDLERS

        class _FakeMod:
            __name__ = "_test_fake_mod"

            @staticmethod
            def handle(name, tool_input, **kwargs):
                return json.dumps({"ok": True})

        _HANDLERS["_test_fake_tool"] = _FakeMod
        try:
            raw = tool_handle("benchmark_tool", {
                "name": "_test_fake_tool",
                "input": {},
                "n": 10,
                "warmup": 1,
                "tag": "smoke",
            })
            payload = json.loads(raw)
            assert payload["n_samples"] == 10
            assert payload["operation"] == "tool._test_fake_tool"
            assert payload["tag"] == "smoke"
            assert payload["p50_ms"] >= 0.0
            assert "baseline_path" in payload
            assert Path(payload["baseline_path"]).exists()
        finally:
            _HANDLERS.pop("_test_fake_tool", None)

    def test_no_record_skips_baseline_file(self, tmp_path, monkeypatch):
        from agent.perf import baseline as baseline_mod
        monkeypatch.setattr(baseline_mod, "BASELINES_DIR", tmp_path)

        from agent.tools import _HANDLERS

        class _FakeMod:
            __name__ = "_test_fake_mod"

            @staticmethod
            def handle(name, tool_input, **kwargs):
                return json.dumps({"ok": True})

        _HANDLERS["_test_fake_tool"] = _FakeMod
        try:
            raw = tool_handle("benchmark_tool", {
                "name": "_test_fake_tool",
                "input": {},
                "n": 5,
                "warmup": 0,
                "record": False,
            })
            payload = json.loads(raw)
            assert "baseline_path" not in payload
            assert not any(tmp_path.iterdir())
        finally:
            _HANDLERS.pop("_test_fake_tool", None)


class TestProfileTool:
    def test_cprofile_produces_trace(self, tmp_path, monkeypatch):
        from agent.perf import profile as profile_mod
        monkeypatch.setattr(profile_mod, "TRACES_DIR", tmp_path)

        from agent.tools import _HANDLERS

        class _FakeMod:
            __name__ = "_test_fake_mod"

            @staticmethod
            def handle(name, tool_input, **kwargs):
                # Do a tiny bit of work so cProfile has something to record.
                total = 0
                for i in range(1000):
                    total += i
                return json.dumps({"sum": total})

        _HANDLERS["_test_profile_target"] = _FakeMod
        try:
            raw = tool_handle("profile_tool", {
                "name": "_test_profile_target",
                "input": {},
                "profiler": "cprofile",
                "top_n": 5,
            })
            payload = json.loads(raw)
            assert payload["profiler"] == "cprofile"
            assert "trace_path" in payload
            assert Path(payload["trace_path"]).exists()
            assert "top_n_functions" in payload
        finally:
            _HANDLERS.pop("_test_profile_target", None)


class TestCompareBaselines:
    def test_accept_path(self, tmp_path):
        before_path = tmp_path / "before.jsonl"
        after_path = tmp_path / "after.jsonl"
        hw = {"fingerprint_hash": "hw1"}

        before_rec = {
            "operation": "x", "tag": "baseline",
            "p50_ms": 100.0, "p95_ms": 150.0, "p99_ms": 200.0,
            "mem_peak_mb": 100.0, "hardware": hw,
        }
        after_rec = {
            "operation": "x", "tag": "after",
            "p50_ms": 85.0, "p95_ms": 140.0, "p99_ms": 195.0,
            "mem_peak_mb": 100.0, "hardware": hw,
        }
        before_path.write_text(json.dumps(before_rec, sort_keys=True) + "\n")
        after_path.write_text(json.dumps(after_rec, sort_keys=True) + "\n")

        raw = tool_handle("compare_baselines", {
            "before_path": str(before_path),
            "after_path": str(after_path),
        })
        payload = json.loads(raw)
        assert payload["verdict"] == "accept"

    def test_missing_records(self, tmp_path):
        before_path = tmp_path / "empty.jsonl"
        after_path = tmp_path / "also_empty.jsonl"
        before_path.write_text("")
        after_path.write_text("")
        raw = tool_handle("compare_baselines", {
            "before_path": str(before_path),
            "after_path": str(after_path),
        })
        payload = json.loads(raw)
        assert "error" in payload


class TestLatencyBaseline:
    def test_quick_profile(self, tmp_path, monkeypatch):
        from agent.perf import baseline as baseline_mod
        monkeypatch.setattr(baseline_mod, "BASELINES_DIR", tmp_path)

        raw = tool_handle("latency_baseline", {
            "profile": "quick",
            "tag": "smoke",
            "n": 5,
            "warmup": 1,
        })
        payload = json.loads(raw)
        assert payload["profile"] == "quick"
        assert payload["tag"] == "smoke"
        assert len(payload["results"]) >= 3
        # Every result has a baseline_path
        for r in payload["results"]:
            assert Path(r["baseline_path"]).exists()
            assert r["p50_ms"] >= 0.0
