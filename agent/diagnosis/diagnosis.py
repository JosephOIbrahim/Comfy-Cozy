"""CozyDiagnosis core (Mile 1-A·demo) — models · env collect · env_hash · baselines · emit · guard.

The invariant: every fired trigger is EXPLAINED (triggers != [] => findings >= 1).
Enforced ONCE at runtime by the pydantic model (DIAG.C7 as amended); the JSON Schema
at schema/diagnosis.schema.json is the interchange treaty, proven by tests.
Baselines are computed at read time from the documents themselves (DIAG.C8 as
amended) — there is no reference store. Emission is fail-soft, always (DIAG.C1):
the diagnostician never kills the patient. No field is ever fabricated (DIAG.C6).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

log = logging.getLogger(__name__)

SCHEMA_VERSION = "0.1.0"
ENV_HASH_LEN = 32
VRAM_PRESSURE_RATIO = 0.92
DURATION_REGRESSION_RATIO = 1.25
MIN_HISTORY_RUNS = 3
BASELINE_WINDOW = 20  # read-time baseline: newest N clean docs (Cherny cut #1)
OOM_SIGNATURES = ("out of memory", "cuda out of memory", "allocation on device", "oom")
# ComfyUI signals EXECUTION_COMPLETE slightly before /history is written; the
# subscriber tolerates that window with a bounded retry (live-verified 2026-07-12).
HISTORY_SETTLE_RETRIES = 6
HISTORY_SETTLE_DELAY_S = 0.4

FindingCode = Literal[
    "env_torch_cuda_mismatch", "precision_suboptimal", "precision_unsupported_fallback",
    "offload_disabled", "pinned_memory_disabled", "vram_pressure", "thermal_or_power_limit",
    "reference_missing", "stage_anomaly", "unknown_gap",
]
TriggerName = Literal[
    "duration_regression", "stage_regression", "vram_threshold", "oom", "execution_error",
]


class Env(BaseModel):
    model_config = ConfigDict(extra="forbid")
    os: str
    python: str
    torch: str
    torchCuda: str
    driver: str  # literal "unknown" permitted (DIAG.C4)
    comfyuiVersion: str


class Stage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: str = Field(pattern=r"^[^:]+:.+$")  # "{nodeId}:{classType}"
    ms: float = Field(ge=0)


class Run(BaseModel):
    model_config = ConfigDict(extra="forbid")
    promptId: str = Field(min_length=1)
    workflowHash: str = Field(pattern=r"^[a-f0-9]{32}$")
    status: Literal["completed", "error", "interrupted"]
    durationS: float = Field(ge=0)
    vramPeakGb: float | None = None  # null is an honest state — no peak source exists today
    stages: list[Stage] = Field(default_factory=list)


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: FindingCode
    severity: Literal["info", "warn", "critical"]
    actionable: bool
    explanation: str = Field(min_length=8)
    fixHint: str | None = None
    context: dict | None = None


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schemaVersion: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    diagnosisId: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    createdAt: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
    nodeId: str = Field(min_length=1)
    envHash: str = Field(pattern=r"^[a-f0-9]{32}$")
    env: Env
    run: Run
    triggers: list[TriggerName] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)

    @model_validator(mode="after")
    def _invariant(self) -> "Diagnosis":
        """The single runtime enforcer (DIAG.C7 as amended)."""
        if self.triggers and not self.findings:
            raise ValueError("invariant violated: fired trigger(s) with no findings")
        if len(set(self.triggers)) != len(self.triggers):
            raise ValueError("triggers must be unique")
        if self.run.status == "error" and "execution_error" not in self.triggers:
            raise ValueError("invariant violated: status 'error' without execution_error trigger")
        return self

    def to_doc(self) -> dict:
        """Plain dict matching the schema: optional finding fields dropped when None,
        vramPeakGb always present (null is an honest, deliberate state)."""
        doc = self.model_dump()
        for f in doc["findings"]:
            for k in ("fixHint", "context"):
                if f.get(k) is None:
                    f.pop(k, None)
        return doc


def canonical_json(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def env_hash(env: dict) -> str:
    """sha256[:32] of the canonical six-field env block (DIAG.C4, cross-repo parity)."""
    return hashlib.sha256(canonical_json(env).encode("utf-8")).hexdigest()[:ENV_HASH_LEN]


def workflow_hash(workflow: dict) -> str:
    """Hash of the resolved graph that actually ran — reality, not intent."""
    return hashlib.sha256(canonical_json(workflow).encode("utf-8")).hexdigest()[:ENV_HASH_LEN]


def collect_env(base_url: str | None = None) -> dict:
    """Worker-side env block from /system_stats (DIAG.C4/C5: never the agent host).
    Fields the worker cannot report are the literal token "unknown" — honest states."""
    from ..config import COMFYUI_URL
    stats = httpx.get(f"{base_url or COMFYUI_URL}/system_stats", timeout=5.0).json()
    system = stats.get("system", {}) if isinstance(stats, dict) else {}
    torch_ver = str(system.get("pytorch_version") or "unknown")
    cuda_tag = torch_ver.rsplit("+", 1)[1] if "+cu" in torch_ver else "unknown"
    return {
        "os": str(system.get("os") or "unknown"),
        "python": str(system.get("python_version") or "unknown").split()[0],
        "torch": torch_ver,
        "torchCuda": cuda_tag,
        "driver": str(system.get("driver") or "unknown"),
        "comfyuiVersion": str(system.get("comfyui_version") or "unknown"),
    }


def diagnosis_dir() -> Path:
    from ..config import STATE_DIR
    return Path(os.getenv("DIAGNOSIS_DIR") or STATE_DIR / "diagnosis")


def emit(diag: Diagnosis) -> Path:
    """Validate (construction already did) -> atomic write (tmp + os.replace)."""
    day = diag.createdAt[:10]
    out_dir = diagnosis_dir() / day
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{diag.envHash[:8]}_{diag.diagnosisId}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(canonical_json(diag.to_doc()), encoding="utf-8")
    os.replace(tmp, path)
    return path


def load(path: Path) -> Diagnosis:
    return Diagnosis.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def recent_paths(limit: int = 200) -> list[Path]:
    """All diagnosis docs, newest first (date dir + mtime)."""
    root = diagnosis_dir()
    if not root.is_dir():
        return []
    files = [p for day in sorted(root.iterdir(), reverse=True) if day.is_dir()
             for p in sorted(day.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)]
    return files[:limit]


def is_clean(doc: dict) -> bool:
    """Read-time clean predicate (DIAG.C8 as amended): completed, no triggers,
    no warn/critical finding. Info findings do not block learning."""
    return (doc.get("run", {}).get("status") == "completed" and not doc.get("triggers")
            and not any(f.get("severity") in ("warn", "critical") for f in doc.get("findings", [])))


def load_baseline(ehash: str, whash: str, n: int = BASELINE_WINDOW) -> dict:
    """Medians computed lazily from the newest n clean docs for this env x workflow.
    The documents are the database (Cherny cut #1)."""
    durations: list[float] = []
    stage_ms: dict[str, list[float]] = {}
    for p in recent_paths():
        if not p.name.startswith(ehash[:8]):
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if doc.get("envHash") != ehash or doc.get("run", {}).get("workflowHash") != whash:
            continue
        if not is_clean(doc):
            continue
        durations.append(float(doc["run"]["durationS"]))
        for s in doc["run"].get("stages", []):
            stage_ms.setdefault(s["stage"], []).append(float(s["ms"]))
        if len(durations) >= n:
            break
    return {
        "runCount": len(durations),
        "durationMedianS": statistics.median(durations) if durations else None,
        "stageMediansMs": {k: statistics.median(v) for k, v in stage_ms.items()},
    }


def evaluate_triggers(run: dict, baseline: dict, error_text: str = "",
                      vram_total_gb: float | None = None) -> list[str]:
    """Deterministic trigger evaluation. Absent signal -> the trigger stays dormant
    (DIAG.C6). stage_regression is not evaluated in 0.1.0 (checker deferred per D2)."""
    triggers: list[str] = []
    if run.get("status") == "error":
        triggers.append("execution_error")
        if any(sig in error_text.lower() for sig in OOM_SIGNATURES):
            triggers.append("oom")
    peak = run.get("vramPeakGb")
    if peak is not None and vram_total_gb and peak / vram_total_gb >= VRAM_PRESSURE_RATIO:
        triggers.append("vram_threshold")
    median = baseline.get("durationMedianS")
    if (baseline.get("runCount", 0) >= MIN_HISTORY_RUNS and median
            and run.get("durationS", 0) > DURATION_REGRESSION_RATIO * median):
        triggers.append("duration_regression")
    return triggers


def guard_unknown_gap(triggers: list[str], findings: list[Finding],
                      signals: dict | None = None) -> list[Finding]:
    """The invariant's floor: checker silence under a trigger produces unknown_gap,
    never nothing."""
    if triggers and not findings:
        findings = [Finding(
            code="unknown_gap", severity="warn", actionable=False,
            explanation="A trigger fired and no checker could attribute it; raw signals "
                        "are preserved in context for the model to interpret.",
            context={"trigger": triggers[0], "signals": signals or {}},
        )]
    return findings


def build_diagnosis(env: dict, run: dict, node_id: str, error_text: str = "",
                    vram_total_gb: float | None = None) -> Diagnosis:
    """Assemble one document: triggers -> checkers -> guard -> validated model."""
    from .checks import run_checks  # lazy: checks imports Finding from this module
    ehash = env_hash(env)
    baseline = load_baseline(ehash, run["workflowHash"])
    triggers = evaluate_triggers(run, baseline, error_text, vram_total_gb)
    findings = run_checks(env, run, baseline, triggers, error_text)
    findings = guard_unknown_gap(
        triggers, findings, {"cozy": {"error": error_text}} if error_text else {}
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return Diagnosis(
        schemaVersion=SCHEMA_VERSION, diagnosisId=str(uuid.uuid4()), createdAt=now,
        nodeId=node_id, envHash=ehash, env=Env(**env), run=Run(**run),
        triggers=triggers, findings=findings,
    )


# --- TriggerRegistry subscriber (DIAG.C1: never intercepts; best-effort always) ---

_installed = False


def _node_id_from_url(url: str) -> str:
    return url.split("://", 1)[-1].rstrip("/")


def _stages_from_bridge(base_url: str, prompt_id: str, workflow: dict) -> list[dict]:
    """Per-node timing from the bridge, classType joined from the queued graph.
    Bridge absent -> [] (DIAG.C6), never an error."""
    try:
        try:
            from ..tools.canvas_bridge import bridge_auth_headers
            headers = bridge_auth_headers()
        except Exception:
            headers = {}
        resp = httpx.get(f"{base_url}/agent/exec_profile/{prompt_id}", timeout=5.0,
                         headers=headers)
        if resp.status_code != 200:
            return []
        nodes = resp.json().get("nodes", [])
    except Exception:
        return []
    stages = []
    for n in sorted(nodes, key=lambda n: n.get("start", 0)):
        nid = str(n.get("node_id", "")) or "unknown"
        cls = n.get("class_type") or workflow.get(nid, {}).get("class_type") or "unknown"
        stages.append({"stage": f"{nid}:{cls}", "ms": float(n.get("duration_ms", 0.0))})
    return stages


def _fetch_history_entry(base_url: str, prompt_id: str) -> dict | None:
    """/history entry for prompt_id, tolerating the brief window where ComfyUI has
    signalled completion but not yet written history (bounded retry; fail-soft —
    returns None if it never appears, so no fabricated document is emitted)."""
    for attempt in range(HISTORY_SETTLE_RETRIES):
        try:
            history = httpx.get(f"{base_url}/history/{prompt_id}", timeout=5.0).json()
        except Exception:
            return None
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        if entry:
            return entry
        if attempt + 1 < HISTORY_SETTLE_RETRIES:
            time.sleep(HISTORY_SETTLE_DELAY_S)
    return None


def _run_facts_from_history(entry: dict, event) -> tuple[str, float, str]:
    """Status, duration, and error text from ComfyUI's own history messages —
    worker-authoritative (DIAG.C6), immune to the agent's clock. The ws event's
    elapsed_ms mixes epoch/monotonic clocks and must not be trusted for duration.
    Falls back to 0.0s (honest 'unmeasured') only when the worker gives no timing."""
    status_block = entry.get("status") or {}
    status = {"success": "completed", "error": "error"}.get(status_block.get("status_str"))
    if status is None:  # bridge/older worker without status_str
        status = "error" if getattr(event, "is_error", False) else "completed"
    start = end = None
    error_text = ""
    for msg in status_block.get("messages") or []:
        if not (isinstance(msg, (list, tuple)) and len(msg) == 2 and isinstance(msg[1], dict)):
            continue
        name, payload = msg
        ts = payload.get("timestamp")
        if name == "execution_start" and ts is not None:
            start = ts
        elif name in ("execution_success", "execution_error", "execution_interrupted"):
            if ts is not None:
                end = ts
            if name == "execution_error":
                error_text = " ".join(str(payload.get(k, ""))
                                      for k in ("exception_type", "exception_message"))
    duration_s = round((end - start) / 1000.0, 2) if (
        start is not None and end is not None and end >= start) else 0.0
    if not error_text.strip():  # fall back to the ws error event payload
        data = getattr(event, "data", {}) or {}
        error_text = " ".join(str(data.get(k, "")) for k in ("exception_type", "exception_message"))
    return status, duration_s, error_text.strip()


def _diagnose_event(event) -> Path | None:
    from ..config import COMFYUI_URL
    prompt_id = getattr(event, "prompt_id", "") or ""
    if not prompt_id:
        return None
    entry = _fetch_history_entry(COMFYUI_URL, prompt_id)
    if not entry:
        return None  # no resolved graph -> no honest workflowHash -> no document
    workflow = entry.get("prompt", [None, None, {}])[2] or {}
    status, duration_s, error_text = _run_facts_from_history(entry, event)
    env = collect_env(COMFYUI_URL)
    run = {
        "promptId": prompt_id,
        "workflowHash": workflow_hash(workflow),
        "status": status,
        "durationS": duration_s,
        "vramPeakGb": None,  # confirmed absent from every live source (scout U2)
        "stages": _stages_from_bridge(COMFYUI_URL, prompt_id, workflow),
    }
    diag = build_diagnosis(env, run, _node_id_from_url(COMFYUI_URL), error_text)
    return emit(diag)


def _on_event(event) -> None:
    try:
        _diagnose_event(event)
    except Exception:
        log.debug("diagnosis emission failed — suppressed (fail-soft)", exc_info=True)


def install_subscriber() -> bool:
    """Idempotent. Registers on the existing TriggerRegistry; zero execute-path changes."""
    global _installed
    if _installed:
        return True
    try:
        from cognitive.transport.triggers import on_execution_complete, on_execution_error
        on_execution_complete(_on_event)
        on_execution_error(_on_event)
        _installed = True
    except Exception:
        log.debug("diagnosis subscriber not installed — suppressed", exc_info=True)
    return _installed


def smoke_check() -> str:
    """collect env (synthetic if the worker is down) -> hash -> validate a synthetic doc."""
    try:
        env = collect_env()
    except Exception:
        env = {"os": "unknown", "python": "unknown", "torch": "unknown",
               "torchCuda": "unknown", "driver": "unknown", "comfyuiVersion": "unknown"}
    diag = build_diagnosis(env, {
        "promptId": "smoke", "workflowHash": "0" * 32, "status": "completed",
        "durationS": 0.0, "vramPeakGb": None, "stages": [],
    }, node_id="smoke:0")
    assert diag.envHash == env_hash(env)
    print("OK", diag.envHash)
    return diag.envHash
