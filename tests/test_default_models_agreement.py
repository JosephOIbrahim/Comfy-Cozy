"""Single-source agreement for default-model constants (#C1).

After consolidation, the canonical default-model table lives in
agent/config.py. The agent/llm module re-exports it; BrainConfig
reads agent.config.AGENT_MODEL via a factory default. These tests
pin both indirections so a future "let me just hard-code it here"
edit fails immediately.
"""

from __future__ import annotations


def test_agent_llm_default_models_is_canonical_table():
    """agent.llm.DEFAULT_MODELS is the SAME object as the canonical table.

    Identity, not equality — if someone re-declares DEFAULT_MODELS as a
    separate dict that happens to start with the same values, this fails.
    """
    from agent.config import _DEFAULT_AGENT_MODELS as canonical
    from agent.llm import DEFAULT_MODELS

    assert DEFAULT_MODELS is canonical


def test_brain_config_agent_model_matches_agent_config_value():
    """BrainConfig() instantiated with no args picks up agent.config.AGENT_MODEL.

    Previously the dataclass hard-coded "claude-opus-4-7" alongside the
    agent.config and agent.llm declarations — three places to keep in
    sync by comment. Now the dataclass reads AGENT_MODEL via factory.
    """
    from agent.config import AGENT_MODEL
    from agent.brain._sdk import BrainConfig

    cfg = BrainConfig()
    assert cfg.agent_model == AGENT_MODEL
