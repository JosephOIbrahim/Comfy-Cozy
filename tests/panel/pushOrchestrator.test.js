import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  makeFakeNode,
  makeFakeGraph,
  makeFakeApp,
} from "./_stubs/litegraph.js";
import { runPushAgentToCanvas } from "../../panel/web/js/_pushOrchestrator.js";
import {
  getDeltaFailures,
  clearDeltaFailures,
} from "../../panel/web/js/_deltaFailures.js";

/**
 * PASS 5 proxy — end-to-end push pipeline with a vi.fn()-stubbed client
 * and a fake LiteGraph app. Closes the loop that L-10 (integration on
 * applyTouchedSet alone) couldn't reach: the full orchestration order
 * (clear → fetch → pause → apply → setDirty → ackPush), early-return
 * branches, error swallowing, and the ackPush-fails path.
 *
 * Real-canvas L3 (PASS 5 manual) is still the last-mile validation
 * against a live ComfyUI host; this suite is the automated regression
 * net that catches refactor breakage between PASS 4 and PASS 5.
 */

describe("PASS 5 proxy — runPushAgentToCanvas full pipeline", () => {
  let node5;
  let node7;
  let node9;
  let graph;
  let app;
  let originalObserver;
  let client;

  const wf = () => ({
    "5": { class_type: "KSampler", inputs: {} },
    "7": { class_type: "CLIPTextEncode", inputs: {} },
    "9": { class_type: "VAEDecode", inputs: {} },
  });

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
    client = {
      getWorkflowApiWithTouched: vi.fn(),
      ackPush: vi.fn().mockResolvedValue({ ok: true }),
    };
  });

  /* ───── Happy paths ─────────────────────────────────────────────── */

  it("happy widget: client returns touched widget → canvas mutated → ackPush", async () => {
    client.getWorkflowApiWithTouched.mockResolvedValue({
      workflow: wf(),
      touched: [
        { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
      ],
    });

    await runPushAgentToCanvas(app, client);

    expect(node5.widgets[0].value).toBe(8.0);
    expect(client.ackPush).toHaveBeenCalledTimes(1);
    expect(getDeltaFailures()).toEqual([]);
    expect(graph.onAfterChange).toBe(originalObserver);
  });

  it("happy link: client returns touched link → connect called → ackPush", async () => {
    client.getWorkflowApiWithTouched.mockResolvedValue({
      workflow: wf(),
      touched: [
        {
          node_id: "9",
          input_name: "samples",
          kind: "link",
          old_value: null,
          new_value: ["7", 0],
        },
      ],
    });

    await runPushAgentToCanvas(app, client);

    expect(node7._calls.connect).toHaveLength(1);
    expect(node7._calls.connect[0]).toEqual({
      outputSlot: 0,
      targetNode: node9,
      targetSlot: "samples",
    });
    expect(client.ackPush).toHaveBeenCalledTimes(1);
    expect(graph.onAfterChange).toBe(originalObserver);
  });

  it("empty touched: no mutations but ackPush still called (rotates snapshot)", async () => {
    client.getWorkflowApiWithTouched.mockResolvedValue({
      workflow: wf(),
      touched: [],
    });

    await runPushAgentToCanvas(app, client);

    expect(node5.widgets[0].value).toBe(7.0);
    expect(node7._calls.connect).toEqual([]);
    expect(client.ackPush).toHaveBeenCalledTimes(1);
    expect(graph.onAfterChange).toBe(originalObserver);
  });

  /* ───── Early-return paths ──────────────────────────────────────── */

  it("client returns null: no mutations, no ackPush", async () => {
    client.getWorkflowApiWithTouched.mockResolvedValue(null);

    await runPushAgentToCanvas(app, client);

    expect(node5.widgets[0].value).toBe(7.0);
    expect(client.ackPush).not.toHaveBeenCalled();
  });

  it("client returns workflow=null: no mutations, no ackPush", async () => {
    client.getWorkflowApiWithTouched.mockResolvedValue({
      workflow: null,
      touched: [],
    });

    await runPushAgentToCanvas(app, client);

    expect(client.ackPush).not.toHaveBeenCalled();
  });

  it("app.graph absent: no mutations, no ackPush", async () => {
    client.getWorkflowApiWithTouched.mockResolvedValue({
      workflow: wf(),
      touched: [
        { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
      ],
    });
    const appNoGraph = { graph: null, canvas: { setDirty() {} } };

    await runPushAgentToCanvas(appNoGraph, client);

    expect(node5.widgets[0].value).toBe(7.0);
    expect(client.ackPush).not.toHaveBeenCalled();
  });

  /* ───── ackPush failure path ────────────────────────────────────── */

  it("ackPush throws: error swallowed, push otherwise succeeds", async () => {
    client.getWorkflowApiWithTouched.mockResolvedValue({
      workflow: wf(),
      touched: [
        { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
      ],
    });
    client.ackPush.mockRejectedValue(new Error("network down"));

    await expect(runPushAgentToCanvas(app, client)).resolves.toBeUndefined();
    expect(node5.widgets[0].value).toBe(8.0); // widget still applied
    expect(graph.onAfterChange).toBe(originalObserver); // observer restored
  });

  it("getWorkflowApiWithTouched throws: error swallowed", async () => {
    client.getWorkflowApiWithTouched.mockRejectedValue(
      new Error("fetch failed")
    );

    await expect(runPushAgentToCanvas(app, client)).resolves.toBeUndefined();
    expect(client.ackPush).not.toHaveBeenCalled();
    expect(graph.onAfterChange).toBe(originalObserver);
  });

  /* ───── Surface propagation (P3 through orchestrator) ───────────── */

  it("P3 propagates: surfaces from applyTouchedSet visible after orchestrator", async () => {
    client.getWorkflowApiWithTouched.mockResolvedValue({
      workflow: wf(),
      touched: [
        // stale_node_ref
        { node_id: "99", input_name: "x", kind: "widget", new_value: 1 },
        // missing_slot
        {
          node_id: "5",
          input_name: "nope",
          kind: "widget",
          new_value: 1,
        },
      ],
    });

    await runPushAgentToCanvas(app, client);

    const types = new Set(getDeltaFailures().map((f) => f.type));
    expect(types.has("stale_node_ref")).toBe(true);
    expect(types.has("missing_slot")).toBe(true);
    // ackPush still called even with failures — they don't block the
    // snapshot rotation. (The applied ops did apply; surfaces are info.)
    expect(client.ackPush).toHaveBeenCalledTimes(1);
  });

  /* ───── L-7 lifecycle: clearDeltaFailures runs first ────────────── */

  it("L-7 lifecycle: stale failures from a prior push are cleared", async () => {
    // Simulate prior failures hanging around
    const { addDeltaFailure } = await import(
      "../../panel/web/js/_deltaFailures.js"
    );
    addDeltaFailure({ type: "tier3_add", node_id: "stale-from-before" });
    expect(getDeltaFailures()).toHaveLength(1);

    client.getWorkflowApiWithTouched.mockResolvedValue({
      workflow: wf(),
      touched: [],
    });
    await runPushAgentToCanvas(app, client);

    // After push, the stale failure is gone (clearDeltaFailures ran first)
    expect(getDeltaFailures()).toEqual([]);
  });

  /* ───── F-1 end-to-end through orchestrator ─────────────────────── */

  it("F-1 end-to-end: director edits + agent push, both survive", async () => {
    node5.widgets[0].value = 9.0; // director's cfg edit on canvas
    node5.widgets[1].value = 35; // director's steps edit on canvas

    client.getWorkflowApiWithTouched.mockResolvedValue({
      workflow: wf(),
      touched: [
        {
          node_id: "9",
          input_name: "samples",
          kind: "link",
          old_value: null,
          new_value: ["7", 0],
        },
      ],
    });

    await runPushAgentToCanvas(app, client);

    expect(node5.widgets[0].value).toBe(9.0); // director preserved
    expect(node5.widgets[1].value).toBe(35); // director preserved
    expect(node7._calls.connect).toHaveLength(1); // agent applied
    expect(client.ackPush).toHaveBeenCalledTimes(1);
  });

  /* ───── Call-order discipline ───────────────────────────────────── */

  it("call order: getWorkflowApiWithTouched precedes ackPush", async () => {
    const callOrder = [];
    client.getWorkflowApiWithTouched.mockImplementation(async () => {
      callOrder.push("getWorkflowApiWithTouched");
      return { workflow: wf(), touched: [] };
    });
    client.ackPush.mockImplementation(async () => {
      callOrder.push("ackPush");
      return { ok: true };
    });

    await runPushAgentToCanvas(app, client);

    expect(callOrder).toEqual(["getWorkflowApiWithTouched", "ackPush"]);
  });

  it("observer paused during apply, restored before ackPush returns", async () => {
    let observerDuringApply;
    client.getWorkflowApiWithTouched.mockResolvedValue({
      workflow: wf(),
      touched: [
        { node_id: "5", input_name: "cfg", kind: "widget", new_value: 8.0 },
      ],
    });
    // Hook setDirty as the moment-in-the-pause to snapshot the observer
    app.canvas.setDirty = () => {
      observerDuringApply = graph.onAfterChange;
    };

    await runPushAgentToCanvas(app, client);

    expect(observerDuringApply).not.toBe(originalObserver);
    expect(typeof observerDuringApply).toBe("function");
    expect(graph.onAfterChange).toBe(originalObserver);
  });
});
