# Q1 Verification Verdict — LIVRPS Odometer Invariant

**Protocol applied:** `[PROTOCOL: LIVRPS Odometer Invariant Verification]`
from `docs/substrate-egress-v1.1/source/GEMINI_RESPONSE_SUBSTRATE_EGRESS_R6.md`
§ Q1.

**Target:** Moneta repo at `C:/Users/User/Moneta` (HEAD `83549dd`,
branch `main`). Read-only audit; no Moneta code modified.

**Date:** 2026-05-05.

---

## Verdict

**`FALLBACK_REQUIRED`** — with the strongest possible signal: the
class the protocol assumes does not exist in Moneta.

> **Cascading consequence (per R6 § 4 synthesis-killer call):**
> *"if the Q1 protocol returns `FALLBACK_REQUIRED`, the demo arc
> language must be audited: without a native LIVRPS integer, the 1:1
> scalar mapping of tick-to-UI-state is lost, so the demo cannot
> claim frame-perfect UI synchronization during replay."*
>
> **→ DEMO ARC AUDIT FIRES.**

---

## Step 1 [LOCATE]

**Looking for:** the LIVRPS method responsible for committing a new
cognitive intent to the bounded working-memory deque.

**Found:** no such method exists in Moneta.

Moneta's hot-tier abstractions are not a deque. The protocol's
assumed shape (a `collections.deque(maxlen=...)` holding intents,
with an `append` method that commits one) is absent from the
codebase.

The closest semantic analogs and why each fails the locate criterion:

| Candidate | File:line | Why it fails the criterion |
|---|---|---|
| `Moneta.deposit` | `src/moneta/api.py:328-377` | Commits a new memory, but to an ECS struct-of-arrays (not a deque). Bound is `MonetaConfig.max_entities` (default 10000), enforced via consolidation/pruning at sleep pass — **not via deque eviction (`popleft`)**. The ECS has no `maxlen`. |
| `AttentionLog.append` | `src/moneta/attention_log.py:71-73` | Appends a `(entity_id, weight, timestamp)` tuple to a Python list (`self._buffer`). **Unbounded** — the buffer grows freely until the next sleep-pass `drain()` swaps it out. Not a deque. The signal is *attention reinforcement*, not a *cognitive intent commit*. |
| `ECS.add` | `src/moneta/ecs.py` (parallel column write) | Backs `Moneta.deposit`; same struct-of-arrays story. |

Moneta's own scout audit reaches the same conclusion in plain language
(`SCOUT_MONETA_v0_3.md:93`):

> **Spine indexing.** There is **no monotonic step counter and no
> spine prim**. Each rolling daily sublayer is named purely from the
> UTC date of `authored_at` (`_rolling_sublayer_base()` at
> `usd_target.py:90`), with rotation-suffix `_001`, `_002` triggered
> on prim-count cap. Within a sublayer, prims are addressed only by
> `/Memory_<entity_id_hex>` — no parent xform, no time-index spine,
> no scope. The sublayer file name is the only temporal index, and
> it has 1-day granularity.

And on the LIVRPS framing itself (`SCOUT_MONETA_v0_3.md:63`):

> **LIVRPS arcs actually composed: only Local + Sublayer-stack
> ordering.** Inherits, Variants, References, Payloads, Specializes
> are never authored. The composition story today is "stronger
> sublayer position wins"; nothing else is exercised.

**Locate result:** boundary not found.

---

## Step 2 [ISOLATE]

Per the protocol: *"Enumerate all integer properties or state-dict
values mutated within this method. If None → RETURN `FALLBACK_REQUIRED`."*

**No method to enumerate inside.** For completeness, the closest
analogs:

- **`Moneta.deposit` (`api.py:328-377`):** Mutates `self.ecs.*`
  parallel columns (string-of-arrays), `self.vector_index`, and
  calls `self.consolidation.mark_activity(now * 1000)`. **No
  `self._tick`, `self._step_counter`, `self._sequence`, or any
  monotonic class-level integer attribute.** No `+= 1` on any class
  attribute in the deposit path.
- **`AttentionLog.append` (`attention_log.py:71-73`):** Mutates
  `self._buffer` (a list). Single line: `self._buffer.append(...)`.
  **No integer mutation.**
- **`ECS.apply_attention` (`ecs.py:215`):** Contains `updated += 1`,
  but `updated` is a **local-variable loop counter** scoped to the
  function, returned to the caller (`reduce_attention_log`). **Not a
  class attribute.** Fails the protocol's enumeration criterion (the
  protocol targets persistent class-level state).

