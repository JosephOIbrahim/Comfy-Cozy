<p align="center">
  <img src="assets/comfy-cozy-logo.jpg" alt="Comfy Cozy" width="600">
</p>

<p align="center">
  <strong>Patent Pending</strong> &nbsp;|&nbsp; <a href="LICENSE">MIT License</a> &nbsp;|&nbsp; <a href="https://github.com/JosephOIbrahim/Harlo/blob/main/PATENTS.md">Patent Details</a>
</p>

# Comfy Cozy

**Talk to ComfyUI like a colleague. It talks back.**

You describe what you want in plain English. The agent loads workflows, swaps models, tweaks parameters, installs missing nodes, runs generations, analyzes outputs, and learns what works for you -- all without you touching JSON or hunting through menus. It doesn't ask permission -- it makes the change, reports what it did, and every change is undoable.

```mermaid
graph LR
    You([You]) -->|"make it dreamier"| Agent[Comfy Cozy]
    Agent -->|loads, patches, runs| ComfyUI[ComfyUI]
    ComfyUI -->|image| Agent
    Agent -->|"Done. Lowered CFG to 5,<br/>switched to DPM++ 2M Karras.<br/>Here's your render."| You

    style You fill:#d99458,color:#1a1a1a
    style Agent fill:#d9c958,color:#1a1a1a
    style ComfyUI fill:#d99458,color:#1a1a1a
```

> **Session 1** is a capable tool.<br/>
> **Session 100** is a capable tool that knows your style.

> **TL;DR**
> - Plain-English co-pilot for ComfyUI. You describe the change; the agent loads workflows, swaps models, patches parameters, runs generations, evaluates output.
> - **113 MCP tools** across **4 LLM providers** — Claude, GPT-4o, Gemini, Ollama. Swap providers with one env var.
> - Every mutation is a **reversible delta layer** (LIVRPS). Full undo stack. Nothing destructive lands without your say-so.
> - **Experience persists.** Session 1 ships with built-in knowledge. After ~30 runs the agent starts biasing toward what's actually worked for you.
> - Ships three ways: **inside Claude Code/Desktop (MCP)**, **standalone CLI**, **native ComfyUI sidebar**. Pick one.

---

## See It In Action

| You say | What happens |
|---------|-------------|
| *"Load my portrait workflow and make it dreamier"* | Loads the file, lowers CFG, switches sampler, saves with full undo |
| *"I want to use Flux"* | Searches CivitAI + HuggingFace, downloads the model, wires it into your workflow |
| *"Repair this workflow"* | Finds missing nodes, installs the packs, fixes connections, migrates deprecated nodes |
| *"Run this with 30 steps"* | Patches the workflow, validates it, queues it to ComfyUI, shows progress |
| *"Analyze this output"* | Uses Vision AI to diagnose issues and suggest parameter changes |
| *"What model should I use for anime?"* | Searches CivitAI + HuggingFace + your local models, recommends the best fit |
| *"Optimize this for speed"* | Profiles GPU usage, checks TensorRT eligibility, applies optimizations |
| *"Repair and run this"* | Finds missing nodes, installs them, validates, executes -- no confirmation needed |

---

## Sponsor This Project

Comfy Cozy is production software. 4,100+ tests (all mocked, runnable in under a minute) cover the 113 MCP tools that drive the workflow lifecycle end-to-end. Four LLM providers — Anthropic, OpenAI, Gemini, Ollama — sit behind a single abstraction with parity across all four. The [CHANGELOG](CHANGELOG.md) tracks active hardening and new work.

If Comfy Cozy saves you time inside ComfyUI, sponsorship is the most direct way to keep it moving.

**Sponsorship funds:**

- Continued development of the MCP agent layer
- Priority response on sponsor-filed issues
- New intelligence-layer tools — vision evaluators, provisioning, planning

A separate Pro tier with additional offerings is planned. Details when it's ready, not before.

