"""NIM lifecycle wrapper for Comfy-Cozy.

Implements the three lifecycle tools (nim_preflight / nim_run / nim_state) on top
of the engine's two-deadline poll so NIM's cold-start container pull does not
false-fail during WARMUP silence. Spec: tests/manual/PRD_nim_lifecycle.md.

Scope: agent/tools/ only. Built by the cozy ORCHESTRATED chain (Leg 2 Forge).
"""
from __future__ import annotations

# Seam S-1 — NIM class_types (verified in docs/IMPROVEMENT_AREAS_JUNE_2026.md #4;
# Scout re-confirms against FLUX_Dev_NIM_Workflow.json).
NIM_INSTALL_NODES: set[str] = {"InstallNIMNode"}
NIM_LOAD_NODES: set[str] = {"LoadNIMNode"}
NIM_GENERATE_NODES: set[str] = {"NIMFLUXNode"}


import json
import os
import socket
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import httpx

# --- Constants (PRD §5) ----------------------------------------------------
WARMUP_TIMEOUT_COLD = 900.0          # cold container pull budget
WARMUP_TIMEOUT_WARM = 180.0          # warm (image already pulled) budget
COOK_TIMEOUT = 300.0                 # inference budget once cooking starts
WARM_MAX_AGE_S = 24 * 3600.0         # INV-6 host-scoped age bound
TIMEOUT_EVENT = "__timeout__"        # adapter sentinel, comfyui_adapter.py:243

_STATE_PATH = Path(
    os.environ.get(
        "NIM_STATE_PATH",
        str(Path.home() / ".comfy_cozy" / "nim_warm_state.jsonl"),
    )
)


def _host_id() -> str:
    """Host identity for warm-state scoping (injectable via NIM_HOST_ID)."""
    return os.environ.get("NIM_HOST_ID") or socket.gethostname()


class Phase(str, Enum):
    """Lifecycle phase (PRD §5). str-subclass so ``.value`` and JSON work."""

    PREFLIGHT = "PREFLIGHT"
    WARMUP = "WARMUP"
    COOKING = "COOKING"
    DONE = "DONE"
    FAILED = "FAILED"


@dataclass
class PreflightResult:
    node_pack_present: bool
    missing_node_kinds: list[str] = field(default_factory=list)
    vram_free_gb: Optional[float] = None
    recommended_precision: str = "fp8"
    warm: bool = False
    comfy_alive: bool = False
    note: str = ""


@dataclass
class RunResult:
    ok: bool
    phase: Phase
    prompt_id: Optional[str] = None
    images: list = field(default_factory=list)
    warmup_seconds: float = 0.0
    cook_seconds: float = 0.0
    reason: str = ""


# --- Warm-state persistence (FR-3) -----------------------------------------

def _advise_outcome(record: dict) -> None:
    """Neutral local advisor seam: a future outcome-recorder may consume
    warm records to skip cold pulls. No-op by default."""
    return None


def _lookup_warm(model: str) -> Optional[dict]:
    """Newest warm record matching model + this host within WARM_MAX_AGE_S.

    Host-scoped + age-bounded (INV-6). Missing/unreadable file → None.
    """
    try:
        if not _STATE_PATH.exists():
            return None
        host = _host_id()
        now = time.time()
        newest: Optional[dict] = None
        with _STATE_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("model") != model or rec.get("host") != host:
                    continue
                ts = rec.get("ts")
                if not isinstance(ts, (int, float)) or (now - ts) > WARM_MAX_AGE_S:
                    continue
                if newest is None or ts >= newest.get("ts", 0):
                    newest = rec
        return newest
    except Exception:
        return None


