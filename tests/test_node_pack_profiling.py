"""Tests for the Home A node pack's TimingCapture (#5 / P2.3).

The node pack lives at node_pack/comfy_agent_bridge/ (canonical source, vendored
into the repo). profiling.py is pure (no ComfyUI imports) and loaded here by path
so the capture logic has real committed coverage independent of a live server.
"""

import importlib.util
import pathlib

import pytest

_PROFILING = (
    pathlib.Path(__file__).resolve().parent.parent
    / "node_pack" / "comfy_agent_bridge" / "profiling.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("agent_bridge_profiling", _PROFILING)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def TimingCapture():
    return _load().TimingCapture


def _cap(TimingCapture, ticks):
    it = iter(ticks)
    return TimingCapture(lambda: next(it))


def test_durations_between_executing_events(TimingCapture):
    cap = _cap(TimingCapture, [1.0, 1.5, 3.5])
    cap.observe("execution_start", {"prompt_id": "p"})
    cap.observe("executing", {"prompt_id": "p", "node": "a"})   # t=1.0
    cap.observe("executing", {"prompt_id": "p", "node": "b"})   # t=1.5 -> a=500ms
    cap.observe("execution_success", {"prompt_id": "p"})        # t=3.5 -> b=2000ms
    nodes = {n["node_id"]: n for n in cap.profile("p")["nodes"]}
    assert nodes["a"]["duration_ms"] == 500.0
    assert nodes["b"]["duration_ms"] == 2000.0


def test_cached_nodes_recorded_zero_duration(TimingCapture):
    cap = _cap(TimingCapture, [1.0])
    cap.observe("execution_start", {"prompt_id": "p"})
    cap.observe("execution_cached", {"prompt_id": "p", "nodes": ["c1", "c2"]})
    nodes = {n["node_id"]: n for n in cap.profile("p")["nodes"]}
    assert nodes["c1"]["duration_ms"] == 0.0 and nodes["c1"]["cached"] is True
    assert nodes["c2"]["duration_ms"] == 0.0


def test_ordering_by_start(TimingCapture):
    cap = _cap(TimingCapture, [1.0, 1.5, 3.5])
    cap.observe("execution_start", {"prompt_id": "p"})
    cap.observe("execution_cached", {"prompt_id": "p", "nodes": ["z"]})  # start 0.0
    cap.observe("executing", {"prompt_id": "p", "node": "a"})
    cap.observe("executing", {"prompt_id": "p", "node": "b"})
    cap.observe("execution_success", {"prompt_id": "p"})
    order = [n["node_id"] for n in sorted(cap.profile("p")["nodes"], key=lambda n: n["start"])]
    assert order == ["z", "a", "b"]


def test_class_type_field_present(TimingCapture):
    cap = _cap(TimingCapture, [1.0, 2.0])
    cap.observe("executing", {"prompt_id": "p", "node": "a"})
    cap.observe("execution_success", {"prompt_id": "p"})
    assert "class_type" in cap.profile("p")["nodes"][0]


def test_unknown_prompt_returns_none(TimingCapture):
    cap = _cap(TimingCapture, [])
    assert cap.profile("never") is None


def test_non_dict_data_ignored(TimingCapture):
    cap = _cap(TimingCapture, [])
    cap.observe("executing", "not a dict")  # must not raise
    cap.observe("executing", None)
    assert cap.profile("p") is None


def test_missing_prompt_id_ignored(TimingCapture):
    cap = _cap(TimingCapture, [])
    cap.observe("executing", {"node": "a"})  # no prompt_id
    assert cap._profiles == {}


def test_ring_bounded(TimingCapture):
    cap = _cap(TimingCapture, [0.0] * 100)
    for i in range(50):
        cap.observe("execution_start", {"prompt_id": f"p{i}"})
    assert len(cap._profiles) <= 32


def test_execution_start_resets(TimingCapture):
    cap = _cap(TimingCapture, [1.0, 2.0, 5.0, 6.0])
    cap.observe("execution_start", {"prompt_id": "p"})
    cap.observe("executing", {"prompt_id": "p", "node": "a"})
    cap.observe("execution_success", {"prompt_id": "p"})
    cap.observe("execution_start", {"prompt_id": "p"})  # re-run same id
    cap.observe("executing", {"prompt_id": "p", "node": "b"})
    cap.observe("execution_success", {"prompt_id": "p"})
    ids = [n["node_id"] for n in cap.profile("p")["nodes"]]
    assert ids == ["b"]  # old "a" cleared
