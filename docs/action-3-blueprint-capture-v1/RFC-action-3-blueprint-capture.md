# RFC — ACTION 3: BLUEPRINT CAPTURE (serialize the resolved-LIVRPS stack)

**Status.** `DESIGN_ONLY — forge-ready spec, Path D (no code until Jun 16)`. Authored 2026-05-28 by `[GRAPH × ARCHITECT]`.

**Parent.** `docs/rsi-selection-loop-v1/RFC-rsi-selection-loop.md` ("RSI SELECTION LOOP v1 — RFC"). This RFC **discharges** parent escalation **§9/E4** and **§9/E5(i)**. Maps to parent verify-item **§0b (the CRUX)** and creates the parent's **§3 "learned unit"**, which does not exist today.

**Build-order position: #2 of 3.** Fixed, SCOUT-confirmed: Action 1 → **Action 3** → RSI loop.

**Scope.** Make the autonomous path produce and **serialize the resolved-LIVRPS stack** (the compiled blueprint), add a content-addressed **cache keyed by intent** with **layer-level invalidation**, and keep all of it **strictly above** the composition engine — the six-level priority semantics are patent IP and are not touched.

**Path D.** Markdown only. No code, no `agent/stage/` mutation, no runtime wiring until Jun 16. Specifies HOW; does not build.

---

## Causal lineage *(harness/TRACE.md span schema)*

```
span_id:       a3-s0
parent_id:     RFC-rsi-selection-loop §9/E4+E5(i)   (causal predecessor, not wall-clock)
pass:          2
step_type:     plan
input_state:   parent §0b CONFIRMED — resolved LIVRPS stack neither produced nor serialized on the autonomous path
action:        Spec engine-routing of compose + DeltaLayer (de)serialization + intent-keyed blueprint cache
output_state:  forge-ready Action-3 RFC; §3 learned unit defined; resolution semantics unchanged
verifier:      L3 (SPEC-fit vs P<R<V<I<L<S + S=6 read-only) — pending PASS-2 CRUCIBLE
outcome:       success
external_calls: []
```

Substrate annotation *(harness/PLAN.md vocab)*: `comfy-cozy (cognitive/pipeline/, cognitive/core/, cognitive/experience/) MODIFY · LIVRPS resolution semantics NO-TOUCH (patent IP — read-only input) · Moneta CALL-ONLY (blueprints egress via Action 1)`.

---

## §A3.1 — Current state *(grounded in source)*

- **The autonomous path never instantiates the engine.** `cognitive/pipeline/autonomous.py:26` imports `CognitiveGraphEngine` and **never references it again** (grep-confirmed). The path composes a flat API dict, executes it, learns a flat `ExperienceChunk`.
- **`compose_workflow`** (`cognitive/tools/compose.py:60-131`) selects a template by family and sets **flat** `plan.parameters` (`{'cfg':…, 'steps':…}`), but **never applies them into `workflow_data`** and never touches `DeltaLayer`/engine. The emitted workflow is the unmodified template; the params are computed and discarded.
- **`DeltaLayer`** (`cognitive/core/delta.py:39-59`) — `layer_id, opinion(P|R|V|I|L|S), timestamp, description, mutations: dict[str,dict[str,Any]] ({node_id:{param:value}}), creation_hash` (SHA-256 of `{opinion,mutations}` via `__post_init__`). **No `to_dict`/`from_dict`** (grep-confirmed) — this is the serialization gap.
- **`CognitiveGraphEngine`** (`graph.py`): holds `_base_raw` (deepcopy of input) + `_delta_stack: list[DeltaLayer]` (FIFO-capped 1000). `mutate_workflow(mutations, opinion='L', layer_id=None, description='') -> DeltaLayer` (`:54-84`) appends a layer. `to_api_json()` (`:203-209`) returns the **resolved** flat dict and **discards the stack**. No stack serializer anywhere.
- **`_resolve_from_raw`** (`graph.py:106-139`): deepcopy base → **stable-sort deltas ascending by `priority`** → apply weakest-to-strongest (strongest writes last = wins). `LIVRPS_PRIORITY = {P:1,R:2,V:3,I:4,L:5,S:6}` (`delta.py:20-27`); S=6 "inverted/always-wins" **is realized by being the max priority**, not a special case. Resolution is a **pure function of `(base_raw, ordered deltas)`**.
- **`ExperienceChunk`** (`chunk.py:53-84`) already has `to_dict`/`from_dict` and the fields `workflow_hash` + `delta_count` — but the autonomous LEARN path (`autonomous.py:514-520`) leaves both at default (`''`/`0`) and stores **flat** params, which breaks `accumulator._chunk_to_workflow_proxy` (it expects nested `{node_id:{param}}`, `accumulator.py:242-260`).
- **Intent is not in the signature.** `GenerationContextSignature` (`signature.py:21-31`) keys off **resolved params** (family/resolution/cfg/steps/sampler/scheduler/denoise buckets), not the natural-language intent.

## §A3.2 — Target design

