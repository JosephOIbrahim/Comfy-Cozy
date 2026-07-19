"""Registry degradation is recorded ONCE, not once per tool dispatch.

`handle()` calls `_ensure_brain()` on every dispatch. When the brain layer
cannot import (a missing optional dep under the ComfyUI python is the common
case) that failure has to be remembered, or the retry re-appends the same
record to `_DEGRADED` forever and the capability manifest payload grows
without bound. All mocked: the brain import is forced to fail in-process.
"""

import json
import sys
import types

import pytest

import agent.tools as T


class _BoomBrain(types.ModuleType):
    """Stand-in for `agent.brain` whose ALL_BRAIN_TOOLS access always raises.

    Counts accesses so a test can prove the failing import is attempted once
    per process rather than once per dispatch.
    """

    def __init__(self):
        super().__init__("agent.brain")
        self.attempts = 0

    def __getattr__(self, item):
        if item == "ALL_BRAIN_TOOLS":
            self.attempts += 1
            raise RuntimeError("brain layer boom")
        raise AttributeError(item)


@pytest.fixture
def broken_brain(monkeypatch):
    """Force the brain import to fail, isolating every module-level flag.

    Stage is resolved BEFORE the snapshot so its own (real) import results
    are not mistaken for growth caused by the brain retry.
    """
    T._ensure_stage()

    saved_degraded = list(T._DEGRADED)
    saved_loaded = T._brain_loaded
    saved_failed = getattr(T, "_brain_failed", False)
    saved_names = set(T._BRAIN_TOOL_NAMES)

    monkeypatch.setattr("agent.config.BRAIN_ENABLED", True)
    boom = _BoomBrain()
    monkeypatch.setitem(sys.modules, "agent.brain", boom)

    T._DEGRADED.clear()
    T._brain_loaded = False
    T._brain_failed = False
    T._BRAIN_TOOL_NAMES.clear()

    yield boom

    T._DEGRADED[:] = saved_degraded
    T._brain_loaded = saved_loaded
    T._brain_failed = saved_failed
    T._BRAIN_TOOL_NAMES.clear()
    T._BRAIN_TOOL_NAMES.update(saved_names)


class TestBrainFailureRecordedOnce:
    def test_repeated_ensure_brain_appends_one_entry(self, broken_brain):
        for _ in range(5):
            T._ensure_brain()

        assert len(T._DEGRADED) == 1

    def test_failing_import_is_not_retried_per_call(self, broken_brain):
        for _ in range(5):
            T._ensure_brain()

        assert broken_brain.attempts == 1

    def test_entry_shape(self, broken_brain):
        T._ensure_brain()

        entry = T._DEGRADED[0]
        assert entry["module"] == "brain"
        assert entry["layer"] == "brain"
        assert entry["error"] == "RuntimeError: brain layer boom"

    def test_dispatch_does_not_grow_the_degraded_list(self, broken_brain):
        for _ in range(10):
            T.handle("cozy_no_such_tool_at_all", {})

        assert len(T._DEGRADED) == 1

    def test_dispatch_still_answers_when_brain_is_down(self, broken_brain):
        parsed = json.loads(T.handle("cozy_no_such_tool_at_all", {}))

        assert "error" in parsed


class TestStageFailureRecordedOnce:
    def test_stage_module_recorded_once_across_reentry(self, monkeypatch):
        """Every stage import failing twice over still leaves one record each."""
        saved_degraded = list(T._DEGRADED)
        saved_loaded = T._stage_loaded

        def _boom(name, package=None):
            raise ModuleNotFoundError("No module named 'pxr'")

        monkeypatch.setattr(T.importlib, "import_module", _boom)
        T._DEGRADED.clear()
        try:
            T._stage_loaded = False
            T._ensure_stage()
            first = len(T._DEGRADED)

            T._stage_loaded = False
            T._ensure_stage()

            assert first == len(T._STAGE_MODULE_NAMES)
            assert len(T._DEGRADED) == first
        finally:
            T._DEGRADED[:] = saved_degraded
            T._stage_loaded = saved_loaded
