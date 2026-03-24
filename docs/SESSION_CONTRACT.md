# Session Contract — v2.0

## SessionContext API

```python
@dataclass
class SessionContext:
    session_id: str
    workflow: WorkflowSession       # Dict-like, thread-safe (RLock)
    intent_state: dict[str, Any]    # Captures artistic intent per session
    iteration_state: dict[str, Any] # Refinement journey tracking
    demo_state: dict[str, Any]      # Active demo scenario state
    orchestrator_tasks: dict        # Parallel subtask tracking
    created_at: float               # Epoch timestamp
    last_activity: float            # Updated on every access

    def touch() -> None            # Update last_activity
    def age_seconds() -> float     # Seconds since last activity
```

## SessionRegistry API

```python
class SessionRegistry:
    get_or_create(session_id) -> SessionContext  # Thread-safe
    get(session_id) -> SessionContext | None
    destroy(session_id) -> bool
    list_sessions() -> list[str]
    gc_stale(max_age_seconds=3600) -> int  # Never GCs "default"
    count: int                              # Property
    clear() -> None                         # Testing only
```

## State Ownership

| State | Was | Now |
|-------|-----|-----|
| Workflow (load/patch/undo) | `workflow_patch._state` (module-level) | `ctx.workflow` |
| Discovery cache | `comfy_discover._cache` (module-level dict) | Process-level `DiscoveryCache` (bounded, shared) |
| Intent capture | `intent_collector._instance` (singleton) | `ctx.intent_state` |
| Iteration tracking | `iteration_accumulator._instance` (singleton) | `ctx.iteration_state` |
| Demo scenarios | `demo._demo_state` (module-level) | `ctx.demo_state` |
| Orchestrator tasks | `orchestrator._tasks` (module-level) | `ctx.orchestrator_tasks` |
| Brain config | `_sdk._integrated_config` (singleton) | Per-session via registry |

## Thread-Safety

- `WorkflowSession` uses `threading.RLock` for all dict operations
- `SessionRegistry` uses `threading.Lock` for session map access
- `DiscoveryCache` uses `threading.Lock` for cache operations
- Each `SessionContext` can be safely accessed from multiple threads

## Lifecycle

1. **Create**: `get_session_context(session_id)` or `registry.get_or_create(session_id)`
2. **Use**: Pass `ctx` through `handle()` dispatch chain
3. **Persist**: Sessions can be serialized via `save_session` tool
4. **GC**: `registry.gc_stale()` removes sessions idle >1 hour (never "default")
5. **Destroy**: `registry.destroy(session_id)` for explicit cleanup

## Backward Compatibility

- `ctx=None` in `handle()` falls back to default session (v1 behavior)
- All 1290 existing tests pass without modification
- Module-level `_state` in `workflow_patch.py` still works (points to default session)
- Discovery cache is process-level (not session-scoped) — shared data is acceptable

## DiscoveryCache

```python
class DiscoveryCache:
    max_entries: int = 1000
    ttl_seconds: float = 300  # 5 minutes
    get(key) -> Any | None     # Returns None if missing or expired
    set(key, value) -> None    # LRU eviction when full
    invalidate(key) -> None
    clear() -> None
    size: int                  # Property
    stats() -> dict
```
