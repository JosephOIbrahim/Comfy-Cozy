import { describe, it, expect, beforeEach, vi } from "vitest";
import { debounce, withObserverPause } from "../../panel/web/js/_pushControl.js";
import { makeFakeGraph } from "./_stubs/litegraph.js";

describe("L-6 debounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("fires fn once after the configured delay", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced();
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(99);
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("coalesces N rapid calls into one fn invocation", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    for (let i = 0; i < 10; i++) {
      debounced();
      vi.advanceTimersByTime(10); // 10 calls over 100ms total
    }
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(100); // wait past the last call's debounce
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("passes the latest args to fn", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced("first");
    vi.advanceTimersByTime(50);
    debounced("second");
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith("second");
  });

  it("cancel() prevents pending fn from firing", () => {
    const fn = vi.fn();
    const debounced = debounce(fn, 100);
    debounced();
    vi.advanceTimersByTime(50);
    debounced.cancel();
    vi.advanceTimersByTime(100);
    expect(fn).not.toHaveBeenCalled();
  });

  it("swallows errors thrown by fn (event-handler safety)", () => {
    const fn = vi.fn(() => {
      throw new Error("boom");
    });
    const debounced = debounce(fn, 100);
    debounced();
    expect(() => vi.advanceTimersByTime(100)).not.toThrow();
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

describe("L-6 withObserverPause", () => {
  let graph;

  beforeEach(() => {
    graph = makeFakeGraph();
    graph.onAfterChange = function originalHandler() {};
  });

  it("replaces onAfterChange with no-op during fn, restores after", async () => {
    const saved = graph.onAfterChange;
    let observerDuringFn;
    await withObserverPause(graph, () => {
      observerDuringFn = graph.onAfterChange;
    });
    expect(observerDuringFn).not.toBe(saved);
    expect(typeof observerDuringFn).toBe("function");
    expect(graph.onAfterChange).toBe(saved);
  });

  it("restores observer even when fn throws (F-4 mitigation)", async () => {
    const saved = graph.onAfterChange;
    await expect(
      withObserverPause(graph, () => {
        throw new Error("push failure");
      })
    ).rejects.toThrow("push failure");
    expect(graph.onAfterChange).toBe(saved);
  });

  it("restores observer when fn rejects async", async () => {
    const saved = graph.onAfterChange;
    await expect(
      withObserverPause(graph, async () => {
        throw new Error("async failure");
      })
    ).rejects.toThrow("async failure");
    expect(graph.onAfterChange).toBe(saved);
  });

  it("forwards fn's return value", async () => {
    const result = await withObserverPause(graph, () => 42);
    expect(result).toBe(42);
  });

  it("handles null graph as a no-op pause (still runs fn)", async () => {
    let ran = false;
    const result = await withObserverPause(null, () => {
      ran = true;
      return "x";
    });
    expect(ran).toBe(true);
    expect(result).toBe("x");
  });

  it("paused observer does not call the original handler", async () => {
    let originalCalls = 0;
    graph.onAfterChange = () => {
      originalCalls++;
    };
    await withObserverPause(graph, () => {
      // Simulate canvas event firing during the push
      if (typeof graph.onAfterChange === "function") {
        graph.onAfterChange();
      }
    });
    expect(originalCalls).toBe(0);
  });
});
