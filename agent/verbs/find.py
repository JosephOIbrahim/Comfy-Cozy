"""FIND verb engine — models/nodes discovery for ``cozy models list`` / ``cozy nodes list``.

Pure functions that return STRUCTURED data plus a plain-text rendered form the
CLI layer can print directly. Offline-first per WP-FIND: the listings themselves
are local filesystem reads (0 network). The only optional liveness touchpoint is
the workflow missing-node check, which rides the existing ``find_missing_nodes``
tool (loopback ComfyUI only) and degrades gracefully — in human words — when
ComfyUI is down.

Reuses the existing scan logic instead of duplicating it:

- ``agent.tools.comfy_inspect``  — ``list_models`` / ``get_models_summary`` /
  ``list_custom_nodes`` handlers (filesystem layer)
- ``agent.tools.model_compat``   — ``_identify_family`` filename heuristics
- ``agent.tools.comfy_discover`` — ``find_missing_nodes`` (lazy import; the only
  path that may open a loopback socket)

Glyph legend (WP-FIND design, HARNESS_CLI_20260714.md):
``✓`` installed / usable · ``✗`` missing · ``⚠`` needs attention (mismatch).
"""

from __future__ import annotations

import difflib
import json
from pathlib import PurePath

from ..tools import comfy_inspect
from ..tools.comfy_inspect import _MODEL_EXTENSIONS
from ..tools.model_compat import MODEL_FAMILIES, _identify_family
from ..tools.workflow_parse import _extract_api_format

GLYPH_OK = "✓"  # ✓ installed / usable
GLYPH_MISSING = "✗"  # ✗ missing
GLYPH_ATTENTION = "⚠"  # ⚠ needs attention / mismatch

_STATUS_GLYPHS = {
    "ok": GLYPH_OK,
    "missing": GLYPH_MISSING,
    "attention": GLYPH_ATTENTION,
}

# ---------------------------------------------------------------------------
# Command palette — fuzzy-findable front door (no menu diving)
# ---------------------------------------------------------------------------

# Data only; the CLI layer decides how to render it. Existing 11 commands are
# listed as-is (PASS 5: additions allowed, renames forbidden). New FIND
# surfaces appear first so an artist typing "models" lands on the new verb.
PALETTE: tuple[dict, ...] = (
    {
        "command": "cozy models list",
        "summary": "Every model on disk with ✓/⚠/✗ status, grouped by folder",
        "keywords": ("models", "checkpoints", "loras", "vae", "installed", "list", "find"),
    },
    {
        "command": "cozy nodes list",
        "summary": "Installed custom node packs, plus ✗ for packs your workflow needs",
        "keywords": ("nodes", "packs", "custom", "missing", "installed", "list", "find"),
    },
    {
        "command": "cozy run",
        "summary": "Start the interactive CLI agent",
        "keywords": ("agent", "chat", "start", "interactive"),
    },
    {
        "command": "cozy mcp",
        "summary": "Start the MCP server (primary Claude Code integration)",
        "keywords": ("mcp", "server", "claude", "integration"),
    },
    {
        "command": "cozy inspect",
        "summary": "Quick summary of the local ComfyUI installation",
        "keywords": ("inspect", "summary", "installation", "health"),
    },
    {
        "command": "cozy diagnose",
        "summary": "Show the latest run report for a workflow",
        "keywords": ("diagnose", "report", "debug", "last", "run"),
    },
    {
        "command": "cozy parse",
        "summary": "Parse and analyze a workflow JSON file",
        "keywords": ("parse", "workflow", "analyze", "json"),
    },
    {
        "command": "cozy sessions",
        "summary": "List saved agent sessions",
        "keywords": ("sessions", "saved", "history", "resume"),
    },
    {
        "command": "cozy search",
        "summary": "Search for models or nodes across registries",
        "keywords": ("search", "discover", "civitai", "huggingface", "registry"),
    },
    {
        "command": "cozy orchestrate",
        "summary": "Run a workflow through the cognitive stage",
        "keywords": ("orchestrate", "stage", "pipeline", "execute"),
    },
    {
        "command": "cozy autoresearch",
        "summary": "Autonomous research run for a query",
        "keywords": ("autoresearch", "research", "autonomous", "query"),
    },
    {
        "command": "cozy autonomous",
        "summary": "Long-running autonomous experiment harness",
        "keywords": ("autonomous", "harness", "experiments", "loop"),
    },
)

_PALETTE_MIN_SCORE = 0.35


