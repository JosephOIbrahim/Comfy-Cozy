# BUILD_QUEUE.md — Full Pipeline Autobuild

## Tasks

- [x] 1. Register FORESIGHT tools — foresight_tools in __init__.py (95 tools)
- [x] 2. USD Scene Compositor — compositor.py + test_compositor.py (19 tests)
- [x] 3. Scene Validator — scene_validator.py + test_scene_validator.py (12 tests)
- [x] 4. Scene Conditioner — scene_conditioner.py + test_scene_conditioner.py (13 tests)
- [x] 5. Compositor tools — compositor_tools.py + test_compositor_tools.py (14 tests)
- [x] 6. Register Compositor tools — compositor_tools in __init__.py (99 tools)
- [x] 7. Creative Profiles — creative_profiles.py + test_creative_profiles.py (22 tests)
- [x] 8. Injection — injection.py + test_injection.py (20 tests)
- [x] 9. Program Parser — program_parser.py + test_program_parser.py (20 tests)
- [x] 10. Morning Report — morning_report.py + test_morning_report.py (14 tests)
- [x] 11. Autoresearch Runner — autoresearch_runner.py + test_autoresearch_runner.py (15 tests)
- [x] 12. Autoresearch CLI — cli.py updated with --program, --budget-hours, --max-experiments, --report, --resume
- [x] 13. Orchestrate CLI — cli.py updated with scene composition + validation + experience recording steps
- [x] 14. Fix test_health.py mock leak — 4 failing tests (MEDIUM, target 2717 passing)
- [x] 15. Windows grep portability — test_workflow_patch_engine_live.py subprocess→pathlib (LOW, target 2718 passing)
- [x] 17. Item 7 — MiniLM embedder — `agent/embedder.py` exposes `embed(payload: str) -> list[float]` returning 384-dim L2-normalized vectors from `sentence-transformers/all-MiniLM-L6-v2` (lazy-loaded, thread-safe). `requirements.txt` pins `torch==2.5.1` + `sentence-transformers==3.3.1` via `--extra-index-url https://download.pytorch.org/whl/cpu` (CPU-only, no CUDA). `record_outcome` and bridge UNCHANGED. Acceptance test at `tests/embedder/test_minilm_clustering.py` (50 outcomes × 5 themes): MiniLM clusters within-theme >0.4 / between-theme <0.3 / separation >0.15; synthetic hash-based control vectors do NOT cluster (|within−between| <0.05). 3828 passing (3822 baseline + 6 new).
