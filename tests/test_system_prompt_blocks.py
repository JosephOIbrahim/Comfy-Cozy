"""Tests for build_system_prompt_blocks (multi-tier prompt-cache layout).

The function returns up to three system blocks:
  1. stable prefix (cached, ephemeral)
  2. topical knowledge (cached, ephemeral, only when knowledge matches)
  3. volatile session context (uncached, only when session_context given)

These tests pin:
- the block-count shape across input combinations
- cache_control placement (must be on stable + topical, never on volatile)
- deterministic payload across re-invocation (so cache breakpoints hit)
- the stable block is invariant to session_context (otherwise the breakpoint
  is useless — Action 1 finding C2 from the inside-out branch review).
"""

from __future__ import annotations

from unittest.mock import patch

from agent.system_prompt import build_system_prompt_blocks


class TestBuildSystemPromptBlocksShape:
    """Block count varies based on which inputs are populated."""

    def test_returns_only_stable_block_when_no_session_and_no_knowledge(self):
        with patch(
            "agent.system_prompt._detect_relevant_knowledge", return_value=set()
        ):
            blocks = build_system_prompt_blocks()
        assert isinstance(blocks, list)
        assert len(blocks) == 1
        assert blocks[0]["type"] == "text"
        assert "ComfyUI co-pilot" in blocks[0]["text"]

    def test_volatile_block_added_when_session_context_present(self):
        ctx = {
            "name": "demo",
            "notes": [{"text": "User likes SDXL"}],
            "workflow": {},
        }
        with patch(
            "agent.system_prompt._detect_relevant_knowledge", return_value=set()
        ):
            blocks = build_system_prompt_blocks(session_context=ctx)
        assert len(blocks) == 2
        volatile = blocks[-1]
        assert "Session Context" in volatile["text"]
        assert "User likes SDXL" in volatile["text"]

    def test_volatile_block_omitted_when_no_session_context(self):
        with patch(
            "agent.system_prompt._detect_relevant_knowledge", return_value=set()
        ):
            blocks = build_system_prompt_blocks(session_context=None)
        assert len(blocks) == 1

    def test_topical_block_added_when_knowledge_detected(self, tmp_path):
        topical = tmp_path / "controlnet.md"
        topical.write_text("ControlNet usage notes.", encoding="utf-8")
        core = tmp_path / "comfyui_core.md"
        core.write_text("Core rules.", encoding="utf-8")

        with patch("agent.system_prompt.KNOWLEDGE_DIR", tmp_path), patch(
            "agent.system_prompt._detect_relevant_knowledge",
            return_value={"controlnet"},
        ):
            blocks = build_system_prompt_blocks()

        assert len(blocks) == 2
        topical_block = blocks[1]
        assert "ControlNet usage notes" in topical_block["text"]

    def test_topical_block_omitted_when_detector_returns_empty(self, tmp_path):
        (tmp_path / "controlnet.md").write_text("CN", encoding="utf-8")
        with patch("agent.system_prompt.KNOWLEDGE_DIR", tmp_path), patch(
            "agent.system_prompt._detect_relevant_knowledge", return_value=set()
        ):
            blocks = build_system_prompt_blocks()
        assert len(blocks) == 1

    def test_three_blocks_when_topical_and_volatile_both_present(self, tmp_path):
        (tmp_path / "controlnet.md").write_text("CN", encoding="utf-8")
        (tmp_path / "comfyui_core.md").write_text("core", encoding="utf-8")
        ctx = {"name": "s1", "notes": [{"text": "n"}], "workflow": {}}
        with patch("agent.system_prompt.KNOWLEDGE_DIR", tmp_path), patch(
            "agent.system_prompt._detect_relevant_knowledge",
            return_value={"controlnet"},
        ):
            blocks = build_system_prompt_blocks(session_context=ctx)
        assert len(blocks) == 3


class TestBuildSystemPromptBlocksCacheControl:
    """cache_control placement: stable + topical carry it; volatile does NOT."""

    def test_stable_block_has_ephemeral_cache_control(self):
        with patch(
            "agent.system_prompt._detect_relevant_knowledge", return_value=set()
        ):
            blocks = build_system_prompt_blocks()
        assert blocks[0]["cache_control"] == {"type": "ephemeral"}

    def test_topical_block_has_ephemeral_cache_control(self, tmp_path):
        (tmp_path / "controlnet.md").write_text("CN", encoding="utf-8")
        with patch("agent.system_prompt.KNOWLEDGE_DIR", tmp_path), patch(
            "agent.system_prompt._detect_relevant_knowledge",
            return_value={"controlnet"},
        ):
            blocks = build_system_prompt_blocks()
        topical_block = blocks[1]
        assert topical_block["cache_control"] == {"type": "ephemeral"}

    def test_volatile_block_omits_cache_control(self, tmp_path):
        (tmp_path / "controlnet.md").write_text("CN", encoding="utf-8")
        ctx = {"name": "s1", "notes": [{"text": "n"}], "workflow": {}}
        with patch("agent.system_prompt.KNOWLEDGE_DIR", tmp_path), patch(
            "agent.system_prompt._detect_relevant_knowledge",
            return_value={"controlnet"},
        ):
            blocks = build_system_prompt_blocks(session_context=ctx)
        # stable + topical + volatile
        assert len(blocks) == 3
        assert "cache_control" not in blocks[2]


class TestBuildSystemPromptBlocksDeterminism:
    """Same inputs → byte-identical block payloads — required for cache hits."""

    def test_topical_block_byte_identical_across_calls(self, tmp_path):
        (tmp_path / "alpha.md").write_text("alpha file", encoding="utf-8")
        (tmp_path / "bravo.md").write_text("bravo file", encoding="utf-8")
        (tmp_path / "comfyui_core.md").write_text("core", encoding="utf-8")
        with patch("agent.system_prompt.KNOWLEDGE_DIR", tmp_path), patch(
            "agent.system_prompt._detect_relevant_knowledge",
            return_value={"alpha", "bravo"},
        ):
            first = build_system_prompt_blocks()
            second = build_system_prompt_blocks()

        assert first[0]["text"] == second[0]["text"]
        assert first[1]["text"] == second[1]["text"]

    def test_stable_block_invariant_to_session_context(self):
        """Critical: the stable block must NOT change when session_context
        changes. If it does, the cache breakpoint never hits."""
        with patch(
            "agent.system_prompt._detect_relevant_knowledge", return_value=set()
        ):
            no_ctx = build_system_prompt_blocks()
            with_ctx = build_system_prompt_blocks(
                session_context={
                    "name": "s",
                    "notes": [{"text": "x"}],
                    "workflow": {},
                }
            )
        assert no_ctx[0]["text"] == with_ctx[0]["text"]
