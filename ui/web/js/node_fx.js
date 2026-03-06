/* ── SUPER DUPER Node FX ────────────────────────────────────────────
 *  Canvas-level visual effects on ComfyUI nodes:
 *    - Jade glow while executing
 *    - Green flash on completion
 *    - Agent-colored accent bar when touched by the AI
 *  No innerHTML — all rendering via Canvas 2D context.
 * ──────────────────────────────────────────────────────────────────── */

import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

// ── State ───────────────────────────────────────────────────────────

let _executingNodeId = null;               // currently executing node
const _completedNodes = new Map();         // nodeId -> completion timestamp

const COMPLETE_FLASH_MS = 1000;
const TOUCH_FADE_MS = 30000;

const COLOR_JADE = "#00BB81";
const COLOR_JADE_FILL = "#00BB8130";

// ── Drawing ─────────────────────────────────────────────────────────

function drawNodeFX(node, ctx) {
  const nodeId = String(node.id);

  // ── Executing: pulsing jade glow
  if (nodeId === _executingNodeId) {
    const pulse = 0.5 + Math.sin(Date.now() / 400) * 0.3;

    ctx.save();
    ctx.strokeStyle = COLOR_JADE;
    ctx.lineWidth = 2;
    ctx.shadowColor = COLOR_JADE;
    ctx.shadowBlur = 15;
    ctx.globalAlpha = pulse;

    const r = 6;
    const x = -r;
    const y = -LiteGraph.NODE_TITLE_HEIGHT - r;
    const w = node.size[0] + r * 2;
    const h = node.size[1] + LiteGraph.NODE_TITLE_HEIGHT + r * 2;

    ctx.beginPath();
    ctx.roundRect(x, y, w, h, r);
    ctx.stroke();
    ctx.restore();

    // Request continuous redraws for animation
    if (node.graph) node.graph.change();
  }

  // ── Completed: brief green flash
  const completedAt = _completedNodes.get(nodeId);
  if (completedAt) {
    const elapsed = Date.now() - completedAt;
    if (elapsed < COMPLETE_FLASH_MS) {
      const alpha = 1 - elapsed / COMPLETE_FLASH_MS;

      ctx.save();
      ctx.fillStyle = COLOR_JADE_FILL;
      ctx.globalAlpha = alpha;

      const y = -LiteGraph.NODE_TITLE_HEIGHT;
      ctx.beginPath();
      ctx.roundRect(0, y, node.size[0], node.size[1] + LiteGraph.NODE_TITLE_HEIGHT, 4);
      ctx.fill();
      ctx.restore();

      if (node.graph) node.graph.change();
    } else {
      _completedNodes.delete(nodeId);
    }
  }

  // ── Agent-touched: colored left-edge bar
  if (node._sd_touch) {
    const elapsed = Date.now() - node._sd_touch.time;
    if (elapsed < TOUCH_FADE_MS) {
      const alpha = 1 - elapsed / TOUCH_FADE_MS;

      ctx.save();
      ctx.fillStyle = node._sd_touch.color || COLOR_JADE;
      ctx.globalAlpha = alpha;

      const barH = node.size[1] + LiteGraph.NODE_TITLE_HEIGHT;
      ctx.fillRect(-1, -LiteGraph.NODE_TITLE_HEIGHT, 3, barH);
      ctx.restore();

      if (node.graph) node.graph.change();
    } else {
      delete node._sd_touch;
    }
  }
}

// ── Extension Registration ──────────────────────────────────────────

app.registerExtension({
  name: "SuperDuper.NodeFX",

  async setup() {
    // ── A: Listen to ComfyUI execution events
    api.addEventListener("executing", ({ detail }) => {
      const nodeId = detail ? String(detail) : null;

      if (nodeId === null) {
        // Execution complete — mark last node as completed
        if (_executingNodeId) {
          _completedNodes.set(_executingNodeId, Date.now());
        }
        _executingNodeId = null;
        return;
      }

      // Previous node just finished
      if (_executingNodeId && _executingNodeId !== nodeId) {
        _completedNodes.set(_executingNodeId, Date.now());
      }

      _executingNodeId = nodeId;
    });

    api.addEventListener("executed", ({ detail }) => {
      if (detail && detail.node) {
        const nodeId = String(detail.node);
        _completedNodes.set(nodeId, Date.now());
        if (_executingNodeId === nodeId) {
          _executingNodeId = null;
        }
      }
    });

    // ── B: Hook into LiteGraph node rendering
    const origDrawNode = LGraphCanvas.prototype.drawNode;
    LGraphCanvas.prototype.drawNode = function (node, ctx) {
      origDrawNode.apply(this, arguments);
      drawNodeFX(node, ctx);
    };

    // ── D: Listen for agent touch events from sidebar
    document.addEventListener("superduper:node_touch", (e) => {
      const { nodeId, agentColor } = e.detail || {};
      if (!nodeId || !app.graph) return;

      const node = app.graph.getNodeById(parseInt(nodeId, 10));
      if (node) {
        node._sd_touch = {
          agent: true,
          color: agentColor || COLOR_JADE,
          time: Date.now(),
        };
        if (node.graph) node.graph.change();
      }
    });
  },
});
