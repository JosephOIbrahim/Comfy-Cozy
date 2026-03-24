"""Bounded discovery cache with TTL and LRU eviction.

Replaces the unbounded module-level _cache dict in comfy_discover.py.
Process-level (not session-scoped) — discovery data is shared across
sessions since it reflects the ComfyUI installation, not user state.
"""

import threading
import time
from typing import Any


class DiscoveryCache:
    """Thread-safe bounded cache with TTL expiry and LRU eviction."""

    def __init__(self, max_entries: int = 1000, ttl_seconds: float = 300.0):
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._data: dict[str, dict[str, Any]] = {}
        self._access_times: dict[str, float] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        """Get a cached value, returning None if missing or expired."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if time.time() - entry["ts"] > self.ttl_seconds:
                del self._data[key]
                self._access_times.pop(key, None)
                return None
            self._access_times[key] = time.time()
            return entry["value"]

    def set(self, key: str, value: Any) -> None:
        """Set a cached value, evicting LRU entries if at capacity."""
        with self._lock:
            if key not in self._data and len(self._data) >= self.max_entries:
                self._evict_lru()
            self._data[key] = {"value": value, "ts": time.time()}
            self._access_times[key] = time.time()

    def invalidate(self, key: str) -> None:
        """Remove a single cache entry."""
        with self._lock:
            self._data.pop(key, None)
            self._access_times.pop(key, None)

    def clear(self) -> None:
        """Remove all cache entries."""
        with self._lock:
            self._data.clear()
            self._access_times.clear()

    def _evict_lru(self) -> None:
        """Evict the least recently used entry. Caller holds lock."""
        if not self._access_times:
            return
        oldest_key = min(self._access_times, key=self._access_times.get)
        self._data.pop(oldest_key, None)
        self._access_times.pop(oldest_key, None)

    @property
    def size(self) -> int:
        """Current number of entries."""
        with self._lock:
            return len(self._data)

    def stats(self) -> dict[str, Any]:
        """Cache statistics for diagnostics."""
        with self._lock:
            return {
                "entries": len(self._data),
                "max_entries": self.max_entries,
                "ttl_seconds": self.ttl_seconds,
            }
