# TRACE.md — Leg 0 probe results + recon (evidence by file:line)

## Environment
- ComfyUI **0.22.0** · install `G:\COMFY\ComfyUI` · active venv **comfy3d_env** (py3.14.2) · RTX 4090
- MCP server **v3.0.0**, 113 tools (86 intelligence + 27 brain); **stdio** transport
- Home B pkg: comfy-Cozy `G:\Comfy-Cozy` (`agent/`), installed in **system py3.14** (no in-repo venv)

## Backend symbols (Home A / ComfyUI) — 🟢 GREEN (no HALT)
- `PromptServer` class — `server.py:203` (AST FOUND)
- `PromptServer.instance` — `server.py:205` (set in `__init__`; live server confirms runtime)
- `send_sync(event, data, sid=None)` — `server.py:1228` (AST FOUND); broadcast use `server.py:1233`
- `send` (async) — `server.py:1126`
- route table — `routes = web.RouteTableDef()` `server.py:250`; `self.routes` `:251`; `app.add_routes` `:1076`
- `@routes.post` decorator — 25 uses (`/prompt` `server.py:927`, `/upload/image` `:450`)
- **VERDICT:** Phase-0 push via `PromptServer.instance.routes.post` + `send_sync` is sound.

## Frontend symbols (Home A) — 🟢 GREEN (served; final in-tab confirm optional)
- `/scripts/app.js` served — `comfy3d_env/.../comfyui_frontend_package/static/scripts/app.js`
  (shim: `export const app = window.comfyAPI.app.app`)
- `/scripts/api.js` served — same `static/scripts/api.js` (`export const api = window.comfyAPI.api.api`)
- **IMPORT-PATH GATE → ABSOLUTE `"/scripts/app.js"`** (not relative)
- `loadGraphData(` — `static/assets/GraphView-*.js`; `registerExtension` present; `api.addEventListener` present
- Optional in-tab confirm:
  `import('/scripts/app.js').then(m=>console.log('loadGraphData',typeof m.app.loadGraphData))`
  `import('/scripts/api.js').then(m=>console.log('addEventListener',typeof m.api.addEventListener))`

## Gate resolutions
- **TRANSPORT (#1-readback) → PULL.** MCP stdio req/resp (`mcp_server.py:7,27`); no server→agent push.
  FE change hooks exist (`onNodeAdded`/`onConnectionChange`/`onConfigure`/`graphChanged`).
  Design: debounced FE `POST /agent/canvas_changed` → backend buffer → `get_canvas_state()` pull (Home B);
  loop-prevent via `window.__agentLoad`. **Fork A = PULL.**
- **VRAM (#5) → DURATION-ONLY.** WS `executing`(`execution.py:487`)/`executed`(`:425,:565`)/
  `execution_cached`(`:755`)/`execution_error`(`:527`) carry `{node,display_node,prompt_id,output}` —
  **no timestamps, no vram_delta.** Timing = consumer-side; vram dropped (→ DEADENDS).
- **WIDGET-ORDERING (#2, banked) → raw `/object_info` only.** `get_node_info` re-sorts via
  `to_json(sort_keys=True)`: KSampler returned alphabetical vs RAW order
  `[model,seed,steps,cfg,sampler_name,scheduler,positive,negative,latent_image,denoise]`.
  Parser MUST `GET /object_info/{class}` raw.
- **CLIENT-RENDER (#3, Track 4) → 🔵 OPEN (user).** No build until answered.

## Home B seam (Track 1)
- dispatch `handle()` — `tools/__init__.py:215`
- **#4 disclosure:** `get_node_info` TOOLS schema `comfy_api.py:95`; handler `_handle_get_node_info`
  `comfy_api.py:282`; result dict `:305`; tiering precedent = `get_all_nodes` `format` names_only/summary/full
- **#6 surgery:** `workflow_patch.py` — `add_node` `:668`; `connect_nodes` sets
  `inputs[field]=[node_id,out_idx]` `:763/:795`; old_value snapshot `:783` (reversible via undo history)

## Dependency pre-flight (gaps; NONE block Track 1 / Phase-0 bridge)
- comfy3d_env (Home A): **watchdog MISSING** (#8), **imagehash MISSING**; aiohttp/PIL/cv2/httpx/requests/numpy OK
- comfy-Cozy (Home B): **imagehash MISSING**; httpx/requests/watchdog/PIL/cv2/numpy/mcp OK
- `hash_compare_images` impl NOT yet located (grep hit capability registry). `cv2` present both envs → may need
  no new lib. Verify before #7/#9.
- **Installs to start Track 1 + Phase-0 bridge: NONE.** watchdog (#8) + pHash decision (#7/#9) → later, w/ approval.

## Home A skeleton
- `custom_nodes/comfy_agent_bridge/__init__.py` + `web/.gitkeep` created; **import-clean verified** in comfy3d_env
  (`NODE_CLASS_MAPPINGS={}`, `WEB_DIRECTORY=./web`). Full ComfyUI restart pickup = user.
