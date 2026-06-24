"""Runtime model/provider swap + a flat artist-facing alias registry.

The 'easy swap' core. A swap propagates through every cache layer and is ATOMIC:
  1. snapshot (LLM_PROVIDER, AGENT_MODEL, VISION_MODEL)
  2. under the provider lock: reassign config.* ; clear the name-keyed provider
     cache (get_provider never self-invalidates) ; reset the BrainConfig singleton
  3. eagerly construct the provider — a bad key / unreachable endpoint raises HERE
  -> on ANY failure, restore the snapshot and re-raise (no half-swapped state)

The agent loop reads config.AGENT_MODEL dynamically AND re-resolves the provider
per-turn (see agent/main.py), so step 2 reaches the live stream.

Vision is NOT moved by default (also_vision=False): vision needs a multimodal
provider and stays on config.VISION_PROVIDER, so swapping the agent loop to a
text-only Nemotron never breaks analyze_image.
"""
from __future__ import annotations

import logging

from . import _provider_lock, get_provider

log = logging.getLogger(__name__)

_KNOWN = ("anthropic", "openai", "gemini", "ollama", "nvidia")

# alias -> (provider, model). Single source of truth for the swap UX.
# NVIDIA/Nemotron rows stay commented until the endpoint is ratified and the
# model id is verified live (CLAUDE.md rule #1 / PRD_model_swap.md §2.2 + D-1).
MODEL_ALIASES: dict[str, tuple[str, str]] = {
    "claude": ("anthropic", "claude-opus-4-7"),
    "claude-fast": ("anthropic", "claude-haiku-4-5-20251001"),
    # NVIDIA Nemotron-3 — ids verified live via GET /v1/models on the NIM cloud
    # endpoint (integrate.api.nvidia.com), 2026-06-24. 'super' is the agentic /
    # tool-calling default; ultra = max reasoning; nano = fast tier.
    "nemotron": ("nvidia", "nvidia/nemotron-3-super-120b-a12b"),
    "nemotron-ultra": ("nvidia", "nvidia/nemotron-3-ultra-550b-a55b"),
    "nemotron-nano": ("nvidia", "nvidia/nemotron-3-nano-30b-a3b"),
    "gpt-4o": ("openai", "gpt-4o"),
    "gemini": ("gemini", "gemini-2.5-flash"),
    "llama-local": ("ollama", "llama3.1"),
}


def list_aliases() -> dict[str, dict[str, str]]:
    """Artist-facing alias table: alias -> {provider, model}."""
    return {a: {"provider": p, "model": m} for a, (p, m) in MODEL_ALIASES.items()}


def resolve(name: str) -> tuple[str, str]:
    """Resolve an alias OR a 'provider:model' string OR a bare model id."""
    key = name.strip()
    if key in MODEL_ALIASES:
        return MODEL_ALIASES[key]
    if ":" in key and key.split(":", 1)[0] in _KNOWN:
        prov, model = key.split(":", 1)
        return prov, model
    from .. import config

    return config.LLM_PROVIDER, key  # bare id keeps the current provider


def _clear_cache_locked() -> None:
    """Clear the provider cache assuming _provider_lock is already held."""
    from . import _provider_cache

    _provider_cache.clear()


def _reset_brain() -> None:
    """Reset the cached BrainConfig so vision re-reads VISION_MODEL after a swap."""
    try:
        from ..brain._sdk import reset_integrated_config
    except ImportError:  # brain layer genuinely absent — narrow except, not bare
        return
    reset_integrated_config()


def swap(
    *,
    model: str | None = None,
    provider: str | None = None,
    alias: str | None = None,
    also_vision: bool = False,
) -> dict:
    """Swap the agent-loop model/provider at runtime. Returns {provider, model}.

    Atomic: on any failure (bad key, unreachable endpoint, unknown provider) the
    prior config is restored and the error re-raised, so the session is never
    left pointing at a broken provider.
    """
    from .. import config

    if alias:
        provider, model = resolve(alias)
    elif model and not provider:
        provider, model = resolve(model)
    elif not provider:
        provider = config.LLM_PROVIDER
    if not model:
        raise ValueError("swap requires a model, an alias, or provider+model")
    provider = provider.lower().strip()

    snapshot = (config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL)
    try:
        with _provider_lock:
            config.LLM_PROVIDER = provider
            config.AGENT_MODEL = model
            if also_vision:  # opt-in only — vision stays multimodal by default
                config.VISION_MODEL = model
            _clear_cache_locked()
            _reset_brain()
        get_provider(provider)  # eager validation — raises on bad provider/key
    except Exception:
        config.LLM_PROVIDER, config.AGENT_MODEL, config.VISION_MODEL = snapshot
        with _provider_lock:
            _clear_cache_locked()
            _reset_brain()
        raise

    log.info("model swap: %s/%s -> %s/%s", snapshot[0], snapshot[1], provider, model)
    return {"provider": provider, "model": model}
