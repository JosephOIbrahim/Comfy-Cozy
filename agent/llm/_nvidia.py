"""NVIDIA / Nemotron provider — OpenAI-compatible reasoning LLM.

Endpoint-agnostic — the same OpenAI chat-completions shape serves:
  (a) NVIDIA NIM cloud   — https://integrate.api.nvidia.com/v1   (nvapi-... key)
  (b) OpenRouter         — https://openrouter.ai/api/v1          (OPENROUTER_API_KEY)
  (c) Ollama cloud       — https://ollama.com/v1                 ('name:cloud' tags)
  (d) self-hosted vLLM/SGLang/NIM — http://<host>:8000/v1        (key optional)
Pick the endpoint with NVIDIA_BASE_URL; the model id selects the backend model.

Nemotron 'reasoning' models stream <think>...</think> as ordinary content. We
default reasoning OFF (a 'detailed thinking off' system directive) because the
agent loop is tool-heavy and reasoning can exhaust max_tokens before the tool
call is emitted. A stateful stream filter strips any <think> that still leaks,
from BOTH the visible stream AND the returned TextBlock (so replayed history
stays clean). Set NVIDIA_EMIT_REASONING=true to request reasoning ON and surface
it (no filtering).

Requires: pip install openai
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable

from ._base import _record_llm_metric, flatten_system as _flatten_system
from ._ollama import OllamaProvider, _map_stop_reason, _to_response
from ._types import (
    LLMAuthError,
    LLMConnectionError,
    LLMError,
    LLMRateLimitError,
    LLMResponse,
    LLMServerError,
    TextBlock,
    ToolUseBlock,
)

try:
    import openai
except ImportError:
    openai = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

if openai is None:  # surface unavailability at import time, not first use
    log.debug("openai package not installed; NvidiaProvider unavailable (pip install openai)")

_REASONING_ON = "detailed thinking on"
_REASONING_OFF = "detailed thinking off"


def _require_openai() -> None:
    if openai is None:
        raise LLMError(
            "The 'openai' package is required for the NVIDIA provider. "
            "Install it with: pip install openai"
        )


class _ThinkFilter:
    """Strip <think>...</think> spans from a streamed text sequence.

    Stateful across chunks (tags can straddle a chunk boundary). feed() returns
    the visible remainder; reasoning text is dropped entirely.
    """

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self._in_think = False
        self._buf = ""

    def feed(self, text: str) -> str:
        self._buf += text
        out: list[str] = []
        while self._buf:
            if not self._in_think:
                i = self._buf.find(self.OPEN)
                if i == -1:
                    keep = self._tail_len(self._buf, self.OPEN)
                    out.append(self._buf[: len(self._buf) - keep])
                    self._buf = self._buf[len(self._buf) - keep :]
                    break
                out.append(self._buf[:i])
                self._buf = self._buf[i + len(self.OPEN) :]
                self._in_think = True
            else:
                j = self._buf.find(self.CLOSE)
                if j == -1:
                    keep = self._tail_len(self._buf, self.CLOSE)
                    self._buf = self._buf[len(self._buf) - keep :]
                    break
                self._buf = self._buf[j + len(self.CLOSE) :]
                self._in_think = False
        return "".join(out)

    @staticmethod
    def _tail_len(s: str, tag: str) -> int:
        """Length of the longest suffix of s that is a prefix of tag."""
        for k in range(min(len(s), len(tag) - 1), 0, -1):
            if tag.startswith(s[-k:]):
                return k
        return 0


def _strip_think(text: str) -> str:
    """One-shot filter for the non-streaming (create) path."""
    return _ThinkFilter().feed(text)


class NvidiaProvider(OllamaProvider):
    """NVIDIA NIM / Nemotron (and OpenRouter / Ollama-cloud) via OpenAI-compatible API."""

    def __init__(self) -> None:
        _require_openai()
        from ..config import NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_EMIT_REASONING

        self._client = openai.OpenAI(
            base_url=NVIDIA_BASE_URL,
            api_key=NVIDIA_API_KEY or "not-needed",  # self-hosted may need none
        )
        self._emit_reasoning = NVIDIA_EMIT_REASONING
        log.info("NVIDIA provider ready (base_url=%s)", NVIDIA_BASE_URL)  # never log the key

    # ------------------------------------------------------------------
    # Reasoning control + error translation
    # ------------------------------------------------------------------

    def _with_reasoning_directive(self, native_messages: list[dict]) -> list[dict]:
        """Prepend the Nemotron reasoning directive ('detailed thinking on/off').

        OFF by default — cheapest, and maximizes tool-call reliability for the
        tool-heavy agent loop. Merged into an existing leading system message
        so the endpoint sees a single system turn.
        """
        directive = _REASONING_ON if self._emit_reasoning else _REASONING_OFF
        if native_messages and native_messages[0].get("role") == "system":
            head = native_messages[0]
            merged = {"role": "system", "content": f"{directive}\n{head.get('content', '')}"}
            return [merged] + native_messages[1:]
        return [{"role": "system", "content": directive}] + native_messages

    @staticmethod
    def _translate(e: Any) -> Exception:
        """Map an APIStatusError to a human-language LLM error (repo convention)."""
        body = (str(e) or "").lower()
        if "tool" in body and ("not support" in body or "unsupported" in body):
            return LLMError(
                "This NVIDIA/Nemotron model does not support tool-calling, which the "
                "agent requires. Switch to a tool-capable Nemotron model."
            )
        status = getattr(e, "status_code", 0) or 0
        if status >= 500:
            return LLMServerError(str(e), status_code=status)
        return LLMError(str(e))

    # ------------------------------------------------------------------
    # stream
    # ------------------------------------------------------------------

    def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        system,
        tools: list[dict],
        messages: list[dict],
        on_text: Callable[[str], None] | None = None,
        on_thinking: Callable[[str], None] | None = None,
        thinking_budget: int = 0,  # accepted, ignored (Anthropic-only knob)
    ) -> LLMResponse:
        native_tools = self.convert_tools(tools)
        native_messages = self.convert_messages(messages)
        system_str = _flatten_system(system)
        if system_str:
            native_messages = [{"role": "system", "content": system_str}] + native_messages
        native_messages = self._with_reasoning_directive(native_messages)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": native_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if native_tools:
            kwargs["tools"] = native_tools

        start = time.monotonic()
        try:
            stream = self._client.chat.completions.create(**kwargs)
            result = self._consume_stream(stream, on_text=on_text)  # filtered inside
            _record_llm_metric("nvidia", "ok", time.monotonic() - start)
            if not result.usage:  # silent-compaction guard — make the gap observable
                log.warning(
                    "nvidia stream returned no usage; compaction will fall back to a heuristic"
                )
            return result
        except openai.AuthenticationError as e:
            _record_llm_metric("nvidia", "error", time.monotonic() - start)
            raise LLMAuthError("NVIDIA auth failed — check NVIDIA_API_KEY") from e
        except openai.RateLimitError as e:
            _record_llm_metric("nvidia", "error", time.monotonic() - start)
            raise LLMRateLimitError(str(e)) from e
        except openai.APIConnectionError as e:
            _record_llm_metric("nvidia", "error", time.monotonic() - start)
            raise LLMConnectionError(str(e)) from e
        except openai.APIStatusError as e:
            _record_llm_metric("nvidia", "error", time.monotonic() - start)
            raise self._translate(e) from e
        except openai.APIError as e:
            _record_llm_metric("nvidia", "error", time.monotonic() - start)
            raise LLMError(str(e)) from e

    # ------------------------------------------------------------------
    # _consume_stream — filter <think> at the SOURCE (history-safe)
    # ------------------------------------------------------------------

    def _consume_stream(self, stream, *, on_text=None) -> LLMResponse:
        import json

        flt = None if self._emit_reasoning else _ThinkFilter()
        text_parts: list[str] = []
        tool_acc: dict[int, dict] = {}
        finish_reason = model_name = ""
        prompt_tokens = completion_tokens = None

        for chunk in stream:
            cu = getattr(chunk, "usage", None)
            if cu is not None:
                pt = getattr(cu, "prompt_tokens", None)
                ct = getattr(cu, "completion_tokens", None)
                if isinstance(pt, int):
                    prompt_tokens = pt
                if isinstance(ct, int):
                    completion_tokens = ct
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            model_name = chunk.model or model_name
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            delta = choice.delta
            if delta is None:
                continue
            if delta.content:
                visible = flt.feed(delta.content) if flt else delta.content
                if visible:
                    text_parts.append(visible)  # clean block — safe to replay
                    if on_text:
                        on_text(visible)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    acc = tool_acc.setdefault(idx, {"id": tc.id or "", "name": "", "args": []})
                    if tc.id:
                        acc["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            acc["name"] = tc.function.name
                        if tc.function.arguments:
                            acc["args"].append(tc.function.arguments)

        content: list[TextBlock | ToolUseBlock] = []
        full = "".join(text_parts)
        if full:
            content.append(TextBlock(text=full))
        for i in sorted(tool_acc):
            acc = tool_acc[i]
            raw = "".join(acc["args"])
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"_raw": raw}
            content.append(
                ToolUseBlock(
                    id=acc["id"] or f"call_{uuid.uuid4().hex[:24]}",
                    name=acc["name"],
                    input=parsed,
                )
            )
        usage = (
            {"input_tokens": prompt_tokens, "output_tokens": completion_tokens}
            if prompt_tokens is not None and completion_tokens is not None
            else {}
        )
        return LLMResponse(
            content=content,
            stop_reason=_map_stop_reason(finish_reason),
            model=model_name,
            usage=usage,
        )

    # ------------------------------------------------------------------
    # create (vision / one-shot) — filter <think> from the final text too
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        model: str,
        max_tokens: int,
        system,
        messages: list[dict],
        timeout: float | None = None,
        thinking_budget: int = 0,  # accepted, ignored
    ) -> LLMResponse:
        native_messages = self._convert_vision_messages(messages)
        system_str = _flatten_system(system)
        if system_str:
            native_messages = [{"role": "system", "content": system_str}] + native_messages
        native_messages = self._with_reasoning_directive(native_messages)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": native_messages,
        }
        if timeout:
            kwargs["timeout"] = timeout

        start = time.monotonic()
        try:
            response = self._client.chat.completions.create(**kwargs)
        except openai.AuthenticationError as e:
            _record_llm_metric("nvidia", "error", time.monotonic() - start)
            raise LLMAuthError("NVIDIA auth failed — check NVIDIA_API_KEY") from e
        except openai.RateLimitError as e:
            _record_llm_metric("nvidia", "error", time.monotonic() - start)
            raise LLMRateLimitError(str(e)) from e
        except openai.APIConnectionError as e:
            _record_llm_metric("nvidia", "error", time.monotonic() - start)
            raise LLMConnectionError(str(e)) from e
        except openai.APIStatusError as e:
            _record_llm_metric("nvidia", "error", time.monotonic() - start)
            raise self._translate(e) from e
        except openai.APIError as e:
            _record_llm_metric("nvidia", "error", time.monotonic() - start)
            raise LLMError(str(e)) from e

        _record_llm_metric("nvidia", "ok", time.monotonic() - start)
        resp = _to_response(response)
        if not self._emit_reasoning:
            for blk in resp.content:
                if isinstance(blk, TextBlock) and "<think>" in blk.text:
                    blk.text = _strip_think(blk.text)
        return resp
