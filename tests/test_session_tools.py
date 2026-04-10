"""Tests for session_tools — add_note empty validation and session operations."""

import json
import pytest
from unittest.mock import patch

from agent.tools import session_tools


# ---------------------------------------------------------------------------
# Cycle 30: empty/null note validation tests
# ---------------------------------------------------------------------------

class TestAddNoteValidation:
    """_handle_add_note must reject empty or whitespace-only notes."""

    def _call_add_note(self, note, session_name="test-session", note_type="observation"):
        return json.loads(session_tools.handle("add_note", {
            "session_name": session_name,
            "note": note,
            "note_type": note_type,
        }))

    def test_empty_string_note_rejected(self):
        """add_note with empty string must return error."""
        result = self._call_add_note("")
        assert "error" in result
        assert "empty" in result["error"].lower()

    def test_whitespace_only_note_rejected(self):
        """add_note with whitespace-only string must return error."""
        result = self._call_add_note("   ")
        assert "error" in result
        assert "empty" in result["error"].lower()

    def test_tab_only_note_rejected(self):
        """add_note with tab-only string must return error."""
        result = self._call_add_note("\t\n\r")
        assert "error" in result

    def test_valid_note_passes_validation(self):
        """add_note with valid text must pass the empty-check (may fail on I/O, not validation)."""
        with patch("agent.tools.session_tools.add_note") as mock_add:
            mock_add.return_value = {"saved": True, "session": "test-session"}
            result = self._call_add_note("This is a valid note about the workflow.")
        # Must not return an "empty" error
        assert "error" not in result or "empty" not in result.get("error", "")

    def test_single_char_note_passes_validation(self):
        """A single non-whitespace character is a valid note."""
        with patch("agent.tools.session_tools.add_note") as mock_add:
            mock_add.return_value = {"saved": True}
            result = self._call_add_note("x")
        assert "error" not in result or "empty" not in result.get("error", "")

    def test_unknown_tool_returns_error(self):
        """Unknown tool name must return error, not crash."""
        result = json.loads(session_tools.handle("nonexistent_tool", {}))
        assert "error" in result
