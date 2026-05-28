# SCOUT — Rewiring Scope for Write-Back v1

**Question:** Does write-back v1 need connection rewiring (Tier 2), or do
widget/input value edits (Tier 1) suffice — and if rewiring is needed, what
does applying a link change cost on the LiteGraph frontend?

**Method:** Read-only file:line evidence. No fix proposed.

**Output-path note:** Mandate specified `.harness/SCOUT_rewiring_scope.md`,
but the prior scout report was moved out of the hidden `.harness/` into the
visible `harness/` per operator preference. Following that pattern here.

---

### Paths

- Semantic-build tool schemas:
  `agent/tools/workflow_patch.py:266-355` declares `add_node` (`:268`),
  `connect_nodes` (`:295`), and `set_input` (`:328`).
- Handlers:
  - `_handle_add_node` — `agent/tools/workflow_patch.py:667`
  - `_handle_connect_nodes` — `agent/tools/workflow_patch.py:714`
  - `_handle_set_input` — `agent/tools/workflow_patch.py:810`
- LIVRPS mutation surface (composition layer, op-agnostic):
  `agent/stage/mutation_bridge.py:44-214`. Accepts arbitrary `(operation,
  agent_name, delta)`; does not constrain to a particular op set.
- Intent → op mapping in agent prompt:
  `agent/system_prompt.py:34` ("Use add_node/connect_nodes/set_input for
  building workflows instead of raw patches when possible.") and `:54` (lists
  all three in the canonical tool registry).
