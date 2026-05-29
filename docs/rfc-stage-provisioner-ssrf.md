# RFC (DESIGN-ONLY) — s8: Stage Provisioner SSRF + size-cap hardening

**Status:** `DESIGN-ONLY — FROZEN (agent/stage, Path D, no forge until Jun 16)`. Item s8 of the provision-hardening harness (parent: mission m0). **No code in `agent/stage/` is mutated by this RFC.**

## Vulnerability (from provision recon)
`agent/stage/provisioner.py:_stream_download:288` opens `httpx.Client(follow_redirects=True)` and streams `source_url` (read verbatim from the model prim at `provisioner.py:129`) with **no SSRF protection, no host allowlist, no size cap, and no per-redirect private-IP re-validation** — unlike the intelligence-layer `download_model`, which `s2` now hardens. `provision_download` (`agent/stage/provision_tools.py:_handle_provision_download:140`) is prompt-reachable (in `_HANDLERS`) and is now keystone-gated at entry (PROVISION→confirm), but once confirmed it fetches whatever `source_url` says with zero network-egress hardening.

## Proposed fix (when FORGE_ENABLED for stage, post-Jun-16)
Mirror the intelligence-layer hardening inside `provisioner._stream_download`:
1. **SSRF guard** — before/at each hop, reject `localhost`, private/loopback/link-local/reserved IPs, CGNAT (RFC 6598), and metadata endpoints. Reuse the logic equivalent to `agent/tools/comfy_provision.py:_validate_download_url` / `_resolve_and_check_private` (consider extracting a shared `agent/net_safety.py` helper consumed by both, so stage and intelligence layers stay in lockstep).
2. **Host allowlist** — enforce the same `_ALLOWED_DOWNLOAD_HOSTS` (domain + subdomain) on the initial `source_url`. (That allowlist must include `xethub.hf.co` — HF's Xet CDN, where `resolve/main/...` now redirects; added to the intelligence-layer allowlist post-#21 after a live smoke test caught the rejection.)
3. **Manual redirects** — `follow_redirects=False` with per-hop re-validation (today's `True` follows blindly).
4. **Size cap** — abort past a hard byte limit (mirror `_MAX_DOWNLOAD_BYTES`, 20 GB).
5. **sha256** — provisioner already verifies a registered hash; keep it, but see s9 (the hash can be prompt-injected).

## Why frozen
`agent/stage/` is under the Path-D freeze. This is a forge-ready spec; the actual edit waits for `FORGE_ENABLED` (post-Jun-16) and operator sign-off.

## Interim mitigation (already live, non-stage)
The keystone (`s1`) confirm-gates `provision_download` at entry, so it cannot run unattended from a prompt. The residual risk (a *confirmed* provision_download fetching an SSRF/oversized target) is bounded by that human confirmation until this RFC is forged. The deeper `stage_write` source-injection that feeds `source_url` is covered by **s9**.

**Files (proposed, FROZEN):** `agent/stage/provisioner.py`. **This RFC touches none of them.**
