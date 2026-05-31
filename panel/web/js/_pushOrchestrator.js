/**
 * Push orchestration for write-back v1 (the PASS 5 proxy).
 *
 * Composes the production pipeline that runs every time the panel
 * receives a `comfy-cozy:workflow-changed` event:
 *
 *   clearDeltaFailures                                   (L-7)
 *     → client.getWorkflowApiWithTouched                (L-1+L-2)
 *     → withObserverPause(app.graph, ...)               (L-6, P4)
 *         applyTouchedSet(app, workflow, touched)       (L-3+L-4+L-5+L-8)
 *         app.canvas.setDirty                            (host UX)
 *     → client.ackPush                                   (L-1, rotates snapshot)
 *
 * Pure-ish: takes `app` and `client` as arguments. The production caller
 * (panel/web/js/superduperPanel.js) passes the live app import and a
 * real AgentClient instance. Tests pass fakes / vi.fn() stubs.
 *
 * Error handling:
 *   - ackPush failure is caught and logged (best-effort; next push will
 *     recompute touched against the now-stale snapshot, re-applying
 *     widget writes idempotently).
 *   - Any other thrown error is caught at the top, logged, and not
 *     re-thrown — the event handler must not throw into the browser.
 *   - observer pause is guaranteed restored by withObserverPause's
 *     finally clause regardless of throw path inside applyTouchedSet.
 */

import { applyTouchedSet } from "./_pushApplyTouched.js";
import { withObserverPause } from "./_pushControl.js";
import { clearDeltaFailures } from "./_deltaFailures.js";

export async function runPushAgentToCanvas(app, client) {
  // L-7: reset the delta-failure accumulator at the start of every push
  // so the status bar reflects only this push's failures, not prior ones.
  clearDeltaFailures();

  try {
    // L-2: fetch workflow + touched-set together. Empty/null response
    // means the agent has nothing to push (no workflow loaded, or the
    // server's compute_touched returned []). Either way, exit early
    // before touching the canvas.
    const result = await client.getWorkflowApiWithTouched();
    if (!result) return;

    const { workflow, touched } = result;
    if (!workflow || !app || !app.graph) return;

    // L-6: pause onAfterChange while mutating the canvas so writes don't
    // echo back through syncCanvasToAgent (P4). withObserverPause restores
    // in `finally` so the observer never leaks (F-4 mitigation).
    await withObserverPause(app.graph, () => {
      applyTouchedSet(app, workflow, touched);
      if (app.canvas && typeof app.canvas.setDirty === "function") {
        app.canvas.setDirty(true, true);
      }
    });

    // L-2: ack so the server snapshot rotates forward. Failure here is
    // benign — the next push computes touched against the stale snapshot
    // and re-applies the same widget writes (idempotent: widget.value
    // already === new_value, so the diff guard at L-2 short-circuits).
    try {
      await client.ackPush();
    } catch (e) {
      _logDebug("ackPush failed:", e);
    }
  } catch (e) {
    _logDebug("Canvas push failed:", e);
  }
}

function _logDebug(...args) {
  if (typeof console !== "undefined" && console.debug) {
    console.debug("[Comfy Cozy]", ...args);
  }
}
