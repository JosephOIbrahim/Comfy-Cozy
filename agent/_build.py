"""Build identity captured once per process, computed lazily on first access.

Lets a running process report the git commit it actually LOADED, so a stale
server (one launched before a later merge) is detectable: compare this hash to
the on-disk ``git rev-parse --short HEAD``; a mismatch means the process is
running old code and needs a restart. Captured ONCE (first attribute access,
via PEP 562 ``__getattr__``, then cached in module globals) — re-reading at
call time would just echo the current on-disk HEAD and defeat the purpose.
Laziness keeps the two git subprocesses off the import path.

``cwd`` is pinned to the repo root via ``__file__`` (NOT the process cwd),
because the embedded-in-ComfyUI launch runs from a different working directory.
If git is absent/fails (e.g. a future packaged build), this degrades gracefully
to ``hash="unknown"``, ``dirty=None``; the build-stamp/env fallback tier is
intentionally not built — no packaged launch exists today.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    BUILD_HASH: str
    BUILD_DIRTY: bool | None

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


def __getattr__(name: str):
    """Compute BUILD_HASH / BUILD_DIRTY on first access, then cache (PEP 562)."""
    if name == "BUILD_HASH":
        value: "str | bool | None" = _compute_hash()
    elif name == "BUILD_DIRTY":
        value = _compute_dirty()
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


def __dir__() -> "list[str]":
    return [*globals(), "BUILD_HASH", "BUILD_DIRTY"]
