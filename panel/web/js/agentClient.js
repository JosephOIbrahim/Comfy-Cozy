/* ── Agent Client — HTTP/SSE communication ─────────────────────── */

const BASE = "/superduper-panel";

export class AgentClient {
  constructor() {
    this._base = BASE;
  }

  async health() {
    const r = await fetch(`${this._base}/health`);
    return r.json();
  }

  async getGraphState() {
    const r = await fetch(`${this._base}/graph-state`);
    return r.json();
  }

  async setInput(nodeId, inputName, value) {
    const r = await fetch(`${this._base}/set-input`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ node_id: nodeId, input_name: inputName, value }),
    });
    return r.json();
  }

  async rollback() {
    const r = await fetch(`${this._base}/rollback`, { method: "POST" });
    return r.json();
  }

  async getExperience() {
    const r = await fetch(`${this._base}/experience`);
    return r.json();
  }

  async getAutoresearch() {
    const r = await fetch(`${this._base}/autoresearch`);
    return r.json();
  }

  async applyPrediction(predictionId, path) {
    const r = await fetch(`${this._base}/prediction/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prediction_id: predictionId, path }),
    });
    return r.json();
  }

  async ignorePrediction(predictionId) {
    const r = await fetch(`${this._base}/prediction/ignore`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prediction_id: predictionId }),
    });
    return r.json();
  }
}
