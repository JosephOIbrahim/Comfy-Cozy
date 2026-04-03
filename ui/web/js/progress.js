/* ── COMFY COZY Progress Panel ──────────────────────────────────────
 *  Three-level progress visualization:
 *    L1: Agent pipeline indicator (ROUTER → INTENT → EXECUTION → VERIFY)
 *    L2: Execution progress bar (jade fill, indeterminate shimmer)
 *    L3: Node detail line (current node, step, ETA)
 *  No innerHTML — all DOM built via createElement + textContent.
 * ──────────────────────────────────────────────────────────────────── */

// Pipeline stages in order
const PIPELINE = [
  { key: "router",    label: "ROUTER",    colorVar: "--agent-router" },
  { key: "intent",    label: "INTENT",    colorVar: "--agent-intent" },
  { key: "execution", label: "EXECUTION", colorVar: "--agent-execution" },
  { key: "verify",    label: "VERIFY",    colorVar: "--agent-verify" },
];

// ── Stage Element Builder ───────────────────────────────────────────

function _createStageEl(stage) {
  const el = document.createElement("span");
  el.className = "sd-progress-stage sd-progress-stage--waiting";
  el.dataset.stage = stage.key;

  const dot = document.createElement("span");
  dot.className = "sd-progress-stage__dot";
  dot.style.setProperty("--stage-color", `var(${stage.colorVar})`);
  el.appendChild(dot);

  const label = document.createElement("span");
  label.className = "sd-progress-stage__label";
  label.textContent = stage.label;
  el.appendChild(label);

  return el;
}

function _createArrow() {
  const arrow = document.createElement("span");
  arrow.className = "sd-progress-pipeline__arrow";
  arrow.textContent = "\u2192";
  return arrow;
}

// ── Panel Builder ───────────────────────────────────────────────────

/**
 * Create a progress panel DOM element with all three levels.
 * @returns {HTMLElement}
 */
export function createProgressPanel() {
  const panel = document.createElement("div");
  panel.className = "sd-progress-panel";

  // ── Level 1: Pipeline indicator
  const pipeline = document.createElement("div");
  pipeline.className = "sd-progress-pipeline";

  for (let i = 0; i < PIPELINE.length; i++) {
    pipeline.appendChild(_createStageEl(PIPELINE[i]));
    if (i < PIPELINE.length - 1) {
      pipeline.appendChild(_createArrow());
    }
  }
  panel.appendChild(pipeline);

  // ── Level 2: Progress bar
  const barTrack = document.createElement("div");
  barTrack.className = "sd-progress-bar sd-progress-bar--indeterminate";

  const barFill = document.createElement("div");
  barFill.className = "sd-progress-bar__fill";
  barFill.style.width = "0%";
  barTrack.appendChild(barFill);

  panel.appendChild(barTrack);

  // ── Level 3: Node detail line
  const detail = document.createElement("div");
  detail.className = "sd-progress-detail";

  const detailLeft = document.createElement("span");
  detailLeft.className = "sd-progress-detail__left";
  detailLeft.textContent = "Waiting...";
  detail.appendChild(detailLeft);

  const detailRight = document.createElement("span");
  detailRight.className = "sd-progress-detail__right";
  detail.appendChild(detailRight);

  panel.appendChild(detail);

  return panel;
}

// ── Live Update ─────────────────────────────────────────────────────

/**
 * Update all three levels of the progress panel in-place.
 *
 * @param {HTMLElement} panel - The progress panel element
 * @param {object} data
 * @param {object}  [data.pipeline]    - {router, intent, execution, verify} status strings
 * @param {number|null} [data.progress]    - 0-1 fraction, null for indeterminate
 * @param {string}  [data.currentNode] - Current node class_type
 * @param {number}  [data.nodeIndex]   - Current node index (1-based)
 * @param {number}  [data.nodeTotal]   - Total node count
 * @param {number|null} [data.etaSeconds]  - Estimated seconds remaining
 */
export function updateProgress(panel, data) {
  if (!panel || !data) return;

  // ── Level 1: Pipeline stages
  if (data.pipeline) {
    for (const stage of PIPELINE) {
      const status = data.pipeline[stage.key];
      if (status === undefined) continue;

      const el = panel.querySelector(`.sd-progress-stage[data-stage="${stage.key}"]`);
      if (!el) continue;

      // Remove all state classes
      el.classList.remove(
        "sd-progress-stage--waiting",
        "sd-progress-stage--active",
        "sd-progress-stage--complete",
        "sd-progress-stage--error"
      );
      el.classList.add(`sd-progress-stage--${status}`);
    }
  }

  // ── Level 2: Progress bar
  if (data.progress !== undefined) {
    const track = panel.querySelector(".sd-progress-bar");
    const fill = panel.querySelector(".sd-progress-bar__fill");
    if (track && fill) {
      if (data.progress === null) {
        track.classList.add("sd-progress-bar--indeterminate");
        fill.style.width = "0%";
      } else {
        track.classList.remove("sd-progress-bar--indeterminate");
        fill.style.width = `${Math.round(data.progress * 100)}%`;
      }
    }
  }

  // ── Level 3: Node detail
  const left = panel.querySelector(".sd-progress-detail__left");
  const right = panel.querySelector(".sd-progress-detail__right");

  if (left) {
    if (data.currentNode) {
      const idx = data.nodeIndex != null ? `Node ${data.nodeIndex}` : "Node";
      const total = data.nodeTotal != null ? `/${data.nodeTotal}` : "";
      left.textContent = "";

      const prefix = document.createTextNode(`${idx}${total}: `);
      left.appendChild(prefix);

      const nodeName = document.createElement("span");
      nodeName.className = "sd-progress-detail__node";
      nodeName.textContent = data.currentNode;
      left.appendChild(nodeName);
    }
  }

  if (right) {
    if (data.etaSeconds != null) {
      right.textContent = `~${data.etaSeconds}s remaining`;
    } else {
      right.textContent = "";
    }
  }
}
