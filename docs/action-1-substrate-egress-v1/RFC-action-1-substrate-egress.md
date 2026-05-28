# RFC — ACTION 1: SUBSTRATE EGRESS (record_outcome → in-process Moneta deposit)

**Status.** `DESIGN_ONLY — forge-ready spec, Path D (no code until Jun 16)`. Authored 2026-05-28 by `[EXPERIENCE × ARCHITECT]`.

**Parent.** `docs/rsi-selection-loop-v1/RFC-rsi-selection-loop.md` ("RSI SELECTION LOOP v1 — RFC"). This RFC **discharges** parent escalations **§9/E5(ii)** (outcome egress) and **§9/E6** (consolidation cadence), and supplies the decay physics behind **§9/E1** (passive demotion). Maps to parent verify-items **§0a + §0e + §0f**.

**Build-order position: #1 of 3.** Fixed, SCOUT-confirmed: **Action 1 → Action 3 → RSI loop.**

**Scope.** Convert `record_outcome()` from a local JSONL append into an **in-process Moneta `deposit`**, choose and justify the handle lifecycle, wire the session-end `run_sleep_pass()` trigger, and state the decay physics. This is the egress foundation the loop's reward signal rides.

**Path D.** Markdown only. No code, no `agent/stage/` mutation, no runtime wiring until Jun 16. This is the `[EXEC SPEC]` companion the parent defers; it specifies HOW, it does not build.

---

## Causal lineage *(harness/TRACE.md span schema)*

```
span_id:       a1-s0
parent_id:     RFC-rsi-selection-loop §9/E5(ii)+E6   (causal predecessor, not wall-clock)
pass:          2
step_type:     plan
input_state:   parent RFC §0a NOT-CONFIRMED (record_outcome writes local JSONL only), §0e NOT-CONFIRMED (no run_sleep_pass trigger), §0f CONFIRMED-with-caveats
action:        Spec in-process deposit + long-lived handle + session-end sleep-pass trigger
output_state:  forge-ready Action-1 RFC; egress maps to frozen op deposit 1:1; cadence = session-end
verifier:      L3 (SPEC-fit vs Moneta four-op freeze + S=6) — pending PASS-2 CRUCIBLE
outcome:       success
external_calls: []
```

Substrate annotation *(harness/PLAN.md vocab)*: `comfy-cozy (agent/brain/, agent/integrations/) MODIFY · Moneta CALL-ONLY (four-op freeze, never edit source) · SCRIBE NO-TOUCH (Article-II tripwire — see §A1.4)`.

---

## §A1.1 — Current state *(grounded in source)*

- `record_outcome()` = `agent/brain/memory.py:334` `_handle_record_outcome` → `_append_outcome` (`:295`, write at `:314-317`) → `self.cfg.sessions_dir / "{session}_outcomes.jsonl"` (`:237-240`).
- **Record = 11 fields**, deterministic: `schema_version(=1)`, `timestamp`, `session`, `workflow_summary`, `workflow_hash` (sha256 of `key_params`, 16 hex — `:617-620`), `key_params` (required dict), `model_combo`, `render_time_s`, `quality_score∈[0,1]`, `vision_notes`, `user_feedback∈{positive,negative,neutral}`, `goal_id`.
- **Write durability**: per-session `threading.Lock` (WeakValueDictionary), 10 MB rotation (5 backups), then `json.dumps(sort_keys=True, allow_nan=False)` + `f.flush()` + `os.fsync()`.
- **No cursor / replay / offset exists** for outcomes (grep `cursor|replay|tail|offset` across `agent/`). The only tailer is `agent/integrations/moneta.py` — a **StageEvent** file-watch placeholder (outbox/inbox of StageEvents, never reads outcomes, never calls Moneta `deposit`). Loaders re-scan the full file (`:242-293`).
- **In-process deposit exists only on `feature/moneta-memory`** (`agent/memory/moneta_store.py` — absent from master/working tree). It deposits **conversation exchanges, not outcomes**: long-lived `self._handle = Moneta(config)` in `__init__`; `deposit_exchange` → `eid = self._handle.deposit(payload, embedding)` (`:147`); embedding via `get_encoder()` (384-dim MiniLM, consumer-supplied). `close()` runs `run_sleep_pass()` then `handle.close()`.

## §A1.2 — Target design

`record_outcome()` deposits **in-process** instead of appending JSONL:
- **Payload**: a salient projection of the outcome record — `workflow_summary` + `key_params` + `quality_score` + `user_feedback` + `model_combo` — serialized to the deposit string (the full 11-field record may be retained verbatim if preferred; the projection keeps the embedding signal clean).
- **Embedding**: produced **caller-side** via `get_encoder().encode(payload)` (Moneta loads no embedder; embeddings are consumer-supplied — `api.py:328-333`). Dimension **locks on first deposit** → pin one embedder and set `MonetaConfig.embedding_dim` explicitly to fail fast.
- **Call**: `deposit(payload: str, embedding: List[float], protected_floor: float = 0.0) -> UUID` (`api.py:328`). The returned **UUID is the record's canonical identity** — it replaces `workflow_hash`-as-grouping with a true entity id.

## §A1.3 — Handle lifecycle decision *(resolves parent §6-Q1)*

| Option | Speed | Fork-safety / concurrency | Cadence |
|---|---|---|---|
| **Long-lived** (one handle / `storage_uri` / process, reused) | Warm WAL+snapshot; no re-open cost | Safe: single owner; `_ACTIVE_URIS` enforces one live handle; guard with a `threading.Lock` | Supports session-end `run_sleep_pass` |
| Per-deposit (`with Moneta(...)`) | Re-hydrates ECS from WAL/snapshot **every deposit** | **Unsafe**: `_ACTIVE_URIS` check-then-add is unlocked (TOCTOU); concurrent open → `MonetaResourceLockedError` | Cannot sustain a cadence |

