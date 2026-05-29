# RFC (DESIGN-ONLY) — Action 2: wire the BGE embedder into the live MonetaStore relevance ranking

**Status:** `DESIGN-ONLY — FROZEN`. No code on `feature/moneta-memory` is mutated by this RFC.
Forge only **post-Jun-16** (the MonetaStore-wiring deferral) **and** after counsel clears that branch
(patent-coupling: `feature/moneta-memory` is unpushed + counsel-sensitive — never pushed from here).

**Foundation already shipped:** PR #35 swapped the master-scoped embedder
(`agent/embedder.py`) from `all-MiniLM-L6-v2` → `BAAI/bge-small-en-v1.5` (384-dim, L2-normalized,
graceful import, scale-invariant clustering gate). This RFC is the plan to make the *consumer*
(MonetaStore) use that embedder.

## Goal
MonetaStore's `deposit` / `query` relevance ranking runs on the **same canonical BGE embedder** as
the rest of Comfy-Cozy, so cross-session memory retrieval ranks on real BGE semantics — with **one**
embedder/model load, not two.

## Current state (recon'd 2026-05-29, read-only via `git show`)
- **Canonical embedder** — `agent/embedder.py` (master): `embed(str) -> list[float]`, BGE-small-en-v1.5,
  384-dim, lazy thread-safe load, raises a human-readable `RuntimeError` if the `embed` extra is missing.
- **MonetaStore's encoder** — `agent/memory/embeddings.py` (`feature/moneta-memory` only): a **second,
  duplicate** embedder. `MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"`; a `_Encoder` wrapper
  exposing `.encode(text) -> list[float]` (`model.encode(text, convert_to_numpy=True,
  show_progress_bar=False)`); `get_encoder() -> _Encoder | None` (lazy, thread-safe, **swallows load
  failure → returns None**, latched via `_encoder_attempted`).
- **Consumer** — `agent/memory/moneta_store.py` (branch only): `deposit_exchange` → `_encoder.encode`
  → `handle.deposit(payload, embedding)`; `query_relevant` → `_encoder.encode` → `handle.query`;
  `signal_used` → `signal_attention`; `close` → `run_sleep_pass`. Uses the real `moneta` four-op API.
- **Live wiring** — `agent/main.py` (MonetaStore lifecycle in `run_interactive`) +
  `agent/system_prompt.py` (surfaces retrieved memory in the prompt).
- **Branch divergence** — merge-base `2309b41`; **−42** behind master, **+7** unique commits. The +7
  touch: `agent/main.py`, `agent/system_prompt.py`, `agent/memory/{__init__,embeddings,moneta_store}.py`,
  `pyproject.toml`, `scripts/demo_moneta_memory.py`, `tests/test_moneta_store.py`,
  `docs/demo-evidence/moneta-memory-2026-05-15.md`.

## Proposed wiring (forge-time)

**Step 1 — bring the branch current.** Merge `master` into `feature/moneta-memory`.
**Sole conflict: `pyproject.toml`** `[project.optional-dependencies]` — the branch added `[memory]`
(`moneta @ file://…`, `sentence-transformers>=2.2.0`, `allow-direct-references=true`); master added
`[embed]` (`sentence-transformers>=2.2.0`). **Resolution:** keep both extras; have `[memory]` reuse
`[embed]` (or list `sentence-transformers` once and reference it). Every other branch file merges clean
(verified: master did not re-touch them since the merge-base). The branch also gains BGE
(`agent/embedder.py`) + all of today's hardening as a side effect.

**Step 2 — unify the embedder (the actual "wire BGE").** Two options:
- **(a) Minimal:** set `agent/memory/embeddings.py: MODEL_NAME = "BAAI/bge-small-en-v1.5"`. Quick, but
  leaves **two** embedder modules and **two** in-process BGE loads (~2× ~130 MB) — wasteful.
- **(b) RECOMMENDED — single source of truth:** make `_Encoder.encode` delegate to
  `agent.embedder.embed` (the canonical BGE). `get_encoder()` returns a thin adapter over `embed`.
  One model, one load, MonetaStore deposits/queries on BGE automatically; the duplicate MiniLM module
  collapses. **Preserve MonetaStore's disabled-on-failure contract:** `embed()` *raises* on a missing
  backend, but `get_encoder()` must keep returning `None` (latched) — so the adapter wraps `embed` in
  try/except and returns `None` on `RuntimeError`/`ImportError`.

**Step 3 — vector-space migration (load-bearing).** MiniLM and BGE vectors are **not comparable**
(different spaces). Any memories already persisted with MiniLM embeddings must be **re-embedded** (or the
Moneta store reset) at cutover, or queries will rank garbage. `embedding_dim` stays 384 (no schema change).

**Step 4 — symmetric vs asymmetric (A/B at forge-time).** MonetaStore does deposit (passage) + query
(query). BGE's asymmetric retrieval benefits from a query prefix
(`"Represent this sentence for searching relevant passages:"`) on the **query side only**. Master's
`embed()` is symmetric (no prefix). Decide at forge-time: keep symmetric (simpler; the scale-invariant
separation already holds) vs add the prefix on `query_relevant` (potentially better top-k). Bench both on
the demo corpus before committing.

## Verification (forge-time)
- `tests/test_moneta_store.py` (14 mocked cases) stay green.
- `scripts/demo_moneta_memory.py` (cross-session retrieval) re-run on BGE → relevant memories rank first.
- **New test:** `MonetaStore.query_relevant` ranks a same-theme deposit above a cross-theme deposit on the
  real BGE model (the retrieval property — mirrors the master scale-invariant gate, applied end-to-end).
- Master's scale-invariant embedder clustering gate already covers BGE quality upstream.

## Scope / constraints
- **Frozen:** this RFC mutates nothing on `feature/moneta-memory`. Forge post-Jun-16 only.
- **Counsel:** that branch is patent-coupling-sensitive and **never pushed** from this environment without
  Joe + counsel sign-off.
- **Not `agent/stage`:** the wiring is `agent/memory/*` + `agent/main.py` + `agent/system_prompt.py` — none
  under the Path-D `agent/stage` freeze. (The stage `provision_download` SSRF/source-injection RFCs
  `docs/rfc-stage-*.md` are unrelated.)

**Effort estimate:** small once the bring-current lands — Step 1 is a one-file conflict; Step 2 (option b)
is ~1 module; Steps 3–4 are a migration note + an A/B. The risk is concentrated in the cutover migration
(Step 3), not the code.