def command_palette(query: str = "", limit: int = 10) -> list[dict]:
    """Fuzzy-match ``query`` against the command palette.

    Returns a list of ``{"command", "summary", "score"}`` dicts sorted by
    descending score then command name (deterministic). An empty query returns
    the full palette in declaration order (score 0.0). Scores: 1.0 prefix hit,
    0.8 substring hit, otherwise a difflib ratio scaled to 0.7 max; entries
    under the 0.35 floor are dropped.
    """
    q = query.strip().lower()
    if not q:
        return [
            {"command": e["command"], "summary": e["summary"], "score": 0.0}
            for e in PALETTE[: max(0, limit)]
        ]

    scored: list[tuple[float, str, dict]] = []
    for entry in PALETTE:
        haystacks = [entry["command"].lower(), *entry["keywords"], entry["summary"].lower()]
        score = 0.0
        for hay in haystacks:
            if hay.startswith(q):
                score = max(score, 1.0)
            elif q in hay:
                score = max(score, 0.8)
            else:
                ratio = difflib.SequenceMatcher(None, q, hay).ratio()
                score = max(score, round(ratio * 0.7, 4))
        if score >= _PALETTE_MIN_SCORE:
            scored.append((score, entry["command"], entry))

    scored.sort(key=lambda t: (-t[0], t[1]))
    return [
        {"command": e["command"], "summary": e["summary"], "score": s}
        for s, _name, e in scored[: max(0, limit)]
    ]


# ---------------------------------------------------------------------------
# Workflow helpers
# ---------------------------------------------------------------------------


def _resolve_workflow(workflow: dict | None, use_session: bool) -> dict | None:
    """Return the workflow to inspect: explicit arg wins, else session state."""
    if workflow is not None:
        return workflow
    if not use_session:
        return None
    try:
        from ..tools.workflow_patch import get_current_workflow

        return get_current_workflow()
    except Exception:
        return None


def extract_model_references(workflow: dict) -> list[dict]:
    """Collect model filenames referenced by a workflow's node inputs.

    A reference is any string input whose extension looks like a model file
    (same extension set the filesystem scan uses). Deduplicated by filename,
    sorted for deterministic output.
    """
    seen: dict[str, dict] = {}
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for field, value in inputs.items():
            if not isinstance(value, str):
                continue
            if PurePath(value).suffix.lower() not in _MODEL_EXTENSIONS:
                continue
            if value not in seen:
                seen[value] = {
                    "name": value,
                    "field": field,
                    "class_type": node.get("class_type", ""),
                }
    return sorted(seen.values(), key=lambda r: r["name"])


# ---------------------------------------------------------------------------
# Models report — `cozy models list`
# ---------------------------------------------------------------------------


def build_models_report(
    model_type: str | None = None,
    workflow: dict | None = None,
    use_session_workflow: bool = True,
) -> dict:
    """Build the structured models listing (local disk only — 0 network).

    Groups models by their directory under ``models/`` and tags each with its
    base family (filename heuristic) and a status: ``ok`` (✓, present and
    non-empty), ``attention`` (⚠, zero-byte file — likely a failed download).
    If a workflow is supplied or loaded in the session, every model it
    references is checked against the inventory: ``ok`` found, ``missing``
    (✗) not on disk, ``attention`` (⚠) family mismatch against the workflow's
    other models. Never raises; problems land in ``note`` in human words.
    """
    report: dict = {
        "source": str(comfy_inspect.MODELS_DIR),
        "groups": [],
        "workflow": {"checked": False, "references": [], "note": None},
        "note": None,
    }

    # 1 — which model folders exist? (reuses the filesystem-layer scan)
    if model_type:
        type_names = [model_type]
    else:
        summary = json.loads(comfy_inspect.handle("get_models_summary", {}))
        if "error" in summary:
            report["note"] = (
                f"No models folder found at {report['source']} — check "
                "COMFYUI_DATABASE in your .env, or point me at your ComfyUI install."
            )
            _check_workflow_models(report, workflow, use_session_workflow)
            return report
        type_names = sorted(summary.get("types", {}))
        if not type_names:
            report["note"] = (
                f"The models folder at {report['source']} exists but no model "
                "files were found in it yet."
            )

    # 2 — full listing per folder, with family + status tags
    for type_name in type_names:
        listing = json.loads(
            comfy_inspect.handle("list_models", {"model_type": type_name, "format": "full"})
        )
        if "error" in listing:
            available = ", ".join(listing.get("available_types", [])) or "none"
            report["note"] = (
                f"No '{type_name}' folder under {report['source']}. "
                f"Folders that do exist: {available}."
            )
            continue
        models = []
        for item in listing.get("models", []):
            family = _identify_family(item["name"])
            status = "ok"
            note = None
            if item.get("size_bytes", 0) == 0:
                status = "attention"
                note = "zero-byte file — the download probably failed"
            models.append(
                {
                    "name": item["name"],
                    "size": item.get("size", ""),
                    "size_bytes": item.get("size_bytes", 0),
                    "family": family,
                    "family_label": MODEL_FAMILIES.get(family, {}).get("label", "Unknown"),
                    "status": status,
                    "glyph": _STATUS_GLYPHS[status],
                    "note": note,
                }
            )
        report["groups"].append(
            {
                "model_type": type_name,
                "count": len(models),
                "models": models,
            }
        )

    _check_workflow_models(report, workflow, use_session_workflow)
    return report


