# DISPATCH — ComfyUI Agent Tooling (Master / Program)

> **Mission:** Take ComfyUI's agent assistant from *describing* to *doing* — close all ten capability gaps as gated relay dispatches, built on verified APIs, hardened by adversarial tests.
>
> **Structure:** A program of phases. Each phase is a relay (ARCHITECT → FORGE → CRUCIBLE) with line-cited gates and halt-and-surface triggers. **Phase 0 is the canvas bridge, folded in from `DISPATCH_comfyui_agent_bridge.md`** — that standalone file remains valid for bridge-only work; this master supersedes it for program-level work.
>
> **The marathon:** Mile 0 (Bridge) → Mile 5 (Memory). Relay handoffs between legs inside each phase; phases are the segments.

---

## TWO HOMES (where everything lands)

Every piece of this program lives in exactly one of two places. Legs must not cross-write.

- **Home A — ComfyUI custom node pack** `custom_nodes/comfy_agent_bridge/`
  Server-side routes, websocket subscriptions, frontend extension JS.
  *Holds:* Phase 0 push route + loader · 1B canvas-changed route + change hooks + profiling subscription + output watcher · Phase 3 preview subscription.

- **Home B — MCP tool server** (the agent's callable tools)
  *Holds:* Phase 0 `push_workflow_to_canvas` · 1A disclosure wrappers + surgery primitives · Phase 2 parser + `list_assets` · Phase 3 vision cache + memory injection.

---

## MASTER CONSTITUTION (hard invariants — all phases, never violate)

1. **API verification is a gate, not a suggestion.** Every symbol named in this doc is *assumed*, not confirmed. Each phase opens with a Leg 0 that introspects the **real install**. Absent or divergent → **HALT and surface**, never improvise a substitute.
2. **One mutation per script.** Atomic. No multi-purpose files.
3. **Idempotent registration / single subscription.** Routes, WS listeners, and frontend extensions register exactly once and survive hot-reload without throwing or stacking duplicate handlers.
4. **No silent failures.** Routes return structured error JSON with non-200 status on bad input. Tools raise cleanly — no stack vomit, no silent hang.
5. **Validate before broadcast / load / consume.** Never hand garbage to `loadGraphData` or to any consumer.
6. **Path safety.** Any tool taking a filesystem path resolves it, confirms extension + allowed root, rejects traversal — before opening.
7. **Provenance envelope.** Agent→canvas actions carry `{"workflow": <graph>, "meta": {"source": ..., "reason": ...}}`. `workflow` required; `meta` optional.
8. **Reversibility.** Graph-surgery and canvas-push operations snapshot prior state before mutating, so any agent action can be restored. *("Push buttons, explain why, undo all of it.")*
9. **Context-cost guard.** Info-heavy tools default to a summary tier and never blow the context budget by default. (Gap #4 is a feature *and* a rule for every tool built after it.)
10. **External-gate honesty.** If a capability depends on a client/runtime feature outside this build (server-pushed events, mid-tool-call image rendering), verify the dependency exists **before** building the feature. Absent → HALT, surface, do not ship dead code.
11. **Atomic commits, race-safe push.** One leg = one logical commit. Non-fast-forward → fetch + rebase, max 3 attempts, halt on merge conflict.
12. **Gates cite `file:line`.** "Done" is proven, not asserted.

---

## LEG 0 DOCTRINE (per phase)

The symbols differ per phase; the discipline doesn't. Before any phase writes code, introspect its assumed symbols against the live install, record the result, and HALT on any absence. The doctrine is identical to the bridge's Leg 0 — `dir()` / `typeof` / a probe call — applied to that phase's surface.

---

## PROGRAM MAP

| Phase | Gaps | Home | Complexity | Gate risk |
|-------|------|------|-----------|-----------|
| **0 — The Bridge (push)** | #1 push | A + B | Low | Standard Leg 0 |
| **1A — Tool Layer** | #4, #6 | B | Low | Standard Leg 0 |
| **1B — WS Signals** | #1 read-back, #5, #8 | A + B | Low–Med | **#1 transport gate, #5 vram gate** |
| **2 — Comprehension** | #2, #7 | B | Medium | **#2 widget-ordering gate** |
| **3 — Gated / Dependent** | #3, #9, #10 | A + B | Med | **#3 client-render gate (can HALT)** |

**Dependencies:** 1A is independent. 1B requires Phase 0 (extends the node pack, taps the WS the bridge opens). 2 is largely independent. 3's #3 is externally gated.

**Run order:** `1A → Bridge → 1B → 2 → 3`. 1A touches no ComfyUI internals — run it first or in parallel with the Bridge for the cheapest sharpness win; #4 lowers the operating cost of everything after it.

---

# PHASE 0 — THE BRIDGE (push)  ·  Mile 0

*Folded from the standalone bridge dispatch. Foundation: opens the websocket path and the node pack that 1B extends.*

**Leg 0 — verify:** `PromptServer.instance` · `.send_sync` · `routes.post` decorator · `app.loadGraphData` · `api.addEventListener` · working JS import path (`/scripts/app.js` absolute vs `../../scripts/app.js` relative). HALT on any absence.

**Leg 1 — ARCHITECT:** route contract `POST /agent/push_workflow`, event `agent.load_workflow`, envelope (invariant 7), workflow shape-check, error contract. Document: `send_sync` broadcasts to **all** connected clients — multiple tabs all reload (expected, not a bug).

**Leg 2 — FORGE backend** (`__init__.py`, Home A):
```python
from aiohttp import web
from server import PromptServer

@PromptServer.instance.routes.post("/agent/push_workflow")
async def push_workflow(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)
    workflow = data.get("workflow")
    if not isinstance(workflow, dict):
        return web.json_response({"ok": False, "error": "missing or malformed 'workflow'"}, status=400)
    PromptServer.instance.send_sync("agent.load_workflow", data)
    return web.json_response({"ok": True})

NODE_CLASS_MAPPINGS = {}
WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY"]
```

**Leg 3 — FORGE frontend** (`web/agent_bridge.js`, Home A):
```js
import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

app.registerExtension({
  name: "agent.bridge",
  async setup() {
    api.addEventListener("agent.load_workflow", (e) => {
      const wf = e?.detail?.workflow;
      if (!wf) return;
      window.__agentLoad = true;            // tag agent-originated load (Phase 1B loop-prevention)
      app.loadGraphData(wf);
      queueMicrotask(() => { window.__agentLoad = false; });
    });
  },
});
```

**Leg 4 — FORGE push tool** (`push_workflow_to_canvas`, Home B): path-safe (`ALLOWED_ROOT`, `.json`), POSTs `{workflow, meta:{source,reason}}`, `raise_for_status`, 10s timeout.

**Anchor — CRUCIBLE (11 hostile cases):** malformed JSON → 400 · missing `workflow` → 400 · `workflow` list/string/null → 400 · no browser connected → 200, tool doesn't hang · 50MB payload → defined behavior · concurrent pushes → last-write-wins, no crash · double hot-reload → no double-register · two tabs → both reload (asserted) · malformed graph past backend check → frontend fails gracefully · tool path missing/non-json/traversal → clean `ValueError` · `comfy_url` unreachable → clean timeout.

**Gate:** connected tab reloads on push; survives hot-reload; 11 cases green; cited by line.

---

# PHASE 1A — TOOL LAYER  ·  Mile 1  ·  Home B

*Zero ComfyUI internals. Pure agent-side. Lowest activation cost in the program.*

### 1A.1 — Progressive Disclosure  (gap #4)

**Goal:** Add a `detail` tier to info-heavy tools so introspection stops eating the context budget.

**Leg 0 — verify:** catalog the info-heavy tools (`get_node_info`, `get_learned_patterns`, etc.) and their current response shape; confirm the MCP server's wrapping pattern allows adding a param + post-processing the response.

**Contract:** `detail = "summary" (≤200 tok) | "signature" (≤1KB, required inputs only) | "full" (current)`. **Default `summary`.** Oversize responses auto-truncate with `"call again with detail='full' for the rest"`.

**Invariant carry:** `summary` and `signature` may compress, but **never drop a required input** — required-input fidelity is non-negotiable even at the smallest tier.

**Legs:** ARCHITECT (tier definitions, token budgets, truncation-hint format, tool list) → FORGE (response-shaping wrapper).

**Gate (cite lines):** `get_node_info("ByteDance2ReferenceNode")` returns ≤200 tok at `summary` (vs the ~3,500 cited), ≤1KB at `signature`, unchanged at `full`; truncation hint present; default is `summary`.

**Hostile:** tool with no summarizable structure · deeply nested duplicated schema (the COMFY_DYNAMICCOMBO case) · a tool where naive summary would drop a required input (must NOT).

### 1A.2 — Graph Surgery  (gap #6)

**Goal:** `delete_node`, `replace_node`, `rewire_around` — so editing stops meaning "rewrite the whole graph."

**Leg 0 — verify (graph schema gate):** introspect how `add_node` / `connect_nodes` mutate the graph JSON; confirm the **link array structure and slot indexing** in this version. Do **not** assume link representation.

**Contracts:**
- `delete_node(id)` → removes node + all incident links, no dangling references.
- `replace_node(id, new_class_type, input_mapping)` → swaps class, reconnects compatible inputs via mapping.
- `rewire_around(id)` → connects the deleted node's upstream to its downstream where slot types match, drops where they don't, **returns what it dropped**.

**Invariant carry (reversibility, #8):** every primitive snapshots prior graph state before mutating.

**Legs:** ARCHITECT (per-primitive contract, slot-compatibility resolution, dangling-link policy, snapshot format) → FORGE.

**Gate (cite lines):** delete cleans all links of a node feeding 3 consumers · replace preserves compatible connections · rewire_around bridges matching slots, drops + reports mismatches · every op produces a restorable snapshot.

**Hostile:** delete nonexistent id · replace with incompatible class (reject/report, never silently corrupt) · rewire where slot types mismatch (drop + report, never mis-wire) · multi-in/multi-out node (defined behavior) · concurrent surgery + push.

---

# PHASE 1B — WS SIGNALS  ·  Mile 2  ·  Home A (+ B)

*All three tap the same event stream the Phase 0 bridge opened. Build the subscription once; expose three signals. **Requires Phase 0.***

### 1B.1 — Canvas Read-back  (finish gap #1 → bidirectional)

**Goal:** detect artist edits on the live canvas mid-conversation and surface them to the agent.

**Leg 0 — TRANSPORT GATE:** confirm LiteGraph change hooks exist (`graph.onNodeAdded` / `onConnectionChange` / app change events) **and** confirm whether the agent transport accepts **server-pushed** events. If the transport can't push to the agent → **fall back to pull**: a `get_canvas_state()` tool. Decide here, do not assume push works.

**Recommended design:** debounced "canvas dirty" signal + `get_canvas_state()` pull, rather than streaming every keystroke. Pull-based survives a no-push transport.

**Invariant carry — LOOP PREVENTION (named hostile case):** an agent push (Phase 0) tags the load (`window.__agentLoad`); the change hook **ignores tagged loads** so the agent's own write never echoes back as an "artist edit" and triggers reprocessing.

**Legs:** ARCHITECT (change-event payload: what changed; debounce window; diff vs full-state) → FORGE frontend (hook + debounce + `POST /agent/canvas_changed` or buffer) → FORGE tool (`get_canvas_state()`, Home B; optional WS relay if transport supports).

**Gate (cite lines):** artist edit → agent retrieves accurate current state within debounce window; rapid edits don't flood (debounce holds); agent-originated loads do **not** register as edits.

**Hostile:** rapid edits (debounce) · **edit during agent push (no echo loop)** · disconnect mid-edit · huge graph diff.

### 1B.2 — Execution Profiling  (gap #5)

**Goal:** `get_execution_profile(prompt_id)` → per-node timing, so optimization stops being theoretical.

**Leg 0 — VRAM GATE:** confirm the WS sends per-node `executing`/`executed` events with timestamps; confirm whether **vram delta** is actually available. If not in the stream → ship **duration-only**, surface the gap. Do not promise data that isn't there.

**Contract:** `→ [{node_id, class_type, duration_ms, vram_delta_mb?}]`, ordered, + baseline store for regression flagging.

**Legs:** ARCHITECT (aggregation, baseline storage/compare) → FORGE (subscribe to the events the bridge already taps, aggregate per `prompt_id`, expose tool).

**Gate (cite lines):** profile matches a known render's node timings, correctly ordered; baseline comparison flags a planted regression.

**Hostile:** profile a `prompt_id` that never ran · cancelled mid-run (partial) · cached nodes ~0ms (don't flag as anomaly) · concurrent prompts.

### 1B.3 — Output Watcher  (gap #8)

**Goal:** report the files actually written, robust against custom nodes saving to nonstandard paths.

**Leg 0 — verify:** confirm `watchdog`/`inotify` available; confirm configurable output roots; confirm a `prompt_id`↔file-write correlation heuristic (timing-based may be fuzzy — be honest about confidence).

**Contract:** filesystem watcher on configured roots + per-execution snapshot diff → exact new files.

**Legs:** ARCHITECT (watched roots, diff window, correlation heuristic) → FORGE (watcher + diff + expose).

**Gate (cite lines):** a node writing outside `output/` is still caught; diff returns exactly the new files; unrelated writes don't false-positive.

**Hostile:** write to an unwatched path (must surface "add this root", not vanish) · two simultaneous executions (correlation) · file written then deleted mid-run · permissions error on a watched dir.

---

# PHASE 2 — COMPREHENSION  ·  Mile 3  ·  Home B

### 2.1 — UI→API Parser  (gap #2)

**Goal:** convert UI-format workflow JSON → API format so any community-shared workflow is legible without a browser round-trip.

**Leg 0 — WIDGET-ORDERING GATE (the trap):** `widgets_values` order is **NOT** assumed stable. Mapping goes through `/object_info` schema order **per node version** — never positional index. Confirm `/object_info` returns reliable input ordering. **Catalog the edge cases that break naive mapping:** seed + `control_after_generate` (2 values, 1 logical input) · boolean/toggle widgets · combo / autogrow nodes · hidden inputs · multiline text.

**Rule:** unmappable node (e.g. custom node absent from `/object_info`) → **surface, do not guess**.

**Legs:** ARCHITECT (the walk; schema-lookup mapping; explicit per-edge-case handling table; the unmappable rule) → FORGE.

**Gate (cite lines):** a known UI workflow round-trips to API format that executes **identically**; the `seed + control_after_generate` case maps correctly; a node missing from `/object_info` is surfaced, not mismapped.

**Hostile:** node with `control_after_generate` · custom node not installed (not in `/object_info`) · reroute nodes · group nodes · a widget order that differs from positional (proves schema-lookup, not index).

### 2.2 — Local Asset Awareness  (gap #7)

**Goal:** `list_assets(type, recent=N, search)` — so reference/img2img workflows stop stalling on "give me the path."

**Leg 0 — verify:** confirm input dir locations; confirm an image lib for thumbnails + perceptual hash (reuse the pHash from `hash_compare_images`); confirm thumbnail return is consumable by the client (else metadata-only, gated).

**Contract:** index `ComfyUI/input/` + recent outputs + configurable roots; return metadata + thumbnail + pHash; collapse perceptual duplicates.

**Legs:** ARCHITECT (indexed roots, cache structure, search semantics, dedup threshold) → FORGE (walk + cache + pHash dedup + tool).

**Gate (cite lines):** lists images from `input/` and recent outputs; search filters; perceptual dupes collapse; thumbnails render where the client supports them.

**Hostile:** empty dir · dir with thousands of files (recent cap / pagination) · corrupt image file · two perceptually-identical files (dedup) · non-image in an image dir.

---

# PHASE 3 — GATED / DEPENDENT  ·  Mile 4–5

### 3.1 — Streaming Previews  (gap #3)  ·  Home A

**Goal:** surface KSampler preview frames during long renders for mid-flight steering.

**Leg 0 — HARD CLIENT-RENDER GATE (can HALT the phase):** confirm the client/runtime can display images **mid-tool-call**. Two sub-modes — (a) *show the user* (client renders streamed frames) vs (b) *show the agent for steering* (agent runtime accepts image inputs mid-execution + the model reasons over them). Verify which, if either, the runtime supports. **If neither → HALT, do not build.** This is the dead-code risk flagged at planning.

**If gate passes:** subscribe to the preview WS messages (already broadcast for KSampler), decode, pipe as base64 frames; surface per-node tensor shapes for debug; expose abort → requeue-with-changed-params.

**Gate (cite lines):** previews appear during a render; abort path kills + requeues with changed CFG/params.

**Hostile:** workflow with no preview-emitting node · abort mid-stream · oversized frames · rapid frame flood (throttle).

### 3.2 — Vision Cache  (gap #9)  ·  Home B

**Goal:** pHash-based cache for `analyze_image` so "verify every output" becomes affordable.

**Leg 0 — verify:** reuse pHash from `hash_compare_images`; confirm a cache store.

**Contract:** if pHash distance < threshold → return cached analysis; invalidate on prompt/workflow change.

**Legs:** ARCHITECT (threshold tuning, invalidation triggers, cache key) → FORGE (cache layer wrapping `analyze_image`).

**Gate (cite lines):** re-analyzing a perceptually-identical image returns cached (instant); a changed image re-analyzes; workflow-change invalidation fires.

**Hostile:** near-threshold pHash distance (boundary — must not false-dedup two different images) · cache size growth (eviction) · stale entry after workflow change.

### 3.3 — Proactive Memory  (gap #10)  ·  Home B

**Goal:** auto-inject relevance-filtered memory at conversation start, like the workflow context already injected — so continuity stops being cosmetic.

**Leg 0 — verify:** confirm `get_learned_patterns` / `get_recommendations` data shape; confirm the existing auto-injection channel (how workflow context is injected today — reuse it).

**Contract:** relevance scorer (current workflow `class_types` overlap + recency) → small injected snippet (**within the #4 context budget**); passive "memory hit" event when a request matches a stored pattern.

**Legs:** ARCHITECT (relevance scorer, injection budget, hit-event trigger) → FORGE.

**Gate (cite lines):** opening on a Seedance workflow surfaces prior Seedance preferences; irrelevant memory is **not** injected; injection stays within budget.

**Hostile:** no relevant memory (inject nothing, not noise) · too much relevant memory (rank + cap) · stale memory (recency weighting) · request matching multiple patterns.

---

## RELAY HANDOFF PROTOCOL (program-wide)

At every leg boundary the outgoing leg writes: **what's done** (file:line), **what the next leg inherits** (contracts, confirmed symbols), **anything that drifted** from this dispatch's assumptions (especially Leg 0 findings that changed the plan). The incoming leg confirms the gate before proceeding. No leg starts on an unverified gate.

## HALT-AND-SURFACE TRIGGERS (program-wide)

Stop and surface — do not improvise — if:
- Any Leg 0 symbol is absent or behaves unexpectedly.
- The agent transport can't receive server-pushed events (1B → fall back to pull, surface the decision).
- vram delta isn't in the WS stream (1B.2 → ship duration-only, surface).
- The client can't render mid-tool-call images (3.1 → HALT the phase).
- `widgets_values` can't be mapped via `/object_info` for a node (2.1 → surface, don't guess).
- A CRUCIBLE case can't pass without weakening it.

## DEFINITION OF DONE

**Per phase:** every gate cited by `file:line`, all hostile cases green, master clean.

**Program:** the agent can read the canvas, push to it, edit it surgically and reversibly, profile and locate its own outputs, parse any shared workflow, resolve local assets, and reason from relevant memory — without describing a single thing it could instead do. Every phase's external gate either passed or was surfaced as a documented HALT.
