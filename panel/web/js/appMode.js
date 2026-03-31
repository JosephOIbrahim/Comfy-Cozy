/* ── APP Mode — Chat Interface ──────────────────────────────────── */

import { createPredictionCard } from "./predictionOverlay.js";

export function createAppMode(container, client) {
  const messagesEl = document.createElement("div");
  messagesEl.className = "sdp-messages";
  messagesEl.setAttribute("role", "log");
  messagesEl.setAttribute("aria-live", "polite");

  const inputBar = document.createElement("div");
  inputBar.className = "sdp-input-bar";

  const textarea = document.createElement("textarea");
  textarea.className = "sdp-input";
  textarea.placeholder = "Ask about your workflow...";
  textarea.rows = 1;

  const sendBtn = document.createElement("button");
  sendBtn.className = "sdp-send";
  sendBtn.textContent = "\u2192";
  sendBtn.setAttribute("aria-label", "Send message");

  inputBar.appendChild(textarea);
  inputBar.appendChild(sendBtn);

  container.appendChild(messagesEl);
  container.appendChild(inputBar);

  // State
  let busy = false;
  const history = _loadHistory();

  // Render saved history
  if (history.length === 0) {
    _addSystem("What would you like to do with your workflow?");
  } else {
    for (const msg of history) {
      _renderMessage(msg.role, msg.text, false);
    }
    _scrollToBottom();
  }

  // Input handling
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      _send();
    }
  });
  sendBtn.addEventListener("click", _send);

  // Auto-resize textarea
  textarea.addEventListener("input", () => {
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 96) + "px";
  });

  function _send() {
    const text = textarea.value.trim();
    if (!text || busy) return;

    _addUser(text);
    textarea.value = "";
    textarea.style.height = "auto";
    _setBusy(true);

    // Check for view commands
    if (text.startsWith("/experience") || text.startsWith("/research")) {
      // These are handled by panel shell via custom event
      const event = new CustomEvent("sdp-command", { detail: { command: text.slice(1).split(" ")[0] } });
      container.dispatchEvent(event);
      _setBusy(false);
      return;
    }

    _showTyping();
    // Agent communication would happen here via SSE
    // For now, show a placeholder response
    setTimeout(() => {
      _clearTyping();
      _addAgent("Agent connected. Waiting for backend wiring.");
      _setBusy(false);
    }, 500);
  }

  function _setBusy(state) {
    busy = state;
    sendBtn.disabled = state;
    textarea.disabled = state;
    sendBtn.textContent = state ? "..." : "\u2192";
  }

  function _addUser(text) {
    _renderMessage("user", text);
    _saveMessage("user", text);
  }

  function _addAgent(text) {
    _renderMessage("agent", text);
    _saveMessage("agent", text);
  }

  function _addSystem(text) {
    _renderMessage("system", text);
  }

  let typingEl = null;

  function _showTyping() {
    if (typingEl) return;
    typingEl = document.createElement("div");
    typingEl.className = "sdp-msg";
    typingEl.innerHTML = `
      <span class="sdp-msg__label">Agent</span>
      <div class="sdp-typing">
        <span class="sdp-typing__dot"></span>
        <span class="sdp-typing__dot"></span>
        <span class="sdp-typing__dot"></span>
      </div>
    `;
    messagesEl.appendChild(typingEl);
    _scrollToBottom();
  }

  function _clearTyping() {
    if (typingEl) {
      typingEl.remove();
      typingEl = null;
    }
  }

  function _renderMessage(role, text, scroll = true) {
    const msg = document.createElement("div");
    msg.className = `sdp-msg sdp-msg--${role}`;

    if (role !== "system") {
      const label = document.createElement("span");
      label.className = "sdp-msg__label";
      label.textContent = role === "user" ? "You" : "Agent";
      msg.appendChild(label);
    }

    const body = document.createElement("div");
    body.className = "sdp-msg__body";

    if (role === "agent") {
      body.innerHTML = _renderMarkdown(text);
    } else {
      body.textContent = text;
    }

    msg.appendChild(body);
    messagesEl.appendChild(msg);

    if (scroll) _scrollToBottom();
    return msg;
  }

  function _scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // Simple markdown rendering (bold, italic, code, code blocks)
  function _renderMarkdown(text) {
    let html = _esc(text);
    // Code blocks
    html = html.replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>");
    // Inline code
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    // Italic
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
    // Line breaks
    html = html.replace(/\n/g, "<br>");
    return html;
  }

  function _esc(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  // LocalStorage persistence
  function _loadHistory() {
    try {
      const raw = localStorage.getItem("sd-panel-history");
      return raw ? JSON.parse(raw) : [];
    } catch { return []; }
  }

  function _saveMessage(role, text) {
    history.push({ role, text });
    if (history.length > 100) history.splice(0, history.length - 100);
    try {
      localStorage.setItem("sd-panel-history", JSON.stringify(history));
    } catch { /* quota exceeded */ }
  }

  // Public API for adding tool cards and predictions
  return {
    addToolCard(name, params) {
      const card = document.createElement("div");
      card.className = "sdp-tool";
      const header = document.createElement("div");
      header.className = "sdp-tool__header";
      header.innerHTML = `<span>${_esc(name)}</span><span class="sdp-tool__chevron">\u25B8</span>`;

      const body = document.createElement("div");
      body.className = "sdp-tool__body";
      for (const [k, v] of Object.entries(params)) {
        const row = document.createElement("div");
        row.className = "sdp-tool__row";
        row.innerHTML = `<span class="sdp-tool__key">${_esc(k)}</span><span>${_esc(String(v))}</span>`;
        body.appendChild(row);
      }

      header.addEventListener("click", () => card.classList.toggle("sdp-tool--expanded"));
      card.appendChild(header);
      card.appendChild(body);
      messagesEl.appendChild(card);
      _scrollToBottom();
    },

    addPrediction(prediction) {
      const card = createPredictionCard(prediction, {
        onApply: (p) => client.applyPrediction(p.id, p.paths[0]),
        onIgnore: (p) => client.ignorePrediction(p.id),
      });
      messagesEl.appendChild(card);
      _scrollToBottom();
    },

    showProgress(pct, nodeLabel) {
      let prog = messagesEl.querySelector(".sdp-progress");
      if (!prog) {
        prog = document.createElement("div");
        prog.className = "sdp-progress";
        prog.innerHTML = `
          <div class="sdp-progress__bar"><div class="sdp-progress__fill"></div></div>
          <div class="sdp-progress__label">
            <span class="sdp-progress__node"></span>
            <span class="sdp-progress__pct"></span>
          </div>
        `;
        messagesEl.appendChild(prog);
      }
      prog.querySelector(".sdp-progress__fill").style.width = `${pct}%`;
      prog.querySelector(".sdp-progress__node").textContent = nodeLabel || "";
      prog.querySelector(".sdp-progress__pct").textContent = `${Math.round(pct)}%`;
      _scrollToBottom();
    },

    hideProgress() {
      const prog = messagesEl.querySelector(".sdp-progress");
      if (prog) prog.remove();
    },

    addMessage: _addAgent,
  };
}
