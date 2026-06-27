# Contributing to Comfy-Cozy

Comfy-Cozy is an AI co-pilot for VFX artists using ComfyUI — a driver, not a
generator. It makes small, validated changes to existing workflows instead of
rewriting them. This guide covers everything you need to set up, test, and
submit a change.

You do not need to be a software engineer to contribute. If you are a lighting
TD, compositor, or texture artist who knows ComfyUI well, you are exactly the
kind of contributor this project is built for. The commands below are copy-paste
ready, and each section explains *what* it does and *why* it matters.

---

## Prerequisites

- **Python 3.10 or newer.** Check with `python --version`. The project targets
  `>=3.10` (see `pyproject.toml`).
- **git.** For cloning the repository and submitting changes.
- A working **ComfyUI** install is *optional* for development. The test suite is
  fully mocked, so you can develop and run every test without ComfyUI or an API
  key. You only need a live ComfyUI when you want to exercise the agent against
  real workflows.

---

## Setup

Clone the repository and install it in editable mode with the development extras:

```bash
pip install -e ".[dev]"
```

What this does:

- **`-e` (editable)** links the installed package back to your working copy, so
  your edits take effect immediately without reinstalling.
- **`.[dev]`** pulls in the development dependencies (test runner, linter, and
  friends) on top of the runtime requirements.

After install, two entry points are available:

```bash
agent run          # CLI agent — standalone fallback for trying things by hand
agent mcp          # MCP server — the primary interface (Claude Code / Desktop)
```

If you plan to drive the agent from Claude Code or Claude Desktop, register the
MCP server in your client config:

```json
{
  "mcpServers": {
    "comfyui-agent": {
      "command": "agent",
      "args": ["mcp"],
      "cwd": "G:/Comfy-Cozy"
    }
  }
}
```

---

## Running the tests

The whole suite is **mocked** — there is no ComfyUI server, no network, and no
API key involved. That means tests are fast, deterministic, and safe to run on
any machine.

```bash
python -m pytest tests/ -v                  # Everything (~4540 tests, ~3 min)
python -m pytest tests/ -m "not integration" -v   # Skip the opt-in integration tests
python -m pytest tests/ --cov=agent         # With a coverage report
```

Narrow the scope while you iterate on one area:

```bash
python -m pytest tests/test_workflow_patch.py -v                              # One file
python -m pytest tests/test_workflow_patch.py::TestApplyPatch -v              # One class
python -m pytest tests/test_workflow_patch.py::TestApplyPatch::test_load_and_patch -v  # One test
```

**Always run the suite before you submit a change.** A change that drops the
passing count below the current baseline is treated as a regression and should
not be shipped.

### How the tests are built

Understanding the test conventions makes it much easier to add your own:

- **Everything is mocked.** HTTP calls to ComfyUI are patched with
  `unittest.mock.patch`. You never need a running server or a real key.
- **autouse fixtures** in `tests/conftest.py` keep tests isolated from one
  another: `_reset_conn_session` snapshots and restores the per-connection
  workflow state, and `reset_workflow_state` deep-copies and restores the shared
  workflow state between tests. You get this isolation for free — no setup needed.
- **Shared fixtures** you will reach for often:
  - `sample_workflow` — a minimal SD1.5 workflow as an API-format dict.
  - `sample_workflow_file` — the same workflow written to a temp JSON file.
  - `fake_image` — a tiny valid PNG for vision-related tests.
- **The common pattern:** load a workflow, call the tool's `handle()`, parse the
  returned JSON string with `json.loads()`, then assert on the fields. Tools
  always return JSON strings, never Python objects.
- **Integration tests** are marked `@pytest.mark.integration` and are
  *deselected by default*. They are opt-in because they may need a live ComfyUI
  or external services. Run them deliberately with
  `python -m pytest tests/integration/ -v` when you touch persistence, the
  dispatcher, or external adapters.

---

## Code quality

The project uses `ruff` for both linting and formatting, with a 99-character
line length (configured in `pyproject.toml`).

```bash
ruff check agent/ tests/      # Lint — report style and correctness issues
ruff format agent/ tests/     # Format — auto-apply the canonical style
```

Run both before you commit. A few conventions the codebase holds to:

- **99-character lines.** Match the existing wrapping.
- **Type hints everywhere.** Annotate function signatures.
- **Deterministic JSON.** Serialize with `sort_keys=True` (use the shared
  `to_json()` helper in `agent/tools/_util.py`) so output is reproducible.
