"""Moneta end-to-end — subprocess round-trip through outbox/inbox.

Spawns a child Python process acting as a fake Moneta consumer. The child
tails the outbox JSONL files, and for each `write` event whose attr_name
matches a known trigger ("ping"), writes a delta file into the inbox.
The parent stage's MonetaAdapter then ingests that delta and applies it.

This validates the bidirectional integration story under realistic
transport (separate processes, real filesystem) — the unit tests in
`test_cozy_persistence.py::TestMonetaAdapter` only exercise the adapter
within a single process.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

import pytest

pxr = pytest.importorskip("pxr", reason="usd-core not installed")

from agent.integrations.moneta import (  # noqa: E402
    MonetaAdapter,
    MonetaAdapterConfig,
)
from agent.stage.cognitive_stage import CognitiveWorkflowStage  # noqa: E402

pytestmark = pytest.mark.integration


def test_round_trip_through_subprocess_consumer(tmp_path):
    outbox = tmp_path / "outbox"
    inbox = tmp_path / "inbox"
    outbox.mkdir()
    inbox.mkdir()
    ready_marker = tmp_path / "child_ready"

    # The fake-Moneta script runs in a subprocess. It tails the outbox
    # directory for JSONL files, parses each line, and for every write
    # event whose attr_name == "ping", writes a delta file into the inbox
    # producing a "pong" attribute on the same prim. The pong value is
    # hardcoded "received" because the StageEvent for writes doesn't
    # include the original value in its payload (by design — see
    # cognitive_stage.py:_emit construction). Round-trip is verified by
    # the parent observing the pong attribute, not by value preservation.
    child_script = f"""
import json, time
from pathlib import Path

OUTBOX = Path({str(outbox)!r})
INBOX = Path({str(inbox)!r})
READY = Path({str(ready_marker)!r})

offsets = {{}}
emitted = 0
READY.write_text("ready", encoding="utf-8")

while True:
    for jsonl_path in sorted(OUTBOX.glob("stage-events-*.jsonl")):
        last_offset = offsets.get(str(jsonl_path), 0)
        try:
            with open(jsonl_path, "r", encoding="utf-8") as f:
                f.seek(last_offset)
                for raw_line in f:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("op") != "write":
                        continue
                    if record.get("attr_name") != "ping":
                        continue
                    prim_path = record.get("prim_path")
                    if prim_path is None:
                        continue
                    delta_file = INBOX / f"echo_{{emitted:04d}}.delta.json"
                    delta_file.write_text(json.dumps({{
                        "agent_name": "moneta_echo",
                        "delta": {{f"{{prim_path}}:pong": "received"}},
                    }}), encoding="utf-8")
                    emitted += 1
                offsets[str(jsonl_path)] = f.tell()
        except FileNotFoundError:
            continue
    time.sleep(0.05)
"""

    # Start the parent-side adapter BEFORE spawning the child so the
    # outbox file exists / has a chance to be written to as soon as we
    # write our first prim.
    cws = CognitiveWorkflowStage()
    config = MonetaAdapterConfig(
        outbox_dir=outbox,
        inbox_dir=inbox,
        poll_interval_seconds=0.05,
    )
    adapter = MonetaAdapter(config, cws)
    adapter.start()

    proc = subprocess.Popen(
        [sys.executable, "-c", child_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    try:
        # Wait for the child to signal ready.
        deadline = time.time() + 10.0
        while time.time() < deadline and not ready_marker.exists():
            if proc.poll() is not None:
                out, err = proc.communicate(timeout=1.0)
                pytest.fail(
                    f"echo subprocess died early: rc={proc.returncode}\n"
                    f"stderr: {err.decode(errors='replace')!r}"
                )
            time.sleep(0.05)
        assert ready_marker.exists(), "echo subprocess never started"

        # Parent writes the trigger prim. The MonetaAdapter emits a JSONL
        # record into the outbox; the child sees attr_name == "ping" and
        # writes back a delta marking pong = "received". The adapter then
        # ingests that delta and applies it to the parent stage.
        cws.write("/workflows/test", "ping", "hello")

        # Poll the parent stage waiting for the echoed pong to land.
        deadline = time.time() + 10.0
        pong = None
        while time.time() < deadline:
            pong = cws.read("/workflows/test", "pong")
            if pong is not None:
                break
            if proc.poll() is not None:
                out, err = proc.communicate(timeout=1.0)
                pytest.fail(
                    f"echo subprocess died waiting for pong: "
                    f"rc={proc.returncode}\n"
                    f"stderr: {err.decode(errors='replace')!r}"
                )
            time.sleep(0.1)

        assert pong == "received", (
            f"expected pong='received', got {pong!r}; "
            f"events_emitted={adapter.events_emitted}, "
            f"deltas_ingested={adapter.deltas_ingested}, "
            f"ingest_failures={adapter.ingest_failures}"
        )

        # The adapter saw at least one outbound + one inbound event
        assert adapter.events_emitted >= 1
        assert adapter.deltas_ingested >= 1
    finally:
        # Cleanup — kill the subprocess and stop the adapter.
        if proc.poll() is None:
            os.kill(proc.pid, signal.SIGKILL)
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
        adapter.stop()
        cws.close_subscribers()
