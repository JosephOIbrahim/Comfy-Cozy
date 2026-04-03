/**
 * Workflow Zone — visual workflow representation in the sidebar.
 *
 * Shows a compact node list with slot-colored dots, value previews,
 * and bidirectional canvas-sidebar synchronization.
 *
 * Part of the v2.0 production-grade UI redesign.
 */

import { slotColorForNode } from "./tokens.js";

let _zoneEl = null;
let _listEl = null;
let _countEl = null;
let _diffEl = null;
let _expanded = false;
let _nodes = [];
let _selectedNodeId = null;

/**
 * Create the Workflow Zone DOM element.
 * Call once during sidebar initialization.
 */
export function createWorkflowZone() {
  _zoneEl = document.createElement("div");
  _zoneEl.className = "sd-workflow-zone sd-workflow-zone--collapsed";

  // Header (clickable toggle)
  const header = document.createElement("div");
  header.className = "sd-workflow-zone__header";
  header.addEventListener("click", toggleZone);

  const title = document.createElement("span");
  title.className = "sd-workflow-zone__title";
  title.textContent = "Workflow";

  _countEl = document.createElement("span");
  _countEl.className = "sd-workflow-zone__count";
  _countEl.textContent = "";

  const chevron = document.createElement("span");
  chevron.className = "sd-workflow-zone__chevron";
  chevron.textContent = "\u25B8"; // right-pointing triangle

  header.appendChild(title);
  header.appendChild(_countEl);
  header.appendChild(chevron);
  _zoneEl.appendChild(header);

  // Diff badge container
  _diffEl = document.createElement("div");
  _diffEl.style.display = "none";
  _zoneEl.appendChild(_diffEl);

  // Node list
  _listEl = document.createElement("div");
  _listEl.className = "sd-workflow-zone__list";
  _zoneEl.appendChild(_listEl);

  // Listen for canvas node selection events
  document.addEventListener("superduper:canvas_node_selected", (e) => {
    if (e.detail && e.detail.nodeId) {
      highlightNode(e.detail.nodeId);
    }
  });

  return _zoneEl;
}

/**
 * Toggle the workflow zone expanded/collapsed.
 */
function toggleZone() {
  _expanded = !_expanded;
  if (_expanded) {
    _zoneEl.classList.remove("sd-workflow-zone--collapsed");
    _zoneEl.classList.add("sd-workflow-zone--expanded");
  } else {
    _zoneEl.classList.remove("sd-workflow-zone--expanded");
    _zoneEl.classList.add("sd-workflow-zone--collapsed");
  }
}

/**
 * Update the node list from workflow JSON (API format).
 * @param {Object} workflowData - {node_id: {class_type, inputs}}
 */
export function updateWorkflowNodes(workflowData) {
  if (!_listEl || !workflowData) return;

  _listEl.innerHTML = "";
  _nodes = [];

  const nodeIds = Object.keys(workflowData).sort((a, b) => {
    // Sort by class_type for visual grouping
    const typeA = workflowData[a].class_type || "";
    const typeB = workflowData[b].class_type || "";
    return typeA.localeCompare(typeB);
  });

  for (const nodeId of nodeIds) {
    const nodeData = workflowData[nodeId];
    const classType = nodeData.class_type || "Unknown";
    const color = slotColorForNode(classType);
    const preview = getValuePreview(nodeData.inputs);

    const row = createNodeRow(nodeId, classType, color, preview);
    _listEl.appendChild(row);
    _nodes.push({ id: nodeId, classType, element: row });
  }

  _countEl.textContent = nodeIds.length + " nodes";
}

/**
 * Create a single node row element.
 */
function createNodeRow(nodeId, classType, color, preview) {
  const row = document.createElement("div");
  row.className = "sd-node-row";
  row.dataset.nodeId = nodeId;

  row.addEventListener("click", () => {
    highlightNode(nodeId);
    // Dispatch event for canvas to pick up
    document.dispatchEvent(new CustomEvent("superduper:sidebar_node_selected", {
      detail: { nodeId, classType },
    }));
  });

  const dot = document.createElement("span");
  dot.className = "sd-node-row__dot";
  dot.style.background = color;
  dot.style.boxShadow = `0 0 4px ${color}55`;

  const name = document.createElement("span");
  name.className = "sd-node-row__name";
  name.textContent = classType;

  row.appendChild(dot);
  row.appendChild(name);

  if (preview) {
    const value = document.createElement("span");
    value.className = "sd-node-row__value";
    value.textContent = preview;
    row.appendChild(value);
  }

  return row;
}

/**
 * Extract a short value preview from a node's inputs.
 * Shows the most interesting literal value (not connections).
 */
function getValuePreview(inputs) {
  if (!inputs) return "";

  // Priority order: dimensions, model names, sampler names, CFG, steps
  if (inputs.width && inputs.height) {
    return `${inputs.width}\u00d7${inputs.height}`;
  }
  if (inputs.ckpt_name && typeof inputs.ckpt_name === "string") {
    return inputs.ckpt_name.split("/").pop().split(".")[0];
  }
  if (inputs.lora_name && typeof inputs.lora_name === "string") {
    return inputs.lora_name.split("/").pop().split(".")[0];
  }
  if (inputs.sampler_name) return inputs.sampler_name;
  if (inputs.scheduler) return inputs.scheduler;
  if (inputs.cfg !== undefined && typeof inputs.cfg !== "object") {
    return "cfg " + inputs.cfg;
  }
  if (inputs.steps !== undefined && typeof inputs.steps !== "object") {
    return inputs.steps + " steps";
  }
  if (inputs.text && typeof inputs.text === "string") {
    return inputs.text.slice(0, 30) + (inputs.text.length > 30 ? "\u2026" : "");
  }
  return "";
}

/**
 * Highlight a node row (from canvas selection or sidebar click).
 */
export function highlightNode(nodeId) {
  // Deselect previous
  if (_selectedNodeId) {
    const prev = _listEl?.querySelector(`[data-node-id="${_selectedNodeId}"]`);
    if (prev) prev.classList.remove("sd-node-row--selected");
  }

  _selectedNodeId = nodeId;

  const row = _listEl?.querySelector(`[data-node-id="${nodeId}"]`);
  if (row) {
    row.classList.add("sd-node-row--selected");
    row.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}

/**
 * Show a diff badge after agent modifications.
 * @param {Object} diffData - {modified: [{node_id, field, old_value, new_value}]}
 */
export function showDiff(diffData) {
  if (!_diffEl || !diffData) return;

  _diffEl.innerHTML = "";
  _diffEl.style.display = "block";

  const count = diffData.modified ? diffData.modified.length : 0;
  if (count === 0) {
    _diffEl.style.display = "none";
    return;
  }

  const badge = document.createElement("div");
  badge.className = "sd-diff-badge";

  const summary = count === 1
    ? "1 change"
    : `${count} changes`;

  badge.textContent = summary;

  // Add detail for first change
  if (diffData.modified && diffData.modified[0]) {
    const first = diffData.modified[0];
    if (first.field && first.old_value !== undefined && first.new_value !== undefined) {
      badge.textContent += ` \u2014 ${first.field}: ${first.old_value} \u2192 ${first.new_value}`;
    }
  }

  _diffEl.appendChild(badge);
}

/**
 * Clear the diff badge.
 */
export function clearDiff() {
  if (_diffEl) {
    _diffEl.innerHTML = "";
    _diffEl.style.display = "none";
  }
}