[**Become a sponsor →**](https://github.com/sponsors/JosephOIbrahim) &nbsp;·&nbsp; [Acknowledgments](SPONSORS.md)

---

## Get Running

```mermaid
flowchart LR
    A["Clone"] -->|30 sec| B["Install"]
    B -->|10 sec| C["Paste key"]
    C -->|done| D(["agent run"])

    style A fill:#d9c958,color:#1a1a1a
    style B fill:#d9c958,color:#1a1a1a
    style C fill:#d9c958,color:#1a1a1a
    style D fill:#d99458,color:#1a1a1a
```

**Three prerequisites, four copy-paste steps. Under 2 minutes start to finish.**

| | What you need | Where to get it | Time |
|---|------|-----------------|------|
| 1 | **Python 3.11+** | [python.org/downloads](https://python.org/downloads) | already have it? skip |
| 2 | **ComfyUI running** | [github.com/comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI) | already have it? skip |
| 3 | **One LLM backend** | API key (Anthropic / OpenAI / Google) OR [Ollama](https://ollama.com) (free, local, no key) | 1 min to grab a key |

**Already have all three? Copy-paste these four blocks. That's it.**

### 1. Clone

```bash
git clone https://github.com/JosephOIbrahim/Comfy-Cozy.git
cd Comfy-Cozy
```

### 2. Install

```bash
pip install -e .
```

One command. No build step. No Docker. No conda. Just pip.

<details>
<summary>Want the test suite too? (optional, click to expand)</summary>

```bash
pip install -e ".[dev]"           # + 4,100+ passing tests
pip install -e ".[dev,stage]"     # + USD stage subsystem (~200MB, most users skip)
```

</details>

### 3. API key

```bash
cp .env.example .env
```

Open `.env` in any text editor, paste your key on the first line:

```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

<details>
<summary>Using OpenAI, Gemini, or Ollama instead? (click to expand)</summary>

Pick one block, paste into `.env`:

```bash
# --- OpenAI ---
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
# first time only: pip install openai

# --- Gemini ---
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
# first time only: pip install google-genai

# --- Ollama (fully local, free, no key) ---
LLM_PROVIDER=ollama
AGENT_MODEL=llama3.1
# first time only: ollama pull llama3.1
```

</details>

<details>
<summary>ComfyUI installed somewhere non-default? (click to expand)</summary>

Add one more line to `.env`:

```
COMFYUI_DATABASE=C:/path/to/your/ComfyUI
```

</details>

### Step 4 of 4 -- Go

```bash
agent run
```

Type what you want. Type `quit` when you're done.

---

## Connect the Sidebar to ComfyUI

The agent also lives **inside ComfyUI** as a native sidebar panel. To enable it, create two symlinks from ComfyUI's `custom_nodes/` folder to Comfy-Cozy:

**Windows (run as Administrator):**

```cmd
cd C:\path\to\ComfyUI\custom_nodes
mklink /D comfy-cozy-panel C:\path\to\Comfy-Cozy\panel
mklink /D comfy-cozy-ui C:\path\to\Comfy-Cozy\ui
```

**Linux / macOS:**

```bash
cd /path/to/ComfyUI/custom_nodes
ln -s /path/to/Comfy-Cozy/panel comfy-cozy-panel
ln -s /path/to/Comfy-Cozy/ui comfy-cozy-ui
```

Restart ComfyUI. The Comfy Cozy chat panel appears in the **left sidebar**.

```mermaid
graph LR
    CN["ComfyUI/custom_nodes/"] --> P["comfy-cozy-panel/ (symlink)"]
    CN --> U["comfy-cozy-ui/ (symlink)"]
    P -->|"canvas sync (headless)"| Panel["panel/__init__.py"]
    U -->|"sidebar + chat"| UI["ui/__init__.py"]

    style CN fill:#d99458,color:#1a1a1a
    style P fill:#d9c958,color:#1a1a1a
    style U fill:#d99458,color:#1a1a1a
```

**Both symlinks are required:**
- **`comfy-cozy-panel`** -- Canvas sync bridge (runs headlessly -- keeps the agent in sync with your live graph)
- **`comfy-cozy-ui`** -- The visible sidebar: chat window, quick actions, status

---

## Pick Your LLM

Comfy Cozy is **provider-agnostic**. Same 113 tools, same streaming, same vision analysis -- swap one env var.

### Anthropic (default)

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional overrides (defaults shown):
#   AGENT_MODEL=claude-opus-4-7                  -- main loop
#   FAST_MODEL=claude-haiku-4-5-20251001         -- low-stakes triage
#   VISION_MODEL=claude-opus-4-7                 -- analyze/compare images
#   THINKING_BUDGET=4000                         -- agent reasoning budget (tokens)
#   VISION_THINKING_BUDGET=2000                  -- vision reasoning budget

# Run
agent run
```

Ships as the default with **Opus 4.7 + extended thinking + three-tier prompt caching**.
The agent runs on Opus 4.7 with a 4K reasoning budget; vision analysis (`analyze_image`,
`compare_outputs`, `suggest_improvements`) runs the same model with its own budget. Set
`FAST_MODEL` if you want to route triage / classification tools to Haiku 4.5.

### OpenAI

```bash
# Install the SDK (one time)
pip install openai

# .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
AGENT_MODEL=gpt-4o           # or gpt-4o-mini for faster/cheaper

# Run
agent run
```

Full tool-use support with streaming. Works with any OpenAI-compatible endpoint.

### Google Gemini

```bash
# Install the SDK (one time)
pip install google-genai

# .env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
AGENT_MODEL=gemini-2.5-flash  # or gemini-2.5-pro

# Run
agent run
```

Function declarations mapped automatically. Supports Gemini's thinking mode.

### Ollama (fully local, no API key)

```bash
# Install Ollama: https://ollama.com
# Pull a model
ollama pull llama3.1

# .env
LLM_PROVIDER=ollama
AGENT_MODEL=llama3.1          # or any model you've pulled

# Run (no API key needed)
agent run
```

Uses Ollama's OpenAI-compatible endpoint at `localhost:11434`. Override with `OLLAMA_BASE_URL` if running remotely. **No data leaves your machine.**

### Architecture

All four providers share the same abstraction layer (`agent/llm/`):

```mermaid
graph LR
    Agent[Agent Loop<br/>113 tools] --> LLM{LLM_PROVIDER}
    LLM -->|anthropic| A["Claude<br/>Streaming + Cache"]
    LLM -->|openai| B["GPT-4o<br/>Tool Calls"]
    LLM -->|gemini| C["Gemini<br/>Function Decl."]
    LLM -->|ollama| D["Ollama<br/>Local + Private"]

    style Agent fill:#d9c958,color:#1a1a1a
    style A fill:#d9c958,color:#1a1a1a
    style B fill:#d99458,color:#1a1a1a
    style C fill:#d9c958,color:#1a1a1a
    style D fill:#d99458,color:#1a1a1a
```

Common types (`TextBlock`, `ToolUseBlock`, `LLMResponse`), unified error hierarchy, provider-specific format conversion handled internally. Switch providers with one env var -- no code changes. All 4 providers have dedicated test suites (132 tests) plus a parameterized conformance suite that verifies protocol compliance across providers. Every `stream()` and `create()` call is instrumented with `llm_call_total` and `llm_call_duration_seconds` metrics (per-provider labels).

### Reasoning + caching (Opus 4.7)

The Anthropic path uses two Opus-4.7-specific features the other providers ignore:

1. **Extended thinking.** Every agent turn ships `thinking={"type": "enabled",
   "budget_tokens": THINKING_BUDGET}`. The streamed `ThinkingBlock`s include a
   cryptographic `signature`; we capture it and replay it on the next turn so
   tool-use loops stay valid (without the signature, Anthropic 400s the next
   request).
2. **Three-tier system prompt.** `system_prompt.build_system_prompt_blocks()`
   returns a list of cache blocks instead of one big string. Two blocks are
   marked `cache_control: ephemeral`; the third (volatile session context) is
   deliberately not cached. Combined with the last-tool cache pin, three of
   Anthropic's four cache breakpoints stay hot across a session.

```mermaid
flowchart TB
    classDef stable   fill:#d99458,stroke:#1a1a1a,color:#1a1a1a,stroke-width:1.2px
    classDef volatile fill:#d9c958,stroke:#d99458,color:#1a1a1a,stroke-width:1.2px

    subgraph SYS[" system prompt blocks "]
        b1["<b>Block 1 · stable prefix</b><br/>identity · paths · RULES<br/>+ comfyui_core.md<br/><i>cache_control: ephemeral</i>"]
        b2["<b>Block 2 · topical knowledge</b><br/>3d / flux / controlnet / video / ...<br/><i>cache_control: ephemeral</i>"]
        b3["<b>Block 3 · session tail</b><br/>notes · recommendations<br/>last-output context<br/><i>uncached</i>"]
    end

    subgraph TOOLS[" tools[] "]
        t1[tool 1]
        t2[tool 2]
        tN[... 100+ tools]
        tL["<b>last tool</b><br/><i>cache_control: ephemeral</i>"]
    end

    subgraph LOOP[" agent turn loop "]
        m1[messages · user input]
        think["<b>ThinkingBlock</b><br/>thinking text<br/>+ signature ✓"]
        tu[ToolUseBlock]
        tr[ToolResultBlock]
        api[(claude-opus-4-7<br/>thinking enabled)]
    end

    b1 --> api
    b2 --> api
    b3 --> api
    t1 --> api
    t2 --> api
    tN --> api
    tL --> api
    m1 --> api
    api --> think --> tu --> tr --> m1

    class b1,b2,tL stable
    class b3,t1,t2,tN,m1,think,tu,tr,api volatile
```

**Tone key.** Blue = blocks pinned in the prompt cache (the stable prefix, the
topical knowledge, and the last-tool breakpoint). Amber = the per-turn volatile
tail: session context, the message log, and the streaming agent loop itself.
Signature-bearing `ThinkingBlock`s are replayed verbatim on each turn so the
API accepts the next request.

---

## Three Ways to Use It

### A. Inside Claude Code / Claude Desktop (recommended)

The agent runs as an MCP server -- Claude can use all 113 tools directly.

Add this to your Claude Code or Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "comfyui-agent": {
      "command": "agent",
      "args": ["mcp"]
    }
  }
}
```

Now talk to Claude about your ComfyUI workflows. It has full access.

### B. Standalone CLI

```bash
agent run                        # Start a conversation
agent run --session my-project   # Auto-saves so you can pick up later
agent run --verbose              # See what's happening under the hood
```

### C. One-click launcher (ComfyUI + agent together)

If you use the **ComfyUI CLI launcher** (`ComfyUI CLI.lnk`), Comfy Cozy is the default mode:

```
[ 1 ]  STABLE          Balanced. Works with everything.
[ 2 ]  DETERMINISTIC   Same prompt = same pixels.
[ 3 ]  FAST            Sage attention + async offload.
[ 4 ]  COMFY COZY  *   Talk to your workflow. (auto-selects in 10s)
```

Select **4** (or wait 10 seconds) -- ComfyUI starts in a background window, then the agent launches ready to talk.

### Handy CLI Commands (no API key needed)

```bash
agent inspect                    # See your installed models and nodes
agent parse workflow.json        # Analyze a workflow file
agent sessions                   # List your saved sessions
```

---

## What the Agent Knows About Your Models

The agent ships with built-in knowledge about how each model family actually behaves. It won't use SD 1.5 settings on a Flux workflow.

| Model | Resolution | CFG | Notes |
|-------|-----------|-----|-------|
| **SD 1.5** | 512x512 | 7-12 | Huge LoRA ecosystem. Negative prompts matter. |
| **SDXL** | 1024x1024 | 5-9 | Better anatomy. Tag-based prompts work best. |
| **Flux** | 512-1024 | ~1.0 (guidance) | No negative prompts. Needs FluxGuidance node + T5 encoder. |
| **SD3** | 1024x1024 | 5-7 | Triple text encoder (CLIP-G, CLIP-L, T5). |
| **LTX-2** (video) | 768x512 | ~25 | 121 steps. Frame count must be (N*8)+1. |
| **WAN 2.x** (video) | 832x480 | 1-3.5 | Dual-noise architecture. 4-20 steps. |

**The agent will never mix model families** -- no SD 1.5 LoRAs on SDXL checkpoints, no Flux ControlNets on SD3.

### Artist-Speak Translation

| You say | What the agent adjusts |
|---------|----------------------|
| *"dreamier"* or *"softer"* | Lower CFG (5-7), more steps, DPM++ 2M Karras |
| *"sharper"* or *"crisper"* | Higher CFG (8-12), Euler or DPM++ SDE |
| *"more photorealistic"* | CFG 7-10, realistic checkpoint, negative: "cartoon, anime" |
| *"more stylized"* | Lower CFG (4-6), artistic checkpoint or LoRA |
| *"faster"* | Fewer steps (15-20), LCM/Lightning/Turbo, smaller resolution |
| *"higher quality"* | More steps (30-50), hires fix, upscaler |
| *"more variation"* | Higher denoise, different seed, lower CFG |
| *"less variation"* | Lower denoise, same seed, higher CFG |

---

## How It Works

```mermaid
graph TB
    subgraph Browser ["ComfyUI Browser"]
        Sidebar["Comfy Cozy Sidebar<br/>Native left panel -- Chat -- Quick Actions"]
    end
    subgraph Backend ["Agent Backend (Python)"]
        Routes["49 REST Routes<br/>+ WebSocket"]
        Tools["113 Tools<br/>workflow -- models -- vision -- session -- provision"]
        Cog["Cognitive Engine<br/>LIVRPS delta stack -- CWM -- experience"]
    end
    subgraph ComfyUI ["ComfyUI"]
        API["/prompt -- /history -- /ws"]
        Canvas["Live Canvas"]
    end
    subgraph Disk ["Persistence"]
        EXP[("experience.jsonl<br/>cross-session learning")]
        Sessions[("sessions/<br/>workflow state")]
    end

    Sidebar <-->|"WebSocket + REST"| Routes
    Sidebar <-->|"canvas sync"| Canvas
    Routes --> Tools
    Tools --> Cog
    Tools -->|httpx| API
    Cog --> EXP
    Tools --> Sessions

    style Browser fill:#d9c958,color:#1a1a1a,stroke:#d99458
    style Backend fill:#d9c958,color:#1a1a1a,stroke:#d99458
    style ComfyUI fill:#d9c958,color:#1a1a1a,stroke:#d99458
    style Disk fill:#d9c958,color:#1a1a1a,stroke:#d99458
```

```mermaid
graph LR
    You([You]) --> Agent[113 Tools]
    Agent --> Understand[UNDERSTAND<br/>What do you have?]
    Understand --> Discover[DISCOVER<br/>What do you need?]
    Discover --> Pilot[PILOT<br/>Make the changes]
    Pilot --> Verify[VERIFY<br/>Did it work?]
    Verify -->|learn| Agent

    style You fill:#d99458,color:#1a1a1a
    style Understand fill:#d9c958,color:#1a1a1a
    style Discover fill:#d9c958,color:#1a1a1a
    style Pilot fill:#d9c958,color:#1a1a1a
    style Verify fill:#d99458,color:#1a1a1a
```

**Four phases, always in order:**

1. **UNDERSTAND** -- Reads your workflow, scans your models, checks what's installed
2. **DISCOVER** -- Searches CivitAI, HuggingFace, ComfyUI Manager (31k+ nodes)
3. **PILOT** -- Makes changes through safe, reversible delta layers (never edits your original)
4. **VERIFY** -- Runs the workflow, checks the output, records what worked

When validation finds errors, the agent **auto-repairs**. One continuous flow, no stopping to ask:

```mermaid
flowchart TD
    Run(["You: 'run this'"]) --> Validate["validate_before_execute"]
    Validate --> Check{"Errors?"}
    Check -->|No| Execute["execute_workflow"]
    Check -->|"Missing nodes"| Repair["repair_workflow<br/>auto_install=true"]
    Check -->|"Missing inputs"| SetInput["set_input<br/>fill required fields"]
    Check -->|"Wrong model name"| Discover["discover<br/>find correct model"]
    Repair --> Revalidate["re-validate"]
    SetInput --> Revalidate
    Discover --> SetInput
    Revalidate --> Check2{"Still errors?"}
    Check2 -->|No| Execute
    Check2 -->|Yes| Report["Report unfixable<br/>issue + ask"]
    Execute --> Done(["Done — image ready"])

    style Run fill:#d99458,color:#1a1a1a
    style Validate fill:#d9c958,color:#1a1a1a
    style Repair fill:#d9c958,color:#1a1a1a
    style SetInput fill:#d9c958,color:#1a1a1a
    style Discover fill:#d9c958,color:#1a1a1a
    style Execute fill:#d99458,color:#1a1a1a
    style Done fill:#d99458,color:#1a1a1a
    style Report fill:#d99458,color:#1a1a1a
```

Every change is undoable. Every generation teaches the agent something. The agent is a doer, not a describer -- say "wire the model" and it wires the model. Say "repair this" and it finds the missing nodes, installs them, and validates. Say "run it" and it validates, fixes anything broken, then executes. No confirmation dialogs, no "would you like me to..." -- it acts, then tells you what it did.

### Event Triggers

Register callbacks (or webhooks) that fire automatically when ComfyUI events happen. Built into the execution pipeline -- no polling.

```mermaid
flowchart LR
    WS["ComfyUI<br/>WebSocket"] -->|event| Parse["ExecutionEvent<br/>.from_ws_message()"]
    Parse --> Dispatch["TriggerRegistry<br/>.dispatch()"]
    Dispatch --> CB1["on_complete<br/>→ auto-evaluate"]
    Dispatch --> CB2["on_error<br/>→ log to session"]
    Dispatch --> CB3["on_progress<br/>→ custom callback"]
    Dispatch --> WH["Webhook<br/>→ POST JSON to URL"]

    style WS fill:#d99458,color:#1a1a1a
    style Parse fill:#d9c958,color:#1a1a1a
    style Dispatch fill:#d9c958,color:#1a1a1a
    style CB1 fill:#d99458,color:#1a1a1a
    style CB2 fill:#d9c958,color:#1a1a1a
    style CB3 fill:#d99458,color:#1a1a1a
    style WH fill:#d99458,color:#1a1a1a
```

```python
from cognitive.transport.triggers import on_execution_complete, register_webhook

# Python callback
on_execution_complete(lambda event: print(f"Done in {event.elapsed:.1f}s"))

# External webhook (POSTs JSON on every execution_complete + execution_error)
register_webhook("https://your-server.com/hook", ["execution_complete", "execution_error"])
```

---

## Autonomous Mode

Write a creative intent. Hit go. No workflow file needed, no parameters to tune -- the agent composes a workflow, runs it on ComfyUI, scores the result, and learns from it automatically.

```mermaid
flowchart TD
    You(["Creative Intent<br/>'cinematic portrait, golden hour'"]) --> INTENT["INTENT<br/>Parse + validate"]
    INTENT --> COMPOSE["COMPOSE<br/>Load template<br/>Blend with experience"]
    COMPOSE --> PROVISION{"PROVISION CHECK<br/>Models on disk?"}
    PROVISION -->|"missing"| WARN["Warning logged<br/>(continues)"]
    PROVISION -->|"all present"| PREDICT
    WARN --> PREDICT["PREDICT<br/>CWM estimates quality<br/>(SNR-adaptive alpha)"]
    PREDICT --> GATE{"GATE<br/>Arbiter:<br/>proceed?"}
    GATE -->|Yes| CB{"CIRCUIT BREAKER<br/>ComfyUI healthy?"}
    GATE -->|Interrupt| STOP(["Interrupted<br/>+ reason"])
    CB -->|Open| FAIL(["Failed: infra down"])
    CB -->|Closed| EXECUTE["EXECUTE<br/>Post to ComfyUI<br/>Monitor WebSocket"]
    EXECUTE --> EVALUATE["EVALUATE<br/>Vision AI or rule-based<br/>(auto-wired)"]
    EVALUATE --> LEARN["LEARN<br/>Record to accumulator<br/>Recalibrate CWM"]
    LEARN --> DONE(["Complete<br/>Experience recorded"])
    EVALUATE -->|"score < threshold<br/>retries remaining"| CB

    style You fill:#d99458,color:#1a1a1a
    style GATE fill:#d9c958,color:#1a1a1a
    style CB fill:#d99458,color:#1a1a1a
    style EXECUTE fill:#d99458,color:#1a1a1a
    style EVALUATE fill:#d9c958,color:#1a1a1a
    style LEARN fill:#d9c958,color:#1a1a1a
    style DONE fill:#d99458,color:#1a1a1a
    style STOP fill:#d9c958,color:#1a1a1a
    style FAIL fill:#d9c958,color:#1a1a1a
    style PROVISION fill:#d9c958,color:#1a1a1a
```

**Use from Python:**

```python
from cognitive.pipeline import create_default_pipeline, PipelineConfig

pipeline = create_default_pipeline()   # fresh accumulator, CWM, arbiter
result = pipeline.run(PipelineConfig(
    intent="cinematic portrait, golden hour",
    model_family="SD1.5",              # optional -- agent detects from intent
))
print(result.success, result.quality.overall, result.stage.value)
if result.warnings:
    print("warnings:", result.warnings)  # e.g. template family fallback
```

- **No executor required.** The pipeline calls ComfyUI directly via the real `execute_workflow` implementation.
- **Vision evaluator auto-wires.** Set `brain_available=True` and the pipeline auto-imports VisionAgent for multi-axis quality scoring (technical, aesthetic, prompt adherence). Falls back to rule-based scoring when vision is unavailable.
- **Auto-retry on low quality.** If score < threshold, adjusts parameters (steps +10, CFG nudged toward 7), and re-executes. Up to 3 attempts. Circuit breaker prevents retrying against a dead ComfyUI.
- **Provision check.** Before execution, scans for referenced models (`ckpt_name`, `lora_name`, `vae_name`). Missing models generate warnings without halting.
- **Template library.** 8 workflows: txt2img (SD 1.5 / SDXL), img2img, LoRA, multi-pass compositing (depth + normals + beauty), ControlNet depth, LTX-2 video, WAN 2.x video. Hardcoded SD 1.5 fallback if no template matches.
- **Adaptive learning.** CWM alpha blending responds to signal quality -- low variance in experience = more trust, high variance = more prior. Recalibrator adjusts confidence thresholds after every 10 predictions.
- **Experience persists across sessions -- crash-safe.** Every run saved atomically (write-to-tmp then `os.replace()`). After 30+ runs, the agent starts using your personal history to bias parameter selection.
- **Pipeline failures are graceful.** Circuit breaker, CWM exceptions, and template mismatches all produce clean `PipelineStage.FAILED` with `result.warnings`.

```mermaid
graph LR
    subgraph Session1 ["Session 1"]
        I1["Intent"] --> C1["Compose"] --> E1["Execute"] --> S1["Score"]
    end
    subgraph Session2 ["Session 2+"]
        I2["Intent"] --> C2["Compose<br/>(+prior runs)"] --> E2["Execute"] --> S2["Score"]
    end
    S1 -->|"atomic save"| JSONL[("experience.jsonl<br/>crash-safe")]
    JSONL -->|"load on startup"| C2
    S2 -->|"atomic save -- cumulative"| JSONL

    style JSONL fill:#d9c958,color:#1a1a1a
    style C2 fill:#d99458,color:#1a1a1a
```

---

## Comfy Cozy Sidebar (Native ComfyUI Integration)

A typography-forward chat panel in ComfyUI's native left sidebar. No floating buttons, no separate windows. Uses ComfyUI's own CSS variables -- adapts to any theme automatically.

```mermaid
graph TB
    subgraph ComfyUI_App ["ComfyUI"]
        subgraph Sidebar ["Left Sidebar"]
            Tab["Comfy Cozy Tab<br/>registerSidebarTab()"]
            Chat["Chat Window<br/>WebSocket -- streaming -- rich text"]
            QA["Quick Actions<br/>Run -- Validate -- Repair -- Optimize -- Undo"]
        end
        Canvas["Canvas"]
    end

    subgraph Bridge ["Bidirectional Canvas Bridge"]
        C2A["Canvas --> Agent<br/>Auto-sync on change"]
        A2C["Agent --> Canvas<br/>Push mutations + highlights"]
    end

    Tab --> Chat
    Tab --> QA
    Sidebar <--> Bridge
    Bridge <--> Canvas

    style ComfyUI_App fill:#d9c958,color:#1a1a1a,stroke:#d99458
    style Sidebar fill:#d9c958,color:#1a1a1a,stroke:#d99458
    style Bridge fill:#d9c958,color:#1a1a1a,stroke:#d99458
```

**What you get:**
- **Native sidebar tab** -- `app.extensionManager.registerSidebarTab()`, sits alongside ComfyUI's built-in panels
- **Design system v3** -- Inter + JetBrains Mono, ComfyUI CSS variables, Pentagram-inspired: hairline borders, generous whitespace, 2px radii, zero ornamentation
- **Chat** -- Auto-growing textarea, streaming responses, rich text (code blocks, bold, inline code), collapsible tool results
- **Node pills** -- Clickable inline node references, color-coded by slot type. Click = select + center on canvas.
- **Quick actions** -- Context-aware chips: Run, Validate, Repair, Optimize, Undo
- **Canvas bridge** -- Agent changes sync to canvas live with node highlighting; canvas re-syncs after each execution
- **Self-healing** -- Missing node warnings with one-click repair, deprecated node migration

**49 panel routes** expose the full tool surface: discovery, provisioning, repair, sessions, execution.

Every request passes through a three-layer security chain:

```mermaid
flowchart TD
    REST([REST Request]) --> Guard["_guard(request, category)"]
    WS([WebSocket /ws]) --> Guard
    Guard --> Auth{check_auth}
    Auth -->|"no token configured"| Rate{check_rate_limit}
    Auth -->|"bearer matches"| Rate
    Auth -->|"missing / wrong"| R401(["401 Unauthorized"])
    Rate -->|"tokens available"| Size{check_size}
    Rate -->|"bucket empty"| R429(["429 -- Retry-After: 1s"])
    Size -->|"Content-Length OK"| Handler(["Route handler"])
    Size -->|"> 10 MB"| R413(["413 Too Large"])
    Size -->|"chunked -- no length"| R411(["411 Length Required"])

    style R401 fill:#d99458,color:#1a1a1a
    style R429 fill:#d9c958,color:#1a1a1a
    style R413 fill:#d99458,color:#1a1a1a
    style R411 fill:#d9c958,color:#1a1a1a
    style Handler fill:#d99458,color:#1a1a1a
    style Guard fill:#d9c958,color:#1a1a1a
```

---

## One-Click Model Provisioning

The agent handles the entire pipeline from "I want Flux" to a wired workflow:

```mermaid
flowchart LR
    Search["Search<br/>CivitAI + HF + Registry"] --> Download["Download<br/>to correct folder"]
    Download --> Verify["Verify<br/>family + compat"]
    Verify --> Wire["Auto-Wire<br/>find loader -- set input"]
    Wire --> Ready["Ready to<br/>Queue"]

    style Search fill:#d9c958,color:#1a1a1a
    style Download fill:#d9c958,color:#1a1a1a
    style Verify fill:#d99458,color:#1a1a1a
    style Wire fill:#d9c958,color:#1a1a1a
    style Ready fill:#d99458,color:#1a1a1a
```

**`provision_model`** -- one tool call that discovers, downloads, verifies compatibility, finds the right loader node in your workflow, and wires the model in.

---

<details>
<summary><b>Architecture Deep Dive</b> (click to expand)</summary>

### Seven Structural Subsystems

The agent is built on seven architectural subsystems. Each one degrades independently -- if one breaks, the rest keep working.

```mermaid
graph TB
    subgraph Foundation ["Foundation Layer"]
        DAG["Workflow Intelligence DAG<br/>6 pure computation nodes"]
        OBS["Time-Sampled State<br/>Monotonic step index"]
        CAP["Capability Registry<br/>113 tools indexed"]
    end

    subgraph Safety ["Safety Layer"]
        GATE["Pre-Dispatch Gate<br/>5 checks, default-deny"]
        BRIDGE["Mutation Bridge<br/>LIVRPS composition + audit"]
    end

    subgraph Integration ["Integration Layer"]
        ADAPT["Inter-Module Adapters<br/>Pure-function translators"]
        DEGRADE["Degradation Manager<br/>Per-subsystem fallbacks"]
    end

    Foundation --> Safety --> Integration

    style Foundation fill:#d9c958,color:#1a1a1a,stroke:#d99458
    style Safety fill:#d9c958,color:#1a1a1a,stroke:#d99458
    style Integration fill:#d9c958,color:#1a1a1a,stroke:#d99458
```

### Workflow Intelligence DAG

Before any workflow runs, a DAG of pure functions analyzes it:

```mermaid
graph LR
    C[Complexity<br/>TRIVIAL to EXTREME] --> M[Model Requirements<br/>VRAM, family, LoRAs]
    M --> O[Optimization<br/>TensorRT, batching]
    O --> R[Risk<br/>SAFE to BLOCKED]
    R --> RD[Readiness<br/>go / no-go]

    style C fill:#d9c958,color:#1a1a1a
    style R fill:#d99458,color:#1a1a1a
    style RD fill:#d99458,color:#1a1a1a
```

### Pre-Dispatch Safety Gate

Every tool call passes through a default-deny gate. Read-only tools bypass it (zero overhead). Destructive tools are always locked. The gate auto-detects loaded workflows AND USD stages: if either kind of workspace state exists for the current connection, mutation tools are allowed without explicit session context. Stage tools (`stage_write`, `stage_add_delta`) are recognized separately from workflow tools — a USD stage can exist independently of any loaded workflow.

```mermaid
flowchart LR
    Tool([Tool Call]) --> Type{"Stage\ntool?"}
    Type -->|No| WF{"Workflow\nloaded?"}
    Type -->|Yes| ST{"Stage\nexists?"}
    WF -->|Yes| Risk{Risk Level?}
    WF -->|No| Deny["Denied:\nno active session"]
    ST -->|Yes| Risk
    ST -->|No| Deny
    Risk -->|"Read-only"| Pass[Pass through]
    Risk -->|"Mutation / Execute"| Checks[5 safety checks]
    Risk -->|"Install / Download"| Escalate[Escalate to LLM]
    Risk -->|"Uninstall / Delete"| Block[Blocked]

    Checks --> OK{All pass?}
    OK -->|Yes| Go[Execute]
    OK -->|No| Stop[Denied + reason]

    style Pass fill:#d99458,color:#1a1a1a
    style Go fill:#d99458,color:#1a1a1a
    style Stop fill:#d99458,color:#1a1a1a
    style Block fill:#d99458,color:#1a1a1a
    style Deny fill:#d99458,color:#1a1a1a
    style Escalate fill:#d9c958,color:#1a1a1a
```

### Per-Connection Session Isolation (all 4 transports)

Every sidebar conversation, every panel chat, every MCP client connection, and every `agent run --session foo` invocation gets its own isolated `WorkflowSession` + `CognitiveWorkflowStage`. State never leaks across tabs, clients, or named sessions. Isolation is propagated via a single `_conn_session` `ContextVar` set at every entry point — and by the per-session dicts inside the four stage modules (`provision`, `foresight`, `compositor`, `hyperagent`).

```mermaid
flowchart LR
    SB["Sidebar tabs<br/>conv.id"] --> H1["_spawn_with_session<br/>(shared helper)"]
    PNL["Panel chats<br/>conv.id"] --> H1
    MCP["MCP clients<br/>conn_xxxxxxxx"] --> H2["mcp_server._handler<br/>sets _conn_session"]
    CLI["agent run --session foo<br/>(CLI)"] --> H3["cli.run<br/>+ _save_and_exit"]
    H1 --> CV[("_conn_ctx<br/>ContextVar")]
    H2 --> CV
    H3 --> CV
    CV --> WP["workflow_patch._get_state()"]
    CV --> ST["stage_tools._get_stage()"]
    CV --> FT["foresight_tools._get_*()"]
    CV --> PV["provision_tools._get_provisioner()"]
    CV --> CT["compositor_tools._scenes[sid]"]
    CV --> HY["hyperagent_tools._meta_agents[sid]"]
    WP --> WS[("Per-session<br/>WorkflowSession + Stage")]
    ST --> WS
    FT --> WS
    PV --> WS
    CT --> WS
    HY --> WS

    style CV fill:#d9c958,color:#1a1a1a
    style WP fill:#d9c958,color:#1a1a1a
    style ST fill:#d9c958,color:#1a1a1a
    style FT fill:#d9c958,color:#1a1a1a
    style PV fill:#d9c958,color:#1a1a1a
    style CT fill:#d9c958,color:#1a1a1a
    style HY fill:#d9c958,color:#1a1a1a
    style WS fill:#d99458,color:#1a1a1a
```

The same connection id is also installed as the per-thread correlation ID via `set_correlation_id`, so every log entry from a single conversation is greppable end-to-end. Parallel tool calls inside a single turn inherit the contextvar via `contextvars.copy_context()` per `ThreadPoolExecutor.submit()`. And `_save_and_exit()` (called on normal exit, atexit, or SIGTERM) self-sets the contextvar before saving so the user's named session never gets corrupted with empty default workflow state.

### LIVRPS -- How Conflicts Get Resolved

All workflow changes are non-destructive layers. When two opinions conflict:

| Priority | Layer | Example |
|----------|-------|---------|
| 6 (strongest) | **Safety** | "CFG above 30 is degenerate" -- always wins |
| 5 | **Local** (your edit) | "Set CFG to 9" |
| 4 | **Inherits** (experience) | "CFG 7.5 worked better last time" |
| 3 | **VariantSets** | Creative profile presets |
| 2 | **References** | Learned recipes |
| 1 (weakest) | **Payloads** | Default template values |

Your edit beats experience. Safety beats everything. Every conflict is deterministic, transparent, and reversible.

This is an intentional inversion of USD's native LIVRPS (where Specializes is weakest). Safety is promoted to strongest for safety-critical override -- the architectural decision documented in the patent application.

### Cognitive State Engine (Phase 0.5 -- live in production)

LIVRPS is no longer a table on a slide. Since Phase 0.5 the engine is a real top-level package (`cognitive/`) installed alongside `agent/`, and `agent/tools/workflow_patch.py` imports it directly at module load -- no try/except, no silent fallback. Every PILOT mutation is recorded as a delta layer with SHA-256 tamper detection, then resolved on demand. The engine is session-scoped via the `_conn_session` ContextVar described above, so each sidebar tab and MCP connection mutates its own delta stack.

```mermaid
graph LR
    User([Tool Call<br/>via MCP]) --> WP["agent/tools/<br/>workflow_patch.py"]
    WP -->|"_get_state() reads<br/>_conn_session ContextVar"| CGE["CognitiveGraphEngine<br/>(per-session)"]
    CGE --> Stack["Delta Stack<br/>P -- R -- V -- I -- L -- S"]
    Stack -->|"sort weakest to strongest<br/>apply, preserve link arrays"| Resolved["Resolved WorkflowGraph"]
    Resolved -->|"to_api_json()"| Comfy["ComfyUI /prompt"]

    style User fill:#d99458,color:#1a1a1a
    style WP fill:#d9c958,color:#1a1a1a
    style CGE fill:#d9c958,color:#1a1a1a
    style Stack fill:#d9c958,color:#1a1a1a
    style Resolved fill:#d99458,color:#1a1a1a
    style Comfy fill:#d99458,color:#1a1a1a
```

The `cognitive/` package is layered by phase -- the core engine (Phase 1) is fully tested at 54/54 adversarial cases. Phase 6 is complete: the autonomous pipeline is fully wired with real executor, template loading, rule-based evaluator, and experience persistence.

```mermaid
graph TB
    Cognitive["cognitive/<br/>(installed top-level package)"]
    Cognitive --> Core["core/<br/>graph -- delta -- models<br/>54/54 tests passing"]
    Cognitive --> Exp["experience/<br/>chunk -- signature -- accumulator"]
    Cognitive --> Pred["prediction/<br/>cwm -- arbiter -- counterfactual"]
    Cognitive --> Trans["transport/<br/>schema_cache -- events -- interrupt"]
    Cognitive --> Pipe["pipeline/<br/>autonomous -- create_default_pipeline<br/>Phase 6 complete"]
    Cognitive --> CogTools["tools/<br/>analyze -- compose -- execute<br/>(cycle 9 deleted 5 dead modules)"]

    style Cognitive fill:#d9c958,color:#1a1a1a
    style Core fill:#d99458,color:#1a1a1a
    style Exp fill:#d9c958,color:#1a1a1a
    style Pred fill:#d9c958,color:#1a1a1a
    style Trans fill:#d99458,color:#1a1a1a
    style Pipe fill:#d99458,color:#1a1a1a
    style CogTools fill:#d9c958,color:#1a1a1a
```

Each delta layer carries its `creation_hash` (SHA-256 of `opinion + sorted-JSON mutations`). `verify_stack_integrity()` walks the stack and flags any layer whose `layer_hash` no longer matches its `creation_hash` -- making post-hoc tampering detectable. Link arrays (`["node_id", output_index]`) are preserved through every parse/mutate/serialize round-trip, which is the #1 failure mode in ComfyUI agents.

### LLM Provider Hardening

The agent supports four LLM providers (Anthropic, OpenAI, Gemini, Ollama). Cycles 7+18+20 closed six real bugs in the streaming, retry, and multi-turn paths, and the Opus 4.7 upgrade (commit `c61c65f`) refined the multi-turn `ThinkingBlock` policy on Anthropic. After this work, every provider correctly: extracts streaming token usage, doesn't duplicate text on retry, doesn't fire callbacks with empty content, doesn't leak reasoning into user-visible text, and handles `ThinkingBlock` correctly on multi-turn replay — Anthropic re-sends signature-bearing thinking blocks (required by the API when extended thinking runs alongside tool use), while OpenAI / Gemini / Ollama drop them (those APIs don't model replayable thinking).

```mermaid
graph TB
    Stream["_stream_with_retry<br/>(agent/main.py)"] --> Track["content_emitted = [False]<br/>per attempt — closure-captured"]
    Track --> Wrap["_wrap_safe + tracking<br/>on_text / on_thinking"]
    Wrap --> Provider{Which provider?}

    Provider -->|Anthropic| A["✓ thinking blocks preserved<br/>in _to_response (with signature)<br/>✓ empty deltas filtered<br/>✓ signature-bearing ThinkingBlock<br/>replayed verbatim in convert_messages<br/>(c61c65f — supersedes cycle 20)"]
    Provider -->|OpenAI| O["✓ stream_options=<br/>{include_usage: true}<br/>✓ ThinkingBlock skipped<br/>in convert_messages (cycle 20)"]
    Provider -->|Gemini| G["✓ thinking / text branches<br/>mutually exclusive (if/elif)<br/>✓ ThinkingBlock skipped<br/>(was sending repr as text)"]
    Provider -->|Ollama| OL["✓ stream_options=<br/>{include_usage: true}<br/>✓ ThinkingBlock pre-filtered<br/>from content list (cycle 20)"]

    Track -->|content emitted + transient error| NoRetry["RAISE — don't retry<br/>(would duplicate text in UI)"]
    Track -->|no content + transient error| Retry["Retry with backoff<br/>RateLimit / Connection / 5xx"]

    style Stream fill:#d9c958,color:#1a1a1a
    style Track fill:#d9c958,color:#1a1a1a
    style A fill:#d99458,color:#1a1a1a
    style O fill:#d99458,color:#1a1a1a
    style G fill:#d99458,color:#1a1a1a
    style OL fill:#d99458,color:#1a1a1a
    style NoRetry fill:#d99458,color:#1a1a1a
    style Retry fill:#d99458,color:#1a1a1a
```

**Cycle 20 — ThinkingBlock multi-turn bug.** When Claude 3.7+ or Claude 4 returns a `ThinkingBlock` in its response, the agent stores it in message history. On the next turn, `convert_messages` must translate that block back to the provider's native format. Before cycle 20, all 4 providers mishandled it: Anthropic sent the raw Python dataclass to the API (400 error), OpenAI silently dropped it, Gemini converted `str(ThinkingBlock(...))` to user-visible text, and Ollama sent raw objects. Fix: all providers now skip ThinkingBlock in convert_messages (the API requires a signature field we don't capture; thinking content is already delivered via the streaming `on_thinking` callback).

**Opus 4.7 evolution (c61c65f).** The cycle-20 fix above strips `ThinkingBlock` across the board. The Opus 4.7 upgrade refined Anthropic's branch: extended-thinking responses now include a cryptographic `signature` on each thinking block, and the API requires the signature on the next turn whenever a `tool_use` block follows. `agent/llm/_anthropic.py:convert_messages` now replays signature-bearing blocks verbatim; signature-less blocks (legacy paths, manually-constructed test fixtures) are dropped silently — a known-fragile path; a future cleanup commit will replace the silent drop with an explicit warning. OpenAI, Gemini, and Ollama retain the cycle-20 behavior; their APIs don't model replayable thinking, so the strip remains correct.

```mermaid
graph LR
    LLM["LLM Response<br/>[TextBlock, ThinkingBlock]"] --> Store["main.py:293<br/>messages.append(content)"]
    Store --> NextTurn["Next turn<br/>convert_messages()"]
    NextTurn -->|"Anthropic, signature ✓"| Replay["ThinkingBlock<br/>→ replay verbatim"]
    NextTurn -->|"Anthropic no-sig / other providers"| Skip["ThinkingBlock<br/>→ skip (continue)"]
    NextTurn --> Keep["TextBlock / ToolUseBlock<br/>→ convert to native format"]
    Replay --> Safe
    Skip --> Safe["API receives only<br/>valid native blocks"]
    Keep --> Safe

    style LLM fill:#d9c958,color:#1a1a1a
    style Store fill:#d9c958,color:#1a1a1a
    style Replay fill:#d99458,color:#1a1a1a
    style Skip fill:#d99458,color:#1a1a1a
    style Keep fill:#d99458,color:#1a1a1a
    style Safe fill:#d99458,color:#1a1a1a
```

The retry tracker pattern is the key insight: an `on_text("Hello ")` followed by a transient `LLMRateLimitError` USED TO retry from scratch, calling `on_text("Hello ")` again, then `on_text("world!")` — the user saw `"Hello Hello world!"` in the UI. After cycle 7, any error fired AFTER content was emitted raises immediately instead of retrying. Tested across all 4 providers via `tests/test_main.py::TestStreamRetryDuplication` + provider-specific regression tests.

### Graceful Degradation

Every subsystem has an independent kill switch. Set any of these to `0` in your `.env` to disable:

`BRAIN_ENABLED` `DAG_ENABLED` `GATE_ENABLED` `OBSERVATION_ENABLED`

All default to ON. The agent works fine with any combination disabled -- features gracefully disappear.

### Experience Loop

Every generation is an experiment. The agent tracks what worked:

- **Sessions 1-30**: Uses built-in knowledge only
- **Sessions 30-100**: Blends knowledge with what it's learned from your renders
- **Sessions 100+**: Primarily driven by your personal history

### Semantic Knowledge Retrieval

The agent ships with 12 knowledge files (1,300+ lines) covering ControlNet preprocessor selection and strength scheduling (174 lines), Flux guidance and T5 encoder tuning (172 lines), multi-pass compositing for Nuke/AE/Fusion (119 lines), video workflows, 3D pipelines, and more. Retrieval is hybrid: keyword triggers fire first (fast path), then TF-IDF semantic search fills gaps when keywords miss. Pure Python, zero external dependencies -- no vector DB required.

```mermaid
flowchart LR
    Context["Workflow context<br/>+ session notes"] --> KW{"Keyword<br/>triggers"}
    KW -->|"≥ 2 files"| Done["Load knowledge"]
    KW -->|"< 2 files"| TFIDF["TF-IDF<br/>cosine similarity"]
    TFIDF --> Merge["Union results"]
    Merge --> Done

    style KW fill:#d9c958,color:#1a1a1a
    style TFIDF fill:#d9c958,color:#1a1a1a
    style Done fill:#d99458,color:#1a1a1a
```

### Tool Inventory

**113 tools across three layers:**

| Layer | Count | Highlights |
|-------|-------|-----------|
| **Intelligence** | 86 | Workflow parsing, model search (CivitAI + HF + 31k nodes), delta patching, auto-wire, provisioning pipeline, execution |
| **Brain** | 27 | Vision analysis, goal planning, pattern memory, GPU optimization, artistic intent capture, iteration tracking |
| **Stage** | 23 | USD cognitive state, LIVRPS composition, predictive experiments, scene composition |

### Workflow Lifecycle

```mermaid
flowchart LR
    Load[Load] --> Validate[Validate]
    Validate --> Errors{"Errors?"}
    Errors -->|"Missing nodes"| Repair[Auto-Repair<br/>install packs]
    Errors -->|"Missing inputs"| Fix[Auto-Fix<br/>set_input]
    Errors -->|None| Analyze[DAG<br/>Analysis]
    Repair --> Validate
    Fix --> Validate
    Analyze --> Gate[Safety<br/>Gate]
    Gate --> Patch[Patch via<br/>Delta Layer]
    Patch --> Run[Run on<br/>ComfyUI]
    Run --> Check[Check<br/>Output]
    Check --> Learn[Record<br/>Experience]

    Patch -->|Undo| Validate
    Check -->|Iterate| Patch

    style Load fill:#d9c958,color:#1a1a1a
    style Repair fill:#d9c958,color:#1a1a1a
    style Fix fill:#d9c958,color:#1a1a1a
    style Analyze fill:#d9c958,color:#1a1a1a
    style Gate fill:#d99458,color:#1a1a1a
    style Run fill:#d99458,color:#1a1a1a
    style Check fill:#d99458,color:#1a1a1a
    style Learn fill:#d9c958,color:#1a1a1a
```

### Project Structure

```
agent/
  llm/                Multi-provider abstraction (Anthropic, OpenAI, Gemini, Ollama)
  tools/              63 tools -- workflow ops, model search, provisioning, auto-wire
                      workflow_patch.py wraps the cognitive engine for non-destructive PILOT
  brain/              27 tools -- vision, planning, memory, optimization
    adapters/         Pure-function translators between brain modules
  stage/              23 tools -- USD state, prediction, composition (USD optional via [stage])
    dag/              Workflow intelligence (6 computation nodes)
  gate/               Pre-dispatch safety (5-check pipeline)
  metrics.py          Observability (Counter, Histogram, Gauge -- pure stdlib, thread-safe)
  degradation.py      Fault isolation manager
  config.py           Environment + 4 kill switches + LLM provider selection
  mcp_server.py       MCP server (primary interface)
cognitive/            LIVRPS state engine -- installed as top-level package (Phase 0.5)
  core/               CognitiveGraphEngine, DeltaLayer, WorkflowGraph (link-preserving)
  experience/         ExperienceChunk, GenerationContextSignature, Accumulator
  prediction/         CognitiveWorldModel, SimulationArbiter, CounterfactualGenerator
  transport/          SchemaCache, ExecutionEvent, interrupt, system_stats, TriggerRegistry
  pipeline/           Autonomous end-to-end orchestration
  tools/              Phase 3 macro-tools (analyze, mutate, query, compose, ...)
ui/
  __init__.py         WEB_DIRECTORY + route registration
  web/js/sidebar.js   Native left sidebar -- chat, quick actions, progress
  web/css/            Design system v3 -- ComfyUI-native CSS variables, theme-reactive
  server/routes.py    WebSocket + REST endpoints for sidebar chat
panel/
  __init__.py         WEB_DIRECTORY + route registration + sys.path injection
  server/routes.py    49 REST routes -- full tool surface
  web/js/             Headless canvas↔agent bridge (no visible UI -- sidebar is primary)
tests/                4,100+ passing tests, all mocked, ~60s
  integration/        Skips cleanly when ComfyUI not running
```

### Production Hardening

| Domain | What it means |
|--------|-------------|
| **Safety** | 5-check default-deny gate. Risk levels 0-4. Destructive ops never auto-execute. |
| **Fault Isolation** | Each subsystem fails independently. Circuit breakers prevent cascading failures. `brain` (threshold=3, timeout=30s) and `comfyui_http` (threshold=5, timeout=60s) registered; `BRAIN_ENABLED=0` kill switch fully enforced in tool registry. Session isolation: each `agent mcp` process gets a unique `conn_XXXXXXXX` namespace; ContextVar set in executor thread before dispatch. Parallel tool dispatch routes through `agent.tools.handle` live module reference -- monkey-patch visible to all ThreadPoolExecutor workers. |
| **Determinism** | Pure computation DAG. Deterministic JSON. Ordinal state enums. Same input = same output. |
| **Audit Trail** | Every mutation logged: who changed what, when, and what got overridden. |
| **Security** | Bearer token auth on all routes including WebSocket — **constant-time `hmac.compare_digest`** comparison (no timing-attack leakage). **WebSocket Origin allowlist** on sidebar + panel (rejects cross-origin connects from `evil.com`; same-origin LAN browsers pass). Path traversal blocked. **`download_model` symlink-bypass guard**: resolves the full target path (parent + filename) and re-checks against `MODELS_DIR` so a planted symlink in a `Custom_Nodes` subdirectory can't escape. SSRF prevented on initial URL and every redirect hop (RFC 1918 + loopback + link-local + CGNAT rejected via DNS resolution). MCP tool errors return `isError=True` per protocol. Gate exceptions deny by default (no silent allow). 10 MB + chunked-transfer size guards. Max 20 concurrent WebSocket connections. Atomic file writes with `flush()`+`os.fsync()` before rename (session.py + workflow_patch.py). Thread-safe token bucket rate limiter. **Handler exception guard**: stream callbacks wrapped with `_wrap_safe` so a misbehaving custom renderer can't crash the agent loop. **Config sanitization**: `COMFYUI_HOST` stripped of whitespace and trailing slashes to prevent malformed URLs. |
| **Observability** | Thread-safe metrics module (`agent/metrics.py`): Counter, Histogram, Gauge. Tool call latency (p50/p99), error rates, LLM call timing, circuit breaker transitions, session counts. JSON + Prometheus text export. Health endpoint includes metrics summary. Zero external dependencies. |
| **Bounded Resources** | Intent history (100), iteration steps (200), demo checkpoints (100). No unbounded growth. |

```mermaid
graph TB
    subgraph Sec ["Security"]
        A1["Auth -- Bearer token<br/>(REST + WebSocket)"]
        A2["Rate limit -- Token bucket<br/>per category"]
        A3["Size guard -- 10 MB limit<br/>+ chunked-transfer block"]
        A4["WS cap -- 20 connections max"]
    end
    subgraph Atom ["Persistence"]
        B1["_save_lock<br/>threading.Lock"]
        B2["Write to .jsonl.tmp"]
        B3["os.replace()<br/>atomic swap"]
        B1 --> B2 --> B3
    end
    subgraph Resil ["Resilience"]
        C1["CWM exception<br/>--> PipelineStage.FAILED"]
        C2["Template mismatch<br/>--> result.warnings"]
        C3["Save failure<br/>--> non-fatal log"]
    end
    subgraph Obs ["Observability"]
        D1["Counter / Histogram / Gauge<br/>thread-safe, pure stdlib"]
        D2["tool_call_total<br/>tool_call_duration_seconds"]
        D3["get_metrics() -- JSON<br/>get_metrics_prometheus() -- text"]
        D1 --> D2 --> D3
    end

    style Sec fill:#d9c958,color:#1a1a1a,stroke:#d99458
    style Atom fill:#d9c958,color:#1a1a1a,stroke:#d99458
    style Resil fill:#d9c958,color:#1a1a1a,stroke:#d99458
    style Obs fill:#d9c958,color:#1a1a1a,stroke:#d99458
```

</details>

---

## Configuration

All settings live in your `.env` file:

| Setting | Default | What it does |
|---------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required for Anthropic)* | Your Claude API key |
| `OPENAI_API_KEY` | | Your OpenAI API key |
| `GEMINI_API_KEY` | | Your Google Gemini API key |
| `LLM_PROVIDER` | `anthropic` | Which LLM to use: `anthropic`, `openai`, `gemini`, `ollama` |
| `AGENT_MODEL` | *(auto per provider)* | Override the model name |
| `FAST_MODEL` | *(auto per provider)* | Model for short triage / classification (Haiku 4.5 default on Anthropic) |
| `VISION_MODEL` | *(same as `AGENT_MODEL`)* | Model for vision tools (`analyze_image`, `compare_outputs`) |
| `THINKING_BUDGET` | `4000` | Extended-thinking budget per agent turn (Anthropic Claude 4.x+ only; `0` disables) |
| `VISION_THINKING_BUDGET` | `2000` | Extended-thinking budget for vision-tool calls (`0` disables) |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama server URL |
| `COMFYUI_HOST` | `127.0.0.1` | Where ComfyUI runs |
| `COMFYUI_PORT` | `8188` | ComfyUI port |
| `COMFYUI_DATABASE` | `~/ComfyUI` | Your ComfyUI folder (models, nodes, workflows) |

---

## Testing

No ComfyUI needed -- everything is mocked:

```bash
python -m pytest tests/ -v        # 4,100+ passing tests, ~70s

# Skip tests that require a real ComfyUI server or API keys
python -m pytest tests/ -v -m "not integration"
```

The `[dev]` install runs the full test suite -- no ComfyUI server or API keys required, everything is mocked. The `test_provisioner.py` tests require `usd-core` (install with `pip install -e ".[stage]"` to resolve them).

---

## License & Patents

**Patent Pending** | [MIT](LICENSE)

Aspects of this architecture -- including deterministic state-evolution, LIVRPS non-destructive composition, predictive experiment pipelines, and the cognitive experience loop -- are the subject of pending US provisional patent applications filed by Joseph O. Ibrahim.

This project shares structural patterns with [Harlo](https://github.com/JosephOIbrahim/Harlo), a USD-native cognitive architecture for persistent AI memory. See Harlo's [PATENTS.md](https://github.com/JosephOIbrahim/Harlo/blob/main/PATENTS.md) for patent details and grant terms.

For questions about patent licensing, commercial licensing, or enterprise arrangements:
**Joseph O. Ibrahim** -- jomar.ibrahim@gmail.com
