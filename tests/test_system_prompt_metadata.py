"""Tests for metadata injection into system prompt during session resume."""

import json
from unittest.mock import patch

from agent.system_prompt import build_system_prompt


# ---------------------------------------------------------------------------
# TestSystemPromptMetadata
# ---------------------------------------------------------------------------

class TestSystemPromptMetadata:
    def test_prompt_includes_last_output_context(self):
        """session_context with last_output_path injects 'Last Output Context'."""
        reconstruct_result = json.dumps({
            "has_context": True,
            "summary": "Generated with dreamshaper at 512x512.",
            "context": {
                "schema_version": 1,
                "intent": {
                    "what_artist_wanted": "A dreamy landscape",
                    "how_agent_interpreted": "Lower CFG, softer sampler",
                },
                "session": {
                    "key_params": {"model": "dreamshaper_8", "cfg": 5.0},
                },
            },
        })

        session_ctx = {
            "last_output_path": "G:/COMFYUI_Database/output/test.png",
        }

        with patch("agent.tools.handle", return_value=reconstruct_result):
            prompt = build_system_prompt(session_context=session_ctx)

        assert "Last Output Context" in prompt

    def test_prompt_no_metadata_when_no_path(self):
        """session_context without last_output_path has no 'Last Output Context'."""
        session_ctx = {"name": "test_session"}

        with patch("agent.tools.handle"):
            prompt = build_system_prompt(session_context=session_ctx)

        assert "Last Output Context" not in prompt

    def test_prompt_metadata_failure_silent(self):
        """If reconstruct_context raises, prompt builds normally."""
        session_ctx = {
            "last_output_path": "G:/COMFYUI_Database/output/test.png",
        }

        with patch("agent.tools.handle", side_effect=Exception("Disk error")):
            prompt = build_system_prompt(session_context=session_ctx)

        # Should build without crashing
        assert "ComfyUI co-pilot" in prompt
        assert "Last Output Context" not in prompt

    def test_prompt_metadata_shows_intent(self):
        """When metadata has intent, prompt includes 'Artist wanted' text."""
        reconstruct_result = json.dumps({
            "has_context": True,
            "summary": "Generated with model at 512x512.",
            "context": {
                "schema_version": 1,
                "intent": {
                    "what_artist_wanted": "Dramatic cinematic lighting",
                    "how_agent_interpreted": "Add rim light, increase contrast",
                },
                "session": {
                    "key_params": {"model": "sd15", "cfg": 7.0},
                },
            },
        })

        session_ctx = {
            "last_output_path": "G:/COMFYUI_Database/output/test.png",
        }

        with patch("agent.tools.handle", return_value=reconstruct_result):
            prompt = build_system_prompt(session_context=session_ctx)

        assert "Artist wanted" in prompt
        assert "Dramatic cinematic lighting" in prompt
