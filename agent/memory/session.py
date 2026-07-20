"""Session persistence — save and restore agent state across conversations.

Sessions capture:
- Loaded workflow state (path, base, current, patch history)
- Agent notes (observations, preferences, learnings)
- Metadata (timestamps, tool call counts)

File format: JSON in sessions/{name}.json with sort_keys=True
for deterministic serialization (He2025 alignment).
"""

import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path

from ..config import SESSIONS_DIR

log = logging.getLogger(__name__)

SCHEMA_VERSION = 3

# Per-session write lock: prevents read-modify-write races on the notes list
# when concurrent requests call add_note() for the same session file.
# RLock (not Lock) so _handle_save_session() can acquire it BEFORE calling
# load_session() + save_session() without deadlocking on the re-entrant save.
# (Cycle 28 TOCTOU fix)
_NOTE_LOCK = threading.RLock()

NOTE_TYPES = ("preference", "observation", "decision", "tip")

# Filename extensions that mark a value as a model-weight file. Used by the
# REMEMBER asset extractor to lift checkpoints / LoRAs / VAEs out of a workflow
# so an artist can reconstruct a look after a context switch. Pure-local: no
# network, no model-registry lookup — just the strings already in the graph.
_MODEL_EXTS = (".safetensors", ".ckpt", ".gguf", ".pt", ".pth", ".bin", ".sft")

# Input-key hints that route a model-weight filename to the checkpoint bucket.
# Anything else with a model extension is honest residue in the "models" bucket
# rather than being mislabeled a checkpoint (ControlNet, upscaler, CLIP-Vision).
_CKPT_HINTS = ("ckpt", "checkpoint", "unet")


