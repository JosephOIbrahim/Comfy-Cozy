/**
 * Push control helpers for write-back v1 (L-6).
 *
 *   debounce(fn, ms)          — coalesce rapid calls; fires once `ms`
 *                                after the last invocation.
 *   withObserverPause(graph,  — runs `fn` inside a save→noop→restore
 *                       fn)     guard on `graph.onAfterChange`. The
 *                                restore happens in `finally`, so even
 *                                a thrown `fn` cannot leak the
 *                                paused observer.
 *
 * Both are pure helpers — no module-level side effects, no host-app
 * imports — so they unit-test cleanly under Vitest.
 *
 * Addresses:
 *   F-4 (observer-pause leak):    finally-restore.
 *   F-5 (concurrent push race):   debounce coalesces; observer pause is
 *                                  scoped to a single push so the saved
 *                                  handler is always the canonical one.
 *   P4  (no echo):                 onAfterChange is replaced by a no-op
 *                                  while the push mutates the canvas, so
 *                                  the resulting graph-changed events
 *                                  don't re-trigger syncCanvasToAgent.
 */

export function debounce(fn, ms) {
  let timer = null;
  function debounced(...args) {
    if (timer !== null) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => {
      timer = null;
      try {
        fn(...args);
      } catch (e) {
        // Swallow — debounce callers (event handlers) shouldn't throw
        // into the timer-thread. Errors inside fn are observable via
        // its own logging.
        // eslint-disable-next-line no-console
        if (typeof console !== "undefined" && console.debug) {
          console.debug("[debounce] fn threw:", e);
        }
      }
    }, ms);
  }
  debounced.cancel = function () {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
  };
  return debounced;
}

// Module-level pause state (F-5 mitigation, CAPSULE option (c)).
// Counts concurrent / nested withObserverPause calls so the saved
// handler is captured exactly ONCE — when depth transitions 0 → 1.
// Subsequent overlapping calls see depth > 0 and reuse the existing
// pause; only the outermost finally (depth → 0) restores. This makes
// the helper safe even when debounce doesn't coalesce events
// (e.g., direct invocations, tests).
let _pauseDepth = 0;
let _savedOnAfterChange = null;
let _pausedGraph = null;

export async function withObserverPause(graph, fn) {
  if (!graph) {
    // No graph — nothing to pause; just run the body.
    return await fn();
  }
  if (_pauseDepth === 0) {
    _savedOnAfterChange = graph.onAfterChange;
    _pausedGraph = graph;
    graph.onAfterChange = _noop;
  }
  _pauseDepth++;
  try {
    return await fn();
  } finally {
    _pauseDepth--;
    if (_pauseDepth === 0 && _pausedGraph !== null) {
      _pausedGraph.onAfterChange = _savedOnAfterChange;
      _savedOnAfterChange = null;
      _pausedGraph = null;
    }
  }
}

/**
 * Test-only: reset the module-level pause state.
 * Production code should never call this. Tests use it in beforeEach
 * to ensure isolation when prior tests leak depth (e.g., via uncaught
 * async rejection during setup).
 */
export function _resetObserverPauseState() {
  _pauseDepth = 0;
  _savedOnAfterChange = null;
  _pausedGraph = null;
}

function _noop() {
  /* paused — see withObserverPause */
}
