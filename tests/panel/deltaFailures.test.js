import { describe, it, expect, beforeEach } from "vitest";
import {
  addDeltaFailure,
  getDeltaFailures,
  clearDeltaFailures,
  deltaFailureCount,
} from "../../panel/web/js/_deltaFailures.js";

describe("L-7 delta-failure accumulator", () => {
  beforeEach(() => {
    clearDeltaFailures();
  });

  it("starts empty after clear", () => {
    expect(deltaFailureCount()).toBe(0);
    expect(getDeltaFailures()).toEqual([]);
  });

  it("records entries of every documented type", () => {
    addDeltaFailure({ type: "tier3_add", node_id: 12, class_type: "LatentUpscale" });
    addDeltaFailure({ type: "tier3_delete", node_id: 5 });
    addDeltaFailure({ type: "stale_node_ref", node_id: 99 });
    addDeltaFailure({ type: "missing_slot", node_id: 7, input_name: "samples" });
    addDeltaFailure({
      type: "malformed",
      node_id: 7,
      input_name: "ctrl",
      raw_value: ["7"],
      reason: "link shape: length=1",
    });
    addDeltaFailure({
      type: "link_rejected",
      node_id: 9,
      input_name: "samples",
      reason: "LiteGraph connect returned falsy",
    });

    expect(deltaFailureCount()).toBe(6);
    const entries = getDeltaFailures();
    expect(entries[0].type).toBe("tier3_add");
    expect(entries[3].input_name).toBe("samples");
    expect(entries[4].raw_value).toEqual(["7"]);
  });

  it("getDeltaFailures returns a copy, not the internal array", () => {
    addDeltaFailure({ type: "stale_node_ref", node_id: 5 });
    const snapshot = getDeltaFailures();
    snapshot.push({ type: "fake", node_id: 99 });
    expect(deltaFailureCount()).toBe(1);
  });

  it("clearDeltaFailures empties the list", () => {
    addDeltaFailure({ type: "stale_node_ref", node_id: 5 });
    addDeltaFailure({ type: "stale_node_ref", node_id: 6 });
    clearDeltaFailures();
    expect(deltaFailureCount()).toBe(0);
    expect(getDeltaFailures()).toEqual([]);
  });

  it("preserves insertion order", () => {
    for (let i = 1; i <= 5; i++) {
      addDeltaFailure({ type: "stale_node_ref", node_id: i });
    }
    const ids = getDeltaFailures().map((e) => e.node_id);
    expect(ids).toEqual([1, 2, 3, 4, 5]);
  });
});
