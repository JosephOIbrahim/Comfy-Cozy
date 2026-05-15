"""Single-source agreement for default-model constants (#C1).

After consolidation, the canonical default-model table lives in
agent/config.py. The agent/llm module re-exports it; BrainConfig
reads agent.config.AGENT_MODEL via a factory default. These tests
pin both indirections so a future "let me just hard-code it here"
edit fails immediately.
"""

from __future__ import annotations


def test_agent_llm_default_models_matches_canonical_table():
    """agent.llm.DEFAULT_MODELS reflects the canonical table by value.

    Uses equality rather than identity: other tests in the suite
    (test_config.py, test_llm_providers.py) call importlib.reload on
    agent.config, which creates a new _DEFAULT_AGENT_MODELS dict object
    that agent.llm.DEFAULT_MODELS no longer points to. Equality
    preserves the no-drift guarantee without coupling this test to
    module-reload ordering elsewhere in the suite.
    """
    from agent.config import _DEFAULT_AGENT_MODELS as canonical
    from agent.llm import DEFAULT_MODELS

    assert DEFAULT_MODELS == canonical


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
