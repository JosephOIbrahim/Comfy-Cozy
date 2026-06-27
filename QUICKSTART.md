# Quick Start — Comfy Cozy

> **Comfy Cozy** is an AI co-pilot for ComfyUI. You describe what you want in
> plain English; the agent loads workflows, swaps models, tweaks parameters,
> installs missing nodes, runs generations, and analyzes outputs — you never
> touch JSON.

This page gets you running in under 2 minutes. For the full walkthrough —
native sidebar, the optional canvas bridge, architecture — see the
[README](README.md).

---

## Prerequisites

| | What you need | Where to get it |
|---|---------------|-----------------|
| 1 | **Python 3.11+** | [python.org/downloads](https://python.org/downloads) |
| 2 | **ComfyUI running** | [github.com/comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI) |
| 3 | **One LLM backend** | An API key (Anthropic / OpenAI / Google / [NVIDIA](https://build.nvidia.com)) or [Ollama](https://ollama.com) (free, local, no key) |

---

## Install — four copy-paste steps

### 1. Clone

```bash
git clone https://github.com/JosephOIbrahim/Comfy-Cozy.git
cd Comfy-Cozy
```

### 2. Install

```bash
pip install -e .
```

One command — no build step, no Docker, no conda. Want the test suite too?
`pip install -e ".[dev]"`.

### 3. Add your key

```bash
cp .env.example .env
```

Open `.env` and paste your key on the first line:

```bash
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

ComfyUI installed somewhere non-default? Add one more line:

```bash
COMFYUI_DATABASE=C:/path/to/your/ComfyUI
```

### 4. Go

```bash
agent run
```

Type what you want. Type `quit` when you're done.

---

## Pick your LLM

Comfy Cozy is provider-agnostic — same tools, same vision analysis. Swap one
env var in `.env`. The default is **Anthropic (Opus 4.7)**.

```bash
# --- Anthropic (default — Opus 4.7) ---
ANTHROPIC_API_KEY=sk-ant-your-key-here

# --- OpenAI ---
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
AGENT_MODEL=gpt-4o
# first time only: pip install openai

# --- Google Gemini ---
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
AGENT_MODEL=gemini-2.5-flash
# first time only: pip install google-genai

# --- Ollama (fully local, free, no key) ---
LLM_PROVIDER=ollama
AGENT_MODEL=llama3.1
# first time only: ollama pull llama3.1

# --- NVIDIA Nemotron ---
LLM_PROVIDER=nvidia
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_API_KEY=nvapi-your-key-here
AGENT_MODEL=nvidia/nemotron-3-super-120b-a12b
# first time only: pip install openai
```

Switch models mid-session with the `swap_model` tool, or per launch with
`agent run --model <alias>`.

---

## Use it inside Claude Code or Desktop (MCP)

Comfy Cozy runs as an MCP server, so the assistant drives ComfyUI alongside its
normal abilities. Add this to your MCP config:

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

Point `cwd` at wherever you cloned Comfy-Cozy, then restart the host.

---

## What you can ask for

The tools cover the whole workflow lifecycle — **discovery** (find models and
node packs), **editing** (patch parameters, swap models, build nodes),
**execution** (validate and run with live progress), **vision** (analyze and
compare outputs), and **provisioning** (install packs, download models). You
just talk:

- "What models do I have installed?"
- "Load my portrait workflow and make it dreamier"
- "Change the sampler to DPM++ 2M Karras and run it"
- "Find me a good LoRA for anime style"
- "Why does this output look oversaturated?"

For everything else — the native sidebar panel, the optional canvas bridge, and
the full provider and architecture notes — see the [README](README.md).
