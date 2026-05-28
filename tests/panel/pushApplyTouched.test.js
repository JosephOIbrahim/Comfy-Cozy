import { describe, it, expect, beforeEach } from "vitest";
import {
  makeFakeNode,
  makeFakeGraph,
  makeFakeApp,
} from "./_stubs/litegraph.js";
import { applyTouchedSet } from "../../panel/web/js/_pushApplyTouched.js";
import {
  getDeltaFailures,
  clearDeltaFailures,
} from "../../panel/web/js/_deltaFailures.js";

/**
 * Canvas fixture: nodes 5 (KSampler with cfg+steps widgets) and 9
 * (VAEDecode with samples widget). The server workflow that MATCHES
 * this canvas is `wfBase()` — tests that don't want to trigger Tier-3
 * detect pass this; tests that DO want Tier-3 build a different shape.
 */
const wfBase = () => ({
  "5": { class_type: "KSampler", inputs: {} },
  "9": { class_type: "VAEDecode", inputs: {} },
});

describe("applyTouchedSet — L-2 widget apply + L-3/L-4/L-5 surfacing", () => {
  let node5;
  let node9;
  let graph;
  let app;

  beforeEach(() => {
    clearDeltaFailures();
    node5 = makeFakeNode(5, {
      widgets: [
        { name: "cfg", value: 7.0 },
        { name: "steps", value: 20 },
      ],
    });
    node9 = makeFakeNode(9, {
      widgets: [{ name: "samples", value: null }],
    });
    graph = makeFakeGraph({ 5: node5, 9: node9 });
    app = makeFakeApp(graph);
  });

  /* ───── L-2 baseline ─────────────────────────────────────────────── */

  it("empty touched is a no-op", () => {
    applyTouchedSet(app, wfBase(), []);
    expect(node5.widgets[0].value).toBe(7.0);
    expect(getDeltaFailures()).toEqual([]);
  });

  it("widget entry writes widget.value", () => {
    applyTouchedSet(app, wfBase(), [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
    ]);
    expect(node5.widgets[0].value).toBe(8.0);
    expect(getDeltaFailures()).toEqual([]);
  });

  it("widget entry where value already equal is a no-op", () => {
    applyTouchedSet(app, wfBase(), [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 7.0 },
    ]);
    expect(node5.widgets[0].value).toBe(7.0);
    expect(getDeltaFailures()).toEqual([]);
  });

  it("multiple widget entries applied in order", () => {
    applyTouchedSet(app, wfBase(), [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
      { node_id: "5", input_name: "steps", kind: "widget", new_value: 25 },
    ]);
    expect(node5.widgets[0].value).toBe(8.0);
    expect(node5.widgets[1].value).toBe(25);
    expect(getDeltaFailures()).toEqual([]);
  });

  /* ───── L-3: ID parse failure surfacing ──────────────────────────── */

  describe("L-3 ID parse failures", () => {
    it("non-numeric node id surfaces malformed (widget)", () => {
      applyTouchedSet(app, wfBase(), [
        {
          node_id: "my-node",
          input_name: "cfg",
          kind: "widget",
          new_value: 8.0,
        },
      ]);
      const failures = getDeltaFailures();
      expect(failures).toHaveLength(1);
      expect(failures[0]).toMatchObject({
        type: "malformed",
        node_id: "my-node",
        input_name: "cfg",
        reason: "non-numeric node id",
      });
      expect(node5.widgets[0].value).toBe(7.0);
    });

    it("non-numeric node id surfaces malformed (link)", () => {
      applyTouchedSet(app, wfBase(), [
        {
          node_id: "subgraph:0",
          input_name: "samples",
          kind: "link",
          new_value: ["7", 0],
        },
      ]);
      const failures = getDeltaFailures();
      expect(failures).toHaveLength(1);
      expect(failures[0].type).toBe("malformed");
      expect(failures[0].reason).toBe("non-numeric node id");
    });

    it("empty string node id surfaces malformed", () => {
      applyTouchedSet(app, wfBase(), [
        { node_id: "", input_name: "x", kind: "widget", new_value: 1 },
      ]);
      expect(getDeltaFailures()[0].type).toBe("malformed");
    });

    it("null node id surfaces malformed", () => {
      applyTouchedSet(app, wfBase(), [
        { node_id: null, input_name: "x", kind: "widget", new_value: 1 },
      ]);
      expect(getDeltaFailures()[0].type).toBe("malformed");
    });

    it("numeric string '42' passes parse and applies", () => {
      const node42 = makeFakeNode(42, {
        widgets: [{ name: "x", value: 0 }],
      });
      graph._nodesById[42] = node42;
      const wf = wfBase();
      wf["42"] = { class_type: "Some", inputs: {} };
      applyTouchedSet(app, wf, [
        { node_id: "42", input_name: "x", kind: "widget", new_value: 9 },
      ]);
      expect(getDeltaFailures()).toEqual([]);
      expect(node42.widgets[0].value).toBe(9);
    });
  });

  /* ───── L-4: Tier-3 detection (top-level) ────────────────────────── */

  describe("L-4 Tier-3 detection", () => {
    it("server-only node surfaces tier3_add", () => {
      const wf = wfBase();
      wf["12"] = { class_type: "LatentUpscale", inputs: {} };
      applyTouchedSet(app, wf, []);
      const failures = getDeltaFailures();
      expect(failures).toHaveLength(1);
      expect(failures[0]).toMatchObject({
        type: "tier3_add",
        node_id: "12",
        class_type: "LatentUpscale",
      });
    });

    it("canvas-only node surfaces tier3_delete", () => {
      // server has only node 5; canvas has 5 and 9 → 9 is canvas-only
      const wf = { "5": { class_type: "KSampler", inputs: {} } };
      applyTouchedSet(app, wf, []);
      const failures = getDeltaFailures();
      expect(failures).toHaveLength(1);
      expect(failures[0]).toMatchObject({
        type: "tier3_delete",
        node_id: "9",
      });
    });

    it("Tier-3 add + delete coexist", () => {
      // server has 5 and 12; canvas has 5 and 9 → 12 is add, 9 is delete
      const wf = {
        "5": { class_type: "KSampler", inputs: {} },
        "12": { class_type: "LatentUpscale", inputs: {} },
      };
      applyTouchedSet(app, wf, []);
      const types = getDeltaFailures()
        .map((f) => f.type)
        .sort();
      expect(types).toEqual(["tier3_add", "tier3_delete"]);
    });

    it("touched entry on Tier-3 node is skipped in main loop", () => {
      const wf = wfBase();
      wf["12"] = { class_type: "LatentUpscale", inputs: {} };
      applyTouchedSet(app, wf, [
        { node_id: "12", input_name: "x", kind: "widget", new_value: 1 },
      ]);
      const failures = getDeltaFailures();
      const tier3 = failures.filter((f) => f.type === "tier3_add");
      const stale = failures.filter((f) => f.type === "stale_node_ref");
      expect(tier3).toHaveLength(1);
      expect(stale).toHaveLength(0);
    });
  });

  describe("L-4 per-touched stale node ref", () => {
    it("touched entry for missing node (not in workflow either) surfaces stale_node_ref", () => {
      // wfBase has 5 and 9; touched references 99 — not in workflow,
      // not on canvas — purely stale agent reference.
      applyTouchedSet(app, wfBase(), [
        { node_id: "99", input_name: "cfg", kind: "widget", new_value: 8.0 },
      ]);
      const failures = getDeltaFailures();
      expect(failures).toHaveLength(1);
      expect(failures[0].type).toBe("stale_node_ref");
      expect(node5.widgets[0].value).toBe(7.0);
    });
  });

  /* ───── L-5: missing-slot + unknown-kind ─────────────────────────── */

  describe("L-5 missing-slot + unknown-kind", () => {
    it("widget entry for missing input name surfaces missing_slot", () => {
      applyTouchedSet(app, wfBase(), [
        {
          node_id: "5",
          input_name: "nonexistent",
          kind: "widget",
          new_value: 8.0,
        },
      ]);
      const failures = getDeltaFailures();
      expect(failures).toHaveLength(1);
      expect(failures[0]).toMatchObject({
        type: "missing_slot",
        node_id: "5",
        input_name: "nonexistent",
        reason: "widget not found",
      });
      expect(node5.widgets[0].value).toBe(7.0);
    });

    it("widget entry on node with null widgets array surfaces missing_slot", () => {
      const node10 = makeFakeNode(10);
      node10.widgets = null;
      graph._nodesById[10] = node10;
      const wf = wfBase();
      wf["10"] = { class_type: "Some", inputs: {} };
      applyTouchedSet(app, wf, [
        { node_id: "10", input_name: "x", kind: "widget", new_value: 1 },
      ]);
      const failures = getDeltaFailures();
      expect(failures).toHaveLength(1);
      expect(failures[0].type).toBe("missing_slot");
      expect(failures[0].reason).toBe("node has no widgets");
    });

    it("unknown kind surfaces malformed", () => {
      applyTouchedSet(app, wfBase(), [
        {
          node_id: "5",
          input_name: "cfg",
          kind: "unknown",
          new_value: 8.0,
        },
      ]);
      const failures = getDeltaFailures();
      expect(failures).toHaveLength(1);
      expect(failures[0]).toMatchObject({
        type: "malformed",
        node_id: "5",
        input_name: "cfg",
        raw_value: 8.0,
      });
      expect(failures[0].reason).toContain("unknown");
    });
  });

  /* ───── L-8 deferred (link no-op) ────────────────────────────────── */

  it("link entry on existing node is NOT applied (L-8 deferred) — no failures", () => {
    applyTouchedSet(app, wfBase(), [
      {
        node_id: "9",
        input_name: "samples",
        kind: "link",
        old_value: ["7", 0],
        new_value: ["8", 0],
      },
    ]);
    expect(node9._calls.connect).toEqual([]);
    expect(node9._calls.disconnectInput).toEqual([]);
    expect(getDeltaFailures()).toEqual([]);
  });

  /* ───── F-1 scenarios (P2 preservation) ──────────────────────────── */

  describe("F-1 director-edit survival", () => {
    it("director-edited untouched neighbour survives (link touch)", () => {
      node5.widgets[0].value = 8.0; // director's edit on canvas
      applyTouchedSet(app, wfBase(), [
        {
          node_id: "9",
          input_name: "samples",
          kind: "link",
          new_value: ["7", 0],
        },
      ]);
      expect(node5.widgets[0].value).toBe(8.0);
      expect(node5.widgets[1].value).toBe(20);
    });

    it("director-edited sibling widget survives (widget touch)", () => {
      node5.widgets[1].value = 30; // director edited steps
      applyTouchedSet(app, wfBase(), [
        { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
      ]);
      expect(node5.widgets[0].value).toBe(8.0);
      expect(node5.widgets[1].value).toBe(30);
    });
  });

  /* ───── safety / null-input ──────────────────────────────────────── */

  describe("safety", () => {
    it("handles null app/graph gracefully", () => {
      expect(() => applyTouchedSet(null, wfBase(), [])).not.toThrow();
      expect(() => applyTouchedSet({ graph: null }, wfBase(), [])).not.toThrow();
      expect(() => applyTouchedSet({}, wfBase(), [])).not.toThrow();
    });

    it("handles non-array touched gracefully", () => {
      expect(() => applyTouchedSet(app, wfBase(), null)).not.toThrow();
      expect(() => applyTouchedSet(app, wfBase(), undefined)).not.toThrow();
      expect(() => applyTouchedSet(app, wfBase(), "not-array")).not.toThrow();
      expect(() => applyTouchedSet(app, wfBase(), {})).not.toThrow();
      expect(node5.widgets[0].value).toBe(7.0);
    });

    it("handles entries that are not plain objects", () => {
      expect(() =>
        applyTouchedSet(app, wfBase(), [null, undefined, "string", 42])
      ).not.toThrow();
      expect(node5.widgets[0].value).toBe(7.0);
    });

    it("null workflow skips Tier-3 detect cleanly", () => {
      // When workflow is null/undefined, Tier-3 detect returns empty
      // and the main loop still runs (touched only).
      applyTouchedSet(app, null, [
        { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
      ]);
      expect(node5.widgets[0].value).toBe(8.0);
    });
  });
});