- **Existing canvas write-back surface** (the closest thing to "write-back
  v1" in shipped code): `panel/web/js/superduperPanel.js:87-118`,
  function `pushAgentToCanvas`.
- Frontend graph inspection panel: `panel/web/js/graphMode.js`.
- SPEC document for `SPEC_bet3out_writeback`: **NOT FOUND.** `harness/SPEC.md`
  is the moneta-bridge embeddings spec, unrelated. `grep -rln
  "writeback\|bet3"` across `harness/` and `docs/` returned no matches. This
  scout therefore reasons against the architect's framing in the mandate +
  the actually-shipped write-back surface, not against a written SPEC.

---

### Mutation Mix (Step 1)

The agent is **explicitly directed to use connect_nodes as a first-class
build tool**, not as a rare fallback.

- `agent/system_prompt.py:34`: *"Use add_node/connect_nodes/set_input for
  building workflows instead of raw patches when possible."* — `connect_nodes`
  appears alongside `set_input` in the same instruction.
- `agent/system_prompt.py:54`: lists the trio as the canonical
  semantic-composition surface.
- `agent/tools/workflow_patch.py:296-300` (tool description):
  *"Connect one node's output to another node's input. This sets the
  connection in the workflow graph. Example: connect KSampler output 0 to
  VAEDecode input 'samples'."* — promoted as a primary, not a rare,
  capability.
- Implementation depth: `_handle_connect_nodes` at `:714-807` includes
  COMFY_AUTOGROW_V3 dotted-name support (`:761-769`), engine-mutation routing
  through LIVRPS (`:771-795`), and undo-history snapshotting (`:753`). This
  is not a stub — it's a fully-developed tool, indicating real expected use.
- `grep -rln "connect_nodes"` finds 7 hits under `agent/` (system_prompt,
  workflow_patch, tool_scope, mcp_server, capability_defaults,
  workflow_templates, brain/{planner, orchestrator, demo}) and 7 hits under
  `tests/`. The tool is woven through the planner, orchestrator, tool-scope
  gate, MCP server registration, and tests — central to the agent's surface,
  not peripheral.

**Conclusion (mix):** rewiring is in the agent's main loop by design, not an
edge case.

---

### Capability Dependency (Step 2)

Concrete shipped behaviors that **fundamentally require link mutation**, not
just widget edits:

1. **`migrate_deprecated_nodes`** — CLAUDE.md `Tool Overview / Node Replace`
   row and `agent/tools/` registers `migrate_deprecated_nodes`. Replacing a
   deprecated node with its successor requires re-pointing every link that
   referenced the old node to the new one — a pure link-set operation, not a
   widget edit.
2. **`repair_workflow(auto_install=true)`** — CLAUDE.md `Tool Usage Rules`
   item 5 mandates this flow on missing nodes. When the replacement node
   class has a different input schema (typical), the agent must re-wire
   inputs that pointed at the missing node into the equivalent slot on the
   replacement.
3. **`graphMode` status bar wiring/deprecation actions** —
   `panel/web/js/graphMode.js:330-388` exposes user-facing "Repair" and
   "Migrate" buttons that fire `repairWorkflow` and `/comfy-cozy/migrate-
   deprecated`. Both upstream behaviors mutate links. So the UI itself
   advertises a flow that depends on Tier 2.
4. **Common-recipe expansions** — `agent/knowledge/common_recipes.md:57,64`
   and `agent/knowledge/workflow_optimization.md:32,50-54,105-106` describe
   adding LatentUpscale chains, ControlNet preprocessing chains, and
   ESRGAN upscaler swaps. Each "swap upscaler" / "add ControlNet
   preprocessing" / "insert latent upscale" recipe is fundamentally a
   topology change. (Note: "add a NEW node" is Tier 3 territory if it requires
   layout; the rewiring step that follows the add is Tier 2 regardless.)
5. **Diff-aware push semantics** — `panel/web/js/graphMode.js:157-162`
   already distinguishes link-shaped inputs (`Array.isArray(val) && len 2
   && string + number`) and rejects edits on them (*"No edit for
   connections"*, comment at `:161`). This is parallel evidence that the
   current frontend write-side concedes the gap.

**Direct evidence the gap is real, not theoretical:**
`panel/web/js/superduperPanel.js:90-92` (docstring of `pushAgentToCanvas`):
*"push literal input values onto the live ComfyUI canvas. Only updates widget
values that differ; connections (arrays) are left untouched."*
`:106-107`: `if (apiValue !== undefined && !Array.isArray(apiValue))` —
the actual code filter that drops every link the agent emitted.

So today: agent calls `connect_nodes` → server cache is updated and undo
history records the link → write-back path silently discards the link →
canvas does not reflect what the agent did.

---

### Frontend Cost (Step 3)

**LiteGraph link API in this repo: NOT FOUND in agent-facing code.**

`grep -rn "graph\.removeLink\|node\.connect\|disconnectOutput\|
disconnectInput\|addLink\|removeLink\|connectByName"` across
`ui/web/` and `panel/web/` returned **zero matches**. The frontend
currently uses LiteGraph only for **read** and **node-level** operations:

- `app.graph.serialize()` — `panel/web/js/superduperPanel.js:29`
- `app.graphToPrompt()` — `panel/web/js/superduperPanel.js:40`,
  `ui/web/js/sidebar.js:662`
- `app.graph.getNodeById(...)` — `panel/web/js/superduperPanel.js:101,125`;
  `ui/web/js/node_fx.js:152,216,228`
- `node.widgets` iteration / `widget.value = ...` —
  `panel/web/js/superduperPanel.js:104-109`
- `app.graph.onAfterChange` observer —
  `panel/web/js/superduperPanel.js:66-71`

The LiteGraph link primitives themselves (`LGraph.connect`,
`LGraphNode.connect`, `LGraphNode.disconnectOutput`,
`LGraphNode.disconnectInput`, `LGraph.removeLink`) live in upstream
LiteGraph/ComfyUI, not in this repo. Cost to wire them in:

- Implement a diff step in `pushAgentToCanvas` that walks each node's
  `inputs` for `Array.isArray(v) && v.length===2` entries, compares against
  the canvas node's `inputs[i].link` slot state, and emits connect/
  disconnect calls. New code, not enable-flagging existing code.
- Resolve the ID-shape mismatch: server API uses `[from_node_id_str,
  from_output_int]`; LiteGraph identifies slots by `node.id` (numeric)
  and slot index. The shim is straightforward (`parseInt(node_id, 10)`,
  already done at `panel/web/js/superduperPanel.js:101`) but it has to
  exist.
- Trigger the canvas's `onAfterChange` observer carefully to avoid a
  feedback loop: the observer at `:66-71` would otherwise re-sync the
  just-pushed change back to the agent. Either pause the observer during
  push, or hash-suppress as `_lastGraphHash` at `:19,33-35` already does.

**Suggested link-delta contract shape** (matching server's API representation
at `agent/tools/workflow_patch.py:756`, `:768`, `:795`, `:797`):

```json
{"op":"connect","to_node":"9","to_input":"samples","from_node":"7","from_output":0}
{"op":"disconnect","to_node":"9","to_input":"samples"}
```

This mirrors the connect_nodes tool signature
(`agent/tools/workflow_patch.py:301-323`) one-to-one, so the message schema
is just a transcription of an already-validated server-side op. Disconnect
deduces `from_*` from the prior cached value, which is already snapshotted
in undo history at `:753`.

---

### Tier Confirm (Step 4)

Tier 2 (rewiring between existing nodes) is **layout-free**, confirmed:

- `_handle_connect_nodes` at `agent/tools/workflow_patch.py:714-807` only
  mutates `workflow[to_node]["inputs"][to_input]` (`:795`, `:797`) or
  `inputs[group]` (`:769`). It writes a 2-element `[from_node, from_output]`
  array. **No `node["pos"]`, no `node["size"]`, no graph layout
  properties.**
- `:742-749` explicitly validates that *both* `from_node` and `to_node`
  already exist in `workflow` — connect_nodes refuses to create nodes. So
  no Tier-3 bleed via that path.
- `_handle_add_node` at `:667` does create nodes and would push into Tier 3
  (positions / auto-layout). It is **not** required by the rewiring
  question and is correctly out of scope for write-back v1.
- On the canvas side, applying a link change via LiteGraph (`node.connect`,
  `disconnect*`) does not move nodes. Visual link routing is recomputed by
  LiteGraph, not by our code. So the frontend cost is also layout-free.

No Tier-3 bleed detected. The rewiring scope cleanly stops at link mutation.

---

### VERDICT

**TIER 1+2 (rewiring in v1).**

Tier 1 alone leaves a load-bearing capability gap: the agent is explicitly
directed by `agent/system_prompt.py:34` to use `connect_nodes`, multiple
shipped flows (`migrate_deprecated_nodes`, `repair_workflow`, common
recipes) fundamentally require link mutation, and the current
`pushAgentToCanvas` implementation silently drops every link the agent
emits (`panel/web/js/superduperPanel.js:90-92, 106-107`). Tier 2 is
layout-free per `agent/tools/workflow_patch.py:742-749` (existing-nodes
guard) and `:756,795-797` (only mutates `inputs[*]`), so adding it to v1
does not drag in the deferred Tier-3 auto-layout work.

---

### SPEC IMPLICATION

Message schema adds `{"op":"connect|disconnect", to_node, to_input,
from_node?, from_output?}` ops mirroring `connect_nodes` (`agent/tools/
workflow_patch.py:301-323`); predicates extend to **link-state parity**
(canvas links match server-side `current_workflow` `inputs[*]` arrays for
every existing-node pair); Out-of-Scope amends to keep node create/delete
+ auto-layout as Tier 3 (deferred).

---

### OPEN ITEMS

- The actual `SPEC_bet3out_writeback` document is **NOT FOUND** in
  `harness/` or `docs/`. This scout reasons against the *de facto*
  write-back surface (`superduperPanel.js:pushAgentToCanvas`) and the
  architect's framing. If a written SPEC exists elsewhere (gist, message
  thread, sibling repo), confirming its current "Tier 1 only" scope text
  would tighten the case but does not change the verdict.
- Mutation-mix quantification from **real** session traces was not done.
  Tests (7 hits under `tests/`) show the tool is exercised, but I did not
  count connect_nodes:set_input ratios in shipped TRACE.md or session logs.
  The current evidence is from prompt/tool/design, which is sufficient for
  scope but not for relative-frequency claims.
- LiteGraph's exact link-mutation API (signatures of `node.connect`,
  `LGraph.removeLink`, slot-index semantics) lives in upstream
  LiteGraph/ComfyUI source, not in this repo. The SPEC will need a
  one-paragraph reference into that surface; this scout only confirms our
  side has zero existing usage.
- `_handle_add_node` at `agent/tools/workflow_patch.py:667` is real and the
  agent will call it for "add a LoRA" / "add an upscaler" flows. That
  surfaces a near-future Tier-3 scoping question: how do we render a
  new-node placement on a canvas the agent didn't visually compose? Parked,
  not solved.
- Feedback-loop risk in two-way sync: `superduperPanel.js:66-71`'s
  `onAfterChange` observer would re-sync agent-pushed changes back to the
  server. `_lastGraphHash` (`:19,33-35`) is one mitigation surface; the
  SPEC will need to specify the suppression discipline explicitly.
- `agent/tools/workflow_patch.py:783` reads `old_value` from `workflow[
  to_node]["inputs"][to_input]` *before* the engine path overwrites it.
  This is the prior-link value that a `disconnect` op needs in order to
  identify the source. Confirmed available; no new code needed to expose.
