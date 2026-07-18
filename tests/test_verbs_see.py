"""Tests for the SEE verb engine (agent/verbs/see.py).

All mocked — no ComfyUI server, no network. Live-event tests use the real
TriggerRegistry singleton (in-process, loopback-free) and clean up their
subscriptions so no trigger leaks across tests.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent.verbs.see import (
    StepSample,
    StepTimeCollector,
    _durations,
    render_run_summary,
    step_durations_from_progress_log,
    vram_snapshot,
)

GB = 1024.0**3


def _progress_event(
    node_id: str = "3",
    value: int = 1,
    max_value: int = 20,
    timestamp: float = 100.0,
    prompt_id: str = "p1",
) -> SimpleNamespace:
    """Duck-typed stand-in for cognitive.transport.events.ExecutionEvent."""
    return SimpleNamespace(
        event_type=SimpleNamespace(value="progress"),
        prompt_id=prompt_id,
        node_id=node_id,
        timestamp=timestamp,
        progress_value=value,
        progress_max=max_value,
    )


def _success_result() -> dict:
    return {
        "status": "complete",
        "prompt_id": "p1",
        "total_time_s": 14.2,
        "outputs": [],
        "node_timing": [
            {"node_id": "3", "class_type": "KSampler", "duration_s": 12.4},
            {"node_id": "8", "class_type": "VAEDecode", "duration_s": 1.1},
            {"node_id": "6", "class_type": "CLIPTextEncode", "duration_s": 0.3},
            {"node_id": "4", "class_type": "CheckpointLoaderSimple", "duration_s": 0.2},
        ],
        "progress_events": 20,
        "monitoring": "websocket",
    }


class TestDurationsMath:
    def test_consecutive_same_node_deltas(self):
        samples = [
            StepSample("3", 1, 4, 0.0),
            StepSample("3", 2, 4, 0.5),
            StepSample("3", 3, 4, 1.5),
            StepSample("3", 4, 4, 1.9),
        ]
        assert _durations(samples) == [0.5, 1.0, pytest.approx(0.4)]

    def test_node_switch_yields_no_cross_node_duration(self):
        samples = [
            StepSample("3", 1, 2, 0.0),
            StepSample("3", 2, 2, 0.5),
            StepSample("9", 1, 2, 5.0),  # new node: baseline only
            StepSample("9", 2, 2, 5.4),
        ]
        assert _durations(samples) == [0.5, pytest.approx(0.4)]

    def test_value_reset_on_same_node_reseeds_baseline(self):
        samples = [
            StepSample("3", 1, 2, 0.0),
            StepSample("3", 2, 2, 0.5),
            StepSample("3", 1, 2, 3.0),  # second pass: no 2.5s phantom step
            StepSample("3", 2, 2, 3.3),
        ]
        assert _durations(samples) == [0.5, pytest.approx(0.3)]

    def test_negative_delta_clamped_to_zero(self):
        samples = [StepSample("3", 1, 2, 1.0), StepSample("3", 2, 2, 0.4)]
        assert _durations(samples) == [0.0]


class TestCollectorAccumulation:
    def test_on_event_records_progress_and_times_by_timestamp_delta(self):
        c = StepTimeCollector()
        for i, ts in enumerate([100.0, 100.5, 101.5, 101.9], start=1):
            c.on_event(_progress_event(value=i, timestamp=ts))
        assert c.sample_count == 4
        assert c.step_durations() == [0.5, 1.0, pytest.approx(0.4)]

    def test_on_event_ignores_non_progress_events(self):
        c = StepTimeCollector()
        c.on_event(
            SimpleNamespace(event_type=SimpleNamespace(value="execution_complete"), prompt_id="p1")
        )
        assert c.sample_count == 0

    def test_prompt_id_filter_rejects_other_runs_but_accepts_blank(self):
        c = StepTimeCollector(prompt_id="p1")
        c.on_event(_progress_event(value=1, prompt_id="other"))
        assert c.sample_count == 0
        c.on_event(_progress_event(value=1, prompt_id=""))  # progress data often omits it
        c.on_event(_progress_event(value=2, prompt_id="p1"))
        assert c.sample_count == 2

    def test_on_event_never_raises_on_garbage(self):
        c = StepTimeCollector()
        c.on_event(None)
        c.on_event(object())
        assert c.sample_count == 0

    def test_ingest_progress_log(self):
        log = [
            {"event": "executing_node", "node_id": "3", "elapsed_s": 0.1},
            {"event": "progress", "node_id": "3", "value": 1, "max": 3, "elapsed_s": 1.0},
            {"event": "progress", "node_id": "3", "value": 2, "max": 3, "elapsed_s": 1.6},
            {"event": "progress", "node_id": "3", "value": 3, "max": 3, "elapsed_s": 2.0},
            "garbage",
            {"event": "progress", "value": "not-an-int"},
        ]
        c = StepTimeCollector()
        assert c.ingest_progress_log(log) == 3
        assert c.step_durations() == [pytest.approx(0.6), pytest.approx(0.4)]

    def test_ingest_non_list_is_zero(self):
        c = StepTimeCollector()
        assert c.ingest_progress_log(None) == 0  # type: ignore[arg-type]
        assert c.ingest_progress_log({"event": "progress"}) == 0  # type: ignore[arg-type]

    def test_empty_run(self):
        c = StepTimeCollector()
        assert c.sample_count == 0
        assert c.step_durations() == []


class TestRegistrySubscription:
    def test_install_is_idempotent_and_uninstall_removes(self):
        from cognitive.transport import triggers

        c = StepTimeCollector()
        before = triggers._default_registry.count()
        try:
            assert c.install() is True
            assert c.install() is True  # second call: no second trigger
            assert triggers._default_registry.count() == before + 1
        finally:
            c.uninstall()
            c.uninstall()  # idempotent
        assert triggers._default_registry.count() == before

    def test_dispatched_progress_event_reaches_collector(self):
        from cognitive.transport import triggers
        from cognitive.transport.events import EventType, ExecutionEvent

        c = StepTimeCollector()
        try:
            assert c.install() is True
            for i, ts in enumerate([10.0, 10.5], start=1):
                triggers.dispatch(
                    ExecutionEvent(
                        event_type=EventType.PROGRESS,
                        prompt_id="p1",
                        node_id="3",
                        timestamp=ts,
                        progress_value=i,
                        progress_max=2,
                    )
                )
            triggers.dispatch(
                ExecutionEvent(event_type=EventType.EXECUTION_COMPLETE, prompt_id="p1")
            )
        finally:
            c.uninstall()
        assert c.sample_count == 2
        assert c.step_durations() == [0.5]


class TestStepDurationsFromProgressLog:
    def test_pure_function_matches_collector(self):
        log = [
            {"event": "progress", "node_id": "3", "value": 1, "max": 2, "elapsed_s": 1.0},
            {"event": "progress", "node_id": "3", "value": 2, "max": 2, "elapsed_s": 1.7},
        ]
        assert step_durations_from_progress_log(log) == [pytest.approx(0.7)]

    def test_empty_and_malformed(self):
        assert step_durations_from_progress_log([]) == []
        assert step_durations_from_progress_log([{"event": "progress"}]) == []


class TestVramSnapshot:
    def test_parses_first_vram_device(self):
        stats = {
            "system": {"os": "nt"},
            "devices": [
                {"name": "cpu", "type": "cpu"},
                {
                    "name": "NVIDIA GeForce RTX 4090",
                    "vram_total": 24 * GB,
                    "vram_free": 14 * GB,
                },
            ],
        }
        with patch("agent.tools.comfy_api.handle", return_value=json.dumps(stats)):
            snap = vram_snapshot()
        assert snap == {"name": "NVIDIA GeForce RTX 4090", "total_gb": 24.0, "used_gb": 10.0}

    def test_comfyui_down_returns_none(self):
        down = json.dumps({"error": "Could not connect to ComfyUI. Is it running?"})
        with patch("agent.tools.comfy_api.handle", return_value=down):
            assert vram_snapshot() is None

    def test_handler_raising_returns_none(self):
        with patch("agent.tools.comfy_api.handle", side_effect=RuntimeError("boom")):
            assert vram_snapshot() is None

    def test_no_vram_device_returns_none(self):
        stats = {"devices": [{"name": "cpu"}]}
        with patch("agent.tools.comfy_api.handle", return_value=json.dumps(stats)):
            assert vram_snapshot() is None


class TestRenderRunSummary:
    def _collector(self) -> StepTimeCollector:
        c = StepTimeCollector()
        for i, ts in enumerate([0.0, 0.5, 1.5, 1.9], start=1):
            c.add_sample("3", i, 4, ts)
        return c

    def test_full_summary_with_stats(self):
        snap = {"name": "RTX 4090", "used_gb": 9.8, "total_gb": 24.0}
        out = render_run_summary(self._collector(), _success_result(), poll_stats=lambda: snap)
        lines = out.splitlines()
        assert lines[0] == "run    complete · 14.2 s"
        assert lines[1].startswith("steps  ")
        assert "3 steps ·" in lines[1] and "s/it avg" in lines[1]
        assert lines[2] == "nodes  KSampler 12.4s · VAEDecode 1.1s · CLIPTextEncode 0.3s"
        assert lines[3].startswith("vram   [")
        assert "9.8/24.0 GB" in lines[3] and "RTX 4090" in lines[3]

    def test_summary_without_stats_degrades(self):
        out = render_run_summary(self._collector(), _success_result(), poll_stats=lambda: None)
        assert "vram   unavailable — ComfyUI not reachable" in out
        assert "Traceback" not in out

    def test_poll_raising_degrades_not_raises(self):
        def _boom() -> dict | None:
            raise RuntimeError("socket down")

        out = render_run_summary(self._collector(), _success_result(), poll_stats=_boom)
        assert "vram   unavailable" in out

    def test_empty_run_renders_honest_placeholder(self):
        out = render_run_summary(StepTimeCollector(), None, poll_stats=lambda: None)
        assert "steps  (no step telemetry captured)" in out
        assert "run    " not in out  # no status line without a result
        assert "nodes  " not in out

    def test_falls_back_to_progress_log_when_collector_empty(self):
        result = {
            "status": "error",
            "error": "CUDA out of memory",
            "progress_log": [
                {"event": "progress", "node_id": "3", "value": 1, "max": 2, "elapsed_s": 1.0},
                {"event": "progress", "node_id": "3", "value": 2, "max": 2, "elapsed_s": 1.8},
            ],
        }
        out = render_run_summary(StepTimeCollector(), result, poll_stats=lambda: None)
        assert "run    error" in out
        assert "1 steps ·" in out  # one duration recovered from the log

    def test_no_collector_at_all(self):
        out = render_run_summary(None, _success_result(), poll_stats=lambda: None)
        assert "steps  (no step telemetry captured)" in out
        assert "nodes  KSampler 12.4s" in out

    def test_deterministic_for_fixed_inputs(self):
        snap = {"name": "RTX 4090", "used_gb": 9.8, "total_gb": 24.0}
        a = render_run_summary(self._collector(), _success_result(), poll_stats=lambda: snap)
        b = render_run_summary(self._collector(), _success_result(), poll_stats=lambda: snap)
        assert a == b

    def test_top_nodes_slice_respected(self):
        out = render_run_summary(
            self._collector(), _success_result(), poll_stats=lambda: None, top_nodes=1
        )
        assert "KSampler 12.4s" in out
        assert "VAEDecode" not in out
