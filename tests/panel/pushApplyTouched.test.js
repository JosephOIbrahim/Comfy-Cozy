import { describe, it, expect, beforeEach } from "vitest";
import {
  makeFakeNode,
  makeFakeGraph,
  makeFakeApp,
} from "./_stubs/litegraph.js";
import { applyTouchedSet } from "../../panel/web/js/_pushApplyTouched.js";

describe("L-2 applyTouchedSet — touched-only iteration (F-1 mitigation)", () => {
  let node5;
  let node9;
  let graph;
  let app;

  beforeEach(() => {
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

  it("empty touched is a no-op", () => {
    applyTouchedSet(app, {}, []);
    expect(node5.widgets[0].value).toBe(7.0);
    expect(node5.widgets[1].value).toBe(20);
    expect(node9.widgets[0].value).toBe(null);
  });

  it("widget entry writes widget.value", () => {
    applyTouchedSet(app, {}, [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
    ]);
    expect(node5.widgets[0].value).toBe(8.0);
    expect(node5.widgets[1].value).toBe(20);
  });

  it("widget entry where value already equal is a no-op", () => {
    applyTouchedSet(app, {}, [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 7.0 },
    ]);
    expect(node5.widgets[0].value).toBe(7.0);
  });

  it("widget entry for missing node is silent skip (L-3/L-4 surface later)", () => {
    expect(() =>
      applyTouchedSet(app, {}, [
        { node_id: "99", input_name: "cfg", kind: "widget", new_value: 8.0 },
      ])
    ).not.toThrow();
    expect(node5.widgets[0].value).toBe(7.0);
  });

  it("widget entry for missing input name is silent skip (L-5 surface later)", () => {
    expect(() =>
      applyTouchedSet(app, {}, [
        {
          node_id: "5",
          input_name: "nonexistent",
          kind: "widget",
          new_value: 8.0,
        },
      ])
    ).not.toThrow();
    expect(node5.widgets[0].value).toBe(7.0);
  });

  it("link entry is NOT applied (L-8 deferred)", () => {
    applyTouchedSet(app, {}, [
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
  });

  it("unknown kind is silently dropped", () => {
    applyTouchedSet(app, {}, [
      { node_id: "5", input_name: "cfg", kind: "unknown", new_value: 8.0 },
    ]);
    expect(node5.widgets[0].value).toBe(7.0);
  });

  it("multiple widget entries applied in order", () => {
    applyTouchedSet(app, {}, [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
      { node_id: "5", input_name: "steps", kind: "widget", new_value: 25 },
    ]);
    expect(node5.widgets[0].value).toBe(8.0);
    expect(node5.widgets[1].value).toBe(25);
  });

  it("F-1 scenario: director-edited untouched neighbour survives", () => {
    // Pre-state: director already edited node 5's cfg on canvas
    node5.widgets[0].value = 8.0;
    // Agent only touched node 9 (a link). pushAgentToCanvas runs:
    applyTouchedSet(app, {}, [
      {
        node_id: "9",
        input_name: "samples",
        kind: "link",
        new_value: ["7", 0],
      },
    ]);
    // Director's edit on node 5 is preserved (iteration never touched node 5)
    expect(node5.widgets[0].value).toBe(8.0);
    expect(node5.widgets[1].value).toBe(20);
  });

  it("F-1 scenario (widget-touched only): only touched widget changes", () => {
    // Director edited steps on canvas
    node5.widgets[1].value = 30;
    // Agent only touched cfg
    applyTouchedSet(app, {}, [
      { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
    ]);
    expect(node5.widgets[0].value).toBe(8.0); // agent's change applied
    expect(node5.widgets[1].value).toBe(30); // director's edit preserved
  });

  it("handles null app/graph gracefully", () => {
    expect(() => applyTouchedSet(null, {}, [])).not.toThrow();
    expect(() => applyTouchedSet({ graph: null }, {}, [])).not.toThrow();
    expect(() => applyTouchedSet({}, {}, [])).not.toThrow();
  });

  it("handles non-array touched gracefully", () => {
    expect(() => applyTouchedSet(app, {}, null)).not.toThrow();
    expect(() => applyTouchedSet(app, {}, undefined)).not.toThrow();
    expect(() => applyTouchedSet(app, {}, "not-array")).not.toThrow();
    expect(() => applyTouchedSet(app, {}, {})).not.toThrow();
    expect(node5.widgets[0].value).toBe(7.0);
  });

  it("handles entries that are not plain objects", () => {
    expect(() =>
      applyTouchedSet(app, {}, [null, undefined, "string", 42])
    ).not.toThrow();
    expect(node5.widgets[0].value).toBe(7.0);
  });

  it("skips widget entry where widget array is null", () => {
    const node10 = makeFakeNode(10);
    node10.widgets = null;
    graph._nodesById[10] = node10;
    expect(() =>
      applyTouchedSet(app, {}, [
        { node_id: "10", input_name: "x", kind: "widget", new_value: 1 },
      ])
    ).not.toThrow();
  });
});
