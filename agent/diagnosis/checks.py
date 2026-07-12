"""The zero-LLM checkers — a pinned list of pure functions (DIAG.C9 as amended).

A checker is a function: (env, run, baseline, triggers, error_text) -> list[Finding].
Same inputs, same findings. Absent signal -> [] (that IS the dormant state).
Never raises on the emit path: malformed input -> [] + one log line.
A finding is a record of measurement, never an opinion (Cherny cut #4) — no
world-knowledge tables live here; interpretation is the model's job at read time.

Demo checker set per DISPATCH D2: vram_pressure, env_torch_cuda_mismatch, and the
execution-error mapper (designated code: unknown_gap). Everything else: deferred —
their codes stay in the schema enum; checkers that don't exist never emit them.
"""

from __future__ import annotations

import logging

from .diagnosis import Finding

log = logging.getLogger(__name__)


def check_vram_pressure(env: dict, run: dict, baseline: dict,
                        triggers: list[str], error_text: str) -> list[Finding]:
    """OOM signature -> critical; vram_threshold breach -> warn. Both measured."""
    if "oom" in triggers:
        return [Finding(
            code="vram_pressure", severity="critical", actionable=True,
            explanation="The run failed with an out-of-memory error — the workflow's "
                        "VRAM demand exceeded what the device could serve.",
            fixHint="Reduce resolution or batch size, enable model offload "
                    "(--lowvram), or use tiled VAE decode.",
            context={"cozy": {"error": error_text[:500]}},
        )]
    if "vram_threshold" in triggers:
        peak = run.get("vramPeakGb")
        return [Finding(
            code="vram_pressure", severity="warn", actionable=True,
            explanation=f"VRAM peak {peak} GB breached the pressure threshold — the run "
                        "completed but is one resolution bump from OOM.",
            fixHint="Reduce resolution or batch size, enable model offload, "
                    "or use tiled VAE decode.",
            context={"cozy": {"vramPeakGb": peak}},
        )]
    return []


def check_env_torch_cuda_mismatch(env: dict, run: dict, baseline: dict,
                                  triggers: list[str], error_text: str) -> list[Finding]:
    """Measured-facts form (no ARCH table): an NVIDIA driver is reported by the worker
    while torch carries no CUDA build tag — a misconfiguration both facts prove."""
    driver = env.get("driver", "unknown")
    torch_cuda = env.get("torchCuda", "unknown")
    if driver != "unknown" and torch_cuda == "unknown":
        return [Finding(
            code="env_torch_cuda_mismatch", severity="critical", actionable=True,
            explanation=f"The worker reports NVIDIA driver {driver} but torch "
                        f"({env.get('torch', 'unknown')}) carries no CUDA build tag — "
                        "renders will fall back to CPU.",
            fixHint="Install a CUDA-enabled torch wheel matching the driver "
                    "(pip install torch --index-url https://download.pytorch.org/whl/cu128).",
            context={"cozy": {"driver": driver, "torch": env.get("torch", "unknown")}},
        )]
    return []


def map_execution_error(env: dict, run: dict, baseline: dict,
                        triggers: list[str], error_text: str) -> list[Finding]:
    """Non-OOM execution errors -> unknown_gap with the raw error preserved.
    An error is never allowed to be silent (schema allOf[1])."""
    if "execution_error" not in triggers or "oom" in triggers:
        return []
    parts = error_text.split(" ", 1) if error_text else []
    err = {"class": parts[0] if parts else "unknown",
           "message": parts[1] if len(parts) > 1 else error_text}
    return [Finding(
        code="unknown_gap", severity="warn", actionable=False,
        explanation="Execution failed and no checker could attribute the failure; "
                    "the raw error is preserved in context for the model to interpret.",
        context={"trigger": "execution_error", "signals": {"cozy": {"error": err}}},
    )]


# The pinned registry (DIAG.C9 as amended): a list, not a framework.
# The completeness test pins these names and designated codes — an
# undeclared checker cannot ship.
CHECKS = [check_vram_pressure, check_env_torch_cuda_mismatch, map_execution_error]

DESIGNATED_CODES: dict[str, set[str]] = {
    "check_vram_pressure": {"vram_pressure"},
    "check_env_torch_cuda_mismatch": {"env_torch_cuda_mismatch"},
    "map_execution_error": {"unknown_gap"},
}


def run_checks(env: dict, run: dict, baseline: dict,
               triggers: list[str], error_text: str = "") -> list[Finding]:
    """Run every check on every diagnosis (scope is when you call it — Cherny cut #2)."""
    findings: list[Finding] = []
    for check in CHECKS:
        try:
            findings.extend(check(env, run, baseline, list(triggers), error_text))
        except Exception:
            log.warning("checker %s raised — suppressed (fail-soft)", check.__name__)
    return findings