**(1) Make the autonomous path engine-aware.** At COMPOSE (after `compose_workflow` returns the base template + flat `plan.parameters`), construct `CognitiveGraphEngine(base_template_data)` and translate the params into a **single `mutate_workflow(mutations, opinion=…)`** call — `opinion='I'` (Inherits, experience-derived) for cached/experience params, `opinion='L'` (Local) for current-session overrides; Safety stays `'S'`. Feed `engine.to_api_json()` to EXECUTE **unchanged**. This is the first time the delta stack participates on the autonomous path (today the engine import is dead and params never reach the graph).

**(2) Add `DeltaLayer.to_dict` / `from_dict`** (the only missing serializer — mirror the existing `ExperienceChunk`/`QualityScore` pattern). **Contract, load-bearing:** `from_dict` must **thread the stored `creation_hash` through `__init__`** (which recomputes only when `creation_hash == ''`) so `is_intact` tamper-detection survives the round-trip — `__post_init__` must **not** recompute it.

**(3) Blueprint = `{base_raw, deltas: [layer.to_dict() …]}`.** Because resolution is a pure function of `(base_raw, ordered deltas)`, replaying a deserialized blueprint through a fresh engine reproduces **byte-identical** output. This is parent §3's learned unit.

**(4) Capture at LEARN.** Add a `blueprint` field to `ExperienceChunk`; populate the existing-but-unused `workflow_hash` (content address of the resolved JSON) and `delta_count` (stack depth) at `autonomous.py:514`.

## §A3.3 — Cache key = intent; layer-level invalidation

- **Key:** intent is **not** in `GenerationContextSignature` today, so add a **new key = `sha256(normalized intent)`** stored alongside the blueprint on the chunk; reuse `chunk.workflow_hash` for content-addressed dedupe.
- **Re-runs hit cache:** same intent key → deserialize blueprint → fresh engine → resolve → identical workflow.
- **Edits invalidate at the touched layer only:** each `DeltaLayer` is independently SHA-256-protected and tiered, so a stale layer (e.g. an `I`/experience layer) is **dropped and re-mutated** without touching higher-priority `L`/`S` layers; then re-resolve. Invalidation is per-opinion-tier, never global.

## §A3.4 — Cache-and-invalidate sits ABOVE the engine

The cache is a `dict[intent_key -> Blueprint]` layer **outside** the engine: on hit, deserialize → fresh `CognitiveGraphEngine` → `_resolve`; on partial-stale, drop the offending opinion-tier layers and re-`mutate_workflow`. **No engine internals change.** The six-level `P<R<V<I<L<S` priority and the S=6 stable-sort/last-write-wins behavior are **read-only inputs** to the cache (patent IP — `delta.py:20-27`). Replaying serialized deltas re-runs the *identical* `sorted()` + weakest-to-strongest apply.

## §A3.5 — Dependency edge

- **Depends on: Action 1 (build-order #1).** A captured blueprint becomes a *reusable recipe* only once it can be deposited→consolidated→queried via Action 1's long-lived Moneta handle + session-end cadence. Action 3's serialization is self-contained, but its payoff (the loop reusing winning blueprints) requires Action 1's egress path. Hence the fixed order Action 1 → Action 3.
- **Unblocks: the RSI loop.** Parent §3's learned unit now exists and is queryable; §4 N-shot promotion can group by intent key + blueprint identity.

## §A3.6 — Watch-items / failure modes

- **LOUD design constraint (not a semantics change):** introducing the blueprint **requires routing autonomous compose THROUGH the engine** (it's bypassed today). That is **net-new wiring above the engine**, not a modification of `_resolve`. **If any proposal special-cases S, reorders by chronology, or mutates the resolved dict in place to skip the stack → STOP (breaks patent IP).**
- `creation_hash` round-trip integrity (§A3.2-(2)) — get the `from_dict` threading right or `is_intact` silently breaks.
- FIFO cap (1000) on `_delta_stack` — a blueprint must capture the stack before eviction.
- Intent normalization (case/whitespace/synonyms) determines cache hit rate — under-normalize and re-runs miss; over-normalize and distinct intents collide.
- **Bonus fix:** storing nested `mutations` as `chunk.parameters` repairs the flat-vs-nested mismatch in `accumulator._chunk_to_workflow_proxy` — verify retrieval signatures stop being degenerate.

## §A3.7 — FREEZE CONFIRMATION *(written, per brief)*

**The six-level priority semantics are untouched.** The design only **adds** `DeltaLayer.to_dict`/`from_dict` (new methods; no existing signature changes) and a `blueprint` field on `ExperienceChunk`. `LIVRPS_PRIORITY` and the S=6 stable-sort last-write-wins behavior are **read-only inputs**; replaying serialized deltas yields byte-identical resolution (pure function of `(base_raw, ordered deltas)`). The engine's method API (`mutate_workflow`/`get_resolved_graph`/`to_api_json`/`_resolve_from_raw`) is unchanged.
**The Moneta four-op freeze is untouched** — Action 3 produces the blueprint artifact; egress is Action 1's `deposit`/`query`, no fifth op. **The S=6 Safety arc is untouched** — promoted/cached blueprints are sub-S layers and can never override Safety. No `agent/stage/` mutation. ✅ *(The one constraint — route compose through the engine — is additive wiring above the engine, explicitly not a resolution change.)*
