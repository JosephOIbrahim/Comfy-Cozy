# Mission — Cozy Legacy Store Retirement Scout

**Status:** Active
**Type:** Read-only scout pass
**Output:** `SCOUT_COZY_RETIREMENT_v0_1.md` at repo root
**Sibling:** Follows `SCOUT_COZY_v0_1.md` (Cozy × Moneta integration scout)
**Envelope:** Same marathon-marker discipline as previous scout. ~400–600 line output.

---

## Frame

Read-only scout pass. No code changes. No test runs that mutate state. Output is a written analysis at the repo root.

The previous scout (`SCOUT_COZY_v0_1.md`) identified **six parallel filesystem stores** as the data surface Moneta will replace or front during the Cozy × Moneta integration. The integration design pass concluded that during the demo phase, dual-write to Moneta + legacy stores is required — which adds latency tax to the "It remembered" benchmark Mike Gold will see.

This scout answers a single concrete question:

> **Which of the six legacy stores has the smallest retirement surface — i.e., is the cheapest to remove from the dual-write path entirely and serve from Moneta alone?**

The answer determines whether a strategic option (retire one store before the Mike-credible demo, demonstrating *active migration* rather than just *describing* it) is achievable inside the 8–13 day integration envelope.

The strategic frame: **a substrate that is actively replacing legacy storage tells a stronger story than one that is merely described as capable of replacing it.** Option 3 is structurally forward-looking — Option 2 is only narratively forward-looking.

---

## Locked Premises

Do not relitigate these:

1. Per-session Moneta-handle ownership is the architecture. Process-singleton is off the table.
2. Cozy stays Cozy. No rewrite, no agent loop substitution.
3. `agent/brain/memory.py` is the unified retrieval seam. Loop does not call Moneta directly.
4. Embedder stays on Cozy side. Moneta receives `List[float]`.
5. Synchronous inline writes in `cognitive/experience/accumulator.py`. No batching, no fire-and-forget.
6. Demo + benchmark + token telemetry deliverable is the cut. 8–13 cumulative day envelope for integration.
7. Six legacy filesystem stores remain in scope as the migration target. Eventual deprecation is the destination.
8. Moneta v1.1.0 interface is fixed. No interface changes proposed.

---

## Output Specification

File: `SCOUT_COZY_RETIREMENT_v0_1.md` at repo root. Marathon markers throughout. Sections in the order below.

### §A — The Six Stores Inventoried

For each of the six parallel filesystem stores identified in the previous scout:

- **Name and file path**
- **Function** — what it stores, what it's used for
- **Read surface** — which files/modules read from this store, and how (direct disk access, mediated through a class, etc.)
- **Write surface** — which files/modules write to this store, and from where in the lifecycle
- **Test coverage** — which tests touch this store (by name or count), and whether the tests assert against *disk state* or *behavioral output*
- **External dependencies** — anything outside Cozy that depends on this store's existence or schema (config files, downstream tools, fixture data)

### §B — Retirement Surface Scoring

For each store, score on five dimensions (1 = small/easy, 5 = large/hard):

1. **Read-surface complexity** — how many call sites, how coupled
2. **Write-surface complexity** — same, for writes
3. **Test blast radius** — how many tests must change, and whether they assert disk state vs. behavior
4. **Moneta-replaceability** — how cleanly does Moneta's interface (per-session handle, vector storage, retrieval) map to this store's function? Is anything required that Moneta v1.1.0 doesn't expose?
5. **External-dependency drag** — anything outside Cozy that breaks if this store goes away

Total score per store. Lowest total = smallest retirement surface.

### §C — The Recommendation

Name the single store with the smallest retirement surface. Justify against §B scores.

Answer concretely:

- **Estimated retirement effort** in senior eng days (separate from the integration envelope — i.e., *on top of* the 8–13 days)
- **Whether retirement can run in parallel** with the Cozy × Moneta integration work, or whether it must sequence after
- **Specific test changes required** — count, list of test files, nature of changes (assertion rewrites vs. fixture updates vs. quarantine)
- **Locked-premise contradictions** — if Moneta v1.1.0 cannot fully serve this store's function, name that explicitly

### §D — The Honest Alternatives

If no store has a meaningfully smaller retirement surface than the others — i.e., all six are roughly equivalent in cost — **say so directly.** Recommend Option 2 (annotate + temporal scoping in benchmark output) as the fallback.

If two or more stores are tied for smallest surface, name them and recommend the one that produces the **most strategically legible retirement** — i.e., the one whose deprecation tells the cleanest substrate-vs-product story to a viewer of the demo.

### §E — Open Questions

Anything the scout couldn't answer read-only without code execution or repo-state changes. Same shape as the seven clusters from the previous scout.

---

## Hard Operating Rules

- **Read-only.** No code changes. No test runs that mutate state.
- **Do not propose Moneta interface changes.** Moneta v1.1.0 is fixed.
- **Do not propose rewrites** of any of the six stores. The question is retirement, not refactor.
- **Do not propose retiring more than one store.** The strategic move is "first one already gone," not a multi-store sweep. If two stores are equally cheap, recommend one.
- **False optimism costs more than honest pessimism.** If the analysis reveals that none of the six are cheaply retirable, say so. The fallback (Option 2) is real.
- **Stay inside the same marathon-marker discipline** as the previous scout. Twelve markers is fine. More is fine. Zero is not.

---

## Pressure Valve

Push back where:

- A store appears cheap to retire in isolation but creates a **coupling problem** with one of the other five that wasn't visible from the previous scout.
- **Moneta v1.1.0's interface lacks a capability** one of the stores requires — name the gap explicitly. Don't paper over it.
- The retirement candidate is **technically smallest but strategically weakest** — i.e., retiring it doesn't visibly demonstrate substrate replacement to a viewer of the demo. Name the trade.

---

## Why This Mission Exists

The Cozy × Moneta integration design pass produced a clean 8–13 day envelope for Mike-credible delivery. One open friction point: dual-write to legacy stores adds latency to the demo's benchmark numbers, which Mike's eye is trained to catch.

Three options exist:

1. **Annotate** — two timing buckets in benchmark output, README note explaining dual-write phase. Honest, minimum-viable.
2. **Annotate + temporal scoping** — Phase 1 / Phase 2 framing, target date for legacy deprecation. Forward-looking narratively.
3. **Retire one store before the demo** — bridge has a first plank. Forward-looking structurally.

This scout determines whether **Option 3 is achievable**. If yes: name the store, size the work, sequence it. If no: fall back to Option 2 with full honesty about why Option 3 didn't work.

---

## Sibling References

- `SCOUT_COZY_v0_1.md` — previous scout, integration surface analysis
- Moneta v1.1.0 — singleton surgery complete, per-session handle interface stable

---

*Mission file generated for hand-off to scout. Edit in place if scope shifts.*
