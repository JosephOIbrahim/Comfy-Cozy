# TRACE — Provision / RCE Hardening (security harness)

Append-only causal log. `parent_id` is the causal predecessor, not wall-clock.
*Note:* the mission spec said `.harness/`; this repo's existing convention is `harness/`
(no dot, where `TRACE.md`/`PLAN.md` already live) — using the repo convention.

**Base:** `master 3279781` (after PR #20 fail-open fix `baf4621`). **Branch:** `sec/provision-hardening`.
**Path D:** FORGE non-stage only (`agent/tools`, `agent/gate`); `agent/stage` = RFC-only; `CLAUDE.md` = propose-only. **No push.**

---

```
span_id:       m0
parent_id:     null
pass:          mission-root
step_type:     plan
input_state:   provision recon — prompt->autonomous-fetch + prompt->RCE; ESCALATE non-blocking;
               pickle allowed; dead host-allowlist; repair_workflow auto_install REVERSIBLE;
               provision_model cross-module gate bypass; stage SSRF/source-injection
action:        ARCHITECT->FORGE->CRUCIBLE per items 1-6 (forge), 7 (propose), 8-9 (RFC);
               keystone (item 1) first, gated
output_state:  base confirmed (master 3279781 carries baf4621); harness started on sec/provision-hardening
verifier:      operator (Joe) — Option A approved; PR #20 merged + confirmed on base
outcome:       success
external_calls: [gh pr merge 20 --merge --delete-branch]
```

```
span_id:       s1
parent_id:     m0
pass:          item-1 (KEYSTONE)
step_type:     forge+crucible
input_state:   gate ESCALATE (PROVISION) fell through at agent/tools/__init__.py:339 ->
               a prompt could auto-trigger download_model / install_node_pack (RCE / autonomous-fetch)
action:        ESCALATE -> needs-confirmation BLOCK (no dispatch) unless tool_input["confirm"] is True;
               a confirmed call falls through to dispatch unchanged
output_state:  agent/tools/__init__.py ESCALATE branch rewritten;
               tests/test_gate_escalate_confirm.py added (6 closure-proof tests)
verifier:      L2 adversarial CRUCIBLE — 45/45 PASS on prod (C:\Python314):
               install_node_pack/download_model BLOCKED without confirm (no dispatch);
               confirmed call dispatches (SSRF/scheme reject — no network/subprocess);
               PR#20 fluid path (loaded-workflow set_input) NOT regressed; uninstall still LOCKED;
               full gate suite (33) + #20 suite (5) green
outcome:       success — HOLE CLOSED (keystone gate passed; mission may proceed)
frozen_or_buildable: BUILDABLE (agent/tools/__init__.py — non-stage)
external_calls: []
```

---

## Spans s2-s9 (post-keystone fan-out) — all parent_id = m0

```
s2  FORGE   commit 6e66ca3  BUILDABLE agent/tools/comfy_provision.py
    enforce _ALLOWED_DOWNLOAD_HOSTS (domain+subdomain) in _validate_download_url (was dead code)
    crucible 4/4: off-allowlist rejected; allowlisted+CDN-subdomain accepted; confirmed off-allowlist download rejected.
    regression: provision/download 209 pass. watch: unlisted CDN domains must be added to the allowlist.

s3  FORGE   commit c949a70  BUILDABLE agent/tools/comfy_provision.py
    block pickle (.ckpt/.pt/.pth/.bin) unless allow_pickle=true; optional expected_sha256 verify (_verify_sha256)
    crucible 4/4: _pickle_blocked default-deny + allow/safetensors pass; sha256 match/mismatch.

s4  FORGE   commit 3e5744c  BUILDABLE agent/tools/comfy_provision.py
    repair_workflow auto-install gated behind confirm (REVERSIBLE-classified + bypasses central gate)
    crucible 3/3 (monkeypatched, no git/pip): no-confirm blocks; confirm installs once; report-only ungated.

s5  FORGE   commit 0011ee8  BUILDABLE agent/tools/provision_pipeline.py (guard-comment) — closed-by-keystone
    provision_model is PROVISION -> already keystone-gated at entry; inner download_model intentionally NOT
    re-gated (would double-prompt); inherits s2/s3 handler hardening.
    crucible 2/2: provision_model blocked without confirm; classified PROVISION.

s6  FORGE   commit ba09d71  BUILDABLE agent/gate/checks.py + agent/tools/comfy_provision.py
    check_scope enforces https-only on url/source_url/download_url keys (were ignored);
    download message no longer claims "available immediately -- no restart needed"
    crucible 3/3 + full gate suite (33) green.

s7  PROPOSE-ONLY (NOT committed)  CLAUDE.md
    qualify "auto-provision ... no stopping to ask" for code-executing ops (download/install now need confirm).
    Awaiting operator constitution sign-off.

s8  DESIGN-ONLY RFC  docs/rfc-stage-provisioner-ssrf.md   FROZEN agent/stage/provisioner.py
    SSRF + host-allowlist + manual-redirect + size-cap. Spec only; forge post-Jun-16.

s9  DESIGN-ONLY RFC  docs/rfc-stage-write-injection.md    FROZEN agent/stage/stage_tools.py
    protected-attribute policy: source_url/sha256 cannot be prompt-set ungated. Spec only; forge post-Jun-16.
```

## Verdict
Prompt->RCE / autonomous-fetch surface CLOSED for the non-stage layer (s1 keystone + s2-s6): no PROVISION op
(download_model / install_node_pack / repair_workflow auto-install / provision_model) runs from a prompt without
explicit confirm; downloads are host-allowlisted + pickle-blocked + hash-verifiable; the gate enforces https on
url keys. Stage-layer residue (s8/s9) is bounded by the keystone confirm until the agent/stage freeze lifts.
No push — consolidated operator review pending; operator decides push/PR.

---

## Follow-up — post-merge live smoke test (Xet allowlist gap)

A live model-download smoke test after PR #21 merged surfaced one gap in s2:
`download_model(confirm=true)` for a public HuggingFace file was rejected at the
redirect — HF now serves `resolve/main/...` via its Xet CDN
(`cas-bridge.xethub.hf.co`), which is not a `huggingface.co` subdomain and so
failed the per-hop host-allowlist. Fix: added `xethub.hf.co` to
`_ALLOWED_DOWNLOAD_HOSTS` (matches `cas-bridge.*` via the subdomain rule) plus a
closure-proof test. The keystone (s1) confirm-block and the per-hop allowlist
re-validation both verified working against merged code during the same test.
s2 watch-item ("unlisted CDN domains must be added to the allowlist") — RESOLVED for HF Xet.
