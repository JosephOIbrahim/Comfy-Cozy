"""Custom provider — bring-your-own OpenAI-compatible endpoint.

A thin passthrough over an arbitrary OpenAI chat-completions endpoint. Point
CUSTOM_BASE_URL at whatever you run — self-hosted vLLM / SGLang, LM Studio,
LiteLLM, OpenRouter, or any other OpenAI-shaped gateway — and CUSTOM_API_KEY
supplies the credential (many self-hosted servers need none).

Unlike ``_nvidia.py`` this injects no reasoning directive and does no
``<think>`` stripping — it is a plain passthrough. All streaming, tool,
vision, and error handling is inherited unchanged from ``OpenAIProvider``.

Requires: pip install openai
"""

from __future__ import annotations

import logging

try:
    import openai
except ImportError:
    openai = None  # type: ignore[assignment]

from ._openai import OpenAIProvider
from ._types import LLMError

log = logging.getLogger(__name__)

if openai is None:  # surface unavailability at import time, not first use
    log.debug("openai package not installed; CustomProvider unavailable (pip install openai)")


class CustomProvider(OpenAIProvider):
    """Generic OpenAI-compatible endpoint (self-hosted vLLM/SGLang/LM Studio/LiteLLM/…)."""

    _metric_name = "custom"

    def __init__(self) -> None:
        if openai is None:
            raise LLMError(
                "The 'openai' package is not installed. Install it with: pip install openai"
            )
        from ..config import CUSTOM_API_KEY, CUSTOM_BASE_URL

        self._client = openai.OpenAI(
            base_url=CUSTOM_BASE_URL,
            api_key=CUSTOM_API_KEY or "not-needed",  # self-hosted may need none
        )
        log.info("Custom provider ready (base_url=%s)", CUSTOM_BASE_URL)  # never log the key
