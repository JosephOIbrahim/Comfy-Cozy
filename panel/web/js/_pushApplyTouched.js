/**
 * Pure touched-set apply logic for write-back v1 (L-2 consumer).
 *
 * Given a touched-set (from /comfy-cozy/get-workflow-api-with-touched)
 * and the live LiteGraph app, applies each entry to the canvas:
 *
 *   kind === "widget"  → write widget.value (this leaf)
 *   kind === "link"    → DEFERRED to L-8 (link primitives via LiteGraph)
 *   kind === "unknown" → silently dropped here; L-5 will route to
 *                        addDeltaFailure before reaching this function
 *
 * The iteration is over touched entries ONLY — never over the full
 * server workflow. That iteration constraint is the F-1 mitigation:
 * untouched canvas slots are never read or written, so director-edited
 * neighbours survive every push.
 *
 * Pure-ish: this module reads the `app` passed in. It does not import
 * the host app module. Tests pass a fake app from
 * tests/panel/_stubs/litegraph.js. L-3 (ID-shape), L-4 (Tier-3), and
 * L-5 (missing slot / malformed) will replace the silent skips below
 * with addDeltaFailure entries when those leaves land.
 */

export function applyTouchedSet(app, workflow, touched) {
  if (!app || !app.graph) return;
  if (!Array.isArray(touched)) return;

  for (const entry of touched) {
    if (!entry || typeof entry !== "object") continue;
    if (entry.kind === "widget") {
      _applyTouchedWidget(app, entry);
    } else if (entry.kind === "link") {
      _applyTouchedLink(app, entry);
    }
    // "unknown" kind is dropped here; L-5 will surface before this point.
  }
}

function _applyTouchedWidget(app, entry) {
  // L-3 (ID parse failure), L-4 (Tier-3 stale ref), L-5 (missing slot)
  // will replace these silent returns with addDeltaFailure calls.
  const node = app.graph.getNodeById(parseInt(entry.node_id, 10));
  if (!node || !node.widgets) return;
  const widget = node.widgets.find((w) => w && w.name === entry.input_name);
  if (!widget) return;
  if (widget.value !== entry.new_value) {
    widget.value = entry.new_value;
  }
}

function _applyTouchedLink(_app, _entry) {
  // L-8 will implement: from_node.connect(...) / to_node.disconnectInput(...)
  // via LiteGraph primitives. For now, link entries are tracked but not
  // applied — the touched-set still flows through this leaf so the
  // F-1 mitigation works for widget edits today; links wait for L-8.
}
