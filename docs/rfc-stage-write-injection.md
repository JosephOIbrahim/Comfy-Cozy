# RFC (DESIGN-ONLY) — s9: stage_write source/sha256 injection hardening

**Status:** `DESIGN-ONLY — FROZEN (agent/stage, Path D, no forge until Jun 16)`. Item s9 of the provision-hardening harness (parent: mission m0). **No code in `agent/stage/` is mutated by this RFC.**

## Vulnerability (from provision recon)
`agent/stage/stage_tools.py:_handle_stage_write:219-245` writes an **arbitrary `attr_name`/`value` to an arbitrary `prim_path`** with no key allowlist (only optional `node_type` anchor protection). `stage_write` is `RiskLevel.REVERSIBLE` (`agent/gate/risk_levels.py:128`) and prompt-reachable, so a prompt can:
1. `stage_write` `source_url` = an attacker URL **and** `sha256` = the hash of the attacker's own file, onto a `/models/<type>/<name>` prim;
2. call `provision_download`, which reads those attrs (`provisioner.py:129,135`) and "verifies" successfully (`provisioner.py:326-332`) because actual==expected for the attacker file.

So the sha256 integrity check is **defeatable by the same prompt** that chooses the source — the hash provides no protection against a prompt-driven supply-chain swap.

## Proposed fix (when FORGE_ENABLED for stage, post-Jun-16)
Introduce a **protected-attribute policy** in `stage_write`:
1. **Security-sensitive key allowlist/denylist** — writes to `source_url`, `sha256`, and any provisioning-integrity attribute on `/models/...` prims are either (a) rejected from the generic `stage_write` path, or (b) require the same `confirm=true` escalation the keystone uses (treat such a write as code-execution-adjacent, since it steers a later download).
2. **Separate provisioning-registry API** — register model `source_url`/`sha256` only via a dedicated, gated `register_model`-style path (it already exists at `agent/stage/model_registry.py:register_model:106`), and make `stage_write` refuse those keys, so integrity metadata cannot be set through the generic attribute writer.
3. **Trust pinning** — record where each `source_url`/`sha256` came from (operator vs prompt); `provision_download` refuses prompt-set integrity metadata unless confirmed.

## Why frozen
`agent/stage/` is under the Path-D freeze. Forge-ready spec only; edit waits for `FORGE_ENABLED` (post-Jun-16) + operator sign-off.

## Interim mitigation (already live, non-stage)
`provision_download` is keystone-gated (confirm) at entry, so the inject→download chain cannot run unattended. The residual (a *confirmed* operator unknowingly approving a prompt-injected `source_url`/`sha256`) is what this RFC closes. Note s8 (provisioner SSRF) and s9 (this) compound — both should land together when the stage freeze lifts.

**Files (proposed, FROZEN):** `agent/stage/stage_tools.py` (+ possibly `agent/stage/model_registry.py`). **This RFC touches none of them.**
