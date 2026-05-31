# HARNESS — ComfyUI Agent Tooling

> **Instantiation:** the general harness (AutoScientist × K+S) bound to execute `DISPATCH_comfyui_agent_tooling.md`. Domain-agnostic machinery preserved; everything below is the instantiation.
>
> **Artifact** = the ComfyUI node pack (Home A) + the MCP tool server (Home B). **Champion** = current best *verified* state, tracked per track. **Verifier** = whatever proves a dispatch gate true or false against the live install.

---

## THE SEAM  (how the dispatch and the harness reconcile)

The harness distrusts fixed partitions; the dispatch *is* one. Resolution:

- The dispatch is a **ratified prior** on line structure — human expertise pre-partitions, which the harness normally forbids, but which is admissible *because it's ratified at FRAME and the harness retains the right to reorganize*.
- The harness keeps its teeth: **verifier-gating, champion tracking, dead-end memory, stagnation→reorganize, HALT-on-broken-assumption.** A phase that stagnates or whose Leg 0 HALTs reopens DELIBERATE — the march is not sacred.
- **Competing lines stay dormant** for construction-heavy features (push route, surgery primitives — one canonical build each post-verification) and **activate only at genuine forks**: parser widget-mapping (schema-order vs heuristic vs hybrid), read-back transport (push vs pull), memory relevance scorer. This is the harness's own *re-derive mode*: most sub-problems SOLO, a few UPSHIFT.

---

## OPERATING PRINCIPLES  (carried from template, tuned for this run)

1. **Falsifiable claims** → every acceptance predicate below is checkable; the dispatch's HALT triggers are this run's falsification conditions.
2. **Verifiers gate progression** → a feature cannot be verified against APIs not yet confirmed present. **Leg 0 introspection is an L0 gate**, not optional.
3. **Nothing privileged** → the four tracks run against their own champions; no track's approach is assumed before critique.
4. **Critique before commit** → forks (parser/transport/scorer) get adversarial review on the FORUM before any build cost.
5. **Failures are memory** → `DEADENDS.md` pre-seeded below with 6 known traps. Read before proposing.
6. **Champion is the bar** → each track's seed champion = the *current pain* from the comfy-Cozy report (the thing to beat). Render/vision gains are **noise-aware** — replicate before promoting.
7. **Stagnation triggers reorganization** → a track with no gate-pass in N=3 attempts reopens DELIBERATE; do not push it harder.
8. **Compress at cycle boundaries** → `DIGEST.md` replaced each cycle.
9. **Progress is structured** → `[milestone | track X | step i/N | verifier: PASS/FAIL/PENDING | champion: <state> | next]`. No silent work.
10. **Ledger persists** → reusable recipes (route-registration guard, claim/lock, schema-order mapping) promoted to `LEDGER.md` only after they pass.
11. **Match hands to breadth** → mode is a readout of the live track structure (Complexity Gate below), re-derived at every reorganize.
12. **Tuning** → `stagnation N = 3`, complexity thresholds at template defaults, all overridable in SPEC.

