/* ── Prediction Overlay — Inline arbiter cards ─────────────────── */

export function createPredictionCard(prediction, { onApply, onIgnore, onEvidence }) {
  const isExplicit = prediction.mode === "explicit";

  const card = document.createElement("div");
  card.className = `sdp-prediction${isExplicit ? " sdp-prediction--explicit" : ""}`;

  const header = document.createElement("div");
  header.className = "sdp-prediction__header";
  header.innerHTML = `
    <span class="sdp-prediction__title">Prediction</span>
    <span class="sdp-prediction__conf">${Math.round((prediction.confidence || 0) * 100)}% confidence</span>
  `;
  card.appendChild(header);

  const body = document.createElement("div");
  body.className = "sdp-prediction__body";

  if (prediction.reasoning) {
    const reason = document.createElement("div");
    reason.className = "sdp-prediction__reason";
    reason.textContent = prediction.reasoning;
    body.appendChild(reason);
  }

  if (prediction.paths && prediction.paths.length > 0) {
    for (let i = 0; i < prediction.paths.length; i++) {
      const p = prediction.paths[i];
      const row = document.createElement("div");
      row.className = `sdp-path${i === 0 ? " sdp-path--recommended" : ""}`;
      row.innerHTML = `
        <span><span class="sdp-path__marker">&blacktriangleright;</span><span class="sdp-path__label">${_esc(p.label)}</span></span>
        <span class="sdp-path__quality">quality: ${p.quality.toFixed(2)}</span>
      `;
      body.appendChild(row);
    }
  }

  card.appendChild(body);

  const actions = document.createElement("div");
  actions.className = "sdp-prediction__actions";

  const applyBtn = document.createElement("button");
  applyBtn.className = "sdp-btn sdp-btn--primary";
  applyBtn.textContent = "Apply";
  applyBtn.addEventListener("click", () => {
    _collapse(card, "Applied recommendation");
    if (onApply) onApply(prediction);
  });
  actions.appendChild(applyBtn);

  const ignoreBtn = document.createElement("button");
  ignoreBtn.className = "sdp-btn";
  ignoreBtn.textContent = "Ignore";
  ignoreBtn.addEventListener("click", () => {
    _collapse(card, "Ignored");
    if (onIgnore) onIgnore(prediction);
  });
  actions.appendChild(ignoreBtn);

  if (onEvidence) {
    const evidenceBtn = document.createElement("button");
    evidenceBtn.className = "sdp-btn";
    evidenceBtn.textContent = "Evidence";
    evidenceBtn.addEventListener("click", () => onEvidence(prediction));
    actions.appendChild(evidenceBtn);
  }

  card.appendChild(actions);
  return card;
}

function _collapse(card, message) {
  card.className = "sdp-prediction sdp-prediction--collapsed";
  card.innerHTML = "";
  card.textContent = message;
}

function _esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}
