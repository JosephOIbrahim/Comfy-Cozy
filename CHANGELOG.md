# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- End-to-end integration test suite (`tests/test_e2e_pipeline.py`)
- Release workflow (`.github/workflows/release.yml`)
- This changelog

## [3.1.0] - 2026-04-03

### Added
- Multi-provider LLM abstraction (Anthropic, OpenAI, Gemini, Ollama)
- Panel chat WebSocket with real streaming conversations in the sidebar
- Bidirectional canvas bridge -- agent mutations appear on ComfyUI canvas live
- 23 new panel routes (18 to 50 total) for discovery, provisioning, repair, sessions
- Auto-wire intelligence (`wire_model`, `suggest_wiring`)
- Unified provisioning pipeline (`provision_model`, `provision_status`, `provision_verify`)
- Quick actions bar in APP mode (Repair, Save, Browse, Wiring)
- Model browser overlay with CivitAI + HuggingFace search
- Self-healing workflow status bar with repair/migrate buttons
- Queue Prompt button in panel header
- Rate limiting + auth middleware on all panel routes
- Health check with ComfyUI + LLM provider status
- Execution progress streaming over WebSocket
- 42 LLM provider tests, 19 middleware tests, 6 health tests
- Shared test fixtures (`conftest.py`)
- `LOG_FORMAT=json` env var for structured logging

### Changed
- Rebranded from "Super Duper" to "Comfy Cozy"
- Removed all Pentagram design references
- Panel routes now return generic errors (no more `str(e)` leaking)

### Fixed
- 12 production hardening fixes (XSS, unbounded structures, atomic writes, etc.)
- CI green across 6 matrix combos (Python 3.10-3.12, Ubuntu + Windows)
- Cross-platform test fixes (httpx mocks, path assertions, cache timing)

### Security
- XSS sanitizer with HTML tag allowlist in panel markdown renderer
- 10 MB request size limits on all POST routes
- Bearer token authentication (optional, via `MCP_AUTH_TOKEN`)
- Rate limiting per route category (execute, discover, download, mutation, read)

## [3.0.0] - 2026-03-31

### Added
- Initial Comfy Cozy release (renamed from comfyui-agent)
- 113 tools across intelligence, brain, and stage layers
- Panel UI with APP and GRAPH modes
- CivitAI and HuggingFace model search
- Workflow delta patching with LIVRPS composition
- Vision analysis (Claude Vision API)
- Session persistence and experience learning
- Cognitive architecture: planner, memory, MoE router, orchestrator, foresight
- USD-native stage layer with non-destructive delta composition
- Pre-dispatch safety gate (5-check pipeline)
- Graceful degradation with kill switches
- 2350+ tests, all mocked

### Changed
- Bumped version to 3.0.0 for production release

## [0.2.0] - 2026-02-19

### Added
- Brain layer with 27 tools (planner, memory, MoE router, orchestrator, verify, refine)
- Stage layer with USD cognitive state
- Model profile registry (Flux, SDXL, SD 1.5, LTX-2, WAN 2.x)
- Creative metadata layer: intent capture, iteration tracking, PNG embedding
- Pipeline engine, 3D/audio discovery, planner templates
- Rich CLI with progress indicators
- GitHub releases integration
- Proactive surfacing of relevant models and nodes
- Web UI design system with rich text renderer
- Sidebar workflow context injection
- 796 tests

### Fixed
- He2025 determinism violations (sorted iteration, stable tiebreakers)

## [0.1.0] - 2026-02-10

### Added
- Initial release: ComfyUI Agent with all 5 phases complete
- 40+ tools across UNDERSTAND, DISCOVER, PILOT, VERIFY phases
- MCP server for Claude Desktop integration
- Workflow loading, parsing, patching with full undo
- Node discovery and model search (CivitAI, registry)
- Execution with progress monitoring (HTTP polling + WebSocket)
- Session persistence and outcome recording
- Streaming agent loop with context management
