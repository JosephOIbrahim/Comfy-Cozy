"""Tests for panel/server/chat.py — ConversationState, brain loading, agent runner."""

import queue
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("aiohttp", reason="panel tests require aiohttp")

# Ensure the checkout-only panel package is importable when the suite runs
# against an installed wheel (repo root is not on sys.path in importlib mode).
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from panel.server.chat import (  # noqa: E402
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
        """Exception in run_agent_turn emits 'error' but NEVER leaks the raw
        exception text into the client message (L-PANEL finding B).

        The internal detail must stay server-side (logged with exc_info); the
        bubble the browser renders is a generic, safe message.
        """
        conv = self._make_conv()
        msg_queue = queue.Queue()

        mock_run = MagicMock(side_effect=RuntimeError("API down /secret/path KeyError"))

        with patch("agent.main.run_agent_turn", mock_run), \
             patch("agent.queue_progress.QueueProgressReporter", MagicMock()):
            _run_agent_sync(conv, "hello", msg_queue)

        events = []
        while not msg_queue.empty():
            events.append(msg_queue.get_nowait())

        assert any(e["type"] == "error" for e in events)
        msg = [e for e in events if e["type"] == "error"][0]["message"]
        # the raw exception text must NOT reach the client
        assert "API down" not in msg
        assert "/secret/path" not in msg
        # the safe, contextual message is what the browser sees
        assert "agent turn" in msg and "server logs" in msg

    def test_provider_re_resolved_each_turn(self):
        """A model swap mid-conversation must reach the live stream.

        The loop resolves the provider per turn; a client captured once at
        brain load would keep streaming to the model the artist left.
        """
        conv = self._make_conv()
        msg_queue = queue.Queue()

        before_swap = MagicMock(name="provider-before-swap")
        after_swap = MagicMock(name="provider-after-swap")
        mock_get_provider = MagicMock(side_effect=[before_swap, after_swap])
        streamed_through = []

        def _side_effect(client, messages, system, **kwargs):
            streamed_through.append(client)
            return (messages, len(streamed_through) == 2)  # done on turn 2

        with patch("agent.llm.get_provider", mock_get_provider), \
             patch("agent.main.run_agent_turn", side_effect=_side_effect), \
             patch("agent.queue_progress.QueueProgressReporter", MagicMock()):
            _run_agent_sync(conv, "hello", msg_queue)

        assert mock_get_provider.call_count == 2
        assert streamed_through == [before_swap, after_swap]

    def test_stale_brain_client_is_never_streamed_through(self):
        """The module-global client from _ensure_brain() must not be used.

        get_provider() is the single source of truth once the loop is running —
        the global is the frozen instance a cross-provider swap cannot reach.
        """
        conv = self._make_conv()
        msg_queue = queue.Queue()

        stale_client = MagicMock(name="stale-brain-client")
        live_provider = MagicMock(name="live-provider")
        streamed_through = []

        def _side_effect(client, messages, system, **kwargs):
            streamed_through.append(client)
            return (messages, True)

        with patch("panel.server.chat._client", stale_client), \
             patch("agent.llm.get_provider", MagicMock(return_value=live_provider)), \
             patch("agent.main.run_agent_turn", side_effect=_side_effect), \
             patch("agent.queue_progress.QueueProgressReporter", MagicMock()):
            _run_agent_sync(conv, "hello", msg_queue)

        assert streamed_through == [live_provider]
        assert stale_client not in streamed_through

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
