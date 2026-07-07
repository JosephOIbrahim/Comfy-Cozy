"""Tests for the persisted model selection (agent/llm/_selection.py).

The panel "remembers" the last engine you picked: a swap can record its
selection to a small JSON file and boot can replay it. Best-effort — a bad
file never raises. Fully mocked; the selection path is redirected to a
per-test temp file by the ``_isolate_model_selection`` conftest fixture.
"""

from __future__ import annotations

from unittest.mock import patch

from agent.llm import _selection


# ---------------------------------------------------------------------------
# save / load round-trip + failure modes
# ---------------------------------------------------------------------------


class TestSaveLoad:
    def test_round_trips_provider_and_model(self):
        _selection.save_selection("anthropic", "claude-opus-4-7")
        loaded = _selection.load_selection()
        assert loaded is not None
        assert loaded["provider"] == "anthropic"
        assert loaded["model"] == "claude-opus-4-7"

    def test_round_trips_vision_model(self):
        _selection.save_selection("openai", "gpt-4o", vision_model="claude-opus-4-7")
        loaded = _selection.load_selection()
        assert loaded["vision_model"] == "claude-opus-4-7"

    def test_load_missing_returns_none(self):
        # Fresh per-test path — nothing written yet.
        assert _selection.load_selection() is None

    def test_load_corrupt_returns_none(self):
        path = _selection._selection_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\x00\x01 not json {{{ garbage")
        assert _selection.load_selection() is None  # degrades, never raises

    def test_load_valid_json_but_not_object_returns_none(self):
        # Valid JSON that isn't a dict (e.g. a bare number or list) must degrade
        # to None so apply_saved_selection never .get()s on a non-dict.
        path = _selection._selection_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("42", encoding="utf-8")
        assert _selection.load_selection() is None
        path.write_text("[1, 2, 3]", encoding="utf-8")
        assert _selection.load_selection() is None

    def test_save_creates_parent_dir(self, tmp_path, monkeypatch):
        nested = tmp_path / "a" / "b" / "model_selection.json"
        monkeypatch.setenv("MODEL_SELECTION_PATH", str(nested))
        assert not nested.parent.exists()

        _selection.save_selection("openai", "gpt-4o")

        assert nested.exists()
        # atomic write leaves no temp turd behind
        assert not nested.with_name(nested.name + ".tmp").exists()
        assert _selection.load_selection()["provider"] == "openai"

    def test_clear_selection_removes_file(self):
        _selection.save_selection("openai", "gpt-4o")
        path = _selection._selection_path()
        assert path.exists()
        _selection.clear_selection()
        assert not path.exists()

    def test_clear_selection_missing_is_noop(self):
        # No file present — must not raise.
        _selection.clear_selection()
        assert _selection.load_selection() is None


# ---------------------------------------------------------------------------
# apply_saved_selection — replay via swap, best-effort
# ---------------------------------------------------------------------------


class TestApplySavedSelection:
    def test_applies_via_swap_without_persist_or_probe(self):
        _selection.save_selection("openai", "gpt-4o")
        # _selection lazily does `from .swap import swap`, so patch the source.
        with patch("agent.llm.swap.swap") as mock_swap:
            result = _selection.apply_saved_selection()

        mock_swap.assert_called_once()
        kwargs = mock_swap.call_args.kwargs
        assert kwargs["provider"] == "openai"
        assert kwargs["model"] == "gpt-4o"
        assert kwargs["persist"] is False  # don't re-write what we just read
        assert kwargs["probe"] is False  # boot must not make a live call
        assert result == {"provider": "openai", "model": "gpt-4o"}

    def test_no_file_returns_none_and_does_not_swap(self):
        with patch("agent.llm.swap.swap") as mock_swap:
            assert _selection.apply_saved_selection() is None
        mock_swap.assert_not_called()

    def test_swap_failure_returns_none(self):
        _selection.save_selection("openai", "gpt-4o")
        with patch("agent.llm.swap.swap", side_effect=RuntimeError("bad key")):
            # boot must survive a stale/broken saved selection.
            assert _selection.apply_saved_selection() is None
