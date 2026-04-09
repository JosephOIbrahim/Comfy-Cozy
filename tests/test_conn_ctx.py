"""Tests for agent._conn_ctx — per-connection session name isolation (P0-F).

Covers:
- current_conn_session() returns a stable name within one context
- Different asyncio contexts get different names
- Name propagates correctly into ThreadPoolExecutor threads
- Monkey-patch of agent.tools.handle is visible to parallel workers (P0-H)
"""

import asyncio
import concurrent.futures
import contextvars
import threading


class TestCurrentConnSession:
    """current_conn_session() — returns 'default' outside MCP, UUID inside MCP thread."""

    def test_returns_default_when_contextvar_not_set(self):
        """Outside an MCP handler the function returns 'default' (safe fallback)."""
        import contextvars as _cv
        from agent._conn_ctx import current_conn_session

        # Fresh context with ContextVar never set
        ctx = _cv.copy_context()
        result = ctx.run(current_conn_session)
        assert result == "default"

    def test_returns_contextvar_value_when_set(self):
        """Returns whatever was explicitly set in the ContextVar."""
        import contextvars as _cv
        from agent._conn_ctx import _conn_session, current_conn_session

        ctx = _cv.copy_context()

        def _run():
            _conn_session.set("conn_abcd1234")
            return current_conn_session()

        result = ctx.run(_run)
        assert result == "conn_abcd1234"

    def test_explicit_set_in_executor_thread_works(self):
        """Explicitly setting ContextVar inside executor thread is visible via current_conn_session."""
        from agent._conn_ctx import _conn_session, current_conn_session

        captured = []
        conn_name = "conn_test1234"

        def _worker():
            # mcp_server._handler sets ContextVar explicitly before calling the tool
            _conn_session.set(conn_name)
            captured.append(current_conn_session())

        with concurrent.futures.ThreadPoolExecutor() as ex:
            ex.submit(_worker).result()

        assert captured[0] == conn_name

    def test_default_when_not_set_in_executor_thread(self):
        """Executor thread with no ContextVar set returns 'default', not a UUID."""
        from agent._conn_ctx import current_conn_session

        captured = []

        def _worker():
            captured.append(current_conn_session())

        with concurrent.futures.ThreadPoolExecutor() as ex:
            ex.submit(_worker).result()

        assert captured[0] == "default"


class TestParallelToolDispatch:
    """P0-H — monkey-patch of agent.tools.handle is visible to executor workers."""

    def test_patch_agent_tools_handle_seen_by_workers(self):
        """Patching agent.tools.handle must be visible to ThreadPoolExecutor."""
        from unittest.mock import patch
        from agent.main import run_agent_turn
        from agent.llm import ToolUseBlock
        from unittest.mock import MagicMock

        call_log = []

        def _patched_handle(name, tool_input, **kw):
            call_log.append(name)
            return '{"ok": true}'

        # Two tool calls → parallel executor path in run_agent_turn
        def _make_response():
            response = MagicMock()
            response.stop_reason = "tool_use"
            response.content = [
                ToolUseBlock(id="t1", name="get_all_nodes", input={}),
                ToolUseBlock(id="t2", name="get_system_stats", input={}),
            ]
            return response

        with patch("agent.main._stream_with_retry", return_value=_make_response()):
            with patch("agent.tools.handle", side_effect=_patched_handle):
                client = MagicMock()
                messages = [{"role": "user", "content": "go"}]
                run_agent_turn(client, messages, "system")

        assert "get_all_nodes" in call_log
        assert "get_system_stats" in call_log

    def test_main_no_longer_exports_handle_tool(self):
        """agent.main must not export handle_tool (removed alias → live module ref)."""
        import agent.main as _main
        assert not hasattr(_main, "handle_tool"), (
            "agent.main.handle_tool was removed — patch agent.tools.handle instead"
        )

    def test_chat_patches_correct_target(self):
        """panel/server/chat.py must patch agent.tools.handle, not agent.main.handle_tool."""
        import ast
        from pathlib import Path

        src = Path("panel/server/chat.py").read_text(encoding="utf-8")
        tree = ast.parse(src)

        # Walk AST looking for assignments to _agent_tools.handle
        # and verify no assignments target _main_mod.handle_tool
        found_correct = False
        found_wrong = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute):
                        attr = f"{ast.unparse(target.value)}.{target.attr}"
                        if "handle_tool" in attr and "main" in attr:
                            found_wrong = True
                        if "_agent_tools" in attr and target.attr == "handle":
                            found_correct = True

        assert found_correct, "chat.py must assign to _agent_tools.handle"
        assert not found_wrong, "chat.py must NOT assign to _main_mod.handle_tool"
