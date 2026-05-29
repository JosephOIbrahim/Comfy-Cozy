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

## Items pending (post-keystone)
- s2 item-2: wire dead `_ALLOWED_DOWNLOAD_HOSTS` into `_validate_download_url` — BUILDABLE (comfy_provision.py)
- s3 item-3: safetensors-restrict / pickle-block + sha256/type check — BUILDABLE (comfy_provision.py) [shares comfy_provision seam w/ s2,s6 — serialize]
- s4 item-4: reclassify `repair_workflow(auto_install)` so the inner install gates — BUILDABLE (risk_levels.py + comfy_provision.py)
- s5 item-5: route `provision_model`'s internal `download_model` through the gate — BUILDABLE (provision_pipeline.py)
- s6 item-6: `check_scope` covers `url` keys; fix the misleading "available immediately" message — BUILDABLE (gate/checks.py + comfy_provision.py)
- s7 item-7: CLAUDE.md auto-provision wording — PROPOSE-ONLY (diff, operator sign-off)
- s8 item-8: `provisioner.py` SSRF + size-cap — DESIGN-ONLY RFC (agent/stage — frozen)
- s9 item-9: `stage_tools.py` source/sha256 injection — DESIGN-ONLY RFC (agent/stage — frozen)