def _sessions_dir() -> Path:
    """Ensure sessions directory exists."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    return SESSIONS_DIR


def _validate_session_name(name: str) -> str | None:
    """Validate a session name to prevent path traversal.

    Session names are used directly in filenames. This ensures the
    resulting path stays within the sessions directory.
    Returns None if valid, or an error message string if invalid.
    """
    if not name or not isinstance(name, str):
        return "Session name must be a non-empty string."
    # Reject path separators and directory traversal components
    if "/" in name or "\\" in name:
        return f"Invalid session name '{name}': must not contain path separators."
    if name in (".", "..") or name.startswith(".."):
        return f"Invalid session name '{name}': must not contain '..' components."
    # Reject null bytes and other dangerous characters
    if "\x00" in name:
        return f"Invalid session name '{name}': must not contain null bytes."
    # Reasonable length limit
    if len(name) > 255:
        return "Session name too long (max 255 characters)."
    return None


def save_session(
    name: str,
    *,
    workflow_state: dict | None = None,
    notes: list[str] | None = None,
    metadata: dict | None = None,
) -> dict:
    """Save session state to a named JSON file.

    Acquires _NOTE_LOCK so that concurrent add_note() calls for the same
    session are not lost by a simultaneous save (both use atomic rename).

    Returns {"saved": path, "size_bytes": n} or {"error": msg}.
    """
    name_err = _validate_session_name(name)
    if name_err:
        return {"error": name_err}

    path = _sessions_dir() / f"{name}.json"

    with _NOTE_LOCK:
        session_data = {
            "name": name,
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "schema_version": SCHEMA_VERSION,
            "workflow": _serialize_workflow_state(workflow_state),
            "notes": notes or [],
            "metadata": metadata or {},
        }

        try:
            content = json.dumps(session_data, sort_keys=True, indent=2, allow_nan=False)  # Cycle 60
            _atomic_write(path, content)
            return {"saved": str(path), "size_bytes": len(content)}
        except Exception as e:
            return {"error": f"Failed to save session: {e}"}


def load_session(name: str) -> dict:
    """Load a session from disk.

    Returns the full session dict or {"error": msg}.
    """
    name_err = _validate_session_name(name)
    if name_err:
        return {"error": name_err}

    path = _sessions_dir() / f"{name}.json"

    if not path.exists():
        # Suggest available sessions
        available = list_sessions()
        names = [s["name"] for s in available.get("sessions", [])]
        if names:
            return {
                "error": f"Session '{name}' not found.",
                "available": names,
            }
        return {"error": f"Session '{name}' not found. No saved sessions exist."}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data = _migrate_session(data)
        # Cycle 44: normalize unexpected field types after migration so callers
        # never see non-list notes or non-dict workflow (e.g. manually edited files)
        if not isinstance(data.get("notes"), list):
            log.warning("Session '%s': 'notes' was not a list — resetting to []", name)
            data["notes"] = []
        if not isinstance(data.get("workflow"), dict):
            log.warning("Session '%s': 'workflow' was not a dict — resetting to default", name)
            data["workflow"] = {
                "loaded_path": None,
                "format": None,
                "assets": _extract_workflow_assets(None),
            }
        return data
    except json.JSONDecodeError as e:
        return {"error": f"Corrupt session file: {e}"}
    except Exception as e:
        return {"error": f"Failed to load session: {e}"}


def list_sessions() -> dict:
    """List all saved sessions with metadata.

    Returns {"sessions": [...], "count": n, "directory": path}.
    """
    sessions_dir = _sessions_dir()
    sessions = []

    for path in sorted(sessions_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            sessions.append({
                "name": data.get("name", path.stem),
                "saved_at": data.get("saved_at", ""),
                "notes_count": len(data.get("notes", [])),
                "has_workflow": data.get("workflow", {}).get("loaded_path") is not None,
                "file": str(path),
            })
        except Exception:
            sessions.append({
                "name": path.stem,
                "saved_at": "",
                "notes_count": 0,
                "has_workflow": False,
                "file": str(path),
                "error": "corrupt",
            })

    return {
        "sessions": sessions,
        "count": len(sessions),
        "directory": str(sessions_dir),
    }


def add_note(name: str, note: str, *, note_type: str = "observation") -> dict:
    """Add a typed note to a session (create session if it doesn't exist).

    Returns {"added": True, "total_notes": n} or {"error": msg}.
    """
    name_err = _validate_session_name(name)
    if name_err:
        return {"error": name_err}

    if note_type not in NOTE_TYPES:
        return {
            "error": f"Unknown note type: {note_type}",
            "hint": f"Use one of: {', '.join(NOTE_TYPES)}",
        }

    path = _sessions_dir() / f"{name}.json"

    with _NOTE_LOCK:
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = _empty_session(name)
        else:
            data = _empty_session(name)

        if "notes" not in data:
            data["notes"] = []

        data["notes"].append({
            "text": note,
            "type": note_type,
            "added_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        data["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        try:
            content = json.dumps(data, sort_keys=True, indent=2, allow_nan=False)  # Cycle 60
            _atomic_write(path, content)
            return {"added": True, "total_notes": len(data["notes"])}
        except Exception as e:
            return {"error": f"Failed to save note: {e}"}


def restore_workflow_state(session_data: dict) -> dict | None:
    """Extract workflow state from session data for re-loading.

    Returns the workflow state dict, or None if no workflow was saved.
    """
    wf = session_data.get("workflow")
    if not wf or not wf.get("loaded_path"):
        return None
    return wf


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _migrate_session(data: dict) -> dict:
    """Upgrade session data from older schema versions to current.

    v0 -> v1: adds schema_version field.
    v1 -> v2: typed notes (preference/observation/decision/tip).
    """
    version = data.get("schema_version", 0)
    if version < 1:
        data["schema_version"] = 1
        log.debug("Migrated session '%s' from v0 to v1", data.get("name", "?"))
    if version < 2:
        notes = data.get("notes", [])
        migrated = []
        for note in notes:
            if isinstance(note, str):
                migrated.append({
                    "text": note,
                    "type": "observation",
                    "added_at": data.get("saved_at", ""),
                })
            elif isinstance(note, dict) and "type" not in note:
                note["type"] = "observation"
                migrated.append(note)
            else:
                migrated.append(note)
        data["notes"] = migrated
        data["schema_version"] = 2
        log.debug(
            "Migrated session '%s' from v1 to v2 (typed notes)",
            data.get("name", "?"),
        )
    if version < 3:
        # v2 -> v3: backfill named asset provenance (checkpoints/LoRAs/VAEs/seeds)
        # so sessions saved before REMEMBER v1 gain the field losslessly on load.
        wf = data.get("workflow")
        if isinstance(wf, dict) and "assets" not in wf:
            source = wf.get("current_workflow") or wf.get("base_workflow")
            wf["assets"] = _extract_workflow_assets(source)
        data["schema_version"] = 3
        log.debug(
            "Migrated session '%s' from v2 to v3 (asset provenance)",
            data.get("name", "?"),
        )
    return data


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically using temp-file-then-rename.

    Prevents corrupt session files from interrupted writes. Syncs OS write
    buffers to disk before the rename so a power failure after the rename
    leaves a complete file, not a partially-flushed one. (Cycle 39 fix)
    """
    fd = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        suffix=".tmp",
        delete=False,
    )
    try:
        fd.write(content)
        fd.flush()
        os.fsync(fd.fileno())
        fd.close()
        os.replace(fd.name, str(path))
    except Exception:
        # Clean up temp file on failure — log if cleanup itself fails
        try:
            fd.close()
        except Exception:
            pass
        try:
            Path(fd.name).unlink(missing_ok=True)
        except Exception as _cleanup_exc:  # Cycle 44: log instead of silent swallow
            log.warning("Failed to clean up temp file %s: %s", fd.name, _cleanup_exc)
        raise


