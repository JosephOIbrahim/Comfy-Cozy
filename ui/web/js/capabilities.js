/* ── COMFY COZY Capabilities (manifest renderer) ─────────────────────
 *  Renders GET /agent/capabilities (manifest_schema 1) into the sidebar.
 *
 *  EXPORT-ONLY MODULE: ComfyUI auto-imports every *.js under WEB_DIRECTORY
 *  at page load — top-level side effects here would run before the sidebar
 *  exists. sidebar.js imports and drives this.
 *
 *  Contract rules (mirror _manifest.py):
 *    - render strictly from the manifest, never from hardcoded tool lists
 *    - ignore unknown top-level keys; unknown surface_hint -> 'chat-only'
 *    - every server-derived string lands via createElement + textContent
 *      (never innerHTML) — branch names, descriptions, degraded errors and
 *      health reasons all pass through here
 * ──────────────────────────────────────────────────────────────────── */

const LAYER_ORDER = ["intelligence", "stage", "brain"];

/* ETag cache — module-scoped, so it survives sidebar remounts the same way
 * the session store does. 304 responses reuse the cached manifest. */
let _cache = { etag: null, manifest: null };

/** Fetch the capability manifest (same-origin; ETag-revalidated). */
export async function fetchManifest() {
  const headers = {};
  if (_cache.etag) headers["If-None-Match"] = _cache.etag;
  const res = await fetch("/agent/capabilities", { headers });
  if (res.status === 304 && _cache.manifest) return _cache.manifest;
  if (!res.ok) throw new Error(`capabilities fetch failed: ${res.status}`);
  const manifest = await res.json();
  _cache = { etag: res.headers.get("ETag"), manifest };
  return manifest;
}

/** Short version label for the header chip, e.g. "v5.9.1 · 610b85b*". */
export function versionLabel(manifest) {
  const a = manifest && manifest.agent;
  if (!a) return "v?";
  let label = `v${a.package_version || "?"}`;
  if (a.build_hash && a.build_hash !== "unknown") {
    label += ` · ${a.build_hash}${a.build_dirty ? "*" : ""}`;
  }
  return label;
}

/** True when the running process loaded older code than what's on disk. */
export function isStale(manifest) {
  return Boolean(manifest && manifest.agent && manifest.agent.stale);
}

function _el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function _versionHeader(agent) {
  const head = _el("div", "sd-caps__header");
  head.appendChild(_el("span", "sd-caps__title", "Agent"));

  const ver = _el(
    "span",
    "sd-caps__version",
    `${versionLabel({ agent })}${agent.branch ? ` · ${agent.branch}` : ""}`
  );
  if (agent.loaded_from) ver.title = `loaded from ${agent.loaded_from}`;
  head.appendChild(ver);

  if (agent.stale === true) {
    const badge = _el("span", "sd-caps__badge sd-caps__badge--stale", "stale");
    badge.title =
      `Disk is at ${agent.on_disk_hash || "?"} but this process loaded ` +
      `${agent.build_hash} — restart ComfyUI to pick up the new code.`;
    head.appendChild(badge);
  }
  return head;
}

function _degradedList(degraded) {
  const box = _el("div", "sd-caps__degraded");
  box.appendChild(
    _el("div", "sd-caps__degraded-title", `${degraded.length} module(s) degraded`)
  );
  for (const d of degraded) {
    box.appendChild(
      _el("div", "sd-caps__degraded-row", `${d.layer}/${d.module}: ${d.error}`)
    );
  }
  return box;
}

function _featureCards(features) {
  const wrap = _el("div", "sd-caps__features");
  for (const [key, val] of Object.entries(features)) {
    // Bespoke widgets (switchboard, B2+) mount elsewhere; verbs get chips.
    if (key === "switchboard") continue;
    if (key === "verbs" && Array.isArray(val)) {
      const row = _el("div", "sd-caps__feature");
      row.appendChild(_el("span", "sd-caps__feature-name", "verbs"));
      const chips = _el("span", "sd-caps__chips");
      for (const v of val) chips.appendChild(_el("span", "sd-caps__chip", String(v)));
      row.appendChild(chips);
      wrap.appendChild(row);
      continue;
    }
    if (val && typeof val === "object") {
      const row = _el("div", "sd-caps__feature");
      row.appendChild(_el("span", "sd-caps__feature-name", key));
      row.appendChild(
        _el(
          "span",
          `sd-caps__state sd-caps__state--${val.enabled ? "on" : "off"}`,
          val.enabled ? "on" : "off"
        )
      );
      wrap.appendChild(row);
    }
  }
  return wrap;
}

function _layerGroup(layer, tools, count) {
  const details = document.createElement("details");
  details.className = "sd-caps__layer";

  const summary = document.createElement("summary");
  summary.className = "sd-caps__layer-summary";
  summary.appendChild(_el("span", "sd-caps__layer-name", layer));
  summary.appendChild(_el("span", "sd-caps__layer-count", String(count)));
  details.appendChild(summary);

  for (const t of tools) {
    const row = _el("div", "sd-caps__tool");
    row.appendChild(_el("span", "sd-caps__tool-name", t.name));
    if (t.description) {
      const desc = t.description.length > 110
        ? t.description.slice(0, 107) + "…"
        : t.description;
      const descEl = _el("span", "sd-caps__tool-desc", desc);
      descEl.title = t.description;
      row.appendChild(descEl);
    }
    details.appendChild(row);
  }
  return details;
}

/**
 * Build the full capabilities card from a manifest. Generic by contract:
 * a new agent tool or feature key renders here with zero edits to this file.
 */
export function createCapabilitiesCard(manifest) {
  const card = _el("div", "sd-caps");
  card.appendChild(_versionHeader(manifest.agent || {}));

  if (Array.isArray(manifest.degraded) && manifest.degraded.length) {
    card.appendChild(_degradedList(manifest.degraded));
  }

  if (manifest.features && typeof manifest.features === "object") {
    card.appendChild(_featureCards(manifest.features));
  }

  const tools = Array.isArray(manifest.tools) ? manifest.tools : [];
  const byLayer = new Map();
  for (const t of tools) {
    const layer = LAYER_ORDER.includes(t.layer) ? t.layer : "intelligence";
    if (!byLayer.has(layer)) byLayer.set(layer, []);
    byLayer.get(layer).push(t);
  }
  const catalog = _el("div", "sd-caps__catalog");
  for (const layer of LAYER_ORDER) {
    const group = byLayer.get(layer);
    if (group && group.length) {
      catalog.appendChild(_layerGroup(layer, group, group.length));
    }
  }
  card.appendChild(catalog);
  return card;
}