def _check_workflow_models(report: dict, workflow: dict | None, use_session: bool) -> None:
    """Fill ``report['workflow']`` with per-reference found/missing/mismatch."""
    wf = _resolve_workflow(workflow, use_session)
    if not wf:
        report["workflow"]["note"] = (
            "No workflow loaded — load one to check which of its models are installed."
        )
        return

    # Honest-format gate: artists usually save with ComfyUI's default Save,
    # which produces UI-format JSON. Normalize to the API graph before
    # scanning; a UI-only file has no scannable inputs, so say so instead of
    # a false "references no models" all-clear.
    api_nodes, wf_format = _extract_api_format(wf)
    if wf_format == "ui_only":
        report["workflow"]["note"] = (
            "UI-format file — re-export with Save (API Format) to check its models."
        )
        return

    refs = extract_model_references(api_nodes)
    if not refs:
        report["workflow"]["checked"] = True
        report["workflow"]["note"] = "The loaded workflow does not reference any model files."
        return

    # Index the on-disk inventory by relative name and basename (case-insensitive)
    on_disk: dict[str, str] = {}
    for group in report["groups"]:
        for model in group["models"]:
            rel = model["name"].replace("\\", "/").lower()
            on_disk.setdefault(rel, group["model_type"])
            on_disk.setdefault(PurePath(rel).name, group["model_type"])

    # Family-mismatch baseline: the checkpoint's family if identifiable,
    # else the alphabetically-first known family among the references.
    families: dict[str, str] = {r["name"]: _identify_family(r["name"]) for r in refs}
    known = sorted({f for f in families.values() if f != "unknown"})
    baseline = None
    for ref in refs:
        if "ckpt" in ref["field"].lower() or "checkpoint" in ref["field"].lower():
            if families[ref["name"]] != "unknown":
                baseline = families[ref["name"]]
                break
    if baseline is None and known:
        baseline = known[0]

    entries = []
    for ref in refs:
        name = ref["name"]
        lookup = name.replace("\\", "/").lower()
        found_type = on_disk.get(lookup) or on_disk.get(PurePath(lookup).name)
        family = families[name]
        if found_type is None:
            status, note = "missing", "not found on disk"
        elif len(known) > 1 and family != "unknown" and family != baseline:
            label = MODEL_FAMILIES.get(family, {}).get("label", family)
            base_label = MODEL_FAMILIES.get(baseline, {}).get("label", baseline)
            status = "attention"
            note = f"family mismatch — {label} model in a {base_label} workflow"
        else:
            status, note = "ok", f"found in {found_type}"
        entries.append(
            {
                "name": name,
                "field": ref["field"],
                "family": family,
                "model_type": found_type,
                "status": status,
                "glyph": _STATUS_GLYPHS[status],
                "note": note,
            }
        )

    report["workflow"]["checked"] = True
    report["workflow"]["references"] = entries


# ---------------------------------------------------------------------------
# Nodes report — `cozy nodes list`
# ---------------------------------------------------------------------------


def build_nodes_report(
    workflow_path: str | None = None,
    check_workflow: bool = True,
) -> dict:
    """Build the structured custom-node-pack listing.

    The pack list itself is a pure local disk scan (0 network). When
    ``check_workflow`` is true, the loaded/pathed workflow's node classes are
    checked through the existing ``find_missing_nodes`` tool — the one seam
    that needs live (loopback) ComfyUI. If ComfyUI is down or no workflow is
    loaded, the check is skipped with a human-words note; never raises.
    """
    report: dict = {
        "source": str(comfy_inspect.CUSTOM_NODES_DIR),
        "packs": [],
        "count": 0,
        "workflow": {"checked": False, "missing": [], "note": None},
        "note": None,
    }

    listing = json.loads(comfy_inspect.handle("list_custom_nodes", {}))
    if "error" in listing:
        report["note"] = (
            f"No Custom_Nodes folder found at {report['source']} — check "
            "COMFYUI_DATABASE in your .env."
        )
    else:
        for pack in listing.get("packs", []):
            report["packs"].append(
                {
                    "name": pack["name"],
                    "status": "ok",
                    "glyph": GLYPH_OK,
                    "registers_nodes": bool(pack.get("registers_nodes")),
                    "has_requirements": bool(pack.get("has_requirements")),
                }
            )
        report["count"] = len(report["packs"])

    if check_workflow:
        _check_workflow_nodes(report, workflow_path)
    else:
        report["workflow"]["note"] = "Workflow check skipped."
    return report


