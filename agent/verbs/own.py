"""OWN verb engine — `cozy doctor` / `cozy stats` / `cozy model search <q>` (WP-OWN, Mile 5).

Offline, accountless, private. Every core path here is a local filesystem read
(0 network); the only optional liveness touchpoints are the ComfyUI
reachability check and the GPU/VRAM snapshot, both riding the existing
``agent.tools.comfy_api.handle`` seam (loopback ComfyUI only, and that seam
never raises — a down server comes back as a note, not an error).

Per the ratified scope cut (HARNESS_CLI_20260714.md §WP-OWN): the bundled
offline model index stays DEFERRED (OQ-4). ``search_models`` therefore fuzzy-
matches over the LOCAL model scan only — no registry, no index download.
Remote search remains under the pre-existing ``cozy search`` command.

Reuses instead of duplicating:

- ``agent.verbs.find``          — ``build_models_report`` (the Mile-2 disk scan)
- ``agent.tools.comfy_inspect`` — ``MODELS_DIR`` / ``CUSTOM_NODES_DIR`` seams
- ``agent.tools.comfy_api``     — ``is_comfyui_running`` / ``get_system_stats``
- ``agent.diagnosis.diagnosis`` — ``recent_paths`` (last run-report verdict)

Every ``*_report`` function returns structured data plus has a ``render_*``
plain-text counterpart the CLI layer can print directly. None of them raise.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path, PurePath

from ..tools import comfy_inspect
from .find import GLYPH_MISSING, GLYPH_OK, build_models_report

_SEARCH_MIN_SCORE = 0.35

_BRIDGE_PACK_TOKEN = "comfy_agent_bridge"


def _human_size(n: int) -> str:
    """Render a byte count in artist-friendly units (deterministic)."""
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{size:.1f} GB"  # pragma: no cover — loop always returns


def _check(name: str, ok: bool, note: str, fix_hint: str | None = None) -> dict:
    """One doctor finding: name, pass/fail, note in artist words, optional fix."""
    return {
        "name": name,
        "ok": ok,
        "glyph": GLYPH_OK if ok else GLYPH_MISSING,
        "note": note,
        "fix_hint": fix_hint,
    }


# ---------------------------------------------------------------------------
# Doctor — `cozy doctor`
# ---------------------------------------------------------------------------


def _check_comfyui() -> dict:
    """Is ComfyUI answering on the loopback port? Down is a finding, never an error."""
    try:
        from ..tools import comfy_api

        data = json.loads(comfy_api.handle("is_comfyui_running", {}))
    except Exception:
        return _check(
            "comfyui",
            False,
            "I could not run the ComfyUI liveness check at all.",
            "Start ComfyUI, then run `cozy doctor` again.",
        )
    if data.get("running"):
        gpu = data.get("gpu", "unknown GPU")
        return _check("comfyui", True, f"ComfyUI is up at {data.get('url', '')} ({gpu}).")
    return _check(
        "comfyui",
        False,
        data.get("error", "ComfyUI is not running."),
        "Start ComfyUI, then run `cozy doctor` again. Everything on-disk still works without it.",
    )


def _check_models_folder() -> dict:
    """Does the models folder exist and hold at least one folder of files?"""
    models_dir = Path(comfy_inspect.MODELS_DIR)
    if not models_dir.is_dir():
        return _check(
            "models_folder",
            False,
            f"No models folder at {models_dir}.",
            "Point COMFYUI_DATABASE in your .env at your ComfyUI install "
            "(the folder that contains models/ and Custom_Nodes/).",
        )
    return _check("models_folder", True, f"Models folder found at {models_dir}.")


def _check_custom_nodes_folder() -> dict:
    """Does the Custom_Nodes folder exist?"""
    cn_dir = Path(comfy_inspect.CUSTOM_NODES_DIR)
    if not cn_dir.is_dir():
        return _check(
            "custom_nodes_folder",
            False,
            f"No Custom_Nodes folder at {cn_dir}.",
            "Point COMFYUI_DATABASE in your .env at your ComfyUI install.",
        )
    return _check("custom_nodes_folder", True, f"Custom node packs folder found at {cn_dir}.")


def _check_bridge_pack() -> dict:
    """Is the comfy_agent_bridge node pack on disk? It powers per-node timings."""
    cn_dir = Path(comfy_inspect.CUSTOM_NODES_DIR)
    if not cn_dir.is_dir():
        return _check(
            "bridge_pack",
            False,
            "Could not look for the bridge pack — the Custom_Nodes folder is missing.",
            "Fix the Custom_Nodes folder first (see the check above).",
        )
    try:
        packs = [p.name for p in cn_dir.iterdir() if p.is_dir()]
    except OSError:
        packs = []
    for name in sorted(packs):
        if _BRIDGE_PACK_TOKEN in name.lower().replace("-", "_"):
            return _check("bridge_pack", True, f"Bridge node pack installed ({name}).")
    return _check(
        "bridge_pack",
        False,
        "The comfy_agent_bridge node pack is not installed — run reports will "
        "have no per-node timings.",
        "Install the comfy_agent_bridge pack into Custom_Nodes and restart ComfyUI.",
    )


def _latest_diagnosis_doc() -> dict | None:
    """Newest parseable run-report document, or None. Never raises."""
    try:
        from ..diagnosis.diagnosis import recent_paths

        for p in recent_paths():
            try:
                return json.loads(Path(p).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    except Exception:
        return None
    return None


def _check_last_diagnose() -> dict:
    """Verdict of the newest run report, if one exists. No reports is not a failure."""
    doc = _latest_diagnosis_doc()
    if doc is None:
        return _check(
            "last_run_report",
            True,
            "No run reports yet — they appear automatically after you run a workflow.",
        )
    run = doc.get("run", {}) if isinstance(doc.get("run"), dict) else {}
    status = str(run.get("status", "unknown"))
    findings = doc.get("findings") or []
    criticals = [f for f in findings if isinstance(f, dict) and f.get("severity") == "critical"]
    warns = [f for f in findings if isinstance(f, dict) and f.get("severity") == "warn"]
    when = str(doc.get("createdAt", ""))[:19].replace("T", " ")
    if status == "completed" and not criticals:
        note = f"Last run ({when}) completed"
        note += " clean." if not warns else f" with {len(warns)} warning(s)."
        return _check("last_run_report", True, note)
    trouble = f"{len(criticals)} critical finding(s)" if criticals else f"status '{status}'"
    return _check(
        "last_run_report",
        False,
        f"Last run ({when}) ended with {trouble}.",
        "Run `cozy diagnose --last` for the full report and per-finding fix hints.",
    )


def doctor_report() -> dict:
    """One-key health sweep — every check is a finding, nothing here raises.

    Checks, in order: ComfyUI reachable (loopback only), models folder present,
    Custom_Nodes folder present, bridge node pack installed, and the verdict of
    the most recent run report if one exists. Each check is a dict of
    ``{name, ok, glyph, note, fix_hint}`` with the note in artist words.
    """
    checks = [
        _check_comfyui(),
        _check_models_folder(),
        _check_custom_nodes_folder(),
        _check_bridge_pack(),
        _check_last_diagnose(),
    ]
    problems = [c for c in checks if not c["ok"]]
    summary = (
        "Everything looks healthy."
        if not problems
        else f"{len(problems)} of {len(checks)} checks need attention."
    )
    return {"checks": checks, "ok": not problems, "summary": summary}


def render_doctor_report(report: dict) -> str:
    """Render a doctor report as plain text with ✓/✗ glyphs and fix hints."""
    lines = ["Cozy doctor"]
    for check in report["checks"]:
        lines.append(f"  {check['glyph']}  {check['note']}")
        if not check["ok"] and check.get("fix_hint"):
            lines.append(f"       fix: {check['fix_hint']}")
    lines.append("")
    lines.append(report["summary"])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stats — `cozy stats`
# ---------------------------------------------------------------------------


def _sessions_stats(sessions_dir: Path | str | None) -> dict:
    """Count outcome records per session from the ``*_outcomes.jsonl`` files."""
    if sessions_dir is None:
        from ..config import SESSIONS_DIR

        sessions_dir = SESSIONS_DIR
    sdir = Path(sessions_dir)
    block: dict = {"source": str(sdir), "sessions": [], "total_outcomes": 0, "note": None}
    if not sdir.is_dir():
        block["note"] = "No session history yet — outcomes are recorded as you work."
        return block
    for path in sorted(sdir.glob("*_outcomes.jsonl")):
        count = 0
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                    count += 1
                except ValueError:
                    continue  # a malformed line is skipped, not fatal
        except OSError:
            continue
        session = path.name[: -len("_outcomes.jsonl")]
        block["sessions"].append({"session": session, "outcomes": count})
        block["total_outcomes"] += count
    if not block["sessions"]:
        block["note"] = "No session history yet — outcomes are recorded as you work."
    return block


def _gpu_stats() -> dict:
    """GPU/VRAM snapshot via the existing get_system_stats seam; graceful when down."""
    try:
        from ..tools import comfy_api

        stats = json.loads(comfy_api.handle("get_system_stats", {}))
    except Exception:
        stats = {"error": "unreachable"}
    if not isinstance(stats, dict) or "error" in stats:
        return {
            "available": False,
            "devices": [],
            "note": "ComfyUI is not running — start it to see GPU and VRAM numbers.",
        }
    devices = []
    for dev in stats.get("devices") or []:
        if not isinstance(dev, dict):
            continue
        total = int(dev.get("vram_total") or 0)
        free = int(dev.get("vram_free") or 0)
        devices.append(
            {
                "name": str(dev.get("name", "unknown device")),
                "vram_total": _human_size(total),
                "vram_free": _human_size(free),
                "vram_used": _human_size(max(total - free, 0)),
            }
        )
    return {"available": True, "devices": devices, "note": None}


def stats_report(sessions_dir: Path | str | None = None) -> dict:
    """On-device stats: model counts/sizes by type, session outcomes, GPU snapshot.

    The model numbers reuse the Mile-2 find scan (local disk only, 0 network);
    session counts come from the ``sessions/*_outcomes.jsonl`` files; the GPU
    block is the one optional live touchpoint (loopback ComfyUI) and degrades
    to a note when the server is down. Never raises.
    """
    models_scan = build_models_report(use_session_workflow=False)
    by_type = []
    total_count = 0
    total_bytes = 0
    for group in models_scan["groups"]:
        size_bytes = sum(m.get("size_bytes", 0) for m in group["models"])
        by_type.append(
            {
                "model_type": group["model_type"],
                "count": group["count"],
                "total_size_bytes": size_bytes,
                "total_size": _human_size(size_bytes),
            }
        )
        total_count += group["count"]
        total_bytes += size_bytes
    return {
        "models": {
            "source": models_scan["source"],
            "by_type": by_type,
            "total_count": total_count,
            "total_size_bytes": total_bytes,
            "total_size": _human_size(total_bytes),
            "note": models_scan.get("note"),
        },
        "sessions": _sessions_stats(sessions_dir),
        "gpu": _gpu_stats(),
    }


def render_stats_report(report: dict) -> str:
    """Render a stats report as plain text: models, sessions, then GPU."""
    models = report["models"]
    lines = [f"Models — {models['source']}"]
    if models.get("note"):
        lines.append(f"  {models['note']}")
    width = max((len(t["model_type"]) for t in models["by_type"]), default=0)
    for t in models["by_type"]:
        lines.append(f"  {t['model_type']:<{width}}  {t['count']:>4}  {t['total_size']:>10}")
    lines.append(f"  total: {models['total_count']} models, {models['total_size']}")

    sessions = report["sessions"]
    lines.append("")
    lines.append(f"Sessions — {sessions['source']}")
    if sessions.get("note"):
        lines.append(f"  {sessions['note']}")
    for s in sessions["sessions"]:
        lines.append(f"  {s['session']}: {s['outcomes']} outcome(s)")
    if sessions["sessions"]:
        lines.append(f"  total: {sessions['total_outcomes']} outcome(s)")

    gpu = report["gpu"]
    lines.append("")
    lines.append("GPU")
    if not gpu["available"]:
        lines.append(f"  {gpu['note']}")
    elif not gpu["devices"]:
        lines.append("  ComfyUI is up but reported no GPU devices.")
    else:
        for dev in gpu["devices"]:
            lines.append(
                f"  {dev['name']} — {dev['vram_used']} used of "
                f"{dev['vram_total']} ({dev['vram_free']} free)"
            )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Model search — `cozy model search <q>` (local disk only; OQ-4 index deferred)
# ---------------------------------------------------------------------------


def _score(query: str, haystacks: list[str]) -> float:
    """Best match score: 1.0 prefix, 0.8 substring, difflib ratio scaled to 0.7."""
    best = 0.0
    for hay in haystacks:
        if hay.startswith(query):
            best = max(best, 1.0)
        elif query in hay:
            best = max(best, 0.8)
        else:
            ratio = difflib.SequenceMatcher(None, query, hay).ratio()
            best = max(best, round(ratio * 0.7, 4))
    return best


def search_models(query: str) -> dict:
    """Substring/fuzzy search over the LOCAL model scan — no network, no index.

    Reuses the find engine's disk scan, then scores each model's relative
    name, basename, family label, and folder against the query (same scoring
    shape as the command palette: 1.0 prefix, 0.8 substring, difflib fallback,
    0.35 floor). Deterministic ordering: descending score, then name.
    """
    q = query.strip().lower()
    result: dict = {"query": query.strip(), "matches": [], "note": None}
    if not q:
        result["note"] = (
            "Give me part of a model name — for example: cozy model search sdxl. "
            "This searches your disk only, not the internet."
        )
        return result

    scan = build_models_report(use_session_workflow=False)
    if scan.get("note") and not scan["groups"]:
        result["note"] = scan["note"]
        return result

    scored: list[tuple[float, str, dict]] = []
    for group in scan["groups"]:
        for model in group["models"]:
            name = model["name"]
            haystacks = [
                name.lower(),
                PurePath(name.replace("\\", "/")).name.lower(),
                model.get("family_label", "").lower(),
                group["model_type"].lower(),
            ]
            score = _score(q, haystacks)
            if score < _SEARCH_MIN_SCORE:
                continue
            scored.append(
                (
                    score,
                    name,
                    {
                        "name": name,
                        "model_type": group["model_type"],
                        "size": model.get("size", ""),
                        "family": model.get("family", "unknown"),
                        "family_label": model.get("family_label", "Unknown"),
                        "status": model.get("status", "ok"),
                        "glyph": model.get("glyph", GLYPH_OK),
                        "score": score,
                    },
                )
            )
    scored.sort(key=lambda t: (-t[0], t[1]))
    result["matches"] = [entry for _score_, _name, entry in scored]
    if not result["matches"]:
        result["note"] = (
            f"No local models match '{result['query']}'. Try fewer letters — "
            "this searches your disk only, not the internet."
        )
    return result


def render_search_report(result: dict) -> str:
    """Render model search matches as aligned plain text."""
    lines = [f"Local models matching '{result['query']}' — {len(result['matches'])} found"]
    if result.get("note"):
        lines.append(f"  {result['note']}")
    width = max((len(m["name"]) for m in result["matches"]), default=0)
    for m in result["matches"]:
        lines.append(
            f"  {m['glyph']}  {m['name']:<{width}}  {m['size']:>10}  "
            f"{m['family_label']}  ({m['model_type']})"
        )
    return "\n".join(lines)
