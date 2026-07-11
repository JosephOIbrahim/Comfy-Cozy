"""Build identity captured at import time.

Lets a running process report the git commit it actually LOADED, so a stale
server (one launched before a later merge) is detectable: compare this hash to
the on-disk ``git rev-parse --short HEAD``; a mismatch means the process is
running old code and needs a restart. Captured ONCE at import — re-reading at
call time would just echo the current on-disk HEAD and defeat the purpose.

``cwd`` is pinned to the repo root via ``__file__`` (NOT the process cwd),
because the embedded-in-ComfyUI launch runs from a different working directory.
If git is absent/fails (e.g. a future packaged build), this degrades gracefully
to ``hash="unknown"``, ``dirty=None``; the build-stamp/env fallback tier is
intentionally not built — no packaged launch exists today.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(*args: str) -> "str | None":
    """Run a git command from the repo root; return stripped stdout or None."""
    if not ((_REPO_ROOT / ".git").exists() and (_REPO_ROOT / "pyproject.toml").is_file()):
        return None
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _compute_hash() -> str:
    h = _git("rev-parse", "--short", "HEAD")
    return h if h else "unknown"


def _compute_dirty() -> "bool | None":
    porcelain = _git("status", "--porcelain")
    if porcelain is None:
        return None
    return bool(porcelain)


# Captured ONCE at import — the commit this process loaded.
BUILD_HASH: str = _compute_hash()
BUILD_DIRTY: "bool | None" = _compute_dirty()