**Cross-check on the rest of `src/moneta/`:** grep for `+= 1`
across `ecs.py`, `api.py`, `consolidation.py` returns exactly one hit
(the local `updated += 1` above). No other persistent integer
incrementers exist.

**Isolate result:** zero class-level integer candidates.

---

## Step 3 [DECOUPLING AUDIT]

Vacuous — no candidates to audit. (Recorded for traceability.)

---

## Step 4 [COVERAGE AUDIT]

Vacuous — no candidates to audit. (Recorded for traceability.)

---

## Step 5 [EVALUATE]

Per the protocol decision tree:

> *If zero candidates survive → RETURN `FALLBACK_REQUIRED`.*

Zero candidates not only survive — zero candidates exist. The
verdict is `FALLBACK_REQUIRED` at the strongest level (target
structure absent, not merely structurally coupled).

---

## Why this is `FALLBACK_REQUIRED` and not `PARTIAL_REFINE_CONTRACT`

`PARTIAL_REFINE_CONTRACT` would require a valid private counter that
could be exposed via a property. Moneta has no such counter, public
or private. There is nothing to refine into a contract; there is no
substrate-side artifact to expose.

`PRIMARY_OK` would require a public, monotonic, decoupled integer
attribute on the intent-commit method. Same absence.

---

## Forward action (Comfy-Cozy side)

1. **Demo arc language audit.** Per R6 § 4: the demo cannot claim
   frame-perfect UI synchronization during replay using a Moneta-side
   tick. That language must be removed or qualified in
   `MISSION_SUBSTRATE_EGRESS_V1.1_DELTA.md` and any downstream
   surfaces.

2. **Substrate-side options to surface to Joe.** None of these are
   adopted by this verdict; they are the option space that opens
   when `FALLBACK_REQUIRED` is the outcome:
   - **(a)** Add a monotonic step counter to Moneta's `Moneta` handle
     or `AttentionLog`. Requires MONETA.md §9 escalation — would
     touch the locked concurrency primitive (Decision #3) by adding
     class-level mutable state to a structure currently designed to
     be lock-free under the GIL via swap-and-drain.
   - **(b)** Synthesize the tick on the Comfy-Cozy side from
     `Memory.last_evaluated` (wall-clock unix seconds) — but this
     fails the protocol's *"decoupled from wall-clock time"* guard,
     re-creating the false-positive failure mode the protocol
     explicitly rules out.
   - **(c)** Synthesize the tick from ECS insertion order via
     `len(ecs._ids)` at deposit time — fails Step 3 decoupling
     (derived from `len()`).
   - **(d)** Accept that Moneta's temporal index is sublayer-file
     granularity (1 day, per `_rolling_sublayer_base()` at
     `usd_target.py:90`) and design the demo arc around session-UUID
     boundaries instead of intra-session causal sequencing.
   - Option **(d)** is the only one that does not require either a
     §9 escalation in Moneta or a guard violation in the protocol.

3. **R5 contract derivation impact.** R6 § 4 already flagged this:
   *"if the Q1 protocol returns FALLBACK_REQUIRED, the demo arc
   language must be audited."* That advisory is now load-bearing.

---

## Evidence index (file:line)

| Citation | Source | What it shows |
|---|---|---|
| `attention_log.py:1-37` (module docstring) | Moneta | AttentionLog is append + swap-and-drain on a Python list, not a deque |
| `attention_log.py:63-69` | Moneta | `__init__` initializes `self._buffer: list = []` and asserts GIL — no integer counters initialized |
| `attention_log.py:71-73` | Moneta | `append` mutates only `self._buffer.append(...)` |
| `attention_log.py:75-83` | Moneta | `drain` swap reassigns `self._buffer = []`; no integer mutation |
| `api.py:328-377` | Moneta | `Moneta.deposit` writes to ECS columns + vector index; no class-level integer counter |
| `ecs.py:215` | Moneta | Only `+= 1` in core path is `updated`, a local-variable loop counter (returned, not retained) |
| `SCOUT_MONETA_v0_3.md:63` | Moneta | "LIVRPS arcs actually composed: only Local + Sublayer-stack ordering." |
| `SCOUT_MONETA_v0_3.md:93` | Moneta | "There is no monotonic step counter and no spine prim." |
| `usd_target.py:90` | Moneta | `_rolling_sublayer_base()` — sublayer naming is UTC-date-only, 1-day granularity |
| `MONETA.md` Locked decisions §3 | Moneta | Concurrency primitive locked: append-only attention log, no locks. Adding a class-level monotonic counter would touch this. |

---

**Verdict (final):** `FALLBACK_REQUIRED`. **Demo arc audit fires.**
