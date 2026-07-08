# Comfy-Cozy — Direction Scaffold

> **Snapshot date:** 2026-05-27
> **Author voice:** written as an engineering direction memo — evidence over
> assertion, tradeoffs named, recommendation explicit.
> **How to use:** this is a portable context-transfer doc. Drop it into a fresh
> Claude Desktop session to orient on what Comfy-Cozy is, where it actually
> stands, and where it should go next. For deep architecture, point Desktop at
> `docs/ARCHITECTURE.md`. For governance, `.claude/COZY_CONSTITUTION.md`.

---

## 1. Thesis

Comfy-Cozy is an AI co-pilot for **VFX artists** — lighting TDs, compositors,
texture painters — who live in ComfyUI but never signed up to be node
engineers. It is a **driver, not a generator**: it reads the workflow you
already have, makes small validated changes, reports what it did and why, and
keeps every mutation reversible.

The bet, in one line: **as the agent-drives-ComfyUI pattern commoditizes, the
defensible value moves up the stack — from "an agent can run Comfy" (now table
stakes) to "an agent that translates artist intent, remembers what worked for
you, judges its own output, and never breaks your scene."** Cozy is built to
own that upper layer.

---

## 2. Market context (last-30-days research, treated as evidence)

The field is bifurcating, and Cozy sits in the gap between the two poles.

**Pole A — "generate the whole workflow."** The Codex-drives-ComfyUI pattern is
real and spreading fast (multiple high-engagement X threads in May 2026:
"5 steps, runs Flux/SDXL on 8GB, never touch a node"). This *validates* the
agent-driver thesis but also commoditizes the basic loop. "Point an agent at
Comfy" is now a tweet, not a moat.

