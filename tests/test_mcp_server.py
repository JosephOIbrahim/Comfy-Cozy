"""Tests for the MCP server adapter.

Tests the tool schema conversion and server creation without requiring
the actual mcp SDK (mocked where needed).
"""

import asyncio
import json
from unittest.mock import patch

import pytest


class TestSchemaConversion:
    """Test Anthropic -> MCP schema conversion."""

    def test_convert_basic_schema(self):
        from agent.mcp_server import _convert_schema

        tool_def = {
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "The name"},
                },
                "required": ["name"],
            },
        }
        result = _convert_schema(tool_def)
        assert result["type"] == "object"
        assert "name" in result["properties"]
        assert result["required"] == ["name"]

    def test_convert_empty_schema(self):
        from agent.mcp_server import _convert_schema

        result = _convert_schema({})
        assert result["type"] == "object"
        assert result["properties"] == {}

    def test_convert_schema_without_type(self):
        from agent.mcp_server import _convert_schema

        tool_def = {
            "input_schema": {
                "properties": {"x": {"type": "number"}},
            },
        }
        result = _convert_schema(tool_def)
        assert result["type"] == "object"
        assert "x" in result["properties"]

    def test_convert_all_agent_tools(self):
        """Every agent tool schema should convert without error."""
        from agent.mcp_server import _convert_schema
        from agent.tools import ALL_TOOLS

        for tool_def in ALL_TOOLS:
            schema = _convert_schema(tool_def)
            assert schema["type"] == "object", f"Tool {tool_def['name']} has bad schema"
            assert "properties" in schema, f"Tool {tool_def['name']} missing properties"


class TestServerCreation:
    """Test MCP server creation and tool bridging."""

    def test_create_server(self):
        """Should create a server — mcp is now a core dependency."""
        from agent import mcp_server

        server = mcp_server.create_mcp_server()
        assert server is not None
        assert server.name == "comfyui-agent"


class TestToolBridging:
    """Test that tools are properly bridged to MCP format."""

    def test_all_tools_have_valid_mcp_names(self):
        """Tool names should be valid MCP identifiers (no spaces, etc.)."""
        from agent.tools import ALL_TOOLS

        for tool_def in ALL_TOOLS:
            name = tool_def["name"]
            assert " " not in name, f"Tool name has spaces: {name}"
            assert name == name.lower().replace("-", "_"), \
                f"Tool name should be snake_case: {name}"

    def test_all_tools_have_descriptions(self):
        """Every tool must have a non-empty description for MCP listing."""
        from agent.tools import ALL_TOOLS

        for tool_def in ALL_TOOLS:
            desc = tool_def.get("description", "")
            assert desc, f"Tool {tool_def['name']} has empty description"
            assert len(desc) >= 10, \
                f"Tool {tool_def['name']} description too short: {desc}"

    def test_tool_count_matches_registry(self):
        """MCP server should expose exactly the same tools as the registry."""
        from agent.mcp_server import _convert_schema
        from agent.tools import ALL_TOOLS

        converted = [_convert_schema(t) for t in ALL_TOOLS]
        assert len(converted) == 134


class TestToolExecution:
    """Test tool execution through the MCP bridge."""

    def test_sync_tool_result(self):
        """Verify a simple tool returns expected result format."""
        from agent.tools import handle

        # Use a tool that works without ComfyUI running
        result = handle("identify_model_family", {"model_name": "sdxl_base.safetensors"})
        parsed = json.loads(result)
        assert parsed["family"] == "sdxl"

    def test_unknown_tool_returns_error(self):
        """Unknown tool should return error string, not crash."""
        from agent.tools import handle

        result = handle("totally_fake_tool", {})
        assert "Unknown tool" in result


class TestToolErrorProtocol:
    """Test MCP protocol compliance for tool errors."""

    def test_tool_exception_returns_is_error_true(self):
        """Tool exceptions must return CallToolResult(isError=True) per MCP spec.

        Drives the REAL registered CallToolRequest handler end-to-end (the
        prior version of this test defined a coroutine it never awaited and
        asserted on a hand-built literal — ledger L-FALSE-COVERAGE). The
        patch must precede create_mcp_server(): the handler binds
        agent.tools.handle at creation time. Arguments must be schema-valid
        or the MCP SDK's input validation answers before our handler runs.
        """
        import mcp.types as mcp_types

        async def _drive():
            with patch("agent.tools.handle", side_effect=RuntimeError("test-error")) as mock_h:
                from agent import mcp_server as ms
                srv = ms.create_mcp_server()
                handler = srv.request_handlers[mcp_types.CallToolRequest]
                req = mcp_types.CallToolRequest(
                    method="tools/call",
                    params=mcp_types.CallToolRequestParams(
                        name="set_input",
                        arguments={"node_id": "3", "input_name": "text", "value": "x"},
                    ),
                )
                res = await handler(req)
                return res.root, mock_h

        result, mock_h = asyncio.run(_drive())
        assert mock_h.called, "the dispatch must actually reach agent.tools.handle"
        assert result.isError is True
        assert "set_input" in result.content[0].text
        assert "test-error" in result.content[0].text

    def test_call_tool_result_is_error_shape(self):
        """Verify the exact shape used in the exception handler is valid."""
        import mcp.types as types

        # This mirrors exactly what mcp_server.py now returns on exception
        result = types.CallToolResult(
            isError=True,
            content=[types.TextContent(type="text", text="Error executing my_tool: ValueError")],
        )
        assert result.isError is True
        assert isinstance(result.content[0], types.TextContent)
        assert "my_tool" in result.content[0].text


