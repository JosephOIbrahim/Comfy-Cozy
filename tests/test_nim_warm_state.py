"""C-R10b warm-state durability tests for record_warm_state (nim_lifecycle).

Covers the lost-update race, age-based pruning, read-failure-must-not-wipe,
fsync durability, and garbage-line cleanup. _STATE_PATH resolves at import
time, so tests patch the module attribute (never the env var).
"""
import json
import os
import threading
import time

import pytest

pytest.importorskip("agent.tools.nim_lifecycle")

import agent.tools.nim_lifecycle as nl


def _lines(path):
    return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


# --- (a) concurrent writers: both records survive (lost-update regression) --
def test_concurrent_writes_keep_all_records(tmp_path, monkeypatch):
    state = tmp_path / "warm.jsonl"
    monkeypatch.setattr(nl, "_STATE_PATH", state)
    n_threads, n_iters = 2, 20
    barrier = threading.Barrier(n_threads)

    def writer(tag):
        barrier.wait()
        for i in range(n_iters):
            nl.record_warm_state("flux-dev", host=f"h-{tag}", seq=i)

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    records = [json.loads(ln) for ln in _lines(state)]
    assert len(records) == n_threads * n_iters
    for tag in range(n_threads):
        seqs = sorted(r["seq"] for r in records if r["host"] == f"h-{tag}")
        assert seqs == list(range(n_iters))


# --- (b) records older than WARM_MAX_AGE_S are pruned; fresh survive --------
def test_stale_records_pruned_on_write(tmp_path, monkeypatch):
    state = tmp_path / "warm.jsonl"
    monkeypatch.setattr(nl, "_STATE_PATH", state)
    now = time.time()
    old = {"model": "flux-dev", "host": "old-host", "ts": now - nl.WARM_MAX_AGE_S - 100}
    fresh = {"model": "flux-dev", "host": "fresh-host", "ts": now - 10}
    state.write_text(
        json.dumps(old) + "\n" + json.dumps(fresh) + "\n", encoding="utf-8"
    )

    nl.record_warm_state("flux-dev", host="new-host")

    hosts = {json.loads(ln)["host"] for ln in _lines(state)}
    assert hosts == {"fresh-host", "new-host"}


# --- (c) unreadable file: raise, do NOT truncate history --------------------
def test_read_failure_raises_and_preserves_file(tmp_path, monkeypatch):
    state = tmp_path / "warm.jsonl"
    original = json.dumps({"model": "flux-dev", "host": "h", "ts": time.time()}) + "\n"
    state.write_text(original, encoding="utf-8")

    class _RaisingPath:
        """Path stand-in whose open() raises, simulating a transient I/O error."""

        def __init__(self, real):
            self._real = real

        @property
        def parent(self):
            return self._real.parent

        def exists(self):
            return self._real.exists()

        def open(self, *args, **kwargs):
            raise OSError("transient read glitch")

    monkeypatch.setattr(nl, "_STATE_PATH", _RaisingPath(state))
    with pytest.raises(OSError, match="transient read glitch"):
        nl.record_warm_state("flux-dev")
    assert state.read_text(encoding="utf-8") == original


# --- (d) os.fsync is called before os.replace (durability spy) --------------
def test_fsync_called_during_write(tmp_path, monkeypatch):
    state = tmp_path / "warm.jsonl"
    monkeypatch.setattr(nl, "_STATE_PATH", state)
    calls = []
    real_fsync = os.fsync

    def spy(fd):
        calls.append(fd)
        return real_fsync(fd)

    monkeypatch.setattr(nl.os, "fsync", spy)
    nl.record_warm_state("flux-dev", host="h")
    assert calls, "os.fsync was not called during the warm-state write"
    assert _lines(state)  # the write still landed


# --- (e) garbage lines dropped on rewrite; valid lines kept -----------------
def test_garbage_line_dropped_valid_kept(tmp_path, monkeypatch):
    state = tmp_path / "warm.jsonl"
    monkeypatch.setattr(nl, "_STATE_PATH", state)
    valid = {"model": "flux-dev", "host": "keep-me", "ts": time.time() - 5}
    state.write_text(
        "{not json at all\n" + json.dumps(valid) + "\n", encoding="utf-8"
    )

    nl.record_warm_state("flux-dev", host="new-host")

    lines = _lines(state)
    parsed = [json.loads(ln) for ln in lines]  # every line parses post-rewrite
    assert {r["host"] for r in parsed} == {"keep-me", "new-host"}
    assert len(lines) == 2
