import { describe, it, expect } from "vitest";
import { makeFakeNode, makeFakeGraph, makeFakeApp } from "./_stubs/litegraph.js";

describe("L-0 Vitest stack", () => {
  it("runs at all", () => {
    expect(1 + 1).toBe(2);
  });

  it("fake graph resolves nodes by id and returns null for absent ids", () => {
    const node5 = makeFakeNode(5);
    const graph = makeFakeGraph({ 5: node5 });
    expect(graph.getNodeById(5)).toBe(node5);
    expect(graph.getNodeById(99)).toBe(null);
  });

  it("fake node records connect / disconnectInput / disconnectOutput calls", () => {
    const source = makeFakeNode(7);
    const target = makeFakeNode(9);

    source.connect(0, target, "samples");
    target.disconnectInput("samples");
    source.disconnectOutput(0, target);

    expect(source._calls.connect).toEqual([
      { outputSlot: 0, targetNode: target, targetSlot: "samples" },
    ]);
    expect(target._calls.disconnectInput).toEqual(["samples"]);
    expect(source._calls.disconnectOutput).toEqual([
      { slot: 0, targetNode: target },
    ]);
  });

  it("fake app wires canvas + graph", () => {
    const app = makeFakeApp();
    expect(app.graph).toBeDefined();
    expect(typeof app.canvas.setDirty).toBe("function");
    // Smoke: setDirty does not throw
    app.canvas.setDirty(true, true);
  });
});
