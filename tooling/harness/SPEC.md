# SPEC.md — RATIFIED 2026-05-30

> FRAME gate passed. User ratified P1.1–P4.3 as-written, no amendments.
> MODE: SIMULATED (one context, four tracks interleaved, no external launcher).
> State dir: `tooling/harness/` (isolated — repo-root `harness/` deliberately untouched).

## Outcome
ComfyUI's agent assistant *does* instead of *describes*: reads and pushes the canvas,
edits it surgically and reversibly, profiles and locates its own outputs, parses any
shared workflow, resolves local assets, and reasons from relevant memory.

## Homes
- **Home A — node pack:** `G:\COMFY\ComfyUI\custom_nodes\comfy_agent_bridge\`
- **Home B — MCP tool server:** the comfy-Cozy package at repo root (`G:\Comfy-Cozy`,
  i.e. `..` from cwd). Exact module located by Leg-0 recon (see TRACE).
- **NOT a build target:** `tooling/` — docs + harness state only.

## Acceptance Predicates

### Track 1 — Tool Layer (Home B)
- **P1.1 `#4`** `get_node_info` ≤200 tok at `summary`, ≤1KB at `signature` (required inputs
  never dropped), unchanged at `full`; default `summary`; oversize auto-truncates with a
  `detail='full'` hint.
- **P1.2 `#6`** `delete_node` / `replace_node` / `rewire_around` work; delete leaves no
  dangling links; rewire bridges matching slots and **reports what it dropped**; every op
  snapshots prior graph state (reversible).

### Track 2 — Bridge → WS Signals (Home A+B)
- **P2.1 `#1-push`** a connected tab reloads on push; node pack survives hot-reload; the 11
  bridge hostile cases pass.
- **P2.2 `#1-readback`** an artist edit is retrievable within the debounce window; an
  agent-originated load never registers as an edit (loop-prevention); falls back to
  `get_canvas_state()` pull if the transport can't push.
- **P2.3 `#5`** `get_execution_profile(prompt_id)` returns ordered per-node timing matching a
  known render; a planted regression is flagged; cached (~0ms) nodes are not flagged.
  *(stochastic-timing → replicate on a fresh run before promoting)*
- **P2.4 `#8`** a file written outside `output/` is still caught; the diff returns exactly the
  new files; unrelated writes don't false-positive.

### Track 3 — Comprehension (Home B)
- **P3.1 `#2`** a known UI workflow round-trips to API format that **executes identically**;
  `seed + control_after_generate` maps correctly; a node absent from `/object_info` is
  surfaced, not guessed.
- **P3.2 `#7`** `list_assets` lists images from `input/` and recent outputs; search filters;
  perceptual duplicates collapse; scales to thousands (cap/paginate).

### Track 4 — Gated / Dependent (Home A+B)
- **P4.1 `#3` GATED** — only if the client renders images mid-tool-call. If so: previews
  appear during a render; abort→requeue-with-changed-params works.
- **P4.2 `#9`** a perceptually-identical image returns a cached analysis; a changed image
  re-analyzes; a near-threshold pHash does **not** false-dedup.
  *(stochastic-vision → replicate on a fresh run before promoting)*
- **P4.3 `#10`** opening on a Seedance workflow surfaces prior Seedance preferences;
  irrelevant memory is not injected; injection stays within the P1.1 context budget.

## Out of Scope
Anything outside the ten gaps · multi-user concurrency on the bridge (single-artist) · any
feature resting on an unconfirmed runtime capability until its gate passes · audiobook/
lyrics/transcript generation.

## Falsification Conditions
- A Leg 0 symbol absent/divergent → that feature's approach is wrong as-written; reopen
  DELIBERATE for it.
- Agent transport can neither push nor support a pull tool → `#1-readback` infeasible; drop.
- Client cannot render mid-tool-call images → `#3` falsified, do not build.
- `widgets_values` unmappable via `/object_info` for a class → parser falsified for that
  class; surface.
- `vram_delta` absent from WS stream → ship duration-only.

## Verification Strategy (per predicate → layer · stochastic?)
| Predicate | L0 | L1 | L2 | L3 | L4 | stochastic |
|---|---|---|---|---|---|---|
| P1.1 | ✓ | ✓ | | ✓ (no req-input loss) | | no |
| P1.2 | ✓ | ✓ | ✓ | | | no |
| P2.1 | ✓ | ✓ | ✓ | | ✓ | no |
| P2.2 | ✓ gate | ✓ | ✓ (loop) | | | no |
| P2.3 | ✓ | ✓ | ✓ | | | **yes (timing)** |
| P2.4 | ✓ | ✓ | ✓ | | | no |
| P3.1 | ✓ | ✓ | | ✓ (executes identically) | | no |
| P3.2 | ✓ | ✓ | ✓ | | ✓ (scale) | no |
| P4.1 | ✓ gate | ✓ | | | ✓ | partial |
| P4.2 | ✓ | ✓ | ✓ | | | **yes (vision)** |
| P4.3 | ✓ | ✓ | | ✓ | | no |
