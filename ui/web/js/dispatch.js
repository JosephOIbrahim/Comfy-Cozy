/* ── SUPER DUPER Dispatch Card ──────────────────────────────────────
 *  Agent deployment visualization for MoE routing.
 *  No innerHTML — all DOM built via createElement + textContent.
 * ──────────────────────────────────────────────────────────────────── */

// Agent key -> CSS custom property name
const AGENT_COLORS = {
  router:    "--agent-router",
  intent:    "--agent-intent",
  execution: "--agent-execution",
  verify:    "--agent-verify",
  doctor:    "--agent-doctor",
};

function _agentColor(key) {
  const v = AGENT_COLORS[key];
  return v ? `var(${v})` : "#9a9caa";
}

// ── Status Renderers ────────────────────────────────────────────────

function _createStatusWaiting() {
  const span = document.createElement("span");
  span.className = "sd-dispatch__status sd-dispatch__status--waiting";
  span.textContent = "waiting";
  return span;
}

function _createStatusActive(message) {
  const span = document.createElement("span");
  span.className = "sd-dispatch__status sd-dispatch__status--active";

  const dot = document.createElement("span");
  dot.className = "sd-dispatch__pulse-dot";
  span.appendChild(dot);

  const label = document.createElement("span");
  label.textContent = message || "active";
  span.appendChild(label);

  return span;
}

function _createStatusComplete(duration) {
  const span = document.createElement("span");
  span.className = "sd-dispatch__status sd-dispatch__status--complete";
  span.textContent = "complete \u2713";

  if (duration != null) {
    const badge = document.createElement("span");
    badge.className = "sd-dispatch__duration";
    badge.textContent = duration;
    span.appendChild(badge);
  }

  return span;
}

function _createStatusError(message) {
  const span = document.createElement("span");
  span.className = "sd-dispatch__status sd-dispatch__status--error";
  span.textContent = (message || "error") + " \u2717";
  return span;
}

// ── Card Builder ────────────────────────────────────────────────────

/**
 * Build a dispatch card DOM element showing deployed agents.
 *
 * @param {object} data
 * @param {string} data.prompt - User's original prompt
 * @param {Array}  data.agents - Agent descriptors
 * @param {string} [data.estimate] - Estimated time string (e.g. "~4s")
 * @param {number} [data.nodeCount] - Number of workflow nodes
 * @returns {HTMLElement}
 */
export function createDispatchCard(data) {
  const card = document.createElement("div");
  card.className = "sd-dispatch-card";

  // ── Header
  const header = document.createElement("div");
  header.className = "sd-dispatch__header";
  header.textContent = "AGENTS DEPLOYED";
  card.appendChild(header);

  // ── Prompt quote
  if (data.prompt) {
    const quote = document.createElement("div");
    quote.className = "sd-dispatch__prompt";
    quote.textContent = data.prompt;
    card.appendChild(quote);
  }

  // ── Agent rows
  const rows = document.createElement("div");
  rows.className = "sd-dispatch__rows";

  for (const agent of data.agents) {
    const row = document.createElement("div");
    row.className = "sd-dispatch__row";
    row.dataset.agent = agent.key;

    // Colored dot
    const dot = document.createElement("span");
    dot.className = "sd-dispatch__dot";
    dot.style.backgroundColor = _agentColor(agent.key);
    row.appendChild(dot);

    // Name
    const name = document.createElement("span");
    name.className = "sd-dispatch__name";
    name.textContent = agent.name;
    row.appendChild(name);

    // Role
    const role = document.createElement("span");
    role.className = "sd-dispatch__role";
    role.textContent = agent.role;
    row.appendChild(role);

    // Status area
    const statusArea = document.createElement("span");
    statusArea.className = "sd-dispatch__status-area";

    const statusEl = agent.status === "active"
      ? _createStatusActive()
      : agent.status === "complete"
        ? _createStatusComplete()
        : agent.status === "error"
          ? _createStatusError()
          : _createStatusWaiting();
    statusArea.appendChild(statusEl);
    row.appendChild(statusArea);

    rows.appendChild(row);
  }

  card.appendChild(rows);

  // ── Footer
  const footer = document.createElement("div");
  footer.className = "sd-dispatch__footer";
  const parts = [];
  if (data.estimate) parts.push(`Estimated: ${data.estimate}`);
  parts.push(`${data.agents.length} agents`);
  if (data.nodeCount != null) parts.push(`${data.nodeCount} nodes`);
  footer.textContent = parts.join(" | ");
  card.appendChild(footer);

  return card;
}

// ── Live Update ─────────────────────────────────────────────────────

/**
 * Update an agent row's status in-place.
 *
 * @param {HTMLElement} card      - The dispatch card element
 * @param {string}      agentKey  - Agent key (router, intent, etc.)
 * @param {string}      status    - "waiting" | "active" | "complete" | "error"
 * @param {string}      [message] - Optional status message
 * @param {string}      [duration] - Optional duration string (e.g. "1.2s")
 */
export function updateAgentStatus(card, agentKey, status, message, duration) {
  const row = card.querySelector(`.sd-dispatch__row[data-agent="${agentKey}"]`);
  if (!row) return;

  const area = row.querySelector(".sd-dispatch__status-area");
  if (!area) return;

  // Clear existing status
  area.textContent = "";

  let statusEl;
  switch (status) {
    case "active":
      statusEl = _createStatusActive(message);
      break;
    case "complete":
      statusEl = _createStatusComplete(duration);
      break;
    case "error":
      statusEl = _createStatusError(message);
      break;
    default:
      statusEl = _createStatusWaiting();
  }

  area.appendChild(statusEl);
}
