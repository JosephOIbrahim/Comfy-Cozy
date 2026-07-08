## v5.6.0 — Production Hardening

Turns an external production-readiness audit into a verified fix set. The advertised
`pip install -e ".[dev]"` + `pytest` command now runs with **zero errors** (it used to
throw 27), model swaps to current-generation Claude no longer 400, installs are
deterministic, and the repo finally has a security-disclosure path.

### Fixed
- **F-S1** — `.[dev]` test promise: 27 collection errors → clean skip (`pytest.importorskip("pxr")` guard; the audit's "unguarded import" diagnosis was wrong — the errors were fixture setup).
- **F-API1** — model-swap 400 trap: the thinking-config gate was a frozen allowlist, so Opus 4.8 / Sonnet 5 / Fable 5 fell through to the legacy `budget_tokens` shape those models reject with HTTP 400. Inverted to a legacy denylist; new models now work unmodified.
- **F-S2** — deterministic installs: `uv.lock` committed; the self-contradicting `requirements.txt` (omitted `networkx`, cited a nonexistent `[mcp]` extra) deleted.
- **F-S3** — cross-platform `agent doctor`; retires the Windows-only, `G:\`-hardcoded `_find_comfyui.ps1`.
- **F-S4** — honest MCP docs: the unshipped SSE/`--sse` transport promise removed (stdio-only; `MCP_AUTH_TOKEN` protects the panel/UI/bridge HTTP surfaces, where it is enforced).
- **F-API2** — dead example model ids fixed (`claude-sonnet-5` / `claude-opus-4-8`).
- version metadata drift: `agent/__init__.py` was `5.4.0` while pyproject said `5.5.0`; both now `5.6.0`.

### Added
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` — drafted and adversarially red-teamed.
- `agent doctor` diagnostic (offline-safe; tests cover the ComfyUI-down path).
- mypy in CI (non-blocking; baseline 126 errors, ratchet to blocking when clean).

### Changed
- README + reading materials: ADHD-friendly TL;DR pass, `agent doctor` woven through setup, Community section, adaptive-thinking label in the provider diagram.
- 24 working docs moved to `docs/archive/` (root: 32 → 11 markdown files).
- Counts trued: 84 intelligence / 133 dispatched tools; test count corrected to the verified **4,640+**.

### Verified
Independent fresh-venv run (`.[dev,stage,exr]`, Python 3.13): **4,646 passed / 0 failed / 0 errors**, ruff clean, `uv lock --check` clean, `agent doctor` exits 0 offline. The `.[dev]`-only path (the audit's broken promise) runs **4,236 passed / 0 errors**.

The `Development Status :: 4 - Beta` classifier and the Patent-Pending block are untouched — those are separate human decisions, not part of this SemVer bump.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