**DECISION: long-lived handle.** One `Moneta(MonetaConfig(...))` per `storage_uri` per process, owned by a module-level store keyed by scope, guarded by a `threading.Lock` — mirroring Comfy-Cozy's existing `_outcomes_locks` WeakValueDictionary and `workflow_patch` lock patterns. **Justification:** `_ACTIVE_URIS` is in-memory, unlocked, and not fork-safe (`api.py:166-169,198-204`), so a single reused handle is the *only* concurrency-safe pattern; per-deposit open also throws away the warm consolidation state and the sleep-pass cadence. Cost (single owner + explicit cleanup) is acceptable on a single-workstation runtime. **Construction:** `MonetaConfig(storage_uri="moneta://comfy-cozy/<scope>", snapshot_path=…, wal_path=…)` (durability needs **both** paths — `api.py:220-249`); `use_real_usd=False` (keeps `api.py` importable without `pxr`); `MonetaConfig.ephemeral()` for tests/dry-run.

## §A1.4 — `run_sleep_pass()` trigger *(§0e / discharges E6)*

- **Trigger = session-end**, inheriting Substrate Egress Axiom 1's session-boundary consolidation. Fires via the long-lived handle's **`close()` path** — `run_sleep_pass()` then `handle.close()` (the exact `feature/moneta-memory` `MonetaStore.close()` pattern) — wired at **process exit / MCP shutdown / cozy-loop session boundary** (mirroring the existing MCP `atexit`/SIGTERM stage flush at `agent/mcp_server.py:490/492`).
- **NOT per-deposit** (would thrash) and **NEVER routed through SCRIBE** — Moneta sits outside the SCRIBE/Article-II persistence chain (it owns its own WAL+snapshot). **Any session-end trigger that would route through SCRIBE is a §9 escalation, not a leaf.**
- **Governance note / correction:** `run_sleep_pass` is the harness lever, *"agents never call it."* There is **no "Hard Rule §12"** in the Moneta repo (exhaustive grep; section refs top out at §15). The governing clause is **`ARCHITECTURE.md §2.1`** (echoed in `api.py:452-457` docstring and `docs/api.md:143-144`). Cite §2.1; the task brief's "§12" is a naming artifact.

## §A1.5 — Idempotency: "the deposit IS the record" *(§0a)*

There is **no cursor/replay to build** — today there is literally zero offset tracking for outcomes (§A1.1). The deposit's returned UUID is the durable identity; **Moneta's own WAL+snapshot is the store of record** and hydrates its ECS on restart (`api.py:220-249`) — no Comfy-Cozy-side replay. Transition:
- **Phase 1 (dual-write):** keep the JSONL append *and* deposit, during cutover, for safety.
- **Phase 2 (cutover):** deposit-only. Then `_load_outcomes` / `_load_all_outcomes` / `get_learned_patterns` (which re-scan JSONL today, `:242-293`) must be rewritten to **`query`** Moneta. **Behavior change to flag:** Intra-Session Blindness means same-session deposits are **not queryable until consolidation**, so `get_recommendations` within a live session changes semantics — call this out at cutover.

## §A1.6 — Decay physics *(§0f — defines the loop's passive demotion)*

- `protected_floor = 0.0` on outcome/recipe deposits → they **are demotable** (a positive floor makes a node immune; `api.py:328-333`).
- Fade is **wall-clock half-life** = `MonetaConfig.half_life_seconds` (default `21600.0` = 6 h, tunable), **not per-pass**.
- Decay is **dormant until an eval point fires** — it runs only inside `query` (eval 1), and `run_sleep_pass`'s reduce + scan (eval 2, 3). With no queries and no sleep pass, nothing fades. This is *why* §A1.4's cadence is mandatory: passive demotion (parent §9/E1) is inert without it.

## §A1.7 — Dependency edge

- **Depends on:** nothing in-set — Action 1 is the foundation (build-order #1). Prerequisites: a pinned embedder (`get_encoder`, MiniLM) and a chosen `storage_uri` scope.
- **Unblocks:** Action 3's captured blueprints become reusable recipes *through this deposit→consolidate→query path*; and the RSI loop's reward deposit (parent §1.4) rides this handle + cadence.

## §A1.8 — Watch-items / failure modes

- `MonetaResourceLockedError` (double-open same `storage_uri`) and `ProtectedQuotaExceededError` (protected deposits past `quota_override=100`) — translate to human language (no raw tracebacks).
- `embedding_dim` locks on first deposit → a later different-length vector raises `ValueError`. Pin the embedder; set `embedding_dim` explicitly.
- Fork-unsafety: a forked child inherits `_ACTIVE_URIS` containing the parent URI → cannot reopen. Single-owner pattern avoids this.
- Intra-Session Blindness (above) — within-session recall gap.
- `get_learned_patterns` query-path rewrite at cutover; dual-write divergence risk during Phase 1.
- Register `handle.close()` at process exit, or the URI lock + snapshot daemon leak.

## §A1.9 — FREEZE CONFIRMATION *(written, per brief)*

**The four-op API is untouched.** Action 1 **consumes** the frozen op `deposit(payload, embedding) -> UUID` 1:1 (and, at cutover, the frozen `query`); it adds, removes, reorders **no** op. `run_sleep_pass()` is the harness lever, invoked from a session-end scheduler, **not extended**.
**The S=6 inverted Safety arc is untouched.** Outcome egress is a memory write, orthogonal to LIVRPS delta composition; no payload, handle, or trigger weakens, reorders, or bounded-queues S (`cognitive/core/delta.py:20-27`). **SCRIBE/Article-II not crossed** (§A1.4). No `agent/stage/` mutation. ✅
