"""Tests for the NVIDIA / Nemotron LLM provider.

Fully mocked — the openai SDK is patched in (with fake exception classes), so
these run WITHOUT the optional `openai` package installed (unlike the
importorskip-gated test_llm_ollama.py). No network, no key.

Focus areas beyond the shared OpenAI-compat behavior (inherited from Ollama):
  - <think>...</think> is stripped from BOTH the visible stream AND the
    returned TextBlock, including when tags straddle chunk boundaries
  - reasoning is OFF by default (a 'detailed thinking off' system directive)
  - metric label is 'nvidia' (not 'openai')
  - thinking_budget is accepted and NOT forwarded into the SDK
  - errors are translated to human language (auth, tools-unsupported)
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from agent.llm._types import (
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMResponse,
    LLMServerError,
    ToolUseBlock,
)

_EXC_NAMES = (
    "AuthenticationError",
    "RateLimitError",
    "APIConnectionError",
    "APIStatusError",
    "APIError",
)


@contextmanager
def _provider_ctx(emit_reasoning=False, base_url="https://integrate.api.nvidia.com/v1",
                  api_key="nvapi-test"):
    """Yield an NvidiaProvider with a fully mocked openai SDK (patch stays active)."""
    with (
        patch("agent.llm._nvidia.openai") as mock_openai,
        patch("agent.config.NVIDIA_BASE_URL", base_url),
        patch("agent.config.NVIDIA_API_KEY", api_key),
        patch("agent.config.NVIDIA_EMIT_REASONING", emit_reasoning),
    ):
        mock_openai.OpenAI.return_value = MagicMock()
        for name in _EXC_NAMES:
            setattr(mock_openai, name, type(name, (Exception,), {}))
        from agent.llm._nvidia import NvidiaProvider

        provider = NvidiaProvider()
        provider._mock = mock_openai  # expose fake exception classes to tests
        yield provider


@pytest.fixture
def provider():
    with _provider_ctx() as p:
        yield p


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_stream_chunk(content=None, tool_calls=None, finish_reason=None, model="nemotron"):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice], model=model, usage=None)


def _make_usage_chunk(prompt=10, completion=20, model="nemotron"):
    return SimpleNamespace(
        choices=[],
        model=model,
        usage=SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion),
    )


def _make_tc_delta(index=0, tc_id=None, name=None, arguments=None):
    func = None
    if name is not None or arguments is not None:
        func = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=tc_id, function=func)


def _make_completion(content="Hello", tool_calls=None, model="nemotron", finish_reason="stop"):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=20)
    return SimpleNamespace(choices=[choice], model=model, usage=usage)


def _status_error(provider, status, message):
    err = provider._mock.APIStatusError(message)
    err.status_code = status
    return err


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestNvidiaConstruction:
    def test_missing_openai_sdk(self):
        with patch("agent.llm._nvidia.openai", None):
            from agent.llm._nvidia import NvidiaProvider

            with pytest.raises(LLMError, match="openai.*required"):
                NvidiaProvider()

    def test_uses_base_url_and_key(self):
        with _provider_ctx(base_url="https://openrouter.ai/api/v1", api_key="sk-or-test") as p:
            p._mock.OpenAI.assert_called_with(
                base_url="https://openrouter.ai/api/v1", api_key="sk-or-test"
            )

    def test_missing_key_uses_placeholder(self):
        """Self-hosted NIM may need no key — falls back to 'not-needed'."""
        with _provider_ctx(base_url="http://localhost:8000/v1", api_key=None) as p:
            assert p._mock.OpenAI.call_args.kwargs["api_key"] == "not-needed"


# ---------------------------------------------------------------------------
# <think> filtering — the load-bearing reasoning containment
# ---------------------------------------------------------------------------


class TestNvidiaThinkFilter:
    def test_think_stripped_from_stream_and_block_across_boundaries(self, provider):
        """<think> straddling chunk boundaries is removed from BOTH on_text and
        the returned TextBlock (so it never re-enters replayed history)."""
        chunks = [
            _make_stream_chunk(content="Hello "),
            _make_stream_chunk(content="<thi"),
            _make_stream_chunk(content="nk>secret rea"),
            _make_stream_chunk(content="soning</thi"),
            _make_stream_chunk(content="nk> world"),
            _make_stream_chunk(finish_reason="stop"),
            _make_usage_chunk(prompt=3, completion=2),
        ]
        provider._client.chat.completions.create.return_value = iter(chunks)

        seen = []
        resp = provider.stream(
            model="nemotron", max_tokens=100, system="", tools=[],
            messages=[{"role": "user", "content": "hi"}],
            on_text=seen.append,
        )
        visible = "".join(seen)
        block = resp.content[0].text
        for sink in (visible, block):
            assert "<think>" not in sink
            assert "secret" not in sink
            assert "reasoning" not in sink
            assert "Hello" in sink
            assert "world" in sink

    def test_emit_reasoning_surfaces_think(self):
        """With NVIDIA_EMIT_REASONING=true the <think> span is NOT filtered."""
        with _provider_ctx(emit_reasoning=True) as provider:
            provider._client.chat.completions.create.return_value = iter(
                [
                    _make_stream_chunk(content="<think>reason</think>answer"),
                    _make_stream_chunk(finish_reason="stop"),
                    _make_usage_chunk(),
                ]
            )
            resp = provider.stream(
                model="nemotron", max_tokens=100, system="", tools=[],
                messages=[{"role": "user", "content": "hi"}],
            )
            assert "<think>reason</think>" in resp.content[0].text

    def test_create_strips_think(self, provider):
        """The non-streaming create() path also removes <think> from the text."""
        provider._client.chat.completions.create.return_value = _make_completion(
            content="<think>secret</think>final answer"
        )
        resp = provider.create(
            model="nemotron", max_tokens=100, system="",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert "<think>" not in resp.content[0].text
        assert "secret" not in resp.content[0].text
        assert "final answer" in resp.content[0].text


# ---------------------------------------------------------------------------
# Reasoning directive + capability handling
# ---------------------------------------------------------------------------


class TestNvidiaReasoningDirective:
    def test_reasoning_off_directive_injected(self, provider):
        """Default OFF: a 'detailed thinking off' system directive leads the messages."""
        provider._client.chat.completions.create.return_value = iter(
            [_make_stream_chunk(content="ok"), _make_stream_chunk(finish_reason="stop")]
        )
        provider.stream(
            model="nemotron", max_tokens=100, system="Be helpful", tools=[],
            messages=[{"role": "user", "content": "hi"}],
        )
        msgs = provider._client.chat.completions.create.call_args.kwargs["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"].startswith("detailed thinking off")
        assert "Be helpful" in msgs[0]["content"]  # original system preserved

    def test_reasoning_on_directive_when_emitting(self):
        with _provider_ctx(emit_reasoning=True) as provider:
            provider._client.chat.completions.create.return_value = iter(
                [_make_stream_chunk(content="ok"), _make_stream_chunk(finish_reason="stop")]
            )
            provider.stream(
                model="nemotron", max_tokens=100, system="", tools=[],
                messages=[{"role": "user", "content": "hi"}],
            )
            msgs = provider._client.chat.completions.create.call_args.kwargs["messages"]
            assert msgs[0]["content"].startswith("detailed thinking on")

    def test_thinking_budget_accepted_not_forwarded(self, provider):
        """thinking_budget is an Anthropic-only knob: accepted, never sent to NIM."""
        provider._client.chat.completions.create.return_value = iter(
            [_make_stream_chunk(content="ok"), _make_stream_chunk(finish_reason="stop")]
        )
        provider.stream(
            model="nemotron", max_tokens=100, system="", tools=[],
            messages=[{"role": "user", "content": "hi"}], thinking_budget=4000,
        )
        kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert "thinking_budget" not in kwargs
        assert "thinking" not in kwargs

    def test_stream_options_include_usage(self, provider):
        provider._client.chat.completions.create.return_value = iter(
            [_make_stream_chunk(content="ok"), _make_stream_chunk(finish_reason="stop")]
        )
        provider.stream(
            model="nemotron", max_tokens=100, system="", tools=[],
            messages=[{"role": "user", "content": "hi"}],
        )
        kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert kwargs["stream_options"] == {"include_usage": True}

    def test_usage_mapped_from_terminal_chunk(self, provider):
        provider._client.chat.completions.create.return_value = iter(
            [
                _make_stream_chunk(content="hi"),
                _make_stream_chunk(finish_reason="stop"),
                _make_usage_chunk(prompt=111, completion=222),
            ]
        )
        resp = provider.stream(
            model="nemotron", max_tokens=100, system="", tools=[],
            messages=[{"role": "user", "content": "hi"}],
        )
        assert resp.usage == {"input_tokens": 111, "output_tokens": 222}


# ---------------------------------------------------------------------------
# Metrics label
# ---------------------------------------------------------------------------


class TestNvidiaMetrics:
    def test_stream_metric_labeled_nvidia(self, provider):
        provider._client.chat.completions.create.return_value = iter(
            [_make_stream_chunk(content="ok"), _make_stream_chunk(finish_reason="stop")]
        )
        with patch("agent.llm._nvidia._record_llm_metric") as rec:
            provider.stream(
                model="nemotron", max_tokens=100, system="", tools=[],
                messages=[{"role": "user", "content": "hi"}],
            )
        assert rec.call_args.args[0] == "nvidia"

    def test_create_metric_labeled_nvidia(self, provider):
        provider._client.chat.completions.create.return_value = _make_completion()
        with patch("agent.llm._nvidia._record_llm_metric") as rec:
            provider.create(
                model="nemotron", max_tokens=100, system="",
                messages=[{"role": "user", "content": "hi"}],
            )
        assert rec.call_args.args[0] == "nvidia"


# ---------------------------------------------------------------------------
# Tool calling
# ---------------------------------------------------------------------------


class TestNvidiaTools:
    def test_convert_tools_openai_shape_no_cache_control(self, provider):
        """Inherited convert_tools emits OpenAI function shape, no cache_control."""
        tools = [{"name": "search", "description": "d", "input_schema": {"type": "object"}}]
        result = provider.convert_tools(tools)
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "search"
        assert "cache_control" not in result[0]
        assert not provider.convert_tools([])

    def test_two_interleaved_tool_calls(self, provider):
        """Two distinct tool-call indices accumulate into two ToolUseBlocks."""
        chunks = [
            _make_stream_chunk(tool_calls=[_make_tc_delta(0, tc_id="c0", name="alpha")]),
            _make_stream_chunk(tool_calls=[_make_tc_delta(1, tc_id="c1", name="beta")]),
            _make_stream_chunk(tool_calls=[_make_tc_delta(0, arguments='{"x":1}')]),
            _make_stream_chunk(tool_calls=[_make_tc_delta(1, arguments='{"y":2}')]),
            _make_stream_chunk(finish_reason="tool_calls"),
            _make_usage_chunk(),
        ]
        provider._client.chat.completions.create.return_value = iter(chunks)
        resp = provider.stream(
            model="nemotron", max_tokens=100, system="",
            tools=[{"name": "alpha", "description": "", "input_schema": {}},
                   {"name": "beta", "description": "", "input_schema": {}}],
            messages=[{"role": "user", "content": "go"}],
        )
        tool_blocks = [b for b in resp.content if isinstance(b, ToolUseBlock)]
        assert len(tool_blocks) == 2
        assert {b.name for b in tool_blocks} == {"alpha", "beta"}
        assert {b.id for b in tool_blocks} == {"c0", "c1"}
        by_name = {b.name: b.input for b in tool_blocks}
        assert by_name["alpha"] == {"x": 1}
        assert by_name["beta"] == {"y": 2}
        assert resp.stop_reason == "tool_use"


# ---------------------------------------------------------------------------
# Error mapping / translation
# ---------------------------------------------------------------------------


class TestNvidiaErrors:
    def test_auth_error_fixed_message(self, provider):
        provider._client.chat.completions.create.side_effect = provider._mock.AuthenticationError(
            "bad key"
        )
        with pytest.raises(LLMAuthError, match="NVIDIA auth failed"):
            provider.stream(
                model="nemotron", max_tokens=100, system="", tools=[],
                messages=[{"role": "user", "content": "hi"}],
            )

    def test_rate_limit(self, provider):
        provider._client.chat.completions.create.side_effect = provider._mock.RateLimitError("slow")
        with pytest.raises(LLMRateLimitError):
            provider.create(model="nemotron", max_tokens=100, system="", messages=[])

    def test_connection(self, provider):
        provider._client.chat.completions.create.side_effect = provider._mock.APIConnectionError(
            "unreachable"
        )
        with pytest.raises(LLMConnectionError):
            provider.create(model="nemotron", max_tokens=100, system="", messages=[])

    def test_server_5xx(self, provider):
        provider._client.chat.completions.create.side_effect = _status_error(
            provider, 503, "overloaded"
        )
        with pytest.raises(LLMServerError):
            provider.create(model="nemotron", max_tokens=100, system="", messages=[])

    def test_4xx_maps_to_llm_error(self, provider):
        provider._client.chat.completions.create.side_effect = _status_error(
            provider, 404, "model not found"
        )
        with pytest.raises(LLMError):
            provider.create(model="nemotron", max_tokens=100, system="", messages=[])

    def test_tools_unsupported_translated(self, provider):
        """A 4xx whose body says tools are unsupported gets a human-language message."""
        provider._client.chat.completions.create.side_effect = _status_error(
            provider, 400, "this model does not support tools"
        )
        with pytest.raises(LLMError, match="does not support tool-calling"):
            provider.stream(
                model="nemotron", max_tokens=100, system="",
                tools=[{"name": "t", "description": "", "input_schema": {}}],
                messages=[{"role": "user", "content": "hi"}],
            )


# ---------------------------------------------------------------------------
# Inheritance sanity (NvidiaProvider IS an OpenAI-compatible provider)
# ---------------------------------------------------------------------------


class TestNvidiaInheritance:
    def test_is_llm_provider(self, provider):
        from agent.llm._base import LLMProvider

        assert isinstance(provider, LLMProvider)

    def test_create_returns_llm_response(self, provider):
        provider._client.chat.completions.create.return_value = _make_completion(content="hi")
        resp = provider.create(
            model="nemotron", max_tokens=100, system="",
            messages=[{"role": "user", "content": "hi"}],
        )
        assert isinstance(resp, LLMResponse)
        assert resp.content[0].text == "hi"