def _empty_session(name: str) -> dict:
    return {
        "name": name,
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "schema_version": SCHEMA_VERSION,
        "workflow": {
            "loaded_path": None,
            "format": None,
            "assets": _extract_workflow_assets(None),
        },
        "notes": [],
        "metadata": {},
    }


def save_stage(name: str, stage: "object") -> dict:
    """Save a CognitiveWorkflowStage as a flattened .usda file alongside the session JSON.

    Args:
        name: Session name (matches the .json session file).
        stage: CognitiveWorkflowStage instance.

    Returns:
        {"saved_stage": path} or {"error": msg}.
    """
    name_err = _validate_session_name(name)
    if name_err:
        return {"error": name_err}

    path = _sessions_dir() / f"{name}.usda"
    try:
        stage.flush(path)
        return {"saved_stage": str(path)}
    except Exception as e:
        log.warning("Failed to save stage for session '%s': %s", name, e)
        return {"error": f"Failed to save stage: {e}"}


def load_stage(name: str) -> "object | None":
    """Load a CognitiveWorkflowStage from a .usda file if it exists.

    Args:
        name: Session name to look up.

    Returns:
        CognitiveWorkflowStage instance, or None if not available.
    """
    path = _sessions_dir() / f"{name}.usda"
    if not path.exists():
        return None
    try:
        from ..stage import CognitiveWorkflowStage, HAS_USD
        if not HAS_USD:
            return None
        return CognitiveWorkflowStage(str(path))
    except Exception as e:
        log.warning("Failed to load stage for session '%s': %s", name, e)
        return None


def save_ratchet(name: str, ratchet: "object") -> dict:
    """Save Ratchet decision history as a JSON file alongside the session.

    Args:
        name: Session name (matches the .json session file).
        ratchet: Ratchet instance with history to persist.

    Returns:
        {"saved_ratchet": path, "decisions": count} or {"error": msg}.
    """
    name_err = _validate_session_name(name)
    if name_err:
        return {"error": name_err}

    path = _sessions_dir() / f"{name}.ratchet.json"
    try:
        history = []
        for d in ratchet.history:
            history.append({
                "delta_id": d.delta_id,
                "kept": d.kept,
                "axis_scores": d.axis_scores,
                "composite": d.composite,
                "timestamp": d.timestamp,
            })
        data = {
            "threshold": ratchet.threshold,
            "weights": ratchet.weights,
            "history": history,
        }
        _atomic_write(path, json.dumps(data, sort_keys=True, indent=2, allow_nan=False))  # Cycle 60
        return {"saved_ratchet": str(path), "decisions": len(history)}
    except Exception as e:
        log.warning("Failed to save ratchet for session '%s': %s", name, e)
        return {"error": f"Failed to save ratchet: {e}"}


def load_ratchet(name: str) -> "object | None":
    """Load a Ratchet from a .ratchet.json file if it exists.

    Restores weights, threshold, and replays the decision history.

    Args:
        name: Session name to look up.

    Returns:
        Ratchet instance with restored history, or None.
    """
    path = _sessions_dir() / f"{name}.ratchet.json"
    if not path.exists():
        return None
    try:
        from ..stage.ratchet import Ratchet, RatchetDecision
        data = json.loads(path.read_text(encoding="utf-8"))
        r = Ratchet(
            weights=data.get("weights"),
            threshold=data.get("threshold", 0.5),
        )
        # Replay history
        for d in data.get("history", []):
            r._history.append(RatchetDecision(
                delta_id=d["delta_id"],
                kept=d["kept"],
                axis_scores=d.get("axis_scores", {}),
                composite=d.get("composite", 0.0),
                timestamp=d.get("timestamp", 0.0),
            ))
        return r
    except Exception as e:
        log.warning("Failed to load ratchet for session '%s': %s", name, e)
        return None


def save_experience(name: str, stage: "object") -> dict:
    """Save experience data from a CognitiveWorkflowStage.

    Experience prims live under /experience/ in the USD stage. Since the
    stage is already saved via save_stage(), this extracts a lightweight
    JSON summary of experiences for quick loading without USD.

    Args:
        name: Session name.
        stage: CognitiveWorkflowStage instance.

    Returns:
        {"saved_experience": path, "count": n} or {"error": msg}.
    """
    path = _sessions_dir() / f"{name}.experience.json"
    try:
        from ..stage.experience import query_experience
        chunks = query_experience(stage, limit=10000)
        data = {
            "count": len(chunks),
            "experiences": [c.to_dict() for c in chunks],
        }
        _atomic_write(path, json.dumps(data, sort_keys=True, indent=2, allow_nan=False))  # Cycle 60
        return {"saved_experience": str(path), "count": len(chunks)}
    except Exception as e:
        log.warning("Failed to save experience for session '%s': %s", name, e)
        return {"error": f"Failed to save experience: {e}"}


