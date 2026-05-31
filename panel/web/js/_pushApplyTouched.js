/**
 * Pure touched-set apply logic for write-back v1.
 *
 * Given a {workflow, touched} response from the server and the live
 * LiteGraph app, applies each touched entry to the canvas. Iteration
 * is over touched entries ONLY — never over the full workflow — so
 * director-edited slots survive every push (F-1 mitigation).
 *
 * Surface contract (SPEC P3): every emitted delta is applied or
 * surfaced via addDeltaFailure. Pipeline:
 *
 *   L-2  consumer iteration                        (this file)
 *   L-3  ID-shape parse + parse-failure surfacing  (this file)
 *   L-4  Tier-3 detection (top-level)              (this file)
 *   L-5  unknown-kind / missing-slot surfacing     (this file)
 *   L-8  link primitive apply via LiteGraph        (this file)
 *
 * Pure-ish: this module reads the `app` passed in. It does not import
 * the host app module. Tests pass a fake app from
 * tests/panel/_stubs/litegraph.js.
 */

import { addDeltaFailure } from "./_deltaFailures.js";

export function applyTouchedSet(app, workflow, touched) {
  if (!app || !app.graph) return;

  // L-4: detect Tier-3-shaped deltas (node adds/deletes) at the top.
  // These are surfaced, NEVER applied — Tier-3 is out of scope for
  // write-back v1.
  const tier3 = _detectTier3(app.graph, workflow);
  for (const entry of tier3.add) {
    addDeltaFailure({
      type: "tier3_add",
      node_id: entry.node_id,
      class_type: entry.class_type,
      reason: "server has node not on canvas",
    });
  }
  for (const entry of tier3.delete) {
    addDeltaFailure({
      type: "tier3_delete",
      node_id: entry.node_id,
      reason: "canvas has node not in server workflow",
    });
  }
  const tier3Ids = new Set([
    ...tier3.add.map((e) => String(e.node_id)),
    ...tier3.delete.map((e) => String(e.node_id)),
  ]);

  if (!Array.isArray(touched)) return;

  for (const entry of touched) {
    if (!entry || typeof entry !== "object") continue;
    // If the touched entry refers to a Tier-3 node, the Tier-3 surface
    // already captured it; skip the per-touched apply.
    if (tier3Ids.has(String(entry.node_id))) continue;

    if (entry.kind === "widget") {
      _applyTouchedWidget(app, entry);
    } else if (entry.kind === "link") {
      _applyTouchedLink(app, entry);
    } else {
      // L-5: unknown kind → malformed input shape; surface, don't apply.
      addDeltaFailure({
        type: "malformed",
        node_id: entry.node_id,
        input_name: entry.input_name,
        raw_value: entry.new_value,
        reason: `unknown input shape (kind=${entry.kind})`,
      });
    }
  }
}

function _applyTouchedWidget(app, entry) {
  const parsed = _parseNodeId(entry.node_id);
  if (!parsed.ok) {
    addDeltaFailure({
      type: "malformed",
      node_id: entry.node_id,
      input_name: entry.input_name,
      reason: "non-numeric node id",
    });
    return;
  }
  const node = app.graph.getNodeById(parsed.id);
  if (!node) {
    addDeltaFailure({
      type: "stale_node_ref",
      node_id: entry.node_id,
      input_name: entry.input_name,
      reason: "node not present on canvas",
    });
    return;
  }
  if (!node.widgets) {
    addDeltaFailure({
      type: "missing_slot",
      node_id: entry.node_id,
      input_name: entry.input_name,
      reason: "node has no widgets",
    });
    return;
  }
  const widget = node.widgets.find((w) => w && w.name === entry.input_name);
  if (!widget) {
    addDeltaFailure({
      type: "missing_slot",
      node_id: entry.node_id,
      input_name: entry.input_name,
      reason: "widget not found",
    });
    return;
  }
  if (widget.value !== entry.new_value) {
    widget.value = entry.new_value;
  }
}

