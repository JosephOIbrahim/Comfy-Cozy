"""CLI-session sidecar — the workflow session that survives between ``cozy`` commands.

Every ``cozy`` invocation is its own process, so the in-memory workflow
session (per-connection state in ``agent.tools.workflow_patch``) dies when
the command exits — which broke the open→pull round-trip, ``cozy see`` with
no argument, ``cozy run --recipe`` without ``-w``, and pull's "one undo
away — survives between commands" promise (defect B1).

This module is the fix: a tiny durable sidecar next to the named sessions.

- :func:`persist` snapshots the live session through the
  ``workflow_patch.export_session_state()`` seam into
  ``sessions/_cli_verbs.session.json`` (the ``name.ext`` sibling convention
  the sessions directory already uses), written atomically with the same
  temp-file-then-rename pattern as ``agent/memory/session.py`` and
  deterministic ``sort_keys`` JSON.
- :func:`restore` reads it back and folds it into the live session through
  ``workflow_patch.import_session_state()``.

Missing or damaged sidecars degrade to a one-line human note (or plain
``None`` for the ordinary first-run case) — never a crash, and never a
half-restored session: rejection leaves the live session untouched.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

_SIDECAR_NAME = "_cli_verbs.session.json"


def sidecar_path() -> Path:
    """Where the CLI sidecar lives — a ``name.ext`` sibling in the sessions dir.

    Reads ``agent.config.SESSIONS_DIR`` at call time so tests (and a
    ``COMFY_COZY_HOME`` override) always see the current value.
    """
    from ..config import SESSIONS_DIR

    return SESSIONS_DIR / _SIDECAR_NAME


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` atomically (temp-file, fsync, rename) — same pattern
    as ``agent/memory/session.py``: an interrupted write can never leave a
    truncated sidecar behind."""
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
        try:
            fd.close()
        except Exception:
            pass
        try:
            Path(fd.name).unlink(missing_ok=True)
        except Exception as cleanup_exc:
            log.warning("Could not clean up sidecar temp file: %s", cleanup_exc)
        raise


def persist() -> str | None:
    """Snapshot the live workflow session into the sidecar file.

    Returns ``None`` on success, or one human-worded note when the write
    failed — the command that just ran still worked; only cross-command
    memory is lost. Never raises.
    """
    from ..tools.workflow_patch import export_session_state

    snapshot = export_session_state()
    content = json.dumps(snapshot, indent=2, sort_keys=True, allow_nan=False)
    path = sidecar_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, content)
    except (OSError, ValueError) as exc:
        log.warning("Could not persist the CLI session sidecar: %s", exc)
        return (
            "Heads up: this session couldn't be saved for your next cozy command "
            f"({exc}). The change you just made still landed."
        )
    return None


def restore() -> str | None:
    """Restore the sidecar into the live workflow session.

    Returns ``None`` when the session was restored — or when there was
    simply nothing to restore (no sidecar yet: the ordinary first run).
    Returns one human-worded note when the sidecar exists but couldn't be
    used (unreadable file, damaged JSON, unknown snapshot shape); the live
    session is left untouched in every rejection case. Never raises.
    """
    from ..tools.workflow_patch import import_session_state

    path = sidecar_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        log.warning("Could not read the CLI session sidecar: %s", exc)
        return f"Couldn't read the saved cozy session ({exc}) — starting fresh."

    try:
        snapshot = json.loads(raw)
    except json.JSONDecodeError:
        return (
            "The saved cozy session file is damaged, so this command starts without "
            "it. Your workflow files on disk are untouched."
        )

    err = import_session_state(snapshot)
    if err:
        return f"{err} This command starts without the saved session."
    return None
