"""Persist the last user-selected model/provider so a restart resumes it.

SYNAPSE's model panel "remembers" the last engine you picked. This module is
that memory: a swap can best-effort record its {provider, model, vision_model}
to a small JSON file, and boot can replay it. The location is
``~/.comfy-cozy/model_selection.json`` by default, overridable at runtime with
the ``MODEL_SELECTION_PATH`` env var (read LIVE on every access, never cached).

Every operation is best-effort: a persistence failure MUST NOT break a swap or
crash boot, so writes/loads swallow their errors and degrade to a no-op.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)


def _selection_path() -> Path:
    """Resolve the selection file path, reading the env override live."""
    override = os.environ.get("MODEL_SELECTION_PATH")
    if override:
        return Path(override)
    return Path.home() / ".comfy-cozy" / "model_selection.json"


def save_selection(
    provider: str, model: str, vision_model: str | None = None
) -> None:
    """Atomically persist the current selection. Never raises.

    Writes a temp file in the target directory, then ``os.replace()`` onto the
    target so a reader never observes a half-written file. An OSError (unwritable
    dir, full disk) is logged and swallowed — persistence must not break a swap.
    """
    path = _selection_path()
    payload = json.dumps(
        {
            "provider": provider,
            "model": model,
            "vision_model": vision_model,
            "saved_at": time.time(),
        },
        sort_keys=True,
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        log.warning("could not persist model selection to %s: %s", path, exc)


def load_selection() -> dict | None:
    """Return the persisted selection dict, or None if missing/corrupt.

    A missing file, an unreadable file, or malformed JSON all degrade to None —
    boot resume is best-effort and never raises on a bad file.
    """
    path = _selection_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.debug("no usable model selection at %s: %s", path, exc)
        return None
    # Valid JSON that isn't an object (e.g. "42", "[1]") is not a selection —
    # degrade to None here so callers never .get() on a non-dict.
    return data if isinstance(data, dict) else None


def apply_saved_selection() -> dict | None:
    """Replay the persisted selection via swap. Never crashes boot.

    Applies with ``persist=False`` (don't re-write what we just read), and
    ``probe=False`` / ``require_tools=False`` (boot must not make a live call or
    reject a resume). Returns {provider, model} on success, or None when there is
    no selection or the swap fails.
    """
    sel = load_selection()
    if not sel or not sel.get("provider") or not sel.get("model"):
        return None
    try:
        from .swap import swap  # lazy import — avoids a swap<->selection cycle

        swap(
            provider=sel["provider"],
            model=sel["model"],
            persist=False,
            probe=False,
            require_tools=False,
        )
    except Exception as exc:  # boot must survive a bad/stale saved selection
        log.warning(
            "could not resume saved model %s/%s: %s",
            sel.get("provider"),
            sel.get("model"),
            exc,
        )
        return None
    return {"provider": sel["provider"], "model": sel["model"]}


def clear_selection() -> None:
    """Delete the selection file if present. Never raises."""
    try:
        _selection_path().unlink()
    except (FileNotFoundError, OSError):
        pass
