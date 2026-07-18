#!/usr/bin/env python3
"""Verify the Comfy-Cozy -> ComfyUI symlink chain is intact before launch.

The whole panel integration rides on a chain of symlinks that ComfyUI's repo
never records. If any link dangles, ComfyUI boots a panel-less UI with no clue
why. Run this from the launcher before starting ComfyUI so a broken link fails
loud instead of silently.

Exits 0 if every link resolves to its expected target, non-zero otherwise.
Prints one line per check. Pairs with launch_comfyui_stable.bat.
"""
from __future__ import annotations

import os
import sys

# (label, link path as ComfyUI sees it, expected real target on disk)
CHECKS = [
    (
        "custom_nodes",
        r"G:\COMFY\ComfyUI\custom_nodes",
        r"G:\COMFYUI_Database\Custom_Nodes",
    ),
    (
        "comfy-cozy-panel",
        r"G:\COMFYUI_Database\Custom_Nodes\comfy-cozy-panel",
        r"G:\Comfy-Cozy\panel",
    ),
    (
        "comfy-cozy-ui",
        r"G:\COMFYUI_Database\Custom_Nodes\comfy-cozy-ui",
        r"G:\Comfy-Cozy\ui",
    ),
    (
        "comfy_agent_bridge",
        r"G:\COMFYUI_Database\Custom_Nodes\comfy_agent_bridge",
        r"G:\Comfy-Cozy\node_pack\comfy_agent_bridge",
    ),
]


def check(label: str, link: str, expected: str) -> bool:
    """Return True if `link` resolves to `expected` and the target exists."""
    if not os.path.exists(link) and not os.path.islink(link):
        print(f"  X  {label}: MISSING -> {link}")
        return False
    real = os.path.realpath(link)
    want = os.path.realpath(expected)
    if real != want:
        print(f"  X  {label}: WRONG TARGET")
        print(f"       link   : {link}")
        print(f"       points: {real}")
        print(f"       want  : {want}")
        return False
    if not os.path.isdir(real):
        print(f"  X  {label}: target not a dir -> {real}")
        return False
    print(f"  OK  {label} -> {real}")
    return True


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_agent_import() -> bool:
    """The bridge auth gate fails CLOSED when the agent package cannot import,
    which turns every /agent/* route into a 503 — and panel route setup is
    skipped entirely. Abort the launch loud instead of booting a husk."""
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    try:
        from agent._session_helpers import allowed_origins  # noqa: F401
        from agent.config import MCP_AUTH_TOKEN  # noqa: F401
    except Exception as exc:
        print(f"  X  agent import FAILED in {sys.executable}")
        print(f"       {type(exc).__name__}: {exc}")
        print("       Bridge routes would refuse everything (fail-closed);")
        print("       panel routes would be skipped. Fix the import first.")
        return False
    print("  OK agent package imports (bridge auth layer available)")
    return True


def check_pip_metadata() -> bool:
    """Warn (never fail) when pip metadata or console scripts drift from
    source — it breaks the cozy CLI, not the canvas, so don't block launch."""
    import importlib.metadata as md
    import shutil

    fix = "python -m pip install -e G:\\Comfy-Cozy --no-deps"
    try:
        import agent
        src_ver = agent.__version__
    except Exception:
        return True  # already reported by check_agent_import
    try:
        dist_ver = md.version("comfy-cozy")
    except md.PackageNotFoundError:
        print("  !  pip: 'comfy-cozy' not installed in this python")
        print(f"       fix: {fix}")
        return True
    if dist_ver != src_ver:
        print(f"  !  pip metadata drift: installed {dist_ver} != source {src_ver}")
        print(f"       fix: {fix}")
        return True
    missing = [c for c in ("cozy", "comfy-cozy") if shutil.which(c) is None]
    if missing:
        print(f"  !  console script(s) missing from PATH: {', '.join(missing)}")
        print(f"       fix: {fix}")
        return True
    print(f"  OK pip comfy-cozy {dist_ver} == source; cozy CLI on PATH")
    return True


def check_env_paths() -> bool:
    """Warn when .env lacks the live-install overrides — without them the
    agent resolves output/blueprints against stale COMFYUI_Database paths."""
    env_path = os.path.join(REPO_ROOT, ".env")
    keys: dict[str, str] = {}
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                s = line.strip()
                if s and not s.startswith("#") and "=" in s:
                    k, v = s.split("=", 1)
                    keys[k.strip()] = v.strip()
    for key in ("COMFYUI_INSTALL_DIR", "COMFYUI_OUTPUT_DIR"):
        val = keys.get(key)
        if not val:
            print(f"  !  .env missing {key} — agent falls back to stale Database paths")
        elif not os.path.isdir(val):
            print(f"  !  .env {key}={val} does not exist on disk")
        else:
            print(f"  OK .env {key} -> {val}")
    return True


def check_stale_compressed() -> bool:
    """FAIL if any .br/.gz sibling is OLDER than its source. aiohttp's static
    handler serves precompressed siblings with no freshness comparison, so a
    stale one silently masks every edit to the real file. Fresh siblings
    (deliberate precompression) pass."""
    import glob

    stale: list[str] = []
    fresh = 0
    for webdir in ("panel", "ui"):
        pattern = os.path.join(REPO_ROOT, webdir, "web", "**", "*")
        for comp in glob.glob(pattern, recursive=True):
            if not comp.endswith((".br", ".gz")):
                continue
            src = comp.rsplit(".", 1)[0]
            if os.path.exists(src) and os.path.getmtime(comp) < os.path.getmtime(src):
                stale.append(comp)
            else:
                fresh += 1
    if stale:
        print(f"  X  {len(stale)} stale precompressed asset(s) would shadow-serve old bytes:")
        for s in stale[:5]:
            print(f"       {s}")
        print("       fix: delete them (or regenerate from current sources)")
        return False
    if fresh:
        print(f"  OK {fresh} precompressed asset(s), all fresh")
    else:
        print("  OK no precompressed web assets")
    return True


def check_python() -> bool:
    """Bonus: surface Python version. Warn (not fail) on 3.14 — cp314 wheel gaps."""
    ver = sys.version_info
    tag = f"{ver.major}.{ver.minor}.{ver.micro}"
    if ver.major == 3 and ver.minor == 14:
        print(f"  !  python {tag}  (cp314 wheel gaps are the first hypothesis for import errors)")
        return True  # warning, not a hard fail
    if ver.major != 3 or ver.minor < 3 and not (ver.major == 3 and ver.minor >= 10):
        print(f"  !  python {tag}  (Comfy-Cozy expects 3.10+; 3.12 recommended)")
        return True
    print(f"  OK python {tag}")
    return True


def main() -> int:
    print("Comfy-Cozy launch preflight")
    print("-" * 44)
    links_ok = all(check(label, link, want) for label, link, want in CHECKS)
    agent_ok = check_agent_import()
    fresh_ok = check_stale_compressed()
    check_pip_metadata()   # warn-only: breaks the CLI, not the canvas
    check_env_paths()      # warn-only
    check_python()
    print("-" * 44)
    if links_ok and agent_ok and fresh_ok:
        print("Comfy-Cozy contract intact.")
        return 0
    print("FAILED: the Comfy-Cozy contract is broken (see X lines above).")
    print("ComfyUI would boot degraded. Fix the failures before launching.")
    return 1


if __name__ == "__main__":
    sys.exit(main())