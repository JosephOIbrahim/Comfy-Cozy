# DISPATCH — ComfyUI Agent-Bridge

> **Mission (one sentence):** Build a ComfyUI custom node pack that lets an external agent push a workflow JSON straight onto the live ComfyUI canvas over the existing websocket, plus the MCP tool that calls it — verified against the real install, hardened by adversarial tests.
>
> **Structure:** Relay. 5 legs (Leg 0 → Anchor). Each leg hands off with a line-cited gate check. Dependent work runs sequentially; do not parallelize the legs.

---

## HARD INVARIANTS (constitution — never violate)

1. **API verification is a gate, not a suggestion.** Every ComfyUI / LiteGraph symbol this dispatch names is *assumed*, not confirmed. Leg 0 confirms each one against the actual install via runtime introspection. If a symbol is absent or behaves differently → **HALT and surface**, do not improvise a substitute.
2. **One mutation per script.** Atomic. No multi-purpose files.
3. **Idempotent registration.** The route must not double-register on hot-reload. The frontend listener must register exactly once. Reloading the node pack twice must not throw or stack duplicate handlers.
4. **No silent failures.** The route returns structured error JSON with a non-200 status on bad input. The tool raises cleanly on non-200 and on unreachable host — no stack vomit, no silent hang.
5. **Validate before broadcast.** Never hand garbage to `loadGraphData`. The route shape-checks the payload before `send_sync`.
6. **Path safety on the tool.** The `path` arg is resolved and confirmed to be a `.json` under an allowed root before it's opened. No traversal.
7. **Provenance envelope.** Payload is `{"workflow": <graph>, "meta": {"source": ..., "reason": ...}}`. Frontend loads `e.detail.workflow`; `e.detail.meta` is available for logging. `workflow` is required; `meta` is optional.
8. **Atomic commits, race-safe push.** One leg = one logical commit. On non-fast-forward: fetch + rebase, max 3 attempts, halt on merge conflict.
9. **Gate criteria cite line numbers.** "Done" is proven by `file:line`, not by assertion.

---

## LEG 0 — API VERIFICATION GATE  `Mile 0 of ~5`

**The thing comfy-Cozy skipped. Do this first, write no bridge code until it passes.**

Introspect the *actual* ComfyUI install (the one that will run this), confirm each assumed symbol, record the result:

**Backend (run inside ComfyUI's python / a node that prints at import):**
```python
from server import PromptServer
print("PromptServer.instance:", PromptServer.instance is not None)
print("send_sync:", hasattr(PromptServer.instance, "send_sync"))
print("routes:", hasattr(PromptServer.instance, "routes"))
# confirm the decorator form works: @PromptServer.instance.routes.post("/...")
```

**Frontend (browser console, ComfyUI open):**
```js
console.log("app.loadGraphData:", typeof app.loadGraphData);     // expect "function"
console.log("api.addEventListener:", typeof api.addEventListener); // expect "function"
// confirm send_sync payload arrives as e.detail (vs wrapped/renamed) — see Leg 3 probe
```

**Confirm the working JS import path for this version** — test both and record which resolves:
- `import { app } from "/scripts/app.js"` (absolute)
- `import { app } from "../../scripts/app.js"` (relative from `extensions/<pack>/`)

**GATE:** Every symbol above confirmed present + working import path identified. Any absence → HALT, surface the gap, stop. **Do not proceed to Leg 1 on a missing symbol.**

---

## LEG 1 — ARCHITECT (design only, no code)  `Mile 1 of ~5`

Produce a short design doc covering:
- Directory layout: `custom_nodes/comfy_agent_bridge/{__init__.py, web/agent_bridge.js}`
- **Route contract:** `POST /agent/push_workflow` — request body schema, success response `{"ok": true}`, error responses + status codes.
- **Event contract:** event name `agent.load_workflow`, payload envelope (invariant 7), how `send_sync` → frontend `e.detail` maps (confirmed in Leg 0).
- **Workflow JSON shape check:** minimum validation the route applies before broadcast.
- **Tool contract:** `push_workflow_to_canvas` signature, args, return, error behavior.

**GATE:** Contract written. Note: `send_sync` broadcasts to *all* connected clients — multiple open tabs all reload. Document this as expected behavior, not a bug.

---

## LEG 2 — FORGE: backend route  `Mile 2 of ~5`

Implement `__init__.py`. Reference shape (verify against Leg 0 findings):

```python
from aiohttp import web
from server import PromptServer

@PromptServer.instance.routes.post("/agent/push_workflow")
async def push_workflow(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "invalid json"}, status=400)

    workflow = data.get("workflow")
    if not isinstance(workflow, dict):
        return web.json_response(
            {"ok": False, "error": "missing or malformed 'workflow'"}, status=400
        )

    PromptServer.instance.send_sync("agent.load_workflow", data)
    return web.json_response({"ok": True})

NODE_CLASS_MAPPINGS = {}
WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "WEB_DIRECTORY"]
```

**GATE (cite lines):** route registers without error; returns `ok:true` on valid payload; returns 400 on invalid JSON, on missing `workflow`, and on `workflow` that is a list/string/null. **Double-import / hot-reload does not throw** (invariant 3 — guard the registration).

---

## LEG 3 — FORGE: frontend listener  `Mile 3 of ~5`

Implement `web/agent_bridge.js` using the import path confirmed in Leg 0:

```js
import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

app.registerExtension({
  name: "agent.bridge",
  async setup() {
    api.addEventListener("agent.load_workflow", (e) => {
      const wf = e?.detail?.workflow;
      if (!wf) return;                 // defensive: bad payload doesn't white-screen
      app.loadGraphData(wf);
      // e.detail.meta available here for provenance logging
    });
  },
});
```

**Probe during this leg:** push a known-good workflow, confirm `e.detail.workflow` is the graph (not double-wrapped, not renamed). If the shape differs, fix here — do not patch the backend to match a wrong assumption.

**GATE (cite lines):** extension loads; pushing a valid workflow loads it onto the canvas; listener registered exactly once (reload the page / re-trigger setup → no duplicate handlers); a malformed graph that slips past the backend check fails gracefully without crashing the canvas.

---

## LEG 4 — FORGE: client tool  `Mile 4 of ~5`

Implement `push_workflow_to_canvas` **as an MCP tool** (default — Claude calls it directly). *If standalone-script form is wanted instead, redirect here.*

```python
import json
import os
import requests  # or httpx — match the existing MCP server's http client

ALLOWED_ROOT = os.path.abspath("./workflows")  # adjust to real root

def push_workflow_to_canvas(
    path: str,
    comfy_url: str = "http://127.0.0.1:8188",
    source: str = "agent",
    reason: str = "",
) -> dict:
    full = os.path.abspath(path)
    if not full.startswith(ALLOWED_ROOT) or not full.endswith(".json"):
        raise ValueError(f"path not allowed: {path}")

    with open(full, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    resp = requests.post(
        f"{comfy_url}/agent/push_workflow",
        json={"workflow": workflow, "meta": {"source": source, "reason": reason}},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()
```

**GATE (cite lines):** POSTs to the route; returns the parsed `{"ok": true}`; raises cleanly on non-200; raises cleanly on unreachable `comfy_url` (timeout, not hang); rejects non-existent path, non-json path, and traversal outside `ALLOWED_ROOT`.

---

## ANCHOR LEG — CRUCIBLE (hostile tests, fix-forward, never weaken)  `Mile 5 of ~5`

Write and pass these. **Fix the code, never the test.**

| # | Case | Expected |
|---|------|----------|
| 1 | Malformed JSON body | 400, no broadcast |
| 2 | Missing `workflow` key | 400 |
| 3 | `workflow` is list / string / null | 400 |
| 4 | Valid workflow, **no browser connected** | route returns 200, tool does not hang |
| 5 | Oversized payload (e.g. 50MB graph) | defined behavior — size guard or clean timeout, no crash |
| 6 | Concurrent pushes | last-write-wins on canvas, no crash |
| 7 | Node pack reloaded twice | route does not double-register / throw (invariant 3) |
| 8 | Two tabs open | both reload — documented, asserted as expected |
| 9 | Malformed graph passes backend shape check | frontend `loadGraphData` fails gracefully, canvas survives |
| 10 | Tool: path missing / non-json / traversal | clean `ValueError`, never reaches network |
| 11 | Tool: `comfy_url` unreachable | clean timeout error |

**GATE:** all cases pass. Master clean. Final commit cites the test file + count.

---

## RELAY HANDOFF PROTOCOL

At each leg boundary, the outgoing leg writes:
- **What's done** (file:line proof)
- **What the next leg inherits** (contracts, confirmed symbols)
- **Anything that drifted from this dispatch's assumptions** (esp. Leg 0 findings that changed the plan)

The incoming leg reads that, confirms the gate, then proceeds. No leg starts on an unverified gate.

## HALT-AND-SURFACE TRIGGERS

Stop and surface — do not improvise — if:
- Any Leg 0 symbol is absent or behaves unexpectedly.
- `send_sync` payload arrives in a shape that contradicts the event contract.
- Hot-reload double-registration can't be guarded without an API that doesn't exist.
- A CRUCIBLE case can't pass without weakening it.

## DEFINITION OF DONE

A connected ComfyUI tab reloads its canvas to a pushed workflow when `push_workflow_to_canvas(path)` is called, on a node pack that survives hot-reload, with all 11 hostile cases green and every gate cited by line number.
