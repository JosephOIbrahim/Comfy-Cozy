# L-PANEL — Adversarial Pass (June 2026)

The UI-panel dimension was banked as six cap-killed V0 findings. This is the
adversarial pass: each was probed against live source. Two were forged and
verified this cycle; one was **refuted**; three are real but browser-render-
bound or entangled with a panel-architecture decision, and are recorded here
forge-ready rather than blind-edited (shipping unverified render changes to the
living UI, or deleting documented half-built code, would violate the Floor).

**Evidence:** `tooling/harness/LEDGER.md` (L-PANEL entry) + the probe transcript.

---

## Forged + verified this cycle

### A — `/agent/*` bridge routes were unauthenticated mutation surface ✅ FIXED
`node_pack/comfy_agent_bridge/__init__.py` registered POST `/agent/push_workflow`
(replaces every connected tab's canvas via `send_sync("agent.load_workflow")`),
POST `/agent/canvas_changed` (seeds `_canvas_buffer`, which the agent later
trusts as "what the artist drew" — a confused-deputy seed), and two GETs, with
**no auth check** — while every `/comfy-cozy/*` route was gated. **Fix:**
`bridge_auth_failure()` — Origin-first (browser must be same-origin; a browser
fetch can't attach a Bearer header, so same-origin *is* the auth layer) +
Bearer for non-browser callers when `MCP_AUTH_TOKEN` is set, mirroring the
audited sidebar-WebSocket gate. The agent's own httpx calls now send the Bearer
(`canvas_bridge.bridge_auth_headers()`). **Verified:** `tests/test_bridge_auth.py`
(6 tests, pure logic, no live ComfyUI).

### B — raw `str(e)` leaked into the chat transcript ✅ FIXED (scope corrected)
The "~30 leaking `except` blocks" framing was **wrong** — every `/comfy-cozy/*`
REST handler already logs server-side and returns a generic 500. The real leak
was **5 sites on the chat/WebSocket path** that put the raw exception
(`str(e)` / `f"…{e}"` — internal paths, `[WinError …]`, dict KeyErrors) into the
`{"type":"error","message":…}` frame the browser renders verbatim:
`panel/server/chat.py:253,504`; `ui/server/routes.py:971,973,1311`. **Fix:**
`safe_error_message(context)` in `agent/_session_helpers.py` — the sites keep
their `exc_info=True` server-side logging and emit a generic contextual bubble.
**Verified:** helper unit-tested; the 5 sites route through it (diff-evident).

---

## Refuted

### "MCP_AUTH_TOKEN silently 401s the canvas bridge" ❌ NOT REPRODUCED
The premise is false — the bridge routes were never token-gated, so a set token
could not 401 them. The real defect was the **opposite** (under-protection),
fixed by A. Recorded so it is not re-litigated.

---

## Real, parked forge-ready (browser-render-bound / architecture decision)

> These are genuine. They are **not** forged blind because verifying a render
> fix is browser-bound and the "right" fix is a panel-architecture choice that
> the maintainer + a live session must make. Each carries its exact diff.

### C — token streaming wired but never rendered (typing dots for the whole reply)
The wire **does** stream per-token (`text_delta` frames). The *living* UI is the
sidebar (`ui/web/js/sidebar.js`); its `text_delta` handler (`:464-494`) only
accumulates `session.streamAccum` and shows a typing indicator — it renders text
only when the final `message`/`DONE` frame lands. So the user sees dots for the
whole reply despite a real per-token stream.
- **Forge-ready fix:** in the `text_delta` case (`sidebar.js:486-491`), render
  `session.streamAccum` into the message body on every delta (`renderText` is
  already imported, `chat.js:2`). The existing finalizer still does the final
  rich re-render — no double-render.
- **Entanglement:** `panel/web/js/appMode.js` (currently dead, see E) *already
  renders streaming correctly* (`:146-149`). The architecture choice — patch the
  live `sidebar.js` vs. mount the correct-but-dead `appMode` — is the real
  decision. Do not delete `appMode.js` until this is settled.
- **Verify:** the accumulate-then-render core is jsdom/Vitest-unit-testable once
  `sidebar.js` is made importable (it has top-level side effects today; `vitest.
  config.js` only includes `tests/panel/**`). End-to-end "dots → streaming text"
  is browser-only.

### D — tab-switch drops/truncates the reply mid-turn
Also in `sidebar.js`. ComfyUI destroys+rebuilds the panel DOM on tab-switch
(`:57-61`); the shared WS stays alive, so the request isn't aborted — but the
in-flight reply lives only in `streamAccum` (never in `session.messages` until
finalize), the per-mount `streamingEl` detaches, and the next post-switch delta
hits `!streamingEl` and runs `session.streamAccum = ""` (`:481`), **discarding
all pre-switch text**.
- **Forge-ready fix (two parts):** (1) move the `streamAccum = ""` reset out of
  the delta handler (`:481`) into `setBusy(true)` (`:446`), so a fresh mount's
  first delta appends rather than erases; (2) in `buildSidebar`, after the
  rehydration loop (`:357-358`), if `streamAccum && !turnFinalized`, recreate the
  streaming element, render `renderText(streamAccum)`, and bind it as the
  mount-local `streamingEl`.
- **Verify:** same harness path as C (Vitest after extraction; browser for live).

### E — ~60 KB dead frontend modules (not the claimed ~50 KB)
Real and undersized: **60.3 KB across 9 files** (probe inventory). **The "dead
chat backend" sub-claim is FALSE** — `panel/server/chat.py` is wired at
`panel/server/routes.py:936-938`. Statically dead (zero importers, no
`registerExtension`/`registerSidebarTab`): `panel/web/js/{appMode, graphMode,
experienceDash, autoresearchMonitor, predictionOverlay}.js` (~52 KB) and
`ui/web/js/{discover, status}.js` (108 B stubs). `ui/web/js/{workflow,tokens}.js`
are designed-but-unwired (the "Workflow Zone").
- **Why not deleted this cycle:** (1) `appMode.js`/`graphMode.js` are documented
  as features in `README.md` and are the **half-built correct streaming path**
  (C) — deleting them forecloses the cleaner fix; (2) deletion is cleanliness,
  not a defect; (3) ComfyUI auto-imports every `web/*.js`, so "dead" means
  "wires no surface", which a static read confirms but a maintainer should
  confirm against the roadmap before removal.
- **Recommendation:** a separate cleanup once C's architecture decision lands —
  then either mount `appMode` (and keep it) or delete the dead set together. The
  two 108 B stubs (`discover.js`, `status.js`) are safe to drop anytime.

---

*Forged: A, B (+ tests). Parked forge-ready: C, D, E — each with its exact diff,
pending a browser session and the sidebar-vs-appMode architecture call.*
