# Agent Tooling — Best Practices

> Derived from the `feat/agent-tooling` build (gaps #1–#10, the comfy-Cozy agent harness run).
> Two halves: **(A) engineering** practices for extending this tool system safely, and
> **(B) process** practices for operating the agent/harness reliably. Both are things this run
> learned by getting them wrong first.

---

## A. Engineering — extending the tool system

### A1. Adding a tool is a *four-file* contract, not one
The single biggest recurring break this run: adding a tool in one place and forgetting the others.
A new tool is not "done" until **all four** are updated **in the same commit**:

1. **Module** — create `agent/tools/<name>.py` exporting `TOOLS: list[dict]` + `handle(name, input)`.
2. **Registration** — append the module to `_INTELLIGENCE_MODULE_NAMES` in `agent/tools/__init__.py`.
3. **Gate classification** — add the tool to `TOOL_RISK_LEVELS` in `agent/gate/risk_levels.py`.
   **This is not optional.** Unknown tools default to `REVERSIBLE`, and the pre-dispatch gate denies
   a REVERSIBLE tool that has no undo/session ("No active session… REVERSIBLE but no undo available").
   A tool that works in isolation will be silently gate-blocked end-to-end without this.
   - READ_ONLY: pure reads (list/get/parse/profile/recall).
   - EXECUTION: external side-effects or GPU/API delegation (push to canvas, analyze).
4. **Count-contract tests** — bump `tests/test_tools_registry.py` (the `== N` total **and** the
   `expected` name set) and `tests/test_mcp_server.py` (`== N`). These hardcode the tool count;
   any addition breaks exactly three tests until updated.

> Checklist lives in `node_pack/.../README.md` and `tooling/harness/DEADENDS.md`. Run
> `pytest tests/test_tools_registry.py tests/test_mcp_server.py tests/test_gate.py` after any tool add.

### A2. Verify API symbols against the live install (Leg 0), never from memory or docs
Every ComfyUI/LiteGraph symbol was confirmed via `dir()` / `/object_info` / source read against the
**running 0.22.0 install** before building on it. Findings that changed the plan:
- **Transport is PULL, not push** — MCP is stdio request/response; the agent cannot receive
  server-pushed events. Canvas read-back = FE buffers edits, agent pulls `get_canvas_state`.
- **No vram in the WS stream** — `executing`/`executed` carry no memory fields → profiling is
  duration-only. Don't promise data the runtime doesn't emit.
- **`widgets_values` order is not positional** — map via `/object_info` schema order, and hit the
  **raw** endpoint (the existing `get_node_info` alphabetizes via `to_json(sort_keys=True)`).
- **Previews are binary WS frames** — a stdio agent can't consume them mid-tool-call → feature #3
  falsified, built nothing.

**Rule:** if a symbol/capability is absent or behaves differently than assumed, HALT and surface —
do not substitute. A falsified feature with a documented reason is a *correct* outcome, not a failure.

### A3. Build the producer before (or with) the consumer
#5 shipped as a Home-B tool calling `/agent/exec_profile` while the Home-A route didn't exist — it
404'd live and a payload-only unit test masked it. **When a tool calls an endpoint, the endpoint must
exist and be exercised together.** Prefer one integration test that drives consumer→producer over two
isolated unit tests that each pass alone.

### A4. Reuse before adding dependencies
- Perceptual hashing (#7 dedup, #9 cache) reused `vision._compute_average_hash` (pure Pillow) — **no
  `imagehash` install**.
- The output watcher (#8) used snapshot-diff — **no `watchdog` install**.
- Reversibility (#6 surgery) reused the existing `history` deque + `copy.deepcopy` snapshot.
Check what the codebase already does before pulling a new library or inventing a mechanism.

### A5. Honor the standing invariants in new tools
- **Context-cost guard (#4):** info-heavy tools default to a compact tier and never blow the budget;
  `summary`/`signature` may compress but **never drop a required input**.
- **Reversibility:** any graph/canvas mutation snapshots prior state first.
- **No silent failures:** structured error JSON, non-200 on bad input, no stack vomit.
- **Idempotent registration:** routes/listeners/extensions register once and survive hot-reload
  (guard flag + wrapping `send_sync` only if not already wrapped).
- **Path safety:** any tool taking a filesystem path runs `validate_path`.
- **Honest degradation:** if a slot type can't be resolved offline (e.g. `rewire_around` multi-upstream),
  drop + **report** rather than guess.

### A6. The node pack lives outside the repo — keep them in sync
Home A (`comfy_agent_bridge`) runs from `G:\COMFY\ComfyUI\custom_nodes\` but its canonical source is
now `node_pack/comfy_agent_bridge/` in-repo. **Symlink** the runtime copy to the repo so they never
drift (see the pack README). A plain copy means re-copying after every change and risks a stale
runtime. Restart ComfyUI after changing `__init__.py` or routes.

---

## B. Process — operating the agent/harness reliably

### B1. Never record a verifier's result before its command returns
The single most damaging failure mode this run. Multiple times, a test count / commit hash / "passed"
was written into state or a report **before** the command actually returned — and once a fabricated
"4369 passed" hid a *real* 3-test regression inside a commit. Always: run → read the actual final
line → then write. A "done" without a `file:line` or a real result behind it is not done.

### B2. When the tool channel is unstable, route verification through file Read
During an MCP/tool outage, echoed command output was garbled and contradictory (same `grep -c`
returning both 13 and 0). The reliable workaround: write results to a file, then `Read` it. Don't
trust inline echoed text mid-instability — and don't escalate a tooling glitch to a "HALT" without
confirming it's real (one premature HALT here mislabeled a genuine gate bug as "channel corruption").

### B3. Verify outward/irreversible actions actually happened
The authorized `git push` *appeared* to run but silently didn't land — caught only by checking
`git ls-remote` against origin (no upstream, no ref). After any push/deploy/external call, **confirm
on the far side** (remote ref == local tip), don't trust the success message.

### B4. INTEGRATE and STRESS are not ceremony — they catch what unit tests miss
- INTEGRATE (full mocked suite) caught the gate-classification bug that all per-module tests passed
  around.
- STRESS (hostile cases + live gate probes) confirmed tools reach their handlers through the real
  dispatcher, not just in isolation.
Run the full suite as the gate before every commit of shared-state changes (registry, gate, dispatch).

### B5. Know your pre-existing baseline failures
`test_cozy_persistence::test_kill_after_flush_resumes_cleanly` fails on Windows (`signal.SIGKILL`
doesn't exist there). It is **unrelated** to this work — proven by stash-out and by the
`AttributeError` root cause. Don't chase a red that's red before you touched anything; identify and
document the baseline so a real new failure stands out.

### B6. Scale the rigor to the request
"Find any bug" ≠ "thoroughly audit." This run was asked to drive all the way through Track 4, so it
ran the full FRAME→SKETCH→EXECUTE→INTEGRATE→STRESS→SHIP arc with verifier-gating at each step. Match
that ceremony to the ask; don't impose it on a one-line fix.

---

## C. Carryover items (live-only — need a running instance)

These are **diagnosed and built** but require a live ComfyUI to confirm (the agent has no
browser/live-render access):

1. **#5 timing, live** — after a real generation, `GET /agent/exec_profile/{prompt_id}` should return
   ordered per-node `duration_ms` matching the render; a planted slow node flags as a regression;
   cached (~0ms) nodes don't. (Logic unit-verified; live render is the open check.)
2. **Panel contrast fix** — `.sd-code-inline` (`ui/web/css/superduper.css:325`) sets
   `color: var(--sd-text-1)` on `background: var(--sd-surface-3)`; those theme tokens resolve close
   in the current theme, hiding the text ("solid bars"). Change the `color` to a high-contrast token
   (e.g. `--sd-text-2`) and confirm in the browser.
3. **Bridge integration tests** — all current tests are mocked. Add `@pytest.mark.integration` tests
   that exercise push / canvas read-back / exec_profile against a live server.

---

## TL;DR — the five that would have prevented most of this run's rework

1. Adding a tool = module + registration + **gate class** + **count tests**, one commit.
2. Confirm live API symbols (Leg 0); a falsified feature is a valid, documented outcome.
3. Never write a test/hash/"passed" before the command returns.
4. Verify outward actions on the far side (remote ref, not the success message).
5. Run the full suite as the gate before committing shared-state changes.
