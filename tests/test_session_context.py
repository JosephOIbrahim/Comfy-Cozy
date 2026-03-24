"""Tests for SessionContext and SessionRegistry."""

import time

from agent.session_context import (
    SessionContext,
    SessionRegistry,
    get_registry,
    get_session_context,
)


class TestSessionContext:
    """Tests for the SessionContext dataclass."""

    def test_create_default(self):
        ctx = SessionContext(session_id="test-1")
        assert ctx.session_id == "test-1"
        assert ctx.workflow is not None
        assert ctx.workflow.session_id == "test-1"
        assert ctx.intent_state == {}
        assert ctx.iteration_state == {}
        assert ctx.demo_state == {}
        assert ctx.orchestrator_tasks == {}

    def test_workflow_session_auto_created(self):
        ctx = SessionContext(session_id="auto")
        assert ctx.workflow["current_workflow"] is None
        assert ctx.workflow["loaded_path"] is None

    def test_touch_updates_activity(self):
        ctx = SessionContext(session_id="touch")
        old_activity = ctx.last_activity
        time.sleep(0.01)
        ctx.touch()
        assert ctx.last_activity > old_activity

    def test_age_seconds(self):
        ctx = SessionContext(session_id="age")
        ctx.last_activity = time.time() - 10
        assert ctx.age_seconds() >= 10

    def test_isolated_workflow_state(self):
        """Two SessionContexts have independent workflow state."""
        ctx_a = SessionContext(session_id="a")
        ctx_b = SessionContext(session_id="b")

        ctx_a.workflow["current_workflow"] = {"nodes": "a"}
        ctx_b.workflow["current_workflow"] = {"nodes": "b"}

        assert ctx_a.workflow["current_workflow"] == {"nodes": "a"}
        assert ctx_b.workflow["current_workflow"] == {"nodes": "b"}

    def test_isolated_intent_state(self):
        """Two SessionContexts have independent intent state."""
        ctx_a = SessionContext(session_id="a")
        ctx_b = SessionContext(session_id="b")

        ctx_a.intent_state["foo"] = 1
        assert "foo" not in ctx_b.intent_state


class TestSessionRegistry:
    """Tests for the SessionRegistry."""

    def test_get_or_create(self):
        reg = SessionRegistry()
        ctx = reg.get_or_create("s1")
        assert ctx.session_id == "s1"

    def test_get_or_create_returns_same(self):
        reg = SessionRegistry()
        ctx1 = reg.get_or_create("s1")
        ctx2 = reg.get_or_create("s1")
        assert ctx1 is ctx2

    def test_get_returns_none_for_missing(self):
        reg = SessionRegistry()
        assert reg.get("nonexistent") is None

    def test_get_returns_existing(self):
        reg = SessionRegistry()
        reg.get_or_create("s1")
        ctx = reg.get("s1")
        assert ctx is not None
        assert ctx.session_id == "s1"

    def test_destroy(self):
        reg = SessionRegistry()
        reg.get_or_create("s1")
        assert reg.destroy("s1") is True
        assert reg.get("s1") is None
        assert reg.destroy("s1") is False

    def test_list_sessions(self):
        reg = SessionRegistry()
        reg.get_or_create("a")
        reg.get_or_create("b")
        sessions = reg.list_sessions()
        assert set(sessions) == {"a", "b"}

    def test_count(self):
        reg = SessionRegistry()
        assert reg.count == 0
        reg.get_or_create("a")
        assert reg.count == 1
        reg.get_or_create("b")
        assert reg.count == 2

    def test_clear(self):
        reg = SessionRegistry()
        reg.get_or_create("a")
        reg.clear()
        assert reg.count == 0

    def test_gc_stale_removes_old(self):
        reg = SessionRegistry()
        ctx = reg.get_or_create("old")
        ctx.last_activity = time.time() - 7200  # 2 hours ago
        reg.get_or_create("fresh")  # just created
        removed = reg.gc_stale(max_age_seconds=3600)
        assert removed == 1
        assert reg.get("old") is None
        assert reg.get("fresh") is not None

    def test_gc_stale_never_removes_default(self):
        reg = SessionRegistry()
        ctx = reg.get_or_create("default")
        ctx.last_activity = time.time() - 99999
        removed = reg.gc_stale(max_age_seconds=1)
        assert removed == 0
        assert reg.get("default") is not None

    def test_session_isolation_through_registry(self):
        """Sessions created through the registry are fully isolated."""
        reg = SessionRegistry()
        ctx_a = reg.get_or_create("a")
        ctx_b = reg.get_or_create("b")

        ctx_a.workflow["current_workflow"] = {"test": "a"}
        assert ctx_b.workflow["current_workflow"] is None


class TestGlobalAccessors:
    """Tests for module-level convenience functions."""

    def test_get_session_context(self):
        ctx = get_session_context("global-test")
        assert ctx.session_id == "global-test"
        # Clean up
        get_registry().destroy("global-test")

    def test_get_registry(self):
        reg = get_registry()
        assert isinstance(reg, SessionRegistry)
