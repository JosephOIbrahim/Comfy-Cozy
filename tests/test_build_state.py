"""Build identity module — on-disk state memo under concurrent load.

``on_disk_state()`` runs two git subprocesses on a memo miss and is called once
per manifest request. The /agent/capabilities route serves those off an executor
thread pool, so simultaneous misses are ordinary traffic, not a thought
experiment: without an in-flight guard the fan-out is 2 subprocesses per
concurrent caller. These tests pin the refresh to exactly one git pair per miss
window, the lock-free fast path, and the (None, None) no-git degradation.
"""

import threading

import pytest

from agent import _build


@pytest.fixture(autouse=True)
def clear_memo():
    """on_disk_state caches in a module global — isolate every test from it."""
    saved = _build._on_disk_memo
    _build._on_disk_memo = None
    yield
    _build._on_disk_memo = saved


class _CountingGit:
    """Stand-in for _build._git that records calls and is slow enough to overlap."""

    def __init__(self, result="stub", delay=0.05):
        self.calls = []
        self._result = result
        self._delay = delay
        self._lock = threading.Lock()

    def __call__(self, *args):
        with self._lock:
            self.calls.append(args)
        if self._delay:
            threading.Event().wait(self._delay)
        return self._result


class TestConcurrentRefresh:
    def test_simultaneous_misses_run_git_once(self, monkeypatch):
        threads = 8
        fake = _CountingGit()
        monkeypatch.setattr(_build, "_git", fake)

        gate = threading.Barrier(threads)
        results = [None] * threads

        def worker(index):
            gate.wait()
            results[index] = _build.on_disk_state()

        workers = [threading.Thread(target=worker, args=(i,)) for i in range(threads)]
        for w in workers:
            w.start()
        for w in workers:
            w.join(timeout=10)
            assert not w.is_alive()

        # One branch lookup + one HEAD lookup for the whole burst, not 2 per caller.
        assert len(fake.calls) == 2, fake.calls
        assert all(r == ("stub", "stub") for r in results)

    def test_fast_path_skips_git_entirely(self, monkeypatch):
        fake = _CountingGit(delay=0)
        monkeypatch.setattr(_build, "_git", fake)

        first = _build.on_disk_state()
        assert len(fake.calls) == 2

        for _ in range(5):
            assert _build.on_disk_state() == first
        assert len(fake.calls) == 2

    def test_stale_memo_refreshes(self, monkeypatch):
        fake = _CountingGit(delay=0)
        monkeypatch.setattr(_build, "_git", fake)

        _build.on_disk_state()
        stamp, branch, head = _build._on_disk_memo
        _build._on_disk_memo = (stamp - _build._ON_DISK_TTL_S - 1.0, branch, head)

        _build.on_disk_state()
        assert len(fake.calls) == 4


class TestNoGit:
    def test_degrades_to_unknown(self, monkeypatch):
        monkeypatch.setattr(_build, "_git", lambda *args: None)
        assert _build.on_disk_state() == (None, None)

    def test_unknown_is_memoized_not_retried(self, monkeypatch):
        fake = _CountingGit(result=None, delay=0)
        monkeypatch.setattr(_build, "_git", fake)

        assert _build.on_disk_state() == (None, None)
        assert _build.on_disk_state() == (None, None)
        assert len(fake.calls) == 2
