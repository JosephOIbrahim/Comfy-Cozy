"""Rule 5 of the CLI system prompt must not instruct the agent to bypass the install gate.

CLAUDE.md "Tool Usage Rules" item 5 is the CANONICAL rule text (ledger CANON-RULE5);
this test asserts system_prompt.py against it. Installing node packs is code-executing
(git clone + pip install): repair_workflow(auto_install=true) returns needs_confirmation
listing the packs, and the agent must wait for explicit human approval before re-calling
with confirm=true. The old rule-5 text ("in one continuous flow without stopping to ask")
instructed the agent to self-confirm, bypassing the human gate (ledger C-P0-2).
"""

from agent.system_prompt import build_system_prompt


class TestRule5InstallGate:
    """The real built prompt must mirror the canonical confirm-gated install flow."""

    def test_old_bypass_phrases_absent(self):
        prompt = build_system_prompt()
        assert "without stopping to ask" not in prompt
        assert "auto_install=true) to install" not in prompt

    def test_confirm_gate_flow_present(self):
        prompt = build_system_prompt()
        assert "needs_confirmation" in prompt
        assert "confirm" in prompt
        assert "WAIT for their approval" in prompt
        assert "NEVER self-confirm" in prompt
