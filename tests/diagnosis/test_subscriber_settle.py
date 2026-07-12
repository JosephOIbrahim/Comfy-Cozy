"""The subscriber tolerates the window where ComfyUI has signalled completion but
not yet written /history (live-discovered race, 2026-07-12). Bounded retry,
fail-soft: a report that can't be resolved is dropped, never fabricated."""

import unittest.mock as mock

from agent.diagnosis import diagnosis as diag


class TestHistorySettleRetry:
    def test_retries_until_history_appears(self):
        pid = "abc-123"
        ready = {pid: {"prompt": [0, pid, {"3": {"class_type": "KSampler"}}], "status": {}}}
        responses = [{}, {}, ready]  # two empties (history not yet written), then the entry
        calls = []

        def fake_get(url, timeout=None):
            r = mock.Mock()
            r.json.return_value = responses[min(len(calls), len(responses) - 1)]
            calls.append(url)
            return r

        with mock.patch.object(diag.httpx, "get", side_effect=fake_get), \
             mock.patch.object(diag.time, "sleep") as slept:
            entry = diag._fetch_history_entry("http://x", pid)

        assert entry is not None and "prompt" in entry
        assert len(calls) == 3          # polled until it appeared
        assert slept.call_count == 2    # slept between the two empties, not after success

    def test_gives_up_gracefully_when_never_written(self):
        def fake_get(url, timeout=None):
            r = mock.Mock()
            r.json.return_value = {}
            return r

        with mock.patch.object(diag.httpx, "get", side_effect=fake_get), \
             mock.patch.object(diag.time, "sleep") as slept:
            entry = diag._fetch_history_entry("http://x", "never")

        assert entry is None
        assert slept.call_count == diag.HISTORY_SETTLE_RETRIES - 1  # bounded, no infinite loop

    def test_httpx_error_is_fail_soft(self):
        with mock.patch.object(diag.httpx, "get", side_effect=RuntimeError("conn refused")), \
             mock.patch.object(diag.time, "sleep"):
            assert diag._fetch_history_entry("http://x", "p") is None


class TestRunFactsFromHistory:
    """Duration/status come from ComfyUI's worker-side history timestamps, not the
    agent's clock (the ws event's elapsed_ms mixes epoch/monotonic — live bug 2026-07-12)."""

    def _event(self, is_error=False, data=None):
        return mock.Mock(is_error=is_error, data=data or {}, elapsed_ms=1.783e12)

    def test_success_duration_from_worker_timestamps(self):
        entry = {"status": {"status_str": "success", "messages": [
            ["execution_start", {"timestamp": 1783896403092}],
            ["execution_success", {"timestamp": 1783896457390}],
        ]}}
        status, dur, err = diag._run_facts_from_history(entry, self._event())
        assert status == "completed"
        assert dur == 54.30  # 54298 ms, NOT the event's 1.783e9 epoch-minus-monotonic garbage
        assert err == ""

    def test_error_status_and_text_from_history(self):
        entry = {"status": {"status_str": "error", "messages": [
            ["execution_start", {"timestamp": 1000}],
            ["execution_error", {"timestamp": 4400, "exception_type": "OutOfMemoryError",
                                 "exception_message": "CUDA out of memory"}],
        ]}}
        status, dur, err = diag._run_facts_from_history(entry, self._event(is_error=True))
        assert status == "error"
        assert dur == 3.4
        assert "OutOfMemoryError" in err and "CUDA out of memory" in err

    def test_missing_timing_falls_back_to_zero_not_garbage(self):
        entry = {"status": {"status_str": "success", "messages": []}}
        status, dur, err = diag._run_facts_from_history(entry, self._event())
        assert status == "completed"
        assert dur == 0.0  # honest 'unmeasured', never the clock-mixed event value

    def test_no_status_str_falls_back_to_event_is_error(self):
        entry = {"status": {"messages": []}}
        status, _, _ = diag._run_facts_from_history(entry, self._event(is_error=True))
        assert status == "error"