function _applyTouchedLink(app, entry) {
  const parsed = _parseNodeId(entry.node_id);
  if (!parsed.ok) {
    addDeltaFailure({
      type: "malformed",
      node_id: entry.node_id,
      input_name: entry.input_name,
      reason: "non-numeric node id",
    });
    return;
  }
  const toNode = app.graph.getNodeById(parsed.id);
  if (!toNode) {
    addDeltaFailure({
      type: "stale_node_ref",
      node_id: entry.node_id,
      input_name: entry.input_name,
      reason: "node not present on canvas",
    });
    return;
  }

  const oldVal = entry.old_value;
  const newVal = entry.new_value;
  // Compute deltas once. Same link (old == new) flips both flags off
  // so this becomes a no-op — defensive guard for server emitting a
  // same-value touched entry (the server's L-1 diff normally filters
  // these out at workflow_patch source).
  const needsDisconnect = _isLink(oldVal) && !_linkEq(oldVal, newVal);
  const needsConnect = _isLink(newVal) && !_linkEq(oldVal, newVal);

  // L-8: disconnect first when transitioning between link sources.
  // LiteGraph's disconnectInput accepts the input slot NAME or index;
  // we pass the name to match the connect_nodes server contract
  // (workflow_patch.py:295-326).
  if (needsDisconnect) {
    const ok = toNode.disconnectInput(entry.input_name);
    if (ok === false) {
      addDeltaFailure({
        type: "link_rejected",
        node_id: entry.node_id,
        input_name: entry.input_name,
        reason: "disconnectInput returned falsy",
      });
      return;
    }
  }

  if (needsConnect) {
    const fromIdRaw = newVal[0];
    const fromOutputIdx = newVal[1];
    const fromParsed = _parseNodeId(fromIdRaw);
    if (!fromParsed.ok) {
      addDeltaFailure({
        type: "malformed",
        node_id: fromIdRaw,
        input_name: entry.input_name,
        reason: "non-numeric from-node id",
      });
      return;
    }
    const fromNode = app.graph.getNodeById(fromParsed.id);
    if (!fromNode) {
      addDeltaFailure({
        type: "stale_node_ref",
        node_id: fromIdRaw,
        input_name: entry.input_name,
        reason: "from-node not present on canvas",
      });
      return;
    }
    // L-8: LiteGraph's connect signature is
    //   from_node.connect(from_slot, target_node, target_slot_or_name).
    // Server emits from_output as int → pass directly. Target slot is
    // the input NAME from the touched entry.
    const ok = fromNode.connect(fromOutputIdx, toNode, entry.input_name);
    if (ok === false) {
      addDeltaFailure({
        type: "link_rejected",
        node_id: entry.node_id,
        input_name: entry.input_name,
        reason: "from-node connect returned falsy",
      });
      return;
    }
  }
}

function _detectTier3(graph, workflow) {
  if (!workflow || typeof workflow !== "object" || !graph) {
    return { add: [], delete: [] };
  }
  // LiteGraph exposes graph._nodes as an array; the test stub mirrors this.
  if (!Array.isArray(graph._nodes)) {
    return { add: [], delete: [] };
  }

  const serverIds = new Set(Object.keys(workflow));
  const canvasIds = new Set(
    graph._nodes
      .filter((n) => n && n.id !== undefined && n.id !== null)
      .map((n) => String(n.id))
  );

  const add = [];
  for (const sid of serverIds) {
    if (!canvasIds.has(sid)) {
      const node = workflow[sid];
      add.push({
        node_id: sid,
        class_type:
          node && typeof node === "object" ? node.class_type : undefined,
      });
    }
  }

  const del = [];
  for (const cid of canvasIds) {
    if (!serverIds.has(cid)) {
      del.push({ node_id: cid });
    }
  }

  return { add, delete: del };
}

function _parseNodeId(raw) {
  if (raw === null || raw === undefined) {
    return { ok: false };
  }
  if (typeof raw !== "string" && typeof raw !== "number") {
    return { ok: false };
  }
  const s = String(raw).trim();
  if (s === "" || !/^-?\d+$/.test(s)) {
    return { ok: false };
  }
  return { ok: true, id: parseInt(s, 10) };
}

function _isLink(v) {
  return (
    Array.isArray(v) &&
    v.length === 2 &&
    typeof v[0] === "string" &&
    typeof v[1] === "number" &&
    !Number.isNaN(v[1])
  );
}

function _linkEq(a, b) {
  return _isLink(a) && _isLink(b) && a[0] === b[0] && a[1] === b[1];
}
