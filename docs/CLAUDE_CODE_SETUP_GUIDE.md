# Claude Code Setup — Comfy-Cozy

## For: Joe Ibrahim
## Purpose: Get Claude Code wired up to consume `CLAUDE_CODE_INSTALL_PACK.md`
## Date: April 7, 2026
## Project root: `G:\Comfy-Cozy\`
## Panel subdirectory: `G:\Comfy-Cozy\panel\`

---

# 0. (SKIP IF ALREADY INSTALLED) — Quick Install Verify

You already run Claude Code per your stack notes. Sanity-check it's current.

**Open PowerShell** (not as admin) and run:

```powershell
claude --version
claude doctor
```

**You should see:**

- A version number from `claude --version`
- `claude doctor` reports green on installation type, auth status, Git health, and PATH

**If `claude` is not recognized:** Your PATH lost `%USERPROFILE%\.local\bin`. Fix:

```powershell
[Environment]::SetEnvironmentVariable("PATH", "$env:PATH;$env:USERPROFILE\.local\bin", [EnvironmentVariableTarget]::User)
```

Close and reopen the terminal. Try `claude --version` again.

**If you've never installed it on this machine:** Native installer is the recommended path now (no Node.js, no WSL needed). Run from PowerShell:

```powershell
irm https://claude.ai/install.ps1 | iex
```

Then `claude doctor` to verify.

**Current docs:** https://docs.claude.com/en/docs/claude-code/setup

---

# 1. The Project Layout

Comfy-Cozy is now a **single unified repo** at `G:\Comfy-Cozy\`. Everything lives under one root:

```
G:\Comfy-Cozy\
├── CLAUDE.md                          ← repo-level project context
├── .claude\
│   └── settings.json                  ← project-local Claude Code settings
├── comfy_agent\                       ← Python backend (the Scaffolded Brain)
│   ├── core\                          ← typed graph engine, DeltaLayer
│   ├── intelligence\                  ← UNDERSTAND, DISCOVER, PILOT, VERIFY
│   ├── brain\                         ← Vision, Planner, Memory, Orchestrator
│   ├── api\                           ← server.py with HTTP endpoints
│   └── utils\                         ← hardware_profiler, model registry
├── panel\                             ← ComfyUI custom node (vanilla JS)
│   ├── __init__.py                    ← ComfyUI extension registration
│   └── web\
│       ├── js\
│       └── css\
├── tests\                             ← pytest suite
├── docs\                              ← specs and install pack
│   ├── CLAUDE_CODE_INSTALL_PACK.md
│   ├── PHASE_5_MINIMUM_BUILD_SPEC_V3.md
│   ├── COMFY_COZY_V3_BUILD_SPEC.md
│   └── AGENT_COMMANDMENTS.md
├── data\                              ← SQLite DBs, runtime state (gitignored)
└── .venv312\                          ← Python virtual environment
```

**Why one repo:** The backend and panel are tightly coupled — every Comfy-Cozy v3 feature touches both sides. Splitting them across two repos was friction. One repo, one CLAUDE.md, one Claude Code session.

---

# 2. The Panel ↔ ComfyUI Symlink

**This is the one piece of setup that's not obvious.**

ComfyUI loads custom nodes from `G:\COMFY\ComfyUI\custom_nodes\`. Your panel source lives at `G:\Comfy-Cozy\panel\`. ComfyUI doesn't know about that path — so it won't load the panel unless you bridge the two.

**One-time setup**, run PowerShell as Administrator:

```powershell
New-Item -ItemType SymbolicLink -Path "G:\COMFY\ComfyUI\custom_nodes\Comfy-Cozy-Panel" -Target "G:\Comfy-Cozy\panel"
```

**You should see:** A symlink created at `G:\COMFY\ComfyUI\custom_nodes\Comfy-Cozy-Panel` pointing to `G:\Comfy-Cozy\panel`.

**Verify it worked:**

```powershell
Get-Item "G:\COMFY\ComfyUI\custom_nodes\Comfy-Cozy-Panel" | Select-Object LinkType, Target
```

**You should see:** `LinkType: SymbolicLink`, `Target: G:\Comfy-Cozy\panel`.

**Restart ComfyUI.** It should now load the panel from your dev directory. Every change you (or Claude Code) make to files in `G:\Comfy-Cozy\panel\` is live in ComfyUI without copying anything.

**If symlinks don't work on your setup:** You can fall back to a junction:

```powershell
cmd /c mklink /J "G:\COMFY\ComfyUI\custom_nodes\Comfy-Cozy-Panel" "G:\Comfy-Cozy\panel"
```

Junctions don't need admin and work on the same drive.

---

# 3. The CLAUDE.md (Single File, Repo Root)

Drop this at `G:\Comfy-Cozy\CLAUDE.md`. It carries every project-level constraint Claude Code needs to honor across both backend and panel work.

```markdown
# Comfy-Cozy — Project Context