# ---------------------------------------------------------------------------
# Cycle 31: MCP server tool execution timeout tests
# ---------------------------------------------------------------------------

class TestToolTimeout:
    """run_in_executor must be wrapped with asyncio.wait_for so hung tools don't block forever.

    The outer budget is per-tool (_tool_time_budget) and is a *wait*, not a
    kill: the worker thread is orphaned on expiry, so the budget must strictly
    exceed each tool's inner timeout for its graceful result to reach the
    client.
    """

    def test_wait_for_present_in_source(self):
        """asyncio.wait_for + asyncio.TimeoutError must remain in the dispatch."""
        import inspect
        from agent import mcp_server
        source = inspect.getsource(mcp_server)
        assert "asyncio.wait_for" in source, "asyncio.wait_for must wrap run_in_executor"
        assert "asyncio.TimeoutError" in source, "TimeoutError must be caught"

    def test_default_tool_gets_default_budget(self):
        from agent.mcp_server import _DEFAULT_TOOL_TIMEOUT, _tool_time_budget
        assert _DEFAULT_TOOL_TIMEOUT == 120.0
        assert _tool_time_budget("load_workflow", {}) == 120.0
        assert _tool_time_budget("get_node_info", None) == 120.0

    def test_execute_with_progress_exceeds_inner_timeout(self):
        from agent.mcp_server import _tool_time_budget
        assert _tool_time_budget("execute_with_progress", {"timeout": 300}) >= 360

    def test_malformed_timeout_falls_back_to_default(self):
        from agent.mcp_server import _DEFAULT_TOOL_TIMEOUT, _tool_time_budget
        budget = _tool_time_budget("execute_with_progress", {"timeout": "bogus"})
        assert budget == _DEFAULT_TOOL_TIMEOUT

    def test_nim_run_covers_cold_warmup_plus_cook(self):
        from agent.mcp_server import _tool_time_budget
        assert _tool_time_budget("nim_run", {}) >= 1260

    def test_download_model_is_unbounded(self):
        from agent.mcp_server import _tool_time_budget
        assert _tool_time_budget("download_model", {}) is None

    def test_vision_budget_exceeds_inner_vision_timeout(self):
        from agent.brain.vision import _VISION_TIMEOUT
        from agent.mcp_server import _tool_time_budget
        budget = _tool_time_budget("analyze_image", {})
        assert budget == 120.0
        assert budget > _VISION_TIMEOUT

    def test_caller_timeout_clamped_to_ceiling(self):
        from agent.mcp_server import _tool_time_budget
        budget = _tool_time_budget("execute_workflow", {"timeout": 1e12})
        assert budget <= 86400 + 30

    def test_run_pipeline_scales_with_stage_count(self):
        from agent.mcp_server import _tool_time_budget
        args = {"pipeline": {"stages": [{}, {}, {}]}}
        assert _tool_time_budget("run_pipeline", args) >= 960

    @pytest.mark.asyncio
    async def test_hung_tool_times_out(self):
        """A tool that never returns must trigger TimeoutError within the wait_for budget."""
        import asyncio

        async def fake_executor(func, *args):
            # Simulate a hung tool — never completes
            await asyncio.sleep(9999)

        loop = asyncio.get_running_loop()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                fake_executor(lambda: None),
                timeout=0.01,  # Very short for testing
            )

    @pytest.mark.asyncio
    async def test_fast_tool_not_affected(self):
        """A tool that returns quickly must not be affected by the timeout."""
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: "ok"),
            timeout=5.0,
        )
        assert result == "ok"


# ---------------------------------------------------------------------------
# Cycle 62: request context failure must log at DEBUG (source verification)
# ---------------------------------------------------------------------------

class TestRequestContextLogging:
    """server.request_context failure → log.debug (Cycle 62)."""

    def test_request_context_failure_logged_in_source(self):
        """Source must contain log.debug() inside the request_context except block."""
        import inspect
        from agent import mcp_server
        source = inspect.getsource(mcp_server)
        # Verify the log.debug is present inside the except for request context
        assert "log.debug" in source, "log.debug must be present in mcp_server"
        assert "Request context unavailable" in source, \
            "Specific debug message for request context failure must be present"
