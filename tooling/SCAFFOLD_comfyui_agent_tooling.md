# SCAFFOLDING PROMPT — pre-build groundwork + Leg 0 mechanism

> Paste after ratifying SPEC + mode. Stay inside the harness: gated, atomic commits, progress reporting, **no feature builds yet.** This block makes the groundwork real and turns Leg 0 from a hand-wave into actual probes.

Before any feature work, lay the groundwork. Four blocks, in order. Report per the harness format. HALT where specified.

---

## 1 — State files: populate, don't stub

Create `tooling/harness/` and write **real initial content**, extracted from the loaded HARNESS + DISPATCH (not empty placeholders):

- **SPEC.md** ← ratified predicates P1.1–P4.3 + Outcome + Out-of-Scope + Falsification Conditions + the Verification Strategy table.
- **CHAMPION.md** ← the seed champion per track (= the *current pain* from the dispatch; the floor each track must beat). These are the bar, not "better than nothing."
- **DEADENDS.md** ← the 6 pre-seeded traps from the harness. This file is read before every proposal.
- **PLAN.md** ← the 4 tracks, each `GOAL · CONTRACT · VERIFIER · ranked queue · fork-flag`.
- **DIGEST.md** ← the SKETCH digest: seed champions, `MODE=SIMULATED`, line count, a 0–1 confidence per predicate, open questions.
- **LOG.md / FORUM.md / TRACE.md / LEDGER.md** ← headers only, empty bodies.

Add `tooling/harness/` to `.gitignore` — run-state stays out of commits. Commit the `.gitignore` change only.

## 2 — Workspace skeletons: structure only, no features

- **Home A** — create `G:\COMFY\ComfyUI\custom_nodes\comfy_agent_bridge\` with a minimal `__init__.py` that loads clean (`NODE_CLASS_MAPPINGS={}`, `WEB_DIRECTORY="./web"`, `__all__`) and an empty `web/`. The route + JS are Phase 0 — **not now.** Verify (L0): ComfyUI starts with the pack present, no error. *Note: this lives outside the comfy-Cozy repo — git-init it as its own package if you want it versioned, else leave as files for now.*
- **Home B** — **recon only.** Locate the existing ~113-tool MCP server module in the comfy-Cozy package (`..`). Identify how tools register and the response-wrapping seam `#4` will hook into. Write findings to TRACE. **Create no code.**

## 3 — Dependency pre-flight: inventory, install only on my OK

Identify the ComfyUI python env and the comfy-Cozy env (they may differ). Inventory what the program needs; report present vs missing. **Do not install without my approval.**

- `requests`/`httpx` (push tool) · `watchdog` (`#8` watcher) · the embedding/pHash lib for `#7`/`#9` — **reuse whatever `hash_compare_images` already uses; confirm it's installed, don't add a second one.**

Report the gap list. **HALT for install approval.**

## 4 — Leg 0 diagnostic harness: make verification real

The four gates resolve from the live install. Build the probes; record every result to TRACE.

- **Backend (autonomous):** run a Python introspection script in the ComfyUI venv — confirm `server.PromptServer` class + the `send_sync` method exist (class-level checks need no running server); read ComfyUI's source to confirm the `routes.post` registration pattern. *(Functional route test is Phase 0, not here — Leg 0 confirms the symbols/pattern exist.)*
- **`/object_info` (needs ComfyUI running):** `GET http://127.0.0.1:8188/object_info` — confirm it returns input schema + ordering for the `#2` parser gate. Capture one node's schema as evidence.
- **WS format (`#5` vram gate):** inspect the `executing`/`executed` WS message shape (source read or one captured render) — is per-node timing present? Is `vram_delta`? **If vram is absent → log to DEADENDS (ship duration-only),** per the falsification condition.
- **Frontend (hand to me):** emit the exact browser-console snippet — `typeof app.loadGraphData`, `typeof api.addEventListener`, and the import-path test (`/scripts/app.js` vs `../../scripts/app.js`). I'll run it in my ComfyUI tab and paste results. *(Optional: bundle a throwaway diagnostic web extension that auto-logs these so I just read devtools — your call.)*
- **Transport (`#1` read-back):** recon comfy-Cozy's transport — can it receive server-pushed events, or request/response only? This decides push vs `get_canvas_state()` pull. Write the finding to TRACE.
- **Client-render (`#3`):** I confirm this one — flag it as an open question for me and **build nothing for `#3` until it's answered**, either way.

*If ComfyUI isn't running, ask me to start it before the `/object_info` and WS checks.*

**HALT on any missing backend symbol** — that's a falsification condition, not something to route around.

---

On green Leg 0 (or documented fallbacks for transport/vram/client-render), proceed into DELIBERATE ⇄ EXECUTE on **Track 1 + Track 2-bridge**. Announce the track and lens on entry.
