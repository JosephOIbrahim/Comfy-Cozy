"""Configuration and environment handling."""

import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root regardless of working directory (supports MCP server launch).
# override=True makes the project .env authoritative — it wins over any pre-set OS/shell env
# var, so a stale shell var (e.g. a leftover COMFYUI_DATABASE) can't silently shadow .env.
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

# LLM Provider selection — anthropic (default), openai, gemini, ollama, nvidia
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")

# Provider API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

# NVIDIA / Nemotron (OpenAI-compatible reasoning LLM). Endpoint-agnostic — one
# provider serves NVIDIA NIM cloud, OpenRouter, Ollama cloud, and self-hosted
# vLLM/SGLang/NIM. Pick the endpoint via NVIDIA_BASE_URL; the model id selects
# the backend model. See tooling/harness/PRD_model_swap.md §2.2 (endpoint gate).
#   NVIDIA NIM cloud:  https://integrate.api.nvidia.com/v1   (NVIDIA_API_KEY=nvapi-...)
#   OpenRouter:        https://openrouter.ai/api/v1          (NVIDIA_API_KEY=<openrouter key>)
#   self-hosted:       http://<host>:8000/v1                 (key optional)
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
# Nemotron streams <think>...</think> as plain content. Default OFF: inject a
# 'detailed thinking off' directive + strip any leaked <think> from stream and
# the returned block. Set true to request reasoning ON and surface it.
NVIDIA_EMIT_REASONING = os.getenv("NVIDIA_EMIT_REASONING", "false").lower() in ("1", "true", "yes")
# OpenRouter key (alias for an OpenRouter-hosted NVIDIA_BASE_URL; falls back to NVIDIA_API_KEY).
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Vision is DECOUPLED from the agent-loop provider: analyze_image / compare_outputs
# need a MULTIMODAL provider + key even when AGENT_MODEL is a text-only Nemotron.
# Defaults to anthropic so swapping the agent loop never breaks the brain's vision.
VISION_PROVIDER = os.getenv("VISION_PROVIDER", "anthropic")

# API-key validation is deferred to a callable (T5 from the 5x review).
# Pre-fix this printed at import time, leaking the warning into every
# `agent --help`, `agent inspect`, etc. — confusing because those
# commands don't need an API key. Callers who DO need the LLM call
# `warn_on_missing_api_key()` explicitly at their entry point.
_api_key_warn_emitted = False


def warn_on_missing_api_key() -> None:
    """Emit the API-key-missing warning once per process, IF needed.

    Idempotent: only emits on first call. Safe to call from any command
    that requires the LLM. Commands that DON'T need the LLM (--help,
    inspect, parse, autonomous --execute-mode {mock,dry-run}) should
    NOT call this.
    """
    global _api_key_warn_emitted
    if _api_key_warn_emitted:
        return
    _api_key_warn_emitted = True
    if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        print(
            "WARNING: ANTHROPIC_API_KEY is not set. "
            "Set it in your .env file or environment. "
            "Get your key at https://console.anthropic.com/",
            file=sys.stderr,
        )
    # Validate format (warn, don't block — key may be valid in other formats)
    elif ANTHROPIC_API_KEY and not re.match(r"^sk-ant-", ANTHROPIC_API_KEY):
        print(
            "WARNING: ANTHROPIC_API_KEY doesn't match expected format (sk-ant-...). "
            "Verify your key at https://console.anthropic.com/",
            file=sys.stderr,
        )

# MCP auth token (optional — for future HTTP/SSE transport auth)
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN")

# Third-party API keys (optional — improve rate limits for external services)
CIVITAI_API_KEY = os.getenv("CIVITAI_API_KEY")    # Optional — improves CivitAI rate limits
GITHUB_API_TOKEN = os.getenv("GITHUB_API_TOKEN")   # Optional — improves GitHub API rate limits
HF_TOKEN = os.getenv("HF_TOKEN")                  # Cycle 58: required for gated HF models (Flux, SD3, etc.)