- **Human-readable errors.** Never surface a raw traceback to the user.
  Translate failures into plain language a VFX artist can act on.
- **Surgical changes.** Touch only what the change requires. Do not reformat or
  "improve" adjacent code that your change did not affect.

---

## Where things live

You usually do not need the full map to make a focused change, but here is the
shape of the codebase so you know where to look:

- **`agent/`** — the agent itself: the main loop, CLI, MCP server, config, and
  the three tool layers (`tools/`, `brain/`, `stage/`). Every tool module
  exports `TOOLS: list[dict]` plus a `handle(name, tool_input) -> str` function.
- **`cognitive/`** — a standalone library for workflow composition and
  experience tracking. It deliberately does **not** import from `agent.*`, so
  keep that dependency boundary clean.
- **`tests/`** — the mocked test suite, fixtures, and the opt-in
  `tests/integration/` directory.

For the deeper architecture — the tool dispatch model, session isolation, and
the layer boundaries — read `CLAUDE.md` and `docs/ARCHITECTURE.md`.

---

## Commit conventions

Commits use a category tag in square brackets at the start of the subject line.
This keeps the history scannable and groups related work. The canonical list
lives in `CLAUDE.md` (see the **Commit Messages** section, around lines
300–308):

| Tag            | Use it for                                             |
|----------------|--------------------------------------------------------|
| `[UNDERSTAND]` | New comprehension, analysis, or pattern recognition.   |
| `[PILOT]`      | A targeted fix or behavior change.                     |
| `[DISCOVER]`   | New integrations, sources, or capabilities.            |
| `[VERIFY]`     | Validation, checks, and correctness work.              |
| `[TEST]`       | New or updated tests and fixtures.                     |

Examples, straight from the project history:

```
[UNDERSTAND] Add workflow pattern recognition for ControlNet pipelines
[PILOT] Fix patch validation for multi-output nodes
[DISCOVER] Integrate CivitAI trending models endpoint
[VERIFY] Add perceptual hash comparison for output images
[TEST] Add fixture for SDXL + ControlNet + IP-Adapter workflow
```

Write the subject in the imperative mood ("Add", "Fix", "Integrate") and keep it
to one line. Add a body when the *why* is not obvious from the subject.

---

## Git workflow and authority

This repository runs an agent-managed git workflow with a **three-tier authority
model**. The full rules are in `CLAUDE.md` under **Git Authority Map** (around
lines 251–299). The short version:

1. **Autonomous** — read-only inspection runs freely: `git status`, `git diff`,
   `git log`, `git branch --list`, `git show`, `git grep`.
2. **Authorized per session** — staging and committing specific files
   (`git add <file>` — *never* `git add -A`), `git commit`, and lightweight
   `git tag`. These are fair game once a session grants them.
3. **Requires explicit approval** — anything that touches a remote or rewrites
   history: `git push` (any form), `git reset`, `git rebase`, branch or tag
   deletion, and **any** `--force` flag. These are never done automatically.

A few hard rules worth calling out:

- **Never `git push --force`** (including `--force-with-lease`). History-
  rewriting operations on shared branches are off the table.
- **Push is always a separate, deliberate decision** — never bundled with the
  work that produced it.
- **Stage specific files, not the whole tree.** `git add -A` sweeps in stray
  files; name the files you changed instead.

### Submitting a change (PR flow)

1. Branch from an up-to-date checkout. Keep the branch focused on one change.
2. Make your edit, then run the lint and the test suite:

   ```bash
   ruff check agent/ tests/
   ruff format agent/ tests/
   python -m pytest tests/ -v
   ```

3. Stage only the files you touched and commit with a tagged message:

   ```bash
   git add path/to/changed_file.py
   git commit -m "[PILOT] Fix off-by-one in patch range validation"
   ```

4. Open a pull request. In the description, say what changed, why, and how you
   verified it (which tests you ran and their result). If you could not run
   something, say so plainly.

A good PR is small, validated, and honest about what was and was not tested —
the same principle the agent itself follows with workflows: small, validated
changes over sweeping rewrites.

---

## What we do not do

Keep contributions inside the project's lane:

- We do **not** generate workflows from scratch — we modify existing ones.
- We do **not** replace the ComfyUI GUI — we augment it.
- We do **not** train or fine-tune models — we help artists find and use them.
- We do **not** optimize for developers — every interaction assumes a VFX artist.

Thanks for contributing. Small, careful, well-tested changes are exactly what
keeps this tool trustworthy for the artists who depend on it.
