"""workflow.lock — reproducibility sidecar (hardening doc 3.8).

Re-running a workflow weeks later is not reproducible if a node pack
updated or a model file changed underneath it. ``save_workflow`` writes a
``<name>.lock.json`` sidecar pinning what the graph depends on; the
validate step compares the live environment against it and surfaces
"drifted since lock" WARNINGS — drift informs, it never blocks.

Pinned per lock: ComfyUI version (live /system_stats), each referenced
model file's SHA-256 + size/mtime, and each custom node pack's installed
git commit (read from .git/HEAD — pure file reads, no subprocess). Core
nodes have no pack entry; they are covered by the ComfyUI version pin.

Hash cost: checkpoints run to 12 GB, so SHA-256 results are cached
in-process keyed by (path, size, mtime_ns) and reused from an existing
sidecar when the stat matches — re-saving an unchanged graph never
re-hashes, and validate re-hashes only when a stat actually changed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from pathlib import Path

from ..config import CUSTOM_NODES_DIR, MODELS_DIR
from ._util import to_json

log = logging.getLogger(__name__)

LOCK_SCHEMA = 1
_HASH_CHUNK = 4 * 1024 * 1024

# (resolved path, size, mtime_ns) -> sha256 hex. In-process only; the
# persistent layer is the previous sidecar (same stat => reuse its hash).
_hash_cache: dict[tuple[str, int, int], str] = {}
_hash_lock = threading.Lock()


def lock_path_for(workflow_path: str | Path) -> Path:
    """Sidecar path: <workflow>.lock.json next to the workflow file."""
    p = Path(workflow_path)
    return p.with_name(p.name + ".lock.json")


def _stat_key(path: Path) -> tuple[str, int, int] | None:
    try:
        st = path.stat()
        return (str(path.resolve()), st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def _sha256_file(path: Path, prior: dict | None = None) -> dict:
    """Hash one model file, serving from the stat-keyed caches when possible.

    Returns {"sha256", "size", "mtime_ns"}; raises OSError on read failure.
    ``prior`` is this file's entry from an existing sidecar — when its
    size/mtime match the live stat, its hash is trusted (the same
    assumption the in-process cache makes).
    """
    key = _stat_key(path)
    if key is None:
        raise OSError(f"cannot stat {path}")
    with _hash_lock:
        hit = _hash_cache.get(key)
    if hit is None and prior is not None:
        if prior.get("size") == key[1] and prior.get("mtime_ns") == key[2]:
            hit = prior.get("sha256")
    if hit is None:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(_HASH_CHUNK):
                h.update(chunk)
        hit = h.hexdigest()
        with _hash_lock:
            _hash_cache[key] = hit
    return {"sha256": hit, "size": key[1], "mtime_ns": key[2]}


def _resolve_model(name: str) -> Path | None:
    """Resolve a model input value (may carry a subfolder) under MODELS_DIR."""
    candidate = MODELS_DIR / name
    if candidate.is_file():
        return candidate
    base = Path(name.replace("\\", "/")).name
    try:
        return next((p for p in MODELS_DIR.rglob(base) if p.is_file()), None)
    except OSError:
        return None


def _read_git_commit(pack_dir: Path) -> str:
    """Installed pack's git HEAD commit via file reads (no subprocess)."""
    git = pack_dir / ".git"
    try:
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref: "):
            return head  # detached HEAD: the commit itself
        ref = head[5:].strip()
        ref_file = git / ref
        if ref_file.is_file():
            return ref_file.read_text(encoding="utf-8").strip()
        packed = git / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.endswith(" " + ref):
                    return line.split(" ", 1)[0]
    except OSError:
        pass
    return "unknown"


def _installed_pack_dir(url: str) -> Path | None:
    """Best-effort map of a pack's repo URL to its Custom_Nodes directory."""
    tail = url.rstrip("/").rsplit("/", 1)[-1].lower()
    try:
        for d in CUSTOM_NODES_DIR.iterdir():
            if d.is_dir() and d.name.lower() in (tail, tail.replace("_", "-")):
                return d
    except OSError:
        pass
    return None


def _live_comfyui_version() -> str:
    try:
        from .comfy_api import _get
        return str(_get("/system_stats", timeout=5.0).get("system", {})
                   .get("comfyui_version", "unknown"))
    except Exception:
        return "unknown"


