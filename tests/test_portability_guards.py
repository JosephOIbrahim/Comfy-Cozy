"""Portability guards — fail fast on Windows-hostile patterns in non-test source.

Backstops docs/IMPROVEMENT_AREAS_JUNE_2026.md item #1. Three tests assert ZERO
occurrences in ``agent/`` and ``cognitive/`` (non-test source) of:
  1. module-top POSIX-only imports (resource|fcntl|pwd|grp|termios) outside
     try/except ImportError
  2. shutil.move( / os.rename( used as an atomic-write finalizer (prefer os.replace)
  3. datetime.utcnow()  (deprecated 3.12+)

Pure stdlib (os, re, pathlib). Occurrences under any ``tests/`` directory and
inside try/except ImportError blocks are excluded by design. Each failure lists
offending ``file:line`` so a fix is one click away.
"""

import re
from pathlib import Path

# Repo root = parent of this tests/ directory.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SOURCE_DIRS = ("agent", "cognitive")

# Pattern 1: module-top POSIX-only imports.
_POSIX_IMPORT_RE = re.compile(
    r"^\s*(?:import|from)\s+(resource|fcntl|pwd|grp|termios)\b"
)
# Pattern 2: shutil.move( or os.rename( (literal forms named by the doc).
_MOVE_RENAME_RE = re.compile(r"\b(?:shutil\.move|os\.rename)\s*\(")
# Pattern 3: datetime.utcnow().
_UTCNOW_RE = re.compile(r"\butcnow\s*\(")


def _iter_source_files():
    """Yield non-test .py files under agent/ and cognitive/."""
    for top in _SOURCE_DIRS:
        base = _REPO_ROOT / top
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            # Skip anything under a tests/ directory at any depth.
            if "tests" in path.parts:
                continue
            yield path


def _read_lines(path):
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _in_try_importerror_block(lines, idx):
    """True if line ``idx`` (0-based) is inside a try: ... except ImportError block.

    Walks upward looking for an enclosing ``try:`` whose indentation is shallower
    than the current line, then confirms a matching ``except (...ImportError...)``
    handler exists at that same try-indent level. This is a heuristic sufficient
    for guarded optional imports, which are the only case the doc tolerates.
    """
    cur_indent = len(lines[idx]) - len(lines[idx].lstrip())
    # Find the nearest enclosing try: above this line.
    try_indent = None
    try_line = None
    for j in range(idx - 1, -1, -1):
        line = lines[j]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent < cur_indent and re.match(r"try\s*:", stripped):
            try_indent = indent
            try_line = j
            break
        # A shallower non-try statement means no enclosing try for this line.
        if indent < cur_indent and not re.match(r"try\s*:", stripped):
            # Keep scanning — a try may still enclose at an even shallower level.
            cur_indent = indent
    if try_line is None:
        return False
    # Confirm a matching except ImportError at the try's indent level, below idx.
    for j in range(try_line + 1, len(lines)):
        line = lines[j]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent < try_indent:
            break  # left the try/except suite entirely
        if indent == try_indent and stripped.startswith("except"):
            if "ImportError" in stripped or "ModuleNotFoundError" in stripped:
                return True
            # Some other except at try-level; keep looking for an ImportError one.
    return False


def _scan(pattern, *, allow_guarded_import=False):
    """Return list of 'relpath:lineno' for pattern matches in non-test source."""
    hits = []
    for path in _iter_source_files():
        lines = _read_lines(path)
        for i, line in enumerate(lines):
            if not pattern.search(line):
                continue
            if allow_guarded_import and _in_try_importerror_block(lines, i):
                continue
            rel = path.relative_to(_REPO_ROOT).as_posix()
            hits.append(f"{rel}:{i + 1}")
    return hits


def test_no_unguarded_posix_imports():
    """POSIX-only modules must be imported only inside try/except ImportError."""
    hits = _scan(_POSIX_IMPORT_RE, allow_guarded_import=True)
    assert not hits, (
        "Unguarded POSIX-only imports (resource|fcntl|pwd|grp|termios) "
        "outside try/except ImportError:\n  " + "\n  ".join(hits)
    )


def test_no_shutil_move_or_os_rename_finalizers():
    """Prefer os.replace over shutil.move(/os.rename( for atomic-write finalizers."""
    hits = _scan(_MOVE_RENAME_RE)
    assert not hits, (
        "shutil.move(/os.rename( found (prefer os.replace for cross-platform "
        "atomic overwrite):\n  " + "\n  ".join(hits)
    )


def test_no_datetime_utcnow():
    """datetime.utcnow() is deprecated 3.12+; use datetime.now(timezone.utc)."""
    hits = _scan(_UTCNOW_RE)
    assert not hits, (
        "datetime.utcnow() found (deprecated 3.12+; use "
        "datetime.now(timezone.utc)):\n  " + "\n  ".join(hits)
    )