# Model selection — three tiers, each independently overridable.
#
#   AGENT_MODEL     — main agent loop (planner, tool use, multi-turn dialogue).
#                     Default: claude-opus-4-7 (strongest reasoning + tool use).
#   FAST_MODEL      — short classifications / triage / low-stakes one-shots.
#                     Default: claude-haiku-4-5-20251001 (fast + cheap).
#   VISION_MODEL    — brain/vision.py image analysis (analyze_image, compare_outputs).
#                     Default: same as AGENT_MODEL — Opus 4.7 vision is strong enough
#                     that a separate tier is rarely worth the extra cost.
#
# Override any of these in .env, e.g.:
#   AGENT_MODEL=claude-sonnet-4-20250514
#   FAST_MODEL=claude-haiku-4-5-20251001
#   VISION_MODEL=claude-opus-4-7
_DEFAULT_AGENT_MODELS = {
    "anthropic": "claude-opus-4-7",
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-flash",
    "ollama": "llama3.1",
    # id verified live via GET /v1/models on integrate.api.nvidia.com (2026-06-24)
    "nvidia": "nvidia/nemotron-3-super-120b-a12b",
}
_DEFAULT_FAST_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "ollama": "llama3.1",
    "nvidia": "nvidia/nemotron-3-nano-30b-a3b",
}
AGENT_MODEL = os.getenv(
    "AGENT_MODEL",
    _DEFAULT_AGENT_MODELS.get(LLM_PROVIDER, "claude-opus-4-7"),
)
FAST_MODEL = os.getenv(
    "FAST_MODEL",
    _DEFAULT_FAST_MODELS.get(LLM_PROVIDER, "claude-haiku-4-5-20251001"),
)
VISION_MODEL = os.getenv("VISION_MODEL", AGENT_MODEL)
# ^ AGENT_MODEL only affects CLI mode (agent run). MCP mode inherits the model
# from the host (e.g., Claude Code).

MAX_TOKENS = 16384
MAX_AGENT_TURNS = 30

# Extended thinking — request a reasoning budget on every agent stream.
# 0 disables; non-zero enables interleaved thinking (requires Claude 4.x+).
# Tuned for the agent loop's multi-turn tool use; vision/fast paths read
# their own budgets below.
THINKING_BUDGET = int(os.getenv("THINKING_BUDGET", "4000"))
VISION_THINKING_BUDGET = int(os.getenv("VISION_THINKING_BUDGET", "2000"))

# Adaptive-thinking effort level for Opus 4.7 / 4.6 and Sonnet 4.6.
# Anthropic removed `{type: enabled, budget_tokens: N}` for Opus 4.7
# (returns 400) and replaced it with `{type: adaptive}` + `output_config.effort`.
# Levels: low | medium | high | xhigh | max. Default "high" matches the
# prior "almost always think" semantics of THINKING_BUDGET=4000.
THINKING_EFFORT = os.getenv("THINKING_EFFORT", "high")

# Context management
COMPACT_THRESHOLD = int(os.getenv("COMPACT_THRESHOLD", "120000"))  # tokens — compact at this level
# Optional larger compaction window for a large-context provider (e.g. Nemotron's
# ~1M). Unset (0) => the provider uses COMPACT_THRESHOLD, so Claude/others are
# unchanged. Set this to let a long-context Nemotron use its window instead of
# being throttled to the small default. Kept opt-in (not auto-1M) because a
# self-hosted nvidia endpoint may be a small-context model.
NVIDIA_CONTEXT_WINDOW = int(os.getenv("NVIDIA_CONTEXT_WINDOW", "0")) or None


def effective_compact_threshold(provider: str | None = None) -> int:
    """Compaction threshold for the active (or given) LLM provider.

    Defaults to COMPACT_THRESHOLD for every provider (Claude behavior unchanged).
    When NVIDIA_CONTEXT_WINDOW is set and the provider is nvidia, returns that
    larger window. Reads LLM_PROVIDER dynamically so a runtime model swap is
    honored.
    """
    prov = (provider or LLM_PROVIDER).lower().strip()
    if prov == "nvidia" and NVIDIA_CONTEXT_WINDOW:
        return NVIDIA_CONTEXT_WINDOW
    return COMPACT_THRESHOLD

# API resilience
API_MAX_RETRIES = 3
API_RETRY_DELAY = 1.0  # seconds — base delay, doubles each retry

# ComfyUI connection
COMFYUI_HOST = os.getenv("COMFYUI_HOST", "127.0.0.1").strip().rstrip("/")
_port_raw = os.getenv("COMFYUI_PORT", "8188")
try:
    COMFYUI_PORT = int(_port_raw)
    if not (1 <= COMFYUI_PORT <= 65535):
        print(
            f"WARNING: COMFYUI_PORT={COMFYUI_PORT} out of range (1-65535). Using 8188.",
            file=sys.stderr,
        )
        COMFYUI_PORT = 8188
except ValueError:
    print(
        f"WARNING: COMFYUI_PORT='{_port_raw}' is not a valid integer. "
        "Falling back to default port 8188.",
        file=sys.stderr,
    )
    COMFYUI_PORT = 8188
COMFYUI_URL = f"http://{COMFYUI_HOST}:{COMFYUI_PORT}"