def build_lock(workflow: dict, workflow_bytes: bytes, prior_lock: dict | None = None) -> dict:
    """Build the lock dict for an API-format workflow about to be saved."""
    from .model_compat import _extract_models_from_workflow

    models: dict[str, dict] = {}
    for name in _extract_models_from_workflow(workflow):
        path = _resolve_model(name)
        if path is None:
            models[name] = {"missing": True}
            continue
        prior = ((prior_lock or {}).get("models") or {}).get(name)
        try:
            entry = _sha256_file(path, prior=prior)
        except OSError as e:
            models[name] = {"missing": True, "error": str(e)}
            continue
        entry["path"] = str(path)
        models[name] = entry

    packs: dict[str, dict] = {}
    unmapped: list[str] = []
    try:
        from .comfy_discover import _build_node_to_pack
        index = _build_node_to_pack()
    except Exception:
        index = {}
    for node in workflow.values():
        ct = node.get("class_type") if isinstance(node, dict) else None
        if not ct:
            continue
        info = index.get(ct)
        if info is None:
            # Core/builtin node — covered by the comfyui_version pin.
            continue
        title = info.get("title") or info.get("url", ct)
        if title in packs:
            continue
        pack_dir = _installed_pack_dir(info.get("url", ""))
        if pack_dir is None:
            packs[title] = {"url": info.get("url", ""), "commit": "unknown"}
            unmapped.append(ct)
        else:
            packs[title] = {
                "url": info.get("url", ""),
                "dir": pack_dir.name,
                "commit": _read_git_commit(pack_dir),
            }

    return {
        "schema": LOCK_SCHEMA,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "comfyui_version": _live_comfyui_version(),
        "workflow_sha256": hashlib.sha256(workflow_bytes).hexdigest(),
        "models": models,
        "packs": packs,
        "unmapped_node_classes": sorted(set(unmapped)),
    }


def write_lock_sidecar(workflow_path: str | Path, workflow: dict, workflow_bytes: bytes) -> Path:
    """Write <workflow>.lock.json (best-effort caller; exceptions propagate)."""
    lock_file = lock_path_for(workflow_path)
    prior = None
    try:
        if lock_file.is_file():
            prior = json.loads(lock_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        prior = None
    lock = build_lock(workflow, workflow_bytes, prior_lock=prior)
    lock_file.write_text(to_json(lock, indent=2), encoding="utf-8")
    return lock_file


def check_lock_drift(workflow_path: str | Path) -> list[str]:
    """Compare the live environment against the sidecar; return warnings.

    Cheap path: stat compare per model (re-hash ONLY when size/mtime
    drifted, to confirm a real content change); .git/HEAD re-read per
    pack; one pooled /system_stats call for the version. No sidecar or an
    unreadable one returns [] — the lock is opt-in provenance, not a gate.
    """
    lock_file = lock_path_for(workflow_path)
    try:
        if not lock_file.is_file():
            return []
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    warnings: list[str] = []
    for name, entry in sorted((lock.get("models") or {}).items()):
        if entry.get("missing"):
            continue
        path = Path(entry.get("path", ""))
        key = _stat_key(path) if entry.get("path") else None
        if key is None:
            warnings.append(f"Locked model '{name}' is no longer at {entry.get('path')}.")
            continue
        if key[1] == entry.get("size") and key[2] == entry.get("mtime_ns"):
            continue
        try:
            live = _sha256_file(path)
        except OSError:
            warnings.append(f"Locked model '{name}' can no longer be read.")
            continue
        if live["sha256"] != entry.get("sha256"):
            warnings.append(
                f"Model '{name}' drifted since lock: sha256 "
                f"{entry.get('sha256', '?')[:12]}… → {live['sha256'][:12]}…"
            )
    for title, entry in sorted((lock.get("packs") or {}).items()):
        locked = entry.get("commit", "unknown")
        if locked == "unknown" or "dir" not in entry:
            continue
        live = _read_git_commit(CUSTOM_NODES_DIR / entry["dir"])
        if live != "unknown" and live != locked:
            warnings.append(
                f"Node pack '{title}' drifted since lock: commit "
                f"{locked[:10]} → {live[:10]}."
            )
    locked_ver = lock.get("comfyui_version", "unknown")
    if locked_ver != "unknown":
        live_ver = _live_comfyui_version()
        if live_ver != "unknown" and live_ver != locked_ver:
            warnings.append(
                f"ComfyUI drifted since lock: {locked_ver} → {live_ver}."
            )
    return warnings
