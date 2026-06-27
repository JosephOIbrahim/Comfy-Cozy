# PR: Zero-LLM Recipe layer (B1) — SYNAPSE `routing/recipes` port

**Branch:** `forge/recipe-system-epoch1` (commit pending Joe's word — the harness never pushes)
**Epoch:** cozy-improve epoch 1 · **LEDGER:** `C-RECIPE-SYSTEM` · **Champion track:** `recipe-system`

## What & why

Comfy-Cozy had no deterministic pre-LLM macro layer. The CLAUDE.md "Artistic Intent
Translation" table (8 rows) and `agent/knowledge/common_recipes.md` (~6 graphs) were
de-facto recipe specs the LLM re-derived every turn. This ports the one high-fit element
of SYNAPSE's tiered router — the **Recipe system** (`routing/recipes/base.py`) — as the
missing *deterministic producer* of those specs. Common artist intents ("make it dreamier",
"upscale 2x") become pinned, reviewable, zero-LLM macros.

ComfyUI work is parametric node-graph templating — the most recipe-shaped domain available.
The full SYNAPSE 6-tier cascade was **rejected** as over-engineering here (the agent loop is
already the deep tier; MCP externalizes the model to the host); only the Recipe element fits.

## Design (surgical, simplest-thing-that-works)

- **New module `agent/recipes/`** — `base.py` (engine: `Recipe`, `ParamMutation`, `ToolStep`,
  `$var.field` dataflow, `@find:<class>` node resolution, `RecipeExecutor`, `RecipeRegistry`),
  `builtin.py` (7 recipes from the in-repo specs), `__init__.py` (production binding).
- **Safety inherited, not rebuilt:** every step dispatches through `agent.tools.handle()`, so
  the existing `pre_dispatch_check` gate vets each operation. No second gate path, no bypass.
  Every change is reversible (`undo_workflow_patch`). The frozen `agent/stage/**` and
  `moe_dispatcher` are untouched — recipes sit beside the dispatcher, not inside it.
- **MCP tools** `apply_recipe` / `list_recipes` (`agent/tools/recipes_tool.py`), registered in
  `agent/tools/__init__.py`, classified **READ_ONLY** in `agent/gate/risk_levels.py` (the entry
  is a dispatcher; the inner `set_input`/`add_node`/`connect_nodes` re-enter `handle()` and
  carry/gate the real risk).
- **CLI pre-check** in `agent/main.py:run_interactive`, behind `config.RECIPES_ENABLED`
  (**default OFF** — purely additive, zero behaviour change unless enabled). Recipes never
  hard-fail a turn: a miss / non-apply falls through to the LLM.

## Files changed

| File | Change |
|------|--------|
| `agent/recipes/base.py` | new — recipe engine |
| `agent/recipes/builtin.py` | new — 7-recipe library |
| `agent/recipes/__init__.py` | new — production dispatch binding |
| `agent/tools/recipes_tool.py` | new — `apply_recipe` / `list_recipes` |
| `agent/tools/__init__.py` | register `recipes_tool` |
| `agent/gate/risk_levels.py` | classify both tools READ_ONLY |
| `agent/main.py` | CLI recipe pre-check (RECIPES_ENABLED) |
| `agent/config.py` | `RECIPES_ENABLED` flag (default off) |
| `tests/test_recipes.py` | new — 16 tests |
| `tests/test_tools_registry.py`, `tests/test_mcp_server.py` | tool count 131→133 |
| `CLAUDE.md` | tool count + Recipes table row |

## Gate evidence (the ratchet — ALL must hold)

- **testsGreen** ✓ — 16 new tests pass; full `pytest -m "not integration"` = **4568 passed /
  0 failed / 2 skipped** (the one known Windows SIGKILL baseline test did not fire this run).
- **lintClean** ✓ — `ruff check` clean on all touched files.
- **benchOk** ✓ — feature port, `bench=null` → neutral by construction; no champion regressed.
- **noRegress** ✓ — deterministic; changes confined to the declared blast radius; no frozen-zone touch.
- **notRefuted** ✓ — adversarial review found no weakened test / scope creep / determinism break.

## Try it

```bash
# MCP host (primary): the tools are live now.
list_recipes
apply_recipe {"text": "make it dreamier"}     # on a loaded workflow with a KSampler

# CLI (opt-in):
RECIPES_ENABLED=1 agent run
> upscale it 2x
```

**Merge is reserved for Joe.** This harness commits to `forge/<id>` branches and surfaces this
PR body; it does not push.