**Pole B — "kill the node graph."** Visible backlash against the canvas itself
(an official ComfyUI "how do we improve nodes?" prompt drew "get rid of nodes,
build a real UI"). Appetite for abstraction is high.

**Platform is absorbing the floor.** ComfyUI-Manager is now natively integrated
(preview-before-install, batch missing-node install, conflict detection), and
**Nodes 2.0 (beta)** is live. Native model support keeps expanding (VOID,
BiRefNet, Gemma 4, Stable Audio 3.0, HiDream-O1). NVIDIA NVFP4 / async-offload
landed for video.

**The #1 friction is still orientation, not capability.** The loudest pain in
the wild is setup/VRAM/PyTorch ("burned hours on LTX-Video VRAM + access
violations"), not "the model can't do it."

**Where this puts Cozy:** *not* "generate for me" (unsafe in production, and
commoditizing), *not* "replace the GUI" (artists want their canvas). The
position is: **a colleague who handles the wiring while you make the calls** —
and increasingly, one who *learns your calls over time*.

---

## 3. Current state — honest inventory

What's genuinely shipped and load-bearing:

- **113 dispatched MCP tools** across a three-layer dispatcher (intelligence /
  brain / stage). (Note: a raw grep of `"name":` returns ~155 because schema
  field names collide with tool names; 113 is the reconciled dispatched count
  per commit `d10a9d6`. The drift between docs has bitten before — keep one
  source of truth.)
- **4,268 test functions across 146 files**, all mocked, sub-60s. (Both
  CLAUDE.md figures — "~3,600" and "4,150+" — are stale. Fix them.)
- **6 LLM providers** (Claude / GPT / Gemini / Ollama / NVIDIA Nemotron / any OpenAI-compatible endpoint via `custom`), swappable by env var or mid-session, selection persisted across restarts.
- **Reversible-by-construction**: every mutation is a LIVRPS delta layer with a
  full undo stack. This is the same safety posture as Synapse (atomic,
  idempotent, undo-grouped) — a through-line across the portfolio, and the
  single most important differentiator vs. hobbyist agent-Comfy.
- **Three delivery surfaces**: MCP (inside Claude Code/Desktop), standalone CLI,
  native ComfyUI sidebar.
- **Validate → repair → execute** as one continuous flow for workflow edits;
  installing missing packs pauses exactly once for a human yes
  (needs_confirmation → confirm=true), then re-validates and runs.

What's recent and signals the real trajectory (from git, last ~10 commits):

- **`agent/embedder.py` — MiniLM semantic embeddings.** Experience recall is
  moving from hash-equality toward semantic similarity. This is the substrate
  becoming real: it's what makes "Session 100 knows your style" more than a
  slogan.
- **`agent/engine/` — execution-engine adapter.** The ComfyUI execution path is
  being abstracted behind an interface. This is infrastructure for becoming
  **execution-agnostic** — the door to remote/secondary GPU execution.
- **MoE self-correction passes** — the agent-team layer is being hardened
  (registration-drift detection, deque undo history, atomic BLOCKER.md).

What is explicitly *not* yet real (don't oversell these):

- **Output judgment is still rule-based** (0.7 success / 0.1 failure). The
  vision-based evaluator (Phase 7 #1) is the gate on the entire learning
  promise. Until it lands, the feedback loop is weak.
- **Autonomous harness** (`cozy_loop.py`) runs, but 24-hour self-optimization is
  closer to a research artifact than artist-facing value today.
- **Moneta adapter** is a file-watch placeholder; real wire format pending an
  API contract.

---

## 4. Architecture posture — why the substrate is strategically load-bearing

Three structural choices matter for direction, not just for code cleanliness:

1. **`cognitive/` imports nothing from `agent.*`.** The cognitive layer (LIVRPS
   delta composition, CognitiveGraphEngine, experience persistence, autonomous
   pipeline) is a clean, standalone library. That boundary is what makes it
   **reusable, portable IP** — and it's patent-pending (USD Cognitive
   Substrate). It is not Comfy-specific by accident; it's Comfy-specific *only
   at the edges*.

2. **Three-layer dispatch with graceful degradation.** Tool modules that fail to
   import are logged and skipped. The brain layer auto-registers via
   `__init_subclass__`. This keeps the surface extensible without a brittle
   central registry — important as the tool count grows.

3. **The new engine adapter** turns "execute on the local ComfyUI" into "execute
   on *an* engine." Strategically this is the unlock for the
   **Mac-drives / Threadripper-renders** pipeline shape that's native to how VFX
   actually works.

The honest framing of the substrate: it is **deep, protected IP that the artist
never sees directly**. That's a strength (defensibility) and a sequencing risk
(investment ahead of visible demand). See Risk #3.

---

## 5. Strategic direction — the bets

**Bet 1 — Move up the stack as the platform absorbs the floor.**
ComfyUI-Manager native install + Nodes 2.0 are eating the discovery/install
layer. Don't fight the platform there. Cede what the platform does natively;
double down on what it structurally *won't*: artist-intent translation,
cross-session learning, and output judgment. *Confidence: high. The platform
absorption is observable, not speculative.*

**Bet 2 — Close the learning loop; make "Session 100" real.**
The combination of the **vision evaluator** (replacing rule-based scoring) and
**semantic recall** (the MiniLM embedder, already landing) *is* the moat. Hash
matching can't learn taste; semantic similarity + real output judgment can.
This is the critical path for the core product promise. *Confidence: high on
direction, medium on effort — vision scoring is genuinely hard to get
trustworthy.*

**Bet 3 — Production trust as the brand.**
Validated, reversible, atomic, never-rewrites. This is the line that separates
Cozy from "point Codex at Comfy." It's also the same invariant set as Synapse —
lean into the portfolio-wide safety identity. *Confidence: high. It's already
true; the work is making it legible in positioning.*

**Bet 4 — Execution-agnostic, via the engine adapter.**
The adapter opens the remote-GPU story: the Mac Studio orchestrates; the
Threadripper/4090 renders. That's a real VFX-pipeline shape, not a feature
checkbox. *Confidence: medium. Right direction; validate demand before building
the full remote transport.*

---

## 6. Risks a skeptical reviewer would raise

1. **Platform absorption.** Where Cozy duplicates native ComfyUI-Manager
   (install, conflict detection), that value erodes with each ComfyUI release.
   *Mitigation:* treat install/discovery as commodity plumbing; don't invest
   further there; move value to learning + judgment (Bets 1, 2).

2. **Agent commoditization.** The basic agent-drives-Comfy loop is now trivially
   replicable. *Mitigation:* defensibility lives in the substrate (patented) and
   production trust, **not** in the agent loop itself. Stop marketing the loop;
   market the memory and the safety.

3. **Substrate complexity vs. audience.** The cognitive / USD / LIVRPS / brain-
   SDK / stage stack is sophisticated and the artist sees none of it. Open
   question: is it earning its complexity in *shipped artist value* yet, or is
   it research investment ahead of demand? *Mitigation:* this is a **sequencing**
   call, not a teardown — the IP is strategically load-bearing. But each
   substrate increment should be tied to a visible artist outcome (e.g., recall
   → better recommendations) before the next is built.

4. **Surface area vs. maintenance.** 113 tools, 4,268 tests, autonomous harness,
   Moneta adapter, USD stage layer — large for a small team. *Mitigation:* be
   willing to mark subsystems "stable / parked" and resist net-new surface until
   the learning loop closes.

5. **The core promise is gated on one unbuilt thing.** "Learns what works for
   you" is only as good as the evaluator, which is still rule-based. *Mitigation:*
   the vision evaluator is the single highest-leverage piece of work in the
   repo. Sequence it first.

---

## 7. Concrete next moves (prioritized — critical path first)

1. **Land the vision-based evaluator** (Phase 7 #1). Replace the rule-based
   0.7/0.1 with `analyze_image` scoring. This unblocks the entire learning loop
   and the central product claim. *Highest leverage in the repo.*
2. **Wire semantic recall into the artist surface.** Connect `embedder.py` into
   `get_recommendations` / `get_learned_patterns` so the substrate produces
   *visible* better suggestions, not just better internal matching.
3. **Audit Cozy ↔ native-Manager overlap.** Explicitly decide what to cede to
   the platform vs. keep. Document it.
4. **Auto-retry loop** (Phase 7 #2): re-COMPOSE when `quality.overall <
   threshold`. Depends on (1).
5. **Validate the remote-execution story** before building it — does the engine
   adapter get used for Threadripper offload, or is it premature? One real
   end-to-end test before committing transport work.
6. **Reconcile the docs.** Fix test count (4,268), keep tool count single-sourced
   at 113. Small, but the drift has caused churn already.

---

## 8. Open decisions to resolve in the Desktop session

- **Sequencing:** vision evaluator first (recommended) vs. semantic-recall
  surfacing first? They compound, but the evaluator unblocks more.
- **Substrate cadence:** what's the rule for when a new cognitive-layer
  increment is allowed? Proposal: each one ships only when tied to a visible
  artist-facing outcome.
- **Remote execution:** is the Mac-drives/Threadripper-renders pipeline a near-
  term build or a parked direction? Demand-validate first.
- **Positioning rollout:** where does the new blurb (§9) go — README hero, repo
  description, Sponsors page? Pick the surfaces.

---

## 9. Positioning (canonical blurb — drop-in ready)

**Cozy-Comfy** — *The colleague who drives ComfyUI, so you don't have to wire
it.*

Cozy is an AI co-pilot for VFX artists — lighting TDs, compositors, texture
painters — who live in ComfyUI but never signed up to be node engineers. It
doesn't take a prompt and hand back a black-box graph. It reads the workflow you
already have, makes small, validated changes, and tells you what it did and why.
Every edit is checked before it lands and reversible the second you change your
mind.

Say "dreamier" — it lowers CFG and reaches for the right sampler. Say "this is
slow" — it finds the bottleneck. When a node's missing, it shows you the pack,
waits for your yes, then installs, re-validates, and runs. It speaks your
language, not the terminal's.

While the rest of the field races to make the node graph *disappear*, Cozy makes
a different bet: you don't want your canvas taken away. You want a colleague who
handles the wiring while you make the calls.

---

*End of scaffold. This is a living document — update the snapshot date when the
direction shifts.*
