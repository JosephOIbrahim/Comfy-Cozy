"""Preflight health for the model selector — configured (free) vs reachable (opt-in).

Two independent signals answer "can I actually swap to this engine right now?":

  * CONFIGURED — a STATIC, network-free config read: does the engine have the
    key / endpoint it needs to even be attempted? Always cheap, always safe.
  * REACHABLE — an OPT-IN live 1-token probe: does the key/endpoint actually
    answer? Costs a few tokens per configured provider, so it is off by default.

Every function here is read-only. A health check NEVER mutates the active
selection (config.LLM_PROVIDER / AGENT_MODEL / VISION_MODEL), never calls swap(),
and never raises out of a probe — an unreachable or misconfigured provider yields
reachable=False with a short reason. probe_provider() reaches the endpoint via
get_provider(name), which caches only the provider INSTANCE and does not change
the active provider, so probing is side-effect-free.
"""
from __future__ import annotations

import concurrent.futures
import logging
import time

from . import get_provider

log = logging.getLogger(__name__)

# A probe is the smallest call that still exercises the key/endpoint: 1 token out,
# bounded by a short timeout so an unreachable endpoint can't stall the selector.
_PROBE_MAX_TOKENS = 4
_PROBE_TIMEOUT = 5.0


def _short(exc: Exception) -> str:
    """First non-empty line of an exception's message (or its class), ~160 chars."""
    text = str(exc).strip()
    if not text:
        return type(exc).__name__
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), text.strip())
    return first if len(first) <= 160 else first[:157] + "..."


def provider_configured(provider: str) -> dict:
    """Static, network-free check: does `provider` have what it needs to be tried?

    Reads config LIVE so a runtime swap or reloaded .env is honored. Returns
    {"configured": bool, "reason": str} — reason is "" when configured, otherwise
    a short human explanation of what is missing.
    """
    from .. import config

    if provider == "anthropic":
        if config.ANTHROPIC_API_KEY:
            return {"configured": True, "reason": ""}
        return {"configured": False, "reason": "ANTHROPIC_API_KEY not set"}

    if provider == "openai":
        if config.OPENAI_API_KEY:
            return {"configured": True, "reason": ""}
        return {"configured": False, "reason": "OPENAI_API_KEY not set"}

    if provider == "gemini":
        if config.GEMINI_API_KEY:
            return {"configured": True, "reason": ""}
        return {"configured": False, "reason": "GEMINI_API_KEY not set"}

    if provider == "ollama":
        # Local server with a default base_url — always attemptable (no key needed).
        return {"configured": True, "reason": ""}

    if provider == "nvidia":
        # Configured if a key is present OR the endpoint isn't the NIM cloud
        # (self-hosted vLLM/SGLang endpoints may be keyless). `or ""` keeps the
        # membership test safe if NVIDIA_BASE_URL is ever unset.
        base_url = config.NVIDIA_BASE_URL or ""
        if config.NVIDIA_API_KEY or "integrate.api.nvidia.com" not in base_url:
            return {"configured": True, "reason": ""}
        return {
            "configured": False,
            "reason": "NVIDIA_API_KEY not set (required for the NIM cloud endpoint)",
        }

    if provider == "custom":
        if config.CUSTOM_MODEL:
            return {"configured": True, "reason": ""}
        return {"configured": False, "reason": "CUSTOM_MODEL not set"}

    return {"configured": False, "reason": f"unknown provider {provider!r}"}


def probe_provider(provider: str, model: str, timeout: float = _PROBE_TIMEOUT) -> dict:
    """Live 1-token reachability check for one provider/model. Read-only, never raises.

    Returns {"reachable": bool, "latency_ms": int|None, "detail": str}. On ANY
    exception (bad key, unreachable endpoint, unknown model, missing SDK) returns
    reachable=False with a short one-line detail instead of propagating.

    get_provider() caches only the provider INSTANCE; it does not change
    config.LLM_PROVIDER, so this leaves the active selection untouched.
    """
    # A non-positive timeout would fall through every provider's `if timeout:`
    # guard to an UNBOUNDED client — clamp to the default so a probe is always
    # bounded (an untimed create() could hang the ThreadPoolExecutor join).
    timeout = timeout if timeout and timeout > 0 else _PROBE_TIMEOUT
    start = time.monotonic()
    try:
        prov = get_provider(provider)
        prov.create(
            model=model,
            max_tokens=_PROBE_MAX_TOKENS,
            system="",
            messages=[{"role": "user", "content": "hi"}],
            timeout=timeout,
        )
    except Exception as exc:  # never propagate — a probe failure is data, not a crash
        return {"reachable": False, "latency_ms": None, "detail": _short(exc)}
    latency_ms = int((time.monotonic() - start) * 1000)
    return {"reachable": True, "latency_ms": latency_ms, "detail": ""}


def model_status(probe: bool = False, timeout: float = _PROBE_TIMEOUT) -> dict:
    """Per-alias health map. Configured is always present; reachability is opt-in.

    Default (probe=False) is free and network-free: every alias row is
    {"provider", "model", "configured", "reason"}. probe=True additionally fires a
    tiny live call to each CONFIGURED provider/model — concurrently (not serially),
    each bounded by `timeout` (a slow, retrying endpoint can exceed it) — and merges
    {"reachable", "latency_ms", "detail"} onto the configured rows. Unconfigured
    engines are never probed (cost-honest).

    Never raises: the probe stage is fully defensive and degrades to the
    network-free status on any failure.
    """
    from .swap import list_aliases

    timeout = timeout if timeout and timeout > 0 else _PROBE_TIMEOUT

    status: dict[str, dict] = {}
    for alias, row in list_aliases().items():
        provider = row["provider"]
        model = row["model"]
        status[alias] = {
            "provider": provider,
            "model": model,
            **provider_configured(provider),
        }

    if not probe:
        return status

    try:
        # Unique (provider, model) pairs worth a live call: configured + real model.
        targets: dict[tuple[str, str], None] = {}
        for row in status.values():
            if row.get("configured") and row.get("model"):
                targets[(row["provider"], row["model"])] = None

        results: dict[tuple[str, str], dict] = {}
        pairs = list(targets)
        if pairs:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(pairs))) as pool:
                futures = {pool.submit(probe_provider, p, m, timeout): (p, m) for (p, m) in pairs}
                for fut in concurrent.futures.as_completed(futures):
                    key = futures[fut]
                    try:
                        results[key] = fut.result(timeout=timeout + 2)
                    except Exception as exc:  # a stuck/broken future is reachable=False
                        results[key] = {
                            "reachable": False,
                            "latency_ms": None,
                            "detail": _short(exc),
                        }

        not_probed = {"reachable": None, "latency_ms": None, "detail": "not probed"}
        for row in status.values():
            if row.get("configured"):
                key = (row["provider"], row["model"])
                row.update(results.get(key, not_probed))
    except Exception as exc:  # the entire probe stage is best-effort — never raise
        log.warning("model_status probe stage failed, returning configured-only: %s", _short(exc))

    return status
