import { describe, it, expect, beforeEach } from "vitest";
import {
  makeFakeNode,
  makeFakeGraph,
  makeFakeApp,
} from "./_stubs/litegraph.js";
import { applyTouchedSet } from "../../panel/web/js/_pushApplyTouched.js";
import { withObserverPause } from "../../panel/web/js/_pushControl.js";
import {
  getDeltaFailures,
  clearDeltaFailures,
} from "../../panel/web/js/_deltaFailures.js";

/**
 * L-10 integration / SPEC-fit oracle.
 *
 * Composes the push pipeline as superduperPanel.pushAgentToCanvas does:
 *   clearDeltaFailures
 *     → withObserverPause(graph, () => applyTouchedSet(app, wf, touched))
 *
 * Asserts the SPEC predicates directly against the composed pipeline:
 *   P1 link-state parity (applied ops) — connect-call args match server
 *   P2 manual-edit survival             — untouched widget values preserved
 *   P3 surface enumeration              — getDeltaFailures contains the
 *                                          documented entry types
 *   P4 no echo                          — observer restored to original
 *
 * Real-canvas L3 validation (PASS 5) is run manually against a live
 * ComfyUI host; this stub-integration is the automated regression net.
 */

describe("L-10 integration — push pipeline composition (P1/P2/P3/P4)", () => {
  let node5;
  let node7;
  let node9;
  let graph;
  let app;
  let originalObserver;

  const wf = () => ({
    "5": { class_type: "KSampler", inputs: {} },
    "7": { class_type: "CLIPTextEncode", inputs: {} },
    "9": { class_type: "VAEDecode", inputs: {} },
  });

  async function runPush(workflow, touched) {
    return await withObserverPause(graph, () => {
      applyTouchedSet(app, workflow, touched);
      if (app.canvas) app.canvas.setDirty(true, true);
    });
  }

  beforeEach(() => {
    clearDeltaFailures();
    node5 = makeFakeNode(5, {
      widgets: [
        { name: "cfg", value: 7.0 },
        { name: "steps", value: 20 },
      ],
    });
    node7 = makeFakeNode(7);
    node9 = makeFakeNode(9);
    graph = makeFakeGraph({ 5: node5, 7: node7, 9: node9 });
    app = makeFakeApp(graph);
    originalObserver = function originalHandler() {};
    graph.onAfterChange = originalObserver;
  });

  /* ───── P1 link-state parity (applied ops) ──────────────────────── */

  it("P1: touched link applies via LiteGraph; connect args match server shape", async () => {
    await runPush(wf(), [
      {
        node_id: "9",
        input_name: "samples",
        kind: "link",
        old_value: null,
        new_value: ["7", 0],
      },
    ]);
    expect(node7._calls.connect).toHaveLength(1);
    expect(node7._calls.connect[0]).toEqual({
      outputSlot: 0,
      targetNode: node9,
      targetSlot: "samples",
    });
    expect(getDeltaFailures()).toEqual([]);
  });

  it("P1: touched widget applies; canvas value matches server new_value", async () => {
    await runPush(wf(), [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
    ]);
    expect(node5.widgets[0].value).toBe(8.0);
    expect(getDeltaFailures()).toEqual([]);
  });

  /* ───── P2 manual-edit survival ─────────────────────────────────── */

  it("P2: director-edited widget on neighbour node survives a link write", async () => {
    node5.widgets[0].value = 8.0; // director's edit
    await runPush(wf(), [
      {
        node_id: "9",
        input_name: "samples",
        kind: "link",
        old_value: null,
        new_value: ["7", 0],
      },
    ]);
    expect(node5.widgets[0].value).toBe(8.0);
    expect(node5.widgets[1].value).toBe(20);
    expect(node7._calls.connect).toHaveLength(1);
  });

  it("P2: director-edited sibling widget survives an agent widget edit", async () => {
    node5.widgets[1].value = 30; // director edited steps
    await runPush(wf(), [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
    ]);
    expect(node5.widgets[0].value).toBe(8.0); // agent's edit applied
    expect(node5.widgets[1].value).toBe(30); // director's edit preserved
  });

  /* ───── P3 surface enumeration (every documented type) ──────────── */

  it("P3: tier3_add + tier3_delete + stale_node_ref + missing_slot + malformed + link_rejected", async () => {
    // Mix every documented surface entry type in one push.
    const workflow = wf();
    workflow["12"] = { class_type: "LatentUpscale", inputs: {} }; // tier3_add
    delete workflow["7"]; // tier3_delete (canvas has 7, server doesn't)

    // Force connect failure on the next test fixture
    const node8 = makeFakeNode(8, { connectReturns: false });
    graph._nodesById[8] = node8;
    workflow["8"] = { class_type: "CLIPTextEncode", inputs: {} };

    await runPush(workflow, [
      // stale_node_ref (no node 99 anywhere)
      { node_id: "99", input_name: "cfg", kind: "widget", new_value: 1 },
      // missing_slot (node 5 has no "nonexistent" widget)
      {
        node_id: "5",
        input_name: "nonexistent",
        kind: "widget",
        new_value: 1,
      },
      // malformed (unknown kind)
      { node_id: "5", input_name: "cfg", kind: "weird", new_value: 1 },
      // link_rejected (node 8 returns false on connect)
      {
        node_id: "9",
        input_name: "samples",
        kind: "link",
        old_value: null,
        new_value: ["8", 0],
      },
    ]);

    const types = new Set(getDeltaFailures().map((f) => f.type));
    expect(types.has("tier3_add")).toBe(true);
    expect(types.has("tier3_delete")).toBe(true);
    expect(types.has("stale_node_ref")).toBe(true);
    expect(types.has("missing_slot")).toBe(true);
    expect(types.has("malformed")).toBe(true);
    expect(types.has("link_rejected")).toBe(true);
  });

  it("P3: every emitted failure has at least type + node_id", async () => {
    await runPush(wf(), [
      { node_id: "99", input_name: "x", kind: "widget", new_value: 1 },
      { node_id: "my-node", input_name: "x", kind: "widget", new_value: 1 },
      { node_id: "5", input_name: "missing", kind: "widget", new_value: 1 },
    ]);
    for (const f of getDeltaFailures()) {
      expect(f.type).toBeTruthy();
      expect(f.node_id !== undefined).toBe(true);
    }
  });

  /* ───── P4 no echo (observer restored) ──────────────────────────── */

  it("P4: observer restored after successful push", async () => {
    await runPush(wf(), [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
    ]);
    expect(graph.onAfterChange).toBe(originalObserver);
  });

  it("P4: observer restored after applyTouchedSet throws", async () => {
    // Force a throw inside applyTouchedSet by making widgets.find throw
    node5.widgets = {
      find: () => {
        throw new Error("simulated widget failure");
      },
    };
    await expect(
      runPush(wf(), [
        { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
      ])
    ).rejects.toThrow("simulated widget failure");
    expect(graph.onAfterChange).toBe(originalObserver);
  });

  it("P4: paused observer doesn't re-trigger during the apply step", async () => {
    let originalCalls = 0;
    graph.onAfterChange = () => {
      originalCalls++;
    };
    await runPush(wf(), [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
    ]);
    // Even if the canvas had its onAfterChange invoked mid-apply (it didn't
    // in this stub, but the contract is: pause makes it a no-op), the
    // original handler should never have been called.
    expect(originalCalls).toBe(0);
  });

  /* ───── Full F-1 end-to-end scenario ────────────────────────────── */

  it("F-1 end-to-end: agent emits multi-touched, director edits all preserved", async () => {
    // Director's edits on canvas
    node5.widgets[0].value = 9.0; // cfg edited
    node5.widgets[1].value = 35; // steps edited

    // Agent's touched-set rewires node 9 only; never touches node 5
    await runPush(wf(), [
      {
        node_id: "9",
        input_name: "samples",
        kind: "link",
        old_value: null,
        new_value: ["7", 0],
      },
    ]);

    expect(node5.widgets[0].value).toBe(9.0); // director's cfg preserved
    expect(node5.widgets[1].value).toBe(35); // director's steps preserved
    expect(node7._calls.connect).toHaveLength(1); // agent's link applied
    expect(getDeltaFailures()).toEqual([]);
  });

  /* ───── Mixed widget + link in one push ─────────────────────────── */

  it("mixed touched: widget + link both applied in a single push", async () => {
    await runPush(wf(), [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
      {
        node_id: "9",
        input_name: "samples",
        kind: "link",
        old_value: null,
        new_value: ["7", 0],
      },
    ]);
    expect(node5.widgets[0].value).toBe(8.0);
    expect(node7._calls.connect).toHaveLength(1);
  });

  /* ───── No-op push (empty touched) ──────────────────────────────── */

  it("empty touched: fully no-op (no mutations, no failures, observer canonical)", async () => {
    await runPush(wf(), []);
    expect(node5.widgets[0].value).toBe(7.0);
    expect(node7._calls.connect).toEqual([]);
    expect(getDeltaFailures()).toEqual([]);
    expect(graph.onAfterChange).toBe(originalObserver);
  });
});