def record_warm_state(
    model: str,
    *,
    host: Optional[str] = None,
    warmup_seconds: Optional[float] = None,
    precision: str = "fp8",
    **extra: Any,
) -> dict:
    """Atomically append a warm-state record (write-tmp + os.replace).

    Matches the experience.jsonl durability convention; os.replace is the
    Windows-atomic call (commit 2322a42).
    """
    record = {
        "model": model,
        "host": host or _host_id(),
        "ts": time.time(),
        "warmup_seconds": warmup_seconds,
        "precision": precision,
        **extra,
    }
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    if _STATE_PATH.exists():
        try:
            with _STATE_PATH.open("r", encoding="utf-8") as fh:
                existing = [ln.rstrip("\n") for ln in fh if ln.strip()]
        except Exception:
            existing = []
    existing.append(json.dumps(record, sort_keys=True))
    fd, tmp = tempfile.mkstemp(dir=str(_STATE_PATH.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(existing) + "\n")
        os.replace(tmp, _STATE_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    _advise_outcome(record)
    return record


# --- Preflight (FR-1, read-only — INV-2) -----------------------------------

def nim_preflight(model: str = "flux-dev") -> PreflightResult:
    """Read-only gate: node-pack presence, VRAM, warm-state, liveness.

    Never raises and never writes (AC-1 / test-(e) invariant).
    """
    from ..config import COMFYUI_URL

    node_pack_present = False
    missing: list[str] = []
    vram_free_gb: Optional[float] = None
    comfy_alive = False
    note = ""

    required = NIM_INSTALL_NODES | NIM_LOAD_NODES | NIM_GENERATE_NODES
    try:
        with httpx.Client(timeout=5.0) as client:
            try:
                resp = client.get(f"{COMFYUI_URL}/object_info")
                resp.raise_for_status()
                keys = set(resp.json().keys())
                comfy_alive = True
                missing = sorted(k for k in required if k not in keys)
                node_pack_present = not missing
            except Exception:
                missing = sorted(required)

            try:
                stats = client.get(f"{COMFYUI_URL}/system_stats")
                stats.raise_for_status()
                devices = stats.json().get("devices", [])
                comfy_alive = True
                if devices:
                    free = devices[0].get("vram_free")
                    if isinstance(free, (int, float)):
                        vram_free_gb = free / 1e9
            except Exception:
                pass
    except Exception:
        pass

    if not comfy_alive:
        note = "ComfyUI unreachable"

    warm = _lookup_warm(model) is not None
    return PreflightResult(
        node_pack_present=node_pack_present,
        missing_node_kinds=missing,
        vram_free_gb=vram_free_gb,
        recommended_precision="fp8",
        warm=warm,
        comfy_alive=comfy_alive,
        note=note,
    )


def _select_warmup_budget(pre: PreflightResult, override: Optional[float]) -> float:
    """Budget selection (PRD §5 / AC-4). Extracted for deterministic tests."""
    if override is not None:
        return override
    return WARMUP_TIMEOUT_WARM if pre.warm else WARMUP_TIMEOUT_COLD


# --- Run (FR-2, PRD §5 — two-deadline poll) --------------------------------

def nim_run(
    workflow: dict,
    model: str = "flux-dev",
    *,
    warmup_timeout: Optional[float] = None,
    cook_timeout: float = COOK_TIMEOUT,
    client_id: Optional[str] = None,
) -> RunResult:
    """Submit + poll a NIM workflow with WARMUP-tolerant two-deadline logic.

    WARMUP silence (the adapter's __timeout__ sentinel) is EXPECTED and must
    never fail faster (INV-3); only the warmup/cook deadlines fail the run.
    """
    from ..engine import EngineConnectionError, EngineError, get_engine

    pre = nim_preflight(model)
    if not pre.node_pack_present:
        return RunResult(
            ok=False, phase=Phase.FAILED, reason="NIM node pack not present"
        )

    warmup_budget = _select_warmup_budget(pre, warmup_timeout)
    client_id = client_id or f"nim-{int(time.time() * 1000)}"

    engine = get_engine()
    try:
        prompt_id = engine.queue_prompt(workflow=workflow, client_id=client_id)
    except (EngineConnectionError, EngineError) as e:
        return RunResult(ok=False, phase=Phase.FAILED, reason=str(e))

    phase = Phase.WARMUP
    t_submit = time.monotonic()
    t_cook_start: Optional[float] = None
    saw_any_event = False
    now = t_submit

    try:
        with engine.subscribe_ws(client_id=client_id) as events:
            for ev in events:
                now = time.monotonic()

                # --- deadline checks FIRST, every loop turn (incl __timeout__)
                if phase is Phase.WARMUP and (now - t_submit) > warmup_budget:
                    comfy_alive = nim_preflight(model).comfy_alive
                    if not saw_any_event or not comfy_alive:
                        return RunResult(
                            ok=False,
                            phase=Phase.FAILED,
                            prompt_id=prompt_id,
                            reason=(
                                "warmup timed out with no events / ComfyUI "
                                "unreachable — container stalled"
                            ),
                        )
                    return RunResult(
                        ok=False,
                        phase=Phase.FAILED,
                        prompt_id=prompt_id,
                        reason=(
                            "container still loading past warmup_timeout; "
                            "raise warmup_timeout or pre-pull the image"
                        ),
                    )
                if (
                    phase is Phase.COOKING
                    and t_cook_start is not None
                    and (now - t_cook_start) > cook_timeout
                ):
                    return RunResult(
                        ok=False,
                        phase=Phase.FAILED,
                        prompt_id=prompt_id,
                        reason="cook timed out",
                    )

                if ev.type == TIMEOUT_EVENT:
                    # INV-3: quiet socket is EXPECTED in WARMUP — only the
                    # deadline can fail it. Do not shorten the quiet window.
                    continue

                saw_any_event = True

                if ev.type == "execution_error":
                    nt = ev.data.get("node_type", "?")
                    msg = ev.data.get("exception_message", "")
                    return RunResult(
                        ok=False,
                        phase=Phase.FAILED,
                        prompt_id=prompt_id,
                        reason=f"{nt}: {msg}",
                    )

                # WARMUP -> COOKING transition (PRD §5)
                if phase is Phase.WARMUP:
                    flip = False
                    if ev.type == "executing":
                        nid = ev.data.get("node")
                        cls = (workflow.get(nid) or {}).get("class_type")
                        if cls in NIM_GENERATE_NODES:
                            flip = True
                    elif ev.type == "progress":
                        flip = True
                    if flip:
                        phase = Phase.COOKING
                        t_cook_start = now

                # completion: executing with node == None means prompt complete
                if (
                    ev.type == "executing"
                    and ev.data.get("node") is None
                    and ev.data.get("prompt_id") == prompt_id
                ):
                    break
    except (EngineConnectionError, EngineError) as e:
        return RunResult(
            ok=False, phase=Phase.FAILED, prompt_id=prompt_id, reason=str(e)
        )

    # --- clean completion: collect images + record warm-state -------------
    images: list = []
    try:
        hist = engine.get_history(prompt_id=prompt_id)
        entry = (hist or {}).get(prompt_id, {})
        for node_out in (entry.get("outputs") or {}).values():
            for img in node_out.get("images", []) or []:
                name = img.get("filename") if isinstance(img, dict) else None
                if name:
                    images.append(name)
    except (EngineConnectionError, EngineError):
        pass

    warmup_seconds = round((t_cook_start or now) - t_submit, 1)
    cook_seconds = round(now - (t_cook_start or now), 1)

    try:
        record_warm_state(
            model,
            host=_host_id(),
            warmup_seconds=warmup_seconds,
            precision=pre.recommended_precision,
        )
    except Exception:
        pass

    return RunResult(
        ok=True,
        phase=Phase.DONE,
        prompt_id=prompt_id,
        images=images,
        warmup_seconds=warmup_seconds,
        cook_seconds=cook_seconds,
    )


# --- State (FR-3, read-only) -----------------------------------------------

def nim_state(model: str = "flux-dev") -> dict:
    """Newest warm record for model on this host, or {} (read-only)."""
    return _lookup_warm(model) or {}


# --- MCP tool surface (definitions only; dispatcher registration deferred) -

TOOLS: list[dict] = [
    {
        "name": "nim_preflight",
        "description": (
            "Read-only NIM readiness gate: node-pack presence, free VRAM, "
            "warm-state, and ComfyUI liveness. Never mutates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"model": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "nim_run",
        "description": (
            "Run a NIM workflow with a warmup-tolerant two-deadline poll so a "
            "cold container pull does not false-fail during WARMUP silence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow": {"type": "object"},
                "model": {"type": "string"},
                "warmup_timeout": {"type": "number"},
                "cook_timeout": {"type": "number"},
            },
            "required": ["workflow"],
        },
    },
    {
        "name": "nim_state",
        "description": "Return the newest warm-state record for a NIM model on this host.",
        "input_schema": {
            "type": "object",
            "properties": {"model": {"type": "string"}},
            "required": [],
        },
    },
]


def handle(name: str, tool_input: dict) -> str:
    from dataclasses import asdict

    from ._util import to_json

    try:
        if name == "nim_preflight":
            return to_json(asdict(nim_preflight(tool_input.get("model", "flux-dev"))))
        if name == "nim_run":
            r = nim_run(
                tool_input["workflow"],
                tool_input.get("model", "flux-dev"),
                warmup_timeout=tool_input.get("warmup_timeout"),
                cook_timeout=tool_input.get("cook_timeout", COOK_TIMEOUT),
            )
            d = asdict(r)
            d["phase"] = r.phase.value
            return to_json(d)
        if name == "nim_state":
            return to_json(nim_state(tool_input.get("model", "flux-dev")))
        return to_json({"error": f"Unknown tool: {name}"})
    except Exception as e:
        return to_json({"error": str(e)})