**Lenses (standing):** ANALYST (owns the queues + dead-end registry) · BUILDER (claims a proposal, builds against champion, runs the verifier, logs win *or* failure) · CRITIC (kills weak proposals on the FORUM; runs the dispatch's hostile cases at STRESS).

**Files this run maintains:** `SPEC · CHAMPION · LOG · FORUM · DEADENDS · PLAN · LEDGER · TRACE · DIGEST` — per track where stated.

---

# ═══ FRAME OUTPUT ═══

## SPEC.md  — DRAFT, awaiting ratification

### Outcome
ComfyUI's agent assistant *does* instead of *describes*: reads and pushes the canvas, edits it surgically and reversibly, profiles and locates its own outputs, parses any shared workflow, resolves local assets, and reasons from relevant memory — without describing a single thing it could instead perform.

### Acceptance Predicates  (the bar)

**Track 1 — Tool Layer**
- **P1.1** `#4` `get_node_info` returns ≤200 tok at `summary`, ≤1KB at `signature` (**required inputs never dropped**), unchanged at `full`; default is `summary`; oversize auto-truncates with a `detail='full'` hint.
- **P1.2** `#6` `delete_node` / `replace_node` / `rewire_around` work; delete leaves no dangling links; rewire bridges matching slots and **reports what it dropped**; every op snapshots prior graph state (reversible).

**Track 2 — Bridge → WS Signals**
- **P2.1** `#1-push` a connected tab reloads on push; node pack survives hot-reload; the 11 bridge hostile cases pass.
- **P2.2** `#1-readback` an artist edit is retrievable within the debounce window; an **agent-originated load never registers as an edit** (loop-prevention); falls back to `get_canvas_state()` pull if the transport can't push.
- **P2.3** `#5` `get_execution_profile(prompt_id)` returns ordered per-node timing matching a known render; a planted regression is flagged; cached (~0ms) nodes are not flagged as anomalies.
- **P2.4** `#8` a file written outside `output/` is still caught; the diff returns exactly the new files; unrelated writes don't false-positive.

**Track 3 — Comprehension**
- **P3.1** `#2` a known UI workflow round-trips to API format that **executes identically**; `seed + control_after_generate` maps correctly; a node absent from `/object_info` is surfaced, not guessed.
- **P3.2** `#7` `list_assets` lists images from `input/` and recent outputs; search filters; perceptual duplicates collapse; scales to thousands (cap/paginate).

**Track 4 — Gated / Dependent**
- **P4.1** `#3` **GATED** — only if the client renders images mid-tool-call. If so: previews appear during a render; abort→requeue-with-changed-params works.
- **P4.2** `#9` a perceptually-identical image returns a cached analysis; a changed image re-analyzes; a near-threshold pHash does **not** false-dedup two different images.
- **P4.3** `#10` opening on a Seedance workflow surfaces prior Seedance preferences; irrelevant memory is not injected; injection stays within the P1.1 context budget.

### Out of Scope
Anything outside the ten gaps · multi-user concurrency on the bridge (single-artist assumed) · any feature resting on an unconfirmed runtime capability until its gate passes · audiobook/lyrics/transcript generation (not ComfyUI surface).

### Falsification Conditions  (from the dispatch's HALT triggers)
- A Leg 0 symbol is absent/divergent → that feature's approach is wrong **as written**; reopen DELIBERATE for it.
- The agent transport can neither push **nor** support a pull tool → `#1-readback` is infeasible; document and drop.
- The client cannot render mid-tool-call images → **`#3` is falsified — do not build.**
- `widgets_values` cannot be mapped via `/object_info` for a node class → parser approach falsified for that class; surface it.
- `vram_delta` is absent from the WS stream → the "vram delta" predicate is unmeetable; ship duration-only.

### Verification Strategy  (per predicate → layer · stochastic?)
| Predicate | L0 | L1 | L2 | L3 | L4 | stochastic |
|---|---|---|---|---|---|---|
| P1.1 | ✓ | ✓ | | ✓ (no req-input loss) | | no |
| P1.2 | ✓ | ✓ | ✓ | | | no |
| P2.1 | ✓ | ✓ | ✓ | | ✓ | no |
| P2.2 | ✓ gate | ✓ | ✓ (loop) | | | no |
| P2.3 | ✓ | ✓ | ✓ | | | **yes (timing)** |
| P2.4 | ✓ | ✓ | ✓ | | | no |
| P3.1 | ✓ | ✓ | | ✓ (executes identically) | | no |
| P3.2 | ✓ | ✓ | ✓ | | ✓ (scale) | no |
| P4.1 | ✓ gate | ✓ | | | ✓ | partial |
| P4.2 | ✓ | ✓ | ✓ | | | **yes (vision)** |
| P4.3 | ✓ | ✓ | | ✓ | | no |

> **GATE (FRAME):** SPEC ratified by user. ← *parked here.*

---

# ═══ SKETCH OUTPUT ═══  *(pending ratification; nothing executes pre-gate)*

## Seed Champions  (the bar each track must beat — = current pain)
- **Track 1:** verbose ~3,500-tok introspection responses; "rewrite the whole graph" for any edit.
- **Track 2:** the Phase-0 push bridge (already scoped) — itself the seed; read-back/profiling/watcher must extend it without breaking it.
- **Track 3:** "open it in the browser and re-export" (the punt); "give me the file path" (the stall).
- **Track 4:** no previews (8-min blind renders); re-analyze every image from scratch; cosmetic memory.

## Dependency Graph
- **Home A (node pack):** Phase-0 route+loader → 1B read-back route + change hooks → 1B profiling subscription, 1B watcher → 3.1 preview subscription. *Sequential spine within Track 2.*
- **Home B (MCP server):** 1A disclosure + surgery · 2 parser + assets · 3 cache + memory. *Mostly independent — except the tool registry is shared (see hazard).*
- **Cross-track edges:** only Phase-0 → 1B (internal to Track 2). Tracks 1/3/4 carry no blocking edge to Track 2.
- **SPOF:** the MCP tool registry (Tracks 1 & 4 both write it). **Bottleneck:** the ComfyUI WS stream (Track 2 consumers share one subscription — build once).

## COMPLEXITY GATE  (computed)
| Signal | Rating | Why |
|---|---|---|
| BREADTH | **high** | 4 viable tracks at once |
| INDEPENDENCE | **med–high** | T1/T3 fully independent; T2 self-contained; T4 gated; only shared state = MCP registry |
| HORIZON | **long** | 10 features, multi-cycle |
| REWORK COST | **medium** | real infra; surgery/parser nontrivial to back out |
| VERIFIER COST | **mixed** | L0/L1 cheap; #5 timing, #3 previews, #9 vision are slow + stochastic |

**Decision:** 4 independent lines **AND** long horizon **AND** expensive/stochastic verifiers → **ORCHESTRATED-eligible.**

**HONESTY CONSTRAINT (template):** a single context cannot spawn parallel processes. Therefore:
- **External launcher present** → ORCHESTRATED per the roster below.
- **No launcher** → **downshift to SIMULATED**: hold the 4 tracks open in PLAN, round-robin attention, run Analyst/Builder/Critic per track, **report which track you're on — never narrate simultaneity.** The orchestration spec is emitted regardless, so the run can be launched later without a rewrite.

> **GATE (SKETCH):** every predicate has a confidence + the mode is set. *Met on ratification + launcher answer.*

## PLAN.md — the four tracks
Each: **GOAL · CONTRACT · VERIFIER · queue · fork?**

- **TRACK 1 — Tool Layer** (Home B) · GOAL: stop describing, start manipulating · CONTRACT: P1.1, P1.2 · VERIFIER: L1+L3 (disclosure), L1+L2 (surgery) · queue: `[#4 summary tier → #4 signature tier → #6 delete → #6 replace → #6 rewire]` · **fork: none** (canonical builds).
- **TRACK 2 — Bridge → WS** (Home A + B) · GOAL: bidirectional canvas + free observability · CONTRACT: P2.1–P2.4 · VERIFIER: L1+L2(+L4 push) · queue: `[Phase-0 bridge → #1 read-back → #5 profile → #8 watcher]` (Phase-0 first; rest share the WS subscription) · **fork: read-back transport (push vs pull) — resolve at its Leg 0.**
- **TRACK 3 — Comprehension** (Home B) · GOAL: read any shared workflow, resolve any local asset · CONTRACT: P3.1, P3.2 · VERIFIER: L1+L3 (parser), L1+L2+L4 (assets) · queue: `[#2 parser → #7 assets]` · **fork: parser mapping strategy (schema-order vs heuristic vs hybrid) — competing lines.**
- **TRACK 4 — Gated / Dependent** (Home A + B) · GOAL: steering + cheap verification + real continuity · CONTRACT: P4.1–P4.3 · VERIFIER: L0-gate then L1/L2/L4 · queue: `[#3 (client-render gate FIRST) | #9 cache | #10 memory]` (#9, #10 may proceed independently of #3) · **fork: #10 relevance scorer — competing lines.**

## DEADENDS.md — pre-seeded (read before proposing)
| Axis | Direction | Why rejected |
|---|---|---|
| API trust | assert ComfyUI/LiteGraph symbols from docs/memory | docs reference APIs absent in a given build — introspect the live install (Leg 0) |
| Parser mapping | positional `widgets_values[i]` → input by index | order not stable across node versions; map via `/object_info` schema |
| Read-back | stream every keystroke to the agent | floods context + transport; debounce + pull instead |
| #3 previews | build before confirming client renders mid-call images | dead code if the runtime can't display them |
| #5 vram | promise `vram_delta_mb` unconditionally | may be absent from the WS stream; ship duration-only |
| Registration | re-register route/extension on every reload | throws / stacks duplicate handlers; guard for idempotency |

## VERIFIER LAYERS — instantiated
- **L0** node pack loads in ComfyUI without error · Python lints · JS parses · **Leg 0 symbols confirmed present**. Cheapest, mandatory.
- **L1** the dispatch's line-cited gates: route returns ok/error correctly · tool POSTs+parses · surgery removes links · parser round-trips.
- **L2** the dispatch's hostile cases: malformed inputs · concurrency · debounce-under-flood · boundary pHash · hot-reload double-register.
- **L3** intent, anti-gaming: parser output **executes identically** (not just "is valid API JSON") · pushed workflow renders the same · disclosure tiers never silently drop a required input.
- **L4** scale/adversarial: 50MB payloads · thousands of assets · 8-min render abort · the loop-prevention attack · the client-render gate probe.
- **NOISE-AWARE:** #5 timing and #9 vision are stochastic — a within-variance gain is replicated on a fresh run before it promotes.

---

## ORCHESTRATED HANDOFF  (the launch spec — for an external launcher)

**Roster**
- **Analyst ×1** — maintains `DEADENDS`, ranks each track's proposal queue, extracts what-worked after a champion win.
- **Critic ×1** — kills weak proposals on `FORUM` (the three forks especially); runs all hostile cases at STRESS.
- **Builder ×4** — one per track. **Builder-2 runs Track 2's spine in order** (Phase-0 bridge → read-back → profile → watcher); the rest are free within their queues.

**Claim / lock protocol (concurrency hazards addressed before launch)**
- **Queue:** a builder claims a proposal by appending a claim line (`track · proposal · builder · ts`); others skip claimed proposals.
- **Log:** append-only; each builder writes only its own track section.
- **Champion:** **per-track**, last-write-wins within a track; there is no shared cross-track champion to race.
- **MCP tool registry (the SPOF):** Tracks 1 & 4 both register Home-B tools → **single writer.** Route all tool registration through one integration step, *or* lock the registry file. This is mandatory pre-launch.
- **WS subscription (the bottleneck):** Track 2 builds the subscription once; profiling and watcher attach as consumers, not new subscriptions.

**Heartbeat:** deterministic monitor invokes each agent `read-state → act → write-state`. No agent acts on stale `DIGEST`.

---

## THE ARC  (this run's path)
`FRAME ✓(draft) → SKETCH (this) → DELIBERATE ⇄ EXECUTE (4 tracks) → INTEGRATE (compose pack + server; seam verifiers; the registry merge) → STRESS (every dispatch hostile case as L4 + the gate probes) → SHIP`
Loop-back on stagnation (N=3) or any falsification condition; re-derive mode at each reorganize.

---

## BEGIN
1. **Ratify SPEC** — *"This is the contract. Right? Missing anything?"* (FRAME gate)
2. **Declare launcher vs simulated** — sets ORCHESTRATED or SIMULATED.
3. **Release Track 1 + Track 2-bridge.** First builder action = **Leg 0 introspection against the live ComfyUI install** — the WIDGET-ORDERING, TRANSPORT, VRAM, and CLIENT-RENDER gates resolve from real data, not assumption.
