"""Integration tests — concurrent session isolation and metrics under load."""

import copy
import json
import threading

import pytest

from agent._conn_ctx import _conn_session
from agent.metrics import Counter
from agent.tools import workflow_patch

pytestmark = pytest.mark.integration


@pytest.fixture()
def sample_workflow():
    """Minimal SD1.5 API-format workflow dict."""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "sd15.safetensors"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "seed": 42,
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler",
                "scheduler": "normal",
                "positive": ["3", 0],
                "negative": ["4", 0],
                "latent_image": ["5", 0],
                "denoise": 1.0,
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "a beautiful landscape", "clip": ["1", 1]},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "ugly, blurry", "clip": ["1", 1]},
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
        },
    }


class TestConcurrentSessions:
    """Verify per-connection session isolation under concurrent access."""

    def test_four_concurrent_sessions(
        self, comfyui_available, sample_workflow, tmp_path
    ):
        """4 threads, each with own session, load+patch differently, verify isolation."""
        errors: list[str] = []
        results: dict[int, int] = {}
        barrier = threading.Barrier(4, timeout=10)

        def worker(thread_idx: int) -> None:
            try:
                session_id = f"test_concurrent_{thread_idx}"
                _conn_session.set(session_id)

                # Write a unique workflow file per thread
                wf = copy.deepcopy(sample_workflow)
                wf_path = tmp_path / f"wf_{thread_idx}.json"
                wf_path.write_text(json.dumps(wf), encoding="utf-8")

                barrier.wait()

                # Load workflow into this session's state
                # Use workflow_patch.handle directly to bypass the gate
                # (gate requires an active session which is set up by MCP,
                # not by bare ContextVar assignment)
                load_result = json.loads(
                    workflow_patch.handle(
                        "apply_workflow_patch",
                        {
                            "path": str(wf_path),
                            "patches": [
                                {
                                    "op": "replace",
                                    "path": "/2/inputs/steps",
                                    "value": 20 + thread_idx * 10,
                                }
                            ],
                        },
                    )
                )
                if "error" in load_result:
                    errors.append(
                        f"Thread {thread_idx} load error: {load_result['error']}"
                    )
                    return

                # Read back and verify isolation
                wf_state = workflow_patch.get_current_workflow()
                if wf_state is None:
                    errors.append(f"Thread {thread_idx}: workflow is None")
                    return

                actual_steps = wf_state["2"]["inputs"]["steps"]
                expected_steps = 20 + thread_idx * 10
                if actual_steps != expected_steps:
                    errors.append(
                        f"Thread {thread_idx}: expected steps={expected_steps}, "
                        f"got {actual_steps}"
                    )
                    return
                results[thread_idx] = actual_steps
            except Exception as exc:
                errors.append(f"Thread {thread_idx} exception: {exc}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert not errors, f"Concurrent session errors: {errors}"
        assert len(results) == 4
        # Each thread should see its own unique steps value
        assert sorted(results.values()) == [20, 30, 40, 50]

    def test_metrics_under_concurrent_load(self):
        """4 threads each increment a counter 10 times; total should be 40."""
        counter = Counter("test_concurrent_counter", labels=["thread"])
        errors: list[str] = []
        barrier = threading.Barrier(4, timeout=10)

        def worker(thread_idx: int) -> None:
            try:
                barrier.wait()
                for _ in range(10):
                    counter.inc(thread=str(thread_idx))
            except Exception as exc:
                errors.append(f"Thread {thread_idx}: {exc}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert not errors, f"Metric errors: {errors}"

        snapshot = counter.get()
        total = sum(snapshot.values())
        assert total == 40, f"Expected 40 increments, got {total}"