## What this is
Comfy-Cozy is a cognitive layer for ComfyUI — the Scaffolded Brain
architecture realized as an in-process agent + ComfyUI panel.

The agent backend (Python, comfy_agent package) hosts the typed graph engine,
delta layer system, 61-tool surface, and the Experience Cerebellum.

The panel (vanilla JS, lives in panel/) is the visible surface — Ghost
Workflows, chat interface, Auto-Heal cards, spatial binding to the canvas.

This is one project with two halves. Backend and panel evolve together.

## Architectural locks (NON-NEGOTIABLE)

### Backend locks (apply to comfy_agent/, tests/, anywhere Python lives)
- The typed `CognitiveGraphEngine` and `DeltaLayer` system are the substrate.
  Do not propose alternatives. Wrap, don't replace.
- LIVRPS composition with Safety as STRONGEST opinion (inverted from USD).
  This is patent-relevant. Do not "fix" the inversion.
- The 61-tool surface (Intelligence + Brain layers) is the motor system.
  New work wraps existing tools, never replaces them.
- Python package name remains `comfy_agent`. All imports use that name.

### Panel locks (apply ONLY to files under panel/)
- VANILLA JAVASCRIPT ONLY. No React, Vue, Svelte. No build steps.
- ZERO external runtime dependencies. No Dagre, ELK, D3, Lodash.
  Hand-roll it or vendor a minimal implementation under 200 lines.
- Pentagram design language:
  - Background #0D0D0D
  - Single accent #0066FF
  - Inter typography
  - 1px solid borders
  - Max 4px corner radius
  - NO gradients, NO drop shadows
  - Animations: opacity and transform only, 200ms ease-out, no bouncy easing

If you reach for `npm install` while editing files in panel/, STOP.
You are violating a hard constraint.

The Pentagram lock does NOT apply to the Python backend. The agent
can use any Python dependency the spec authorizes.

## Tech stack
- Python 3.12 in `.venv312`
- Pydantic for schemas, sqlite3 from stdlib for storage
- pytest for testing, run with `pytest -v`
- ComfyUI runs separately at localhost:8188 (started outside Claude Code)
- Backend communicates with ComfyUI over HTTP only
- Panel loaded by ComfyUI via symlink at custom_nodes/Comfy-Cozy-Panel

## Bash/venv on Windows
Claude Code uses Git Bash internally. To activate the venv inside bash:
    source .venv312/Scripts/activate
(NOT the PowerShell `.venv312\Scripts\activate` form)

In shell commands, use forward slashes for paths to avoid bash escaping
issues: `G:/Comfy-Cozy/data/experience.db` not `G:\Comfy-Cozy\data\experience.db`.

## Testing
Always run `pytest` after every file create/modify in the backend.
For panel changes, manual smoke testing in ComfyUI is the gate (no automated
JS test infrastructure exists yet).
Existing passing tests are invariants — never weaken to make new code pass.

## Commit conventions
Conventional commits, prefixed with the phase or mile marker:
"Phase 5 Minimum: <what> (Mile X/Y)"
"Comfy-Cozy v3: <what> (Mile X/Y)"

## What I'm building right now
Phase 5 Minimum (cerebellum receiving side) followed by Comfy-Cozy v3
(Ghost Workflows, Spatial Binding, VRAM Guardrails, Auto-Heal).

