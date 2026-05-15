"""Configuration and environment handling."""

import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root regardless of working directory (supports MCP server launch)
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# LLM Provider selection — anthropic (default), openai, gemini, ollama
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")

# Provider API keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

# Validate ANTHROPIC_API_KEY — warn if missing when provider is anthropic. (Cycle 35 fix)
if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
    print(
        "WARNING: ANTHROPIC_API_KEY is not set. "
        "Set it in your .env file or environment. "
        "Get your key at https://console.anthropic.com/",
        file=sys.stderr,
    )
# Validate Anthropic key format (warn, don't block — key may be valid in other formats)
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
}
_DEFAULT_FAST_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "ollama": "llama3.1",
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

# Context management
COMPACT_THRESHOLD = 120_000  # tokens — start compacting at this level

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

# Project paths
PROJECT_DIR = Path(__file__).parent.parent
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
SESSIONS_DIR = PROJECT_DIR / "sessions"
LOCAL_WORKFLOWS_DIR = PROJECT_DIR / "workflows"
LOG_DIR = PROJECT_DIR / "logs"