# Kill switches — independently disable subsystems (all default ON)
BRAIN_ENABLED = os.getenv("BRAIN_ENABLED", "1") == "1"
OBSERVATION_ENABLED = os.getenv("OBSERVATION_ENABLED", "1") == "1"
DAG_ENABLED = os.getenv("DAG_ENABLED", "1") == "1"
GATE_ENABLED = os.getenv("GATE_ENABLED", "1") == "1"
# Zero-LLM recipe pre-check in the CLI loop. Default OFF — purely additive, opt-in.
# (The apply_recipe / list_recipes MCP tools are always available regardless.)
RECIPES_ENABLED = os.getenv("RECIPES_ENABLED", "0") == "1"

# Paths — cross-platform defaults for ComfyUI database location
def _default_comfyui_database() -> str:
    """Sensible default ComfyUI database path per platform."""
    return str(Path.home() / "ComfyUI")


COMFYUI_DATABASE = Path(os.getenv("COMFYUI_DATABASE", _default_comfyui_database()))
CUSTOM_NODES_DIR = COMFYUI_DATABASE / "Custom_Nodes"
MODELS_DIR = COMFYUI_DATABASE / "models"
WORKFLOWS_DIR = COMFYUI_DATABASE / "Workflows"

# Output directory — may differ from COMFYUI_DATABASE when using extra_model_paths
# or symlinked setups. Override with COMFYUI_OUTPUT_DIR in .env.
def _default_comfyui_output() -> str:
    """Default output directory. Checks COMFYUI_OUTPUT_DIR env var first."""
    env = os.getenv("COMFYUI_OUTPUT_DIR")
    if env:
        return env
    return str(COMFYUI_DATABASE / "output")


COMFYUI_OUTPUT_DIR = Path(_default_comfyui_output())

# ComfyUI installation directory — auto-detected or overridden via env.
# This is the actual ComfyUI repo (with /blueprints, /comfy, etc.),
# which may differ from COMFYUI_DATABASE on split-directory setups.
def _default_comfyui_install() -> str:
    """Auto-detect ComfyUI installation path."""
    env = os.getenv("COMFYUI_INSTALL_DIR")
    if env:
        return env
    # Auto-detect: check common locations for the actual ComfyUI install
    candidates = [
        COMFYUI_DATABASE / "ComfyUI",
        Path.home() / "ComfyUI",
    ]
    for candidate in candidates:
        if (candidate / "comfy").is_dir() or (candidate / "main.py").exists():
            return str(candidate)
    # Fallback: custom_nodes symlink may point back to the install
    custom_nodes_link = CUSTOM_NODES_DIR
    if custom_nodes_link.is_symlink():
        resolved = custom_nodes_link.resolve().parent
        if (resolved / "main.py").exists():
            return str(resolved)
    return str(COMFYUI_DATABASE)


COMFYUI_INSTALL_DIR = Path(_default_comfyui_install())
COMFYUI_BLUEPRINTS_DIR = COMFYUI_INSTALL_DIR / "blueprints"

# Model catalog (rich metadata about installed models)
MODEL_CATALOG_PATH = COMFYUI_DATABASE / "model_catalog.json"

# Experience accumulator persistence — JSONL file that survives between sessions
EXPERIENCE_FILE = COMFYUI_DATABASE / "comfy-cozy-experience.jsonl"

# Auto-initialization (see startup.py)
AUTO_SCAN_MODELS = os.getenv("AUTO_SCAN_MODELS", "false").lower() == "true"
AUTO_SCAN_WORKFLOWS = os.getenv("AUTO_SCAN_WORKFLOWS", "false").lower() == "true"
AUTO_LOAD_WORKFLOW = os.getenv("AUTO_LOAD_WORKFLOW", "")
AUTO_LOAD_SESSION = os.getenv("AUTO_LOAD_SESSION", "")

# Stage persistence — durable USD checkpoint across sessions.
# STAGE_DEFAULT_PATH: if set, ensure_stage() loads from this .usda file on cold
# start and uses it as the default flush target. Empty string = in-memory only.
STAGE_DEFAULT_PATH = os.getenv("STAGE_DEFAULT_PATH", "")
# STAGE_AUTOSAVE_SECONDS: interval for the daemon flush timer. 0 disables.
STAGE_AUTOSAVE_SECONDS = int(os.getenv("STAGE_AUTOSAVE_SECONDS", "300"))
# STAGE_AUTOLOAD_EXPERIENCE: when "true", the cognitive ExperienceAccumulator
# is loaded from EXPERIENCE_FILE on first ensure_stage(). Wires the dormant
# create_default_pipeline() into the live runtime.
STAGE_AUTOLOAD_EXPERIENCE = os.getenv("STAGE_AUTOLOAD_EXPERIENCE", "false").lower() == "true"

# Project paths
PROJECT_DIR = Path(__file__).parent.parent
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
SESSIONS_DIR = PROJECT_DIR / "sessions"
LOCAL_WORKFLOWS_DIR = PROJECT_DIR / "workflows"
LOG_DIR = PROJECT_DIR / "logs"