def load_experience(name: str, stage: "object") -> int:
    """Replay saved experiences into a CognitiveWorkflowStage.

    Reads the .experience.json file and re-records each experience
    into the stage's /experience/ prims.

    Args:
        name: Session name.
        stage: CognitiveWorkflowStage to record into.

    Returns:
        Number of experiences replayed, or 0 if file not found.
    """
    path = _sessions_dir() / f"{name}.experience.json"
    if not path.exists():
        return 0
    try:
        from ..stage.experience import record_experience
        data = json.loads(path.read_text(encoding="utf-8"))
        count = 0
        for exp in data.get("experiences", []):
            record_experience(
                stage,
                initial_state=exp.get("initial_state", {}),
                decisions=exp.get("decisions", []),
                outcome=exp.get("outcome", {}),
                context_signature_hash=exp.get("context_signature_hash", ""),
                predicted_outcome=exp.get("predicted_outcome") or None,
                timestamp=exp.get("timestamp", 0.0),
            )
            count += 1
        return count
    except Exception as e:
        log.warning("Failed to load experience for session '%s': %s", name, e)
        return 0


def _extract_workflow_assets(workflow: dict | None) -> dict:
    """Lift remembered assets from an API-format workflow dict.

    Returns {"checkpoints", "loras", "vaes", "models", "seeds"} — sorted,
    de-duplicated, deterministic. Buckets are chosen by input-key hint
    ('lora' / 'vae' / 'ckpt'|'checkpoint'|'unet'); any other model-weight file
    (ControlNet, upscaler, CLIP-Vision, ...) goes to the honest "models" residue
    rather than being mislabeled a checkpoint. Literal integer seeds are recorded
    (bool is excluded; the ComfyUI -1 "randomize" sentinel is skipped, since it
    does not reproduce a look). Connection inputs (["node_id", index]) and
    non-literal seeds are skipped. Pure and network-free: it only reads strings
    already present in the graph and never touches the cognitive stage or any
    patent-gated substrate (REMEMBER v1).
    """
    assets: dict = {"checkpoints": [], "loras": [], "vaes": [], "models": [], "seeds": []}
    if not isinstance(workflow, dict):
        return assets

    checkpoints: set[str] = set()
    loras: set[str] = set()
    vaes: set[str] = set()
    models: set[str] = set()
    seeds: set[int] = set()

    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for key, value in inputs.items():
            if not isinstance(key, str):
                continue
            k = key.lower()
            if k in ("seed", "noise_seed"):
                # Literal seeds only — bool is an int subclass (exclude it); -1 is
                # the "randomize each run" sentinel and does not reproduce a look.
                if isinstance(value, int) and not isinstance(value, bool) and value != -1:
                    seeds.add(value)
            elif isinstance(value, str):
                if "lora" in k:
                    loras.add(value)
                elif "vae" in k and value.lower().endswith(_MODEL_EXTS):
                    vaes.add(value)
                elif value.lower().endswith(_MODEL_EXTS):
                    if any(hint in k for hint in _CKPT_HINTS):
                        checkpoints.add(value)
                    else:
                        models.add(value)

    assets["checkpoints"] = sorted(checkpoints)
    assets["loras"] = sorted(loras)
    assets["vaes"] = sorted(vaes)
    assets["models"] = sorted(models)
    assets["seeds"] = sorted(seeds)
    return assets


def _serialize_workflow_state(state: dict | None) -> dict:
    """Serialize workflow_patch._state for disk storage."""
    if state is None:
        return {"loaded_path": None, "format": None, "assets": _extract_workflow_assets(None)}

    current = state.get("current_workflow")
    return {
        "loaded_path": state.get("loaded_path"),
        "format": state.get("format"),
        "base_workflow": state.get("base_workflow"),
        "current_workflow": current,
        "history_depth": len(state.get("history", [])),
        # REMEMBER v1: named asset provenance (checkpoints/LoRAs/VAEs/seed) so a
        # session survives a context switch without re-reading the workflow JSON.
        "assets": _extract_workflow_assets(current or state.get("base_workflow")),
        # Don't serialize full history — can be large.
        # User can undo from current_workflow vs base.
    }