def _check_workflow_nodes(report: dict, workflow_path: str | None) -> None:
    """Run the existing find_missing_nodes seam; degrade in human words."""
    try:
        from ..tools import comfy_discover

        tool_input = {"path": workflow_path} if workflow_path else {}
        result = json.loads(comfy_discover.handle("find_missing_nodes", tool_input))
    except Exception:
        report["workflow"]["note"] = (
            "Could not run the workflow node check — the discovery tools "
            "failed to load. The installed-pack list above is still accurate."
        )
        return

    error = result.get("error")
    if error:
        if "not reachable" in error.lower():
            report["workflow"]["note"] = (
                "ComfyUI is not running, so I skipped the live check for "
                "missing workflow nodes. The installed packs above come "
                "straight from your disk."
            )
        elif "no workflow loaded" in error.lower():
            report["workflow"]["note"] = (
                "No workflow loaded — load one to see which of its nodes are missing."
            )
        else:
            report["workflow"]["note"] = f"Workflow node check skipped: {error}"
        return

    report["workflow"]["checked"] = True
    if result.get("status") == "all_installed":
        report["workflow"]["note"] = "Every node in the loaded workflow is available."
        return

    for item in result.get("missing_nodes", []):
        report["workflow"]["missing"].append(
            {
                "node_type": item.get("node_type", ""),
                "status": "missing",
                "glyph": GLYPH_MISSING,
                "pack_title": item.get("pack_title"),
                "pack_url": item.get("pack_url"),
                "pack_installed": bool(item.get("pack_installed")),
            }
        )
    n = len(report["workflow"]["missing"])
    report["workflow"]["note"] = (
        f"{n} node type(s) in the loaded workflow are missing — "
        "run repair to identify and install the packs."
    )


# ---------------------------------------------------------------------------
# Text renderers — the CLI layer prints these as-is (or builds rich tables
# from the structured data instead; both consume the same report dicts)
# ---------------------------------------------------------------------------


def render_models_report(report: dict) -> str:
    """Render a models report as aligned plain text with status glyphs."""
    lines = [f"Models — {report['source']}"]
    if report.get("note"):
        lines.append(f"  {report['note']}")
    for group in report["groups"]:
        lines.append("")
        lines.append(f"{group['model_type']} ({group['count']})")
        width = max((len(m["name"]) for m in group["models"]), default=0)
        for m in group["models"]:
            row = f"  {m['glyph']}  {m['name']:<{width}}  {m['size']:>10}  {m['family_label']}"
            if m.get("note"):
                row += f"  — {m['note']}"
            lines.append(row)
    wf = report.get("workflow") or {}
    if wf.get("references"):
        lines.append("")
        lines.append("Workflow models:")
        for ref in wf["references"]:
            lines.append(f"  {ref['glyph']}  {ref['name']} — {ref['note']}")
    elif wf.get("note"):
        lines.append("")
        lines.append(f"  {wf['note']}")
    return "\n".join(lines)


def render_nodes_report(report: dict) -> str:
    """Render a nodes report as aligned plain text with status glyphs."""
    lines = [f"Custom node packs — {report['source']} ({report['count']})"]
    if report.get("note"):
        lines.append(f"  {report['note']}")
    for pack in report["packs"]:
        suffix = "" if pack["registers_nodes"] else "  (no nodes registered)"
        lines.append(f"  {pack['glyph']}  {pack['name']}{suffix}")
    wf = report.get("workflow") or {}
    if wf.get("missing"):
        lines.append("")
        lines.append("Missing from the loaded workflow:")
        for item in wf["missing"]:
            where = f" — in pack: {item['pack_title']}" if item.get("pack_title") else ""
            lines.append(f"  {item['glyph']}  {item['node_type']}{where}")
    if wf.get("note"):
        lines.append("")
        lines.append(f"  {wf['note']}")
    return "\n".join(lines)


def render_palette(entries: list[dict]) -> str:
    """Render palette matches as plain text."""
    if not entries:
        return "No matching commands. Try 'cozy models list' or 'cozy nodes list'."
    width = max(len(e["command"]) for e in entries)
    return "\n".join(f"  {e['command']:<{width}}  {e['summary']}" for e in entries)
