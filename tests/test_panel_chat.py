"""Tests for panel/server/chat.py — ConversationState, brain loading, agent runner."""

import queue
import threading
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("aiohttp", reason="panel tests require aiohttp")

from panel.server.chat import (
    ConversationState,
    _conversations,
    _MAX_WS_CONNECTIONS,
    _run_agent_sync,
)


# ---------------------------------------------------------------------------
# ConversationState
# ---------------------------------------------------------------------------

class TestConversationState:
    def test_unique_ids(self):
        a, b = ConversationState(), ConversationState()
        assert a.id != b.id

    def test_initial_state(self):
        conv = ConversationState()
        assert conv.messages == []
        assert conv.busy is False
        assert conv.system_prompt is None
        assert conv.workflow_summary is None
        assert conv.missing_nodes is None
        assert conv._workflow_hash is None

    def test_cancelled_event_starts_unset(self):
        """cancelled must start clear — agent thread should run initially."""
        conv = ConversationState()
        assert not conv.cancelled.is_set()

    def test_cancelled_event_can_be_set(self):
        """Setting cancelled prevents further agent turns."""
        conv = ConversationState()
        conv.cancelled.set()
        assert conv.cancelled.is_set()

    def test_has_lock(self):
        conv = ConversationState()
        assert isinstance(conv.lock, type(threading.Lock()))


# ---------------------------------------------------------------------------
# _run_agent_sync — cancellation and turn limits
# ---------------------------------------------------------------------------

class TestRunAgentSync:
    def _make_conv(self) -> ConversationState:
        conv = ConversationState()
        conv.system_prompt = "test system"
        return conv

    def _run_and_collect(self, conv, text="hello", extra_patches=None):
        """Run _run_agent_sync with mocked agent, collect queue events."""
        msg_queue = queue.Queue()
        patches = {
            "panel.server.chat._client": MagicMock(),
            "panel.server.chat.run_agent_turn": None,  # set per test
        }
        if extra_patches:
            patches.update(extra_patches)
        return msg_queue, patches

    def test_cancelled_before_first_turn_returns_immediately(self):
        """If cancelled before first turn, no agent calls made."""
        conv = self._make_conv()
        conv.cancelled.set()

        msg_queue = queue.Queue()
        mock_run = MagicMock()

        with patch("panel.server.chat._client", MagicMock()), \
             patch("agent.main.run_agent_turn", mock_run), \
             patch("agent.queue_progress.QueueProgressReporter", MagicMock()):
            _run_agent_sync(conv, "test", msg_queue)

        mock_run.assert_not_called()
        assert msg_queue.empty()  # No events — returned silently

    def test_done_after_single_successful_turn(self):
        """Single completed turn puts 'done' in queue."""
        conv = self._make_conv()
        msg_queue = queue.Queue()

        mock_run = MagicMock(return_value=([], True))  # done=True

        with patch("agent.main.run_agent_turn", mock_run), \
             patch("agent.queue_progress.QueueProgressReporter", MagicMock()):
            _run_agent_sync(conv, "hello", msg_queue)

        events = []
        while not msg_queue.empty():
            events.append(msg_queue.get_nowait())

        assert any(e["type"] == "done" for e in events)

    def test_error_on_turn_exception(self):
        """Exception in run_agent_turn puts 'error' in queue and returns."""
        conv = self._make_conv()
        msg_queue = queue.Queue()

        mock_run = MagicMock(side_effect=RuntimeError("API down"))

        with patch("agent.main.run_agent_turn", mock_run), \
             patch("agent.queue_progress.QueueProgressReporter", MagicMock()):
            _run_agent_sync(conv, "hello", msg_queue)

        events = []
        while not msg_queue.empty():
            events.append(msg_queue.get_nowait())

        assert any(e["type"] == "error" for e in events)
        error_events = [e for e in events if e["type"] == "error"]
        assert "API down" in error_events[0]["message"]

    def test_cancellation_stops_turns_between_iterations(self):
        """Cancelling mid-run stops at the next inter-turn check."""
        conv = self._make_conv()
        msg_queue = queue.Queue()
        call_count = 0

        def _side_effect(client, messages, system, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                conv.cancelled.set()  # Cancel after first turn
            return (messages, False)  # done=False → would continue

        with patch("agent.main.run_agent_turn", side_effect=_side_effect), \
             patch("agent.queue_progress.QueueProgressReporter", MagicMock()):
            _run_agent_sync(conv, "hello", msg_queue)

        # Only one turn should have run — cancellation stops the second
        assert call_count == 1


# ---------------------------------------------------------------------------
# _conversations registry
# ---------------------------------------------------------------------------

class TestConversationsRegistry:
    def setup_method(self):
        """Snapshot registry and restore after each test."""
        self._snapshot = dict(_conversations)

    def teardown_method(self):
        _conversations.clear()
        _conversations.update(self._snapshot)

    def test_max_connections_constant(self):
        assert _MAX_WS_CONNECTIONS == 20

    def test_conversation_id_is_string(self):
        conv = ConversationState()
        assert isinstance(conv.id, str)
        assert len(conv.id) > 0

    def test_registry_stores_and_removes(self):
        conv = ConversationState()
        _conversations[conv.id] = conv
        assert conv.id in _conversations
        _conversations.pop(conv.id, None)
        assert conv.id not in _conversations
