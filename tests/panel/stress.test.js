import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  makeFakeNode,
  makeFakeGraph,
  makeFakeApp,
} from "./_stubs/litegraph.js";
import { applyTouchedSet } from "../../panel/web/js/_pushApplyTouched.js";
import { runPushAgentToCanvas } from "../../panel/web/js/_pushOrchestrator.js";
import {
  withObserverPause,
  debounce,
} from "../../panel/web/js/_pushControl.js";
import {
  getDeltaFailures,
  clearDeltaFailures,
} from "../../panel/web/js/_deltaFailures.js";

/**
 * PASS 6 STRESS — adversarial / scale scenarios.
 *
 * Per the brief: attacks (clobber, echo, malformed-delta, stale-cache,
 * Tier-3-delta-arrives). Existing tests already cover correctness of
 * each attack class; this suite confirms behaviour holds AT SCALE and
 * under timing / concurrency pressure.
 */

describe("PASS 6 STRESS", () => {
  beforeEach(() => {
    clearDeltaFailures();
  });

  it("100 touched entries on one push apply correctly and quickly", () => {
    const nodes = {};
    const wf = {};
    const touched = [];
    for (let i = 0; i < 100; i++) {
      const n = makeFakeNode(i, {
        widgets: [{ name: "x", value: 0 }],
      });
      nodes[i] = n;
      wf[String(i)] = { class_type: "Test", inputs: {} };
      touched.push({
        node_id: String(i),
        input_name: "x",
        kind: "widget",
        new_value: i + 1,
      });
    }
    const graph = makeFakeGraph(nodes);
    const app = makeFakeApp(graph);

    const start = performance.now();
    applyTouchedSet(app, wf, touched);
    const elapsed = performance.now() - start;

    // Generous bound — a single push of 100 widget edits should be fast.
    expect(elapsed).toBeLessThan(100);
    for (let i = 0; i < 100; i++) {
      expect(nodes[i].widgets[0].value).toBe(i + 1);
    }
    expect(getDeltaFailures()).toEqual([]);
  });

  it("burst events: 50 calls in <10ms produce 1 debounced execution", () => {
    vi.useFakeTimers();
    try {
      const fn = vi.fn();
      const debounced = debounce(fn, 100);
      for (let i = 0; i < 50; i++) {
        debounced();
        vi.advanceTimersByTime(0); // same tick
      }
      // Hasn't fired yet
      expect(fn).not.toHaveBeenCalled();
      vi.advanceTimersByTime(100);
      expect(fn).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("Tier-3 with 50 canvas-only nodes surfaces 50 tier3_delete", () => {
    const nodes = {};
    for (let i = 0; i < 50; i++) {
      nodes[i] = makeFakeNode(i);
    }
    const graph = makeFakeGraph(nodes);
    const app = makeFakeApp(graph);

    applyTouchedSet(app, {}, []);

    const failures = getDeltaFailures();
    expect(failures).toHaveLength(50);
    for (const f of failures) {
      expect(f.type).toBe("tier3_delete");
    }
  });

  it("Tier-3 with 50 server-only nodes surfaces 50 tier3_add", () => {
    const graph = makeFakeGraph({});
    const app = makeFakeApp(graph);
    const wf = {};
    for (let i = 0; i < 50; i++) {
      wf[String(i)] = { class_type: `Class${i}`, inputs: {} };
    }
    applyTouchedSet(app, wf, []);

    const failures = getDeltaFailures();
    expect(failures).toHaveLength(50);
    for (const f of failures) {
      expect(f.type).toBe("tier3_add");
    }
  });

  it("overlapping observer-pauses: observer canonical after both settle", async () => {
    const graph = makeFakeGraph({});
    const original = function originalObserver() {};
    graph.onAfterChange = original;

    let releaseInner;
    const block = new Promise((resolve) => {
      releaseInner = resolve;
    });

    const wrapped = async () => {
      await withObserverPause(graph, async () => {
        await block;
      });
    };

    const p1 = wrapped();
    const p2 = wrapped();
    releaseInner();
    await Promise.all([p1, p2]);
    // Both pushes ran; their saves are nested but each restore puts
    // back the immediately-prior handler, so the eventual restore lands
    // on the original.
    expect(graph.onAfterChange).toBe(original);
  });

  it("slow ackPush (100ms) doesn't deadlock push", async () => {
    const node5 = makeFakeNode(5, { widgets: [{ name: "x", value: 0 }] });
    const graph = makeFakeGraph({ 5: node5 });
    const app = makeFakeApp(graph);
    const client = {
      getWorkflowApiWithTouched: vi.fn().mockResolvedValue({
        workflow: { "5": { class_type: "T", inputs: {} } },
        touched: [
          { node_id: "5", input_name: "x", kind: "widget", new_value: 1 },
        ],
      }),
      ackPush: vi.fn(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve({ ok: true }), 80)
          )
      ),
    };

    const start = performance.now();
    await runPushAgentToCanvas(app, client);
    const elapsed = performance.now() - start;
    // Push completes; should include the ack wait
    expect(elapsed).toBeGreaterThanOrEqual(75);
    expect(client.ackPush).toHaveBeenCalledTimes(1);
    expect(node5.widgets[0].value).toBe(1); // widget applied before the ack wait
  });

  it("mixed malformed deltas don't throw, all surface correctly", () => {
    const node5 = makeFakeNode(5, { widgets: [{ name: "x", value: 0 }] });
    const graph = makeFakeGraph({ 5: node5 });
    const app = makeFakeApp(graph);

    const malformedShapes = [
      // numeric node_id (number type) — _parseNodeId accepts numbers
      { node_id: 5, input_name: "x", kind: "widget", new_value: 1 },
      // unknown kind
      { node_id: "5", input_name: "x", kind: "weird", new_value: 1 },
      // node_id that fails strict numeric regex
      { node_id: "5abc", input_name: "x", kind: "widget", new_value: 1 },
      // undefined node_id
      { node_id: undefined, input_name: "x", kind: "widget", new_value: 1 },
      // very large numeric node_id (still parseable)
      { node_id: "999999999", input_name: "x", kind: "widget", new_value: 1 },
    ];

    expect(() =>
      applyTouchedSet(
        app,
        { "5": { class_type: "T", inputs: {} } },
        malformedShapes
      )
    ).not.toThrow();

    const failures = getDeltaFailures();
    // expect at least: kind=weird → malformed, "5abc" → malformed,
    // undefined → malformed, 999999999 → stale_node_ref (passes parse,
    // not on canvas)
    const types = failures.map((f) => f.type);
    expect(types).toContain("malformed");
    expect(types).toContain("stale_node_ref");
    // The valid numeric "5" entry should have applied (value=1)
    expect(node5.widgets[0].value).toBe(1);
  });

  it("rapid push sequence (5 pushes in series) leaves canvas + observer correct", async () => {
    const node5 = makeFakeNode(5, { widgets: [{ name: "x", value: 0 }] });
    const graph = makeFakeGraph({ 5: node5 });
    const original = function () {};
    graph.onAfterChange = original;
    const app = makeFakeApp(graph);

    let pushCount = 0;
    const client = {
      getWorkflowApiWithTouched: vi.fn(async () => {
        pushCount++;
        return {
          workflow: { "5": { class_type: "T", inputs: {} } },
          touched: [
            {
              node_id: "5",
              input_name: "x",
              kind: "widget",
              new_value: pushCount,
            },
          ],
        };
      }),
      ackPush: vi.fn().mockResolvedValue({ ok: true }),
    };

    for (let i = 0; i < 5; i++) {
      await runPushAgentToCanvas(app, client);
    }

    expect(client.ackPush).toHaveBeenCalledTimes(5);
    expect(node5.widgets[0].value).toBe(5); // last push's value sticks
    expect(graph.onAfterChange).toBe(original); // observer canonical
  });
});
