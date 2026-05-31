import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

// comfy_agent_bridge frontend extension (Home A).
// Listens for agent-pushed workflows and loads them onto the canvas.
// Tags agent-originated loads via window.__agentLoad so Phase 1B read-back
// can ignore them (loop-prevention).
let _changeTimer = null;
const _DEBOUNCE_MS = 800;

function _scheduleCanvasReport() {
  // Loop-prevention: ignore changes triggered by an agent-originated load.
  if (window.__agentLoad) return;
  if (_changeTimer) clearTimeout(_changeTimer);
  _changeTimer = setTimeout(async () => {
    try {
      const wf = await app.graphToPrompt();
      const payload = wf?.output ?? wf;
      await api.fetchApi("/agent/canvas_changed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workflow: payload }),
      });
    } catch (err) {
      console.warn("agent.bridge: canvas report failed", err);
    }
  }, _DEBOUNCE_MS);
}

app.registerExtension({
  name: "agent.bridge",
  async setup() {
    // Agent push -> load onto canvas, tagged so read-back ignores it.
    api.addEventListener("agent.load_workflow", (e) => {
      const wf = e?.detail?.workflow;
      if (!wf) return;
      window.__agentLoad = true; // mark agent-originated load
      try {
        app.loadGraphData(wf);
      } finally {
        // Clear the tag after the load settles so genuine artist edits
        // afterward are still detected.
        queueMicrotask(() => {
          window.__agentLoad = false;
        });
      }
    });

    // Read-back (#1B): debounced report of artist edits. LiteGraph fires
    // graph change hooks on node add/remove/connection/widget change.
    const graph = app.graph;
    if (graph) {
      const prevOnChange = graph.onAfterChange;
      graph.onAfterChange = function (...args) {
        if (prevOnChange) prevOnChange.apply(this, args);
        _scheduleCanvasReport();
      };
    }
  },
});