Full execution plan: docs/CLAUDE_CODE_INSTALL_PACK.md
Specs: docs/PHASE_5_MINIMUM_BUILD_SPEC_V3.md, docs/COMFY_COZY_V3_BUILD_SPEC.md
Constitution: docs/AGENT_COMMANDMENTS.md
```

**Why a single CLAUDE.md works now:** The Pentagram lock is scoped explicitly to `panel/` files via the wording. When Claude Code is editing Python backend code, the lock doesn't apply. When it's editing JS in `panel/`, it does. One file, two scopes, zero ambiguity.

---

# 4. Drop the Specs Where Claude Code Can Find Them

```powershell
cd G:\Comfy-Cozy
mkdir docs -Force
```

Then move/copy these four files into `G:\Comfy-Cozy\docs\`:

- `CLAUDE_CODE_INSTALL_PACK.md` (the 10-mile execution plan)
- `PHASE_5_MINIMUM_BUILD_SPEC_V3.md` (Gemini's Phase 5 spec)
- `COMFY_COZY_V3_BUILD_SPEC.md` (Gemini's Comfy-Cozy v3 spec)
- `AGENT_COMMANDMENTS.md` (the 8 rules)

**Why `docs/` and not the root:** Keeps the repo root clean. The CLAUDE.md at the root is auto-loaded; everything in `docs/` is referenced explicitly by mile prompts.

---

# 5. Project-Local Settings

Create `G:\Comfy-Cozy\.claude\settings.json`:

```json
{
  "env": {
    "PYTHONDONTWRITEBYTECODE": "1",
    "COMFY_AGENT_EXPERIENCE_DB_PATH": "G:/Comfy-Cozy/data/experience.db",
    "COMFY_AGENT_PROPOSAL_TTL_SECONDS": "1800"
  }
}
```

**Why these three:**

- `PYTHONDONTWRITEBYTECODE` — keeps `.pyc` files out of your tree
- `COMFY_AGENT_EXPERIENCE_DB_PATH` — matches the spec default location, lets tests override
- `COMFY_AGENT_PROPOSAL_TTL_SECONDS` — set short (e.g. `2`) for testing the garbage collector, restore to `1800` for normal runs

### Auto-approval

If you want Claude Code to run `pytest` and `git commit` without asking every time, configure auto-approval in the same settings.json. Be conservative — start with read-only and test commands, add commit later when you trust the flow.

**Don't auto-approve `git push`.** Ever. Push is the irreversible step where you actually want a human gate.

---

# 6. Launching Your First Session

```powershell
cd G:\Comfy-Cozy
claude
```

You should see Claude Code start, read `CLAUDE.md`, and present a prompt.

**Sanity-check it loaded the project context:**

```
What project am I in, what are the locked architectural constraints, and what's
the difference between backend and panel locks?
```

**You should see:** Claude Code summarizes Comfy-Cozy, names the typed graph engine, mentions LIVRPS-with-Safety-inverted, references the 61-tool surface, AND distinguishes that Pentagram only applies to files under `panel/`.

**If the panel/backend distinction is missing:** CLAUDE.md isn't loaded properly. Run `/doctor` or check that you launched from `G:\Comfy-Cozy\` (not a parent directory).

---

# 7. Feeding the Install Pack Prompts

This is the core workflow. Once Claude Code is running with the right context, you execute the install pack one mile at a time.

### Step-by-step

**Step A — Tell Claude Code where the install pack lives.**

```
Read docs/CLAUDE_CODE_INSTALL_PACK.md and confirm you understand the structure.
Do NOT start executing yet — just confirm you've read it.
```

**You should see:** Claude Code summarizes the 10 miles, the two tracks, and the 8 Commandments.

**Step B — Run the pre-flight checklist by hand.**

This is the §2 checklist in the install pack. Don't delegate it to Claude Code. Do it yourself in PowerShell:

```powershell
.venv312\Scripts\activate
pytest tests/core/ -v
```

Walk through all 7 pre-flight items. They take 30 minutes. They prevent hours of pain later.

**Step C — Execute Mile 1 by pasting its prompt.**

Find Mile 1 in the install pack. Copy the **entire copy-paste prompt block** (the one inside the code fence starting with `ROLE: [EXPERIENCE × FORGE]`).

Paste it into Claude Code as a single message.

Claude Code will:
1. Read the spec
2. Scout the existing codebase for Pydantic conventions
3. Create the file
4. Run the smoke test
5. Commit
6. Stop

**Step D — Verify, then proceed to Mile 2.**

Read what Claude Code did. Run the test yourself if you want extra confidence. If green, paste the Mile 2 prompt. Repeat.

### Critical rule

**One mile at a time.** Do not paste Mile 1 and Mile 2 prompts together. The install pack is structured around stop points for a reason — they're the human gates from Commandment 8.

---

# 8. The Single-Session Workflow

The unified repo means **one Claude Code session handles everything**:

- Phase 5 Minimum (Track A)
- Comfy-Cozy v3 backend pieces (Track B backend halves)
- Comfy-Cozy v3 panel pieces (Track B panel halves)
- Auto-Heal convergence (Mile 10)

**No more terminal juggling.** Launch once from `G:\Comfy-Cozy\`, work the install pack mile by mile, commit at every gate.

### When to restart the session

- After every critical human gate (Mile 4, Mile 6, Mile 9, Mile 10) — fresh context for the next phase
- If Claude Code drifts (forgets locks, suggests `npm install` for panel work, ignores the spec)
- If you step away for more than a few hours — context gets stale

`/clear` is faster than a full restart but doesn't reload CLAUDE.md. For drift fixes, full restart is safer.

---

# 9. Common Windows Gotchas

### `.venv312` activation in Claude Code's bash

Claude Code uses Git Bash internally on Windows. When it runs commands, the venv activation path is different from PowerShell:

- PowerShell: `.venv312\Scripts\activate`
- Git Bash (what Claude Code sees): `source .venv312/Scripts/activate`

The CLAUDE.md template above already includes this hint. Claude Code should pick it up and stop fighting your venv.

### Path separators in spec files

The specs use Windows paths like `G:\Comfy-Cozy\data\experience.db`. Python on Windows handles both `\` and `/`, but bash gets confused by backslashes in shell commands. When Claude Code is running shell commands, it should use forward slashes: `G:/Comfy-Cozy/data/experience.db`.

The CLAUDE.md template covers this too. If you see weird path errors, that's where to check.

### Image paste

If you need to share screenshots with Claude Code (e.g. showing a broken Ghost Workflow render), use **Alt+V**, not Ctrl+V. Ctrl+V only pastes text on Windows. Or drag-and-drop the image file.

### Long-running ComfyUI processes

Don't have Claude Code start ComfyUI for you — start it yourself in a separate terminal. ComfyUI is long-running and you don't want it tied to the Claude Code session lifetime. The agent talks to ComfyUI over HTTP at localhost:8188 regardless of who started it.

### Symlink vs junction

If the symlink command in §2 fails with a permissions error and you don't want to elevate, use the `mklink /J` junction fallback. Both work for this use case. Junctions are slightly less flexible (same drive only) but Comfy-Cozy and ComfyUI are both on G: so it doesn't matter.

---

# 10. The Restart Protocol

If Claude Code drifts (forgets context, starts violating Pentagram constraints in `panel/` files, ignores the spec), the fix is almost always: **restart the session and re-orient.**

```
1. Type /clear in Claude Code to clear the conversation
2. Type "Read CLAUDE.md and the current mile marker spec, then wait for instructions"
3. Re-paste the mile marker prompt
```

If `/clear` isn't enough, exit Claude Code entirely and relaunch. Each new session reads CLAUDE.md fresh.

**Drift signs to watch for:**

- Claude Code suggests `npm install` for a panel task → constraint violation, restart
- Claude Code modifies an existing test to make a new one pass → Commandment 7 violation, restart and revert the test
- Claude Code skips the test gate "to save time" → Commandment 2 violation, restart and re-run with the test gate explicit
- Claude Code starts editing files outside its declared role → Commandment 5 violation, restart with role isolation reminder
- Claude Code adds a Python dependency for backend work without flagging it → not a hard rule violation but worth pausing to confirm

---

# 11. The First Successful Mile Marker

Your first concrete success in this whole pipeline is:

**Mile 1 of Track A — `comfy_agent/brain/memory/experience.py` schemas, ~30 minutes, two Pydantic models, smoke test green, git commit landed.**

That's the "engine turned over" moment. Once Mile 1 lands cleanly, you know:

- Claude Code is reading CLAUDE.md
- The repo conventions are scoutable
- The Pentagram scope distinction is being honored
- The verification gate works
- Commits are landing
- The 8 Commandments are being honored

Everything after Mile 1 is the same pattern at higher complexity. The hardest part is the first paste.

---

# 12. Quick Reference Card

Pin this somewhere visible while you run the pack.

```
PROJECT ROOT:     G:\Comfy-Cozy\
LAUNCH:           cd G:\Comfy-Cozy && claude
INSTALL PACK:     docs/CLAUDE_CODE_INSTALL_PACK.md
SPECS:            docs/PHASE_5_MINIMUM_BUILD_SPEC_V3.md
                  docs/COMFY_COZY_V3_BUILD_SPEC.md
COMMANDMENTS:     docs/AGENT_COMMANDMENTS.md
PANEL SOURCE:     G:\Comfy-Cozy\panel\
PANEL SYMLINK:    G:\COMFY\ComfyUI\custom_nodes\Comfy-Cozy-Panel
PYTHON PACKAGE:   comfy_agent (unchanged)
TEST:             pytest -v
COMFYUI:          localhost:8188 (start in a separate terminal)
COMMIT:           handled by Claude Code per mile prompt
TAG:              done by hand at completion gates (you, not Claude Code)
DRIFT FIX:        /clear, re-orient, re-paste mile prompt
HARD RESET:       git reset --hard <last good tag>
```

---

# 13. One-Line Frame

**The install pack is the map. Claude Code is the engine. CLAUDE.md is the steering wheel. You are the driver.**

The driver picks the route, calls the gates, and pulls over when something looks wrong. The engine does the work. The map says where to go next.

Mile 1 starts when you paste the first prompt. Good luck.

— End of setup guide —
