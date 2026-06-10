# Comfy-Cozy Science Harness — LEDGER

> Durable memory for the harness (`COMFY_COZY_SCIENCE_HARNESS_v1.md`). Append-only,
> human-readable. This repo's conventions are yours — no schema RFC needed.
> **Lives at:** `G:\Comfy-Cozy\tooling\harness\LEDGER.md`
> **Seeded:** 2026-06-09 from CTO review `wf_2ba4a767-728`.

---

## Conventions

- **Append-only.** New entries land under §APPEND LOG with a date + entry ID. Never edit an
  initial-load entry's verdict in place — supersede it with an appended entry.
- **`verified_by` ∈ {V0, V1, V1-degraded}.** V1 = probed live against the repo + ComfyUI at
  `127.0.0.1:8188`, real producer through real consumer. V0 = doc/README, mocked tests, or a
  cap-killed review finding. V1-degraded = ComfyUI unreachable, claim allowed *with caveat*.
- **A Confirmation of a FINDING ≠ a verified FIX.** The Floor (§4a.2) reserves the word
  "fixed" for *bug reproduced → then clean → V1*. At load, no fix exists. Each forge-eligible
  finding gets its **own** reproduce→clean Confirmation appended when its phase runs.
- **Leads are forge-FORBIDDEN** until a V1 probe converts them to a Confirmation or Assumption.

## Kind legend

```
Confirmation   a probe ran, the signal fired, result recorded
Assumption     a relied-upon mechanism — probe named, holds: true|false|unknown
Canonical      THE answer to a question two artifacts disagree on (supersedes: [...])
DeadEnd        a tried approach that measurably failed (direction + delta + reason)
Lead           surfaced but UNVERIFIED — forge entry forbidden until probed
```

---

## INITIAL LOAD — 2026-06-09

### Confirmations — verified FINDINGS · forge-eligible · fix PENDING its own reproduce→clean

> Verdicts here are V1 by the **review's** live method, pre-cap. The *fix* for each is pending
> the named phase and earns its own Confirmation on reproduce→clean.

```
C-P0-1   repair_workflow reads "missing"; producer find_missing_nodes returns "missing_nodes"
         (+ node_type/pack_title). Repair returns "clean" when nodes ARE missing; mocks hide it.
         locus  comfy_provision.py:1013 ↔ comfy_discover.py:1364 ; mocks test_comfy_provision.py:231-245
         verified_by V1   fix PENDING → branch fix/repair-workflow-contract (H1)
         note   the seam test is required and flips A-SEAM.

C-P0-2   system_prompt.py:24 rule 5 instructs installs "in one continuous flow without stopping
         to ask" — bypasses the needs_confirmation gate. MCP rule fixed; this prompt not.
         locus  system_prompt.py:24,:33 ; gate comfy_provision.py:1040-1070
         verified_by V1   fix PENDING → branch fix/cli-install-gate-prompt (H1)
         note   writes CANON-RULE5.

C-R3     /object_info 4.58 MB / 4.3–4.9 s fetched UNCACHED at 7 sites; per-class 3.3 KB /
         1.4–186 ms (~1400× payload). nim_preflight false-fails → nim_run hard-fails before queue.
         locus  comfy_api.py:243,359,364 (+6 sites)   verified_by V1   fix PENDING → H2 bundle

C-R4     fresh httpx.Client() per engine call, 198–238 ms vs 0.5–1 ms pooled; paid every 1.0s
         poll (~20%/tick). Pooled pattern already at comfy_api.py:24-35.
         locus  comfyui_adapter.py:105,159,191   verified_by V1   fix PENDING → H2 (needs A-CACHE-RESET)

C-R5     vision builds fresh anthropic.Anthropic per call (~0.25–0.29 s + leaked FD); with_options
         ~40 µs. Inner 120 s == MCP 120 s hard kill (vision error can't win); max_retries=2 too.
         locus  _anthropic.py:146-149 ; vision.py:31,211-218   verified_by V1   fix PENDING → H3
         note   with_options + max_retries=0 + _VISION_TIMEOUT→90 s are ONE PR, all required.

C-R6     WebSocket bundle: ping_timeout=20 s kills long model loads; ConnectionClosed escapes
         untranslated (nim_run has NO polling fallback → can waste 900 s); recv_bufsize≠max_size,
         so the real 1 MB cap closes 1009 on previews >1 MB.
         locus  comfyui_adapter.py:229,234,236-256   verified_by V1   fix PENDING → H2/H3

C-R7     install_node_pack runs bare `pip` from PATH → AGENT venv, not ComfyUI python_embeded →
         nodes don't appear though it reports "Dependencies installed successfully."
         locus  comfy_provision.py:552-567   verified_by V1   fix PENDING → H1/H3
         note   COMFYUI_PYTHON probe + [python,-m,pip,...].

C-R8     vision economics: full-res base64; 50 MB guard (~10× API); prompt-cache can never hit;
         cache keys on 64-bit aHash ignoring the prompt → serves the stale "before" analysis.
         locus  vision.py:157-191 ; vision_cache.py:13-96   verified_by V1   fix PENDING → H3
         note   downscale ≤1568 px + guard-to-reality + re-key (SHA-256 of bytes, prompt).

C-R9     misconfig raw-error cluster: no key → SDK jargon; ollama blocked on ANTHROPIC_API_KEY;
         THINKING_BUDGET=high crashes --help with raw ValueError.
         locus  vision.py:209-218 ; cli.py:96-104 ; config.py:112-146   verified_by V1 (reproduced live)
         fix PENDING → H1/H3 (_int_env helper; condition the cli.py:96 gate on provider==anthropic)

C-R10    experience JSONL full 10.9 MB rewrite/run (~11 GB per 1k runs); nim warm-state
         read-all/append/rewrite, never prunes, lost-update race; neither fsyncs (4 modules do).
         locus  accumulator.py:185-238 ; nim_lifecycle.py:101-156   verified_by V1   fix PENDING → H4
         note   see CANON-EXPFILE.

C-R11    discover serial ~45 s worst case (CivitAI then HF); no result cache; never consults
         freshness; full rglob + double stat() per call on shares.
         locus  comfy_discover.py:848-886   verified_by V1   fix PENDING → H2 bundle

C-R12    download_model schema promises progress, emits none (12 GB → silence); no Range resume
         (dies at 95% → restart from 0); confirm omits size/host/dest; exists-check after approval.
         locus  comfy_provision.py:670-847   verified_by V1   fix PENDING → H3/H4

C-R13    ~600 ms of the 896.5 ms cold import is eager stage (networkx 293.6 + pxr ~310), paid by
         every process; brain lazy (55.7 ms) proves the fix.
         locus  agent/tools/__init__.py:31-214   verified_by V1 (-X importtime)   fix PENDING → H2
         note   IMPORTER-SIDE lazy-register ONLY; in-module import moves = [RFC-stage] post-freeze.
```

### Confirmations — verified CLEAR · no action (do not carry as worries)

```
C-CLEAR-CI     "no CI" hypothesis is FALSE — .github/workflows/ci.yml exists (2-OS × 3-Python +
               ruff + pytest).   verified_by V1   no action. (Quality caveat tracked as L-MISC-d.)

C-CLEAR-GATE   pre-dispatch gate is 0.77–5.6 µs/call (116 µs with a path arg), O(1) — 3–4 orders
               below any budget.   verified_by V1 (measured)   no action.
               WARNING: this is gate LATENCY only. Gate CORRECTNESS is L-GATE — unverified.

C-CLEAR-MCP    MCP schema convert 0.08 ms, to_json 0.407 ms, config import 35.4 ms — healthy;
               keep sort_keys.   verified_by V1   no action.
```

### Assumptions — register day one · probes in H0

```
A-SEAM         "repair→discover contract is exercised end-to-end somewhere"
               probe: the H1 seam test (real _handle_find_missing_nodes → repair_workflow,
               HTTP edge-mocked).   holds: FALSE  (C-P0-1 is the proof)   verified_by V1
               → flips true when the seam test lands.

A-CACHE-RESET  "the 4,437-test mocked suite resets cached state between tests"
               probe: H0.2 — inspect the conftest reset surface.
               holds: FALSE  (resets only ContextVar/workflow state)   verified_by V1
               → BLOCKS the H2 merge until an autouse reset fixture exists.

A-GATE-CLOSED  "a broken gate import fails CLOSED"
               probe: H0.1 — force an ImportError on the gate, observe open vs closed.
               holds: UNKNOWN   → gates L-GATE disposition.
```

### Canonical violations — open · write the Canonical in the named phase

```
CANON-EXPFILE  EXPERIENCE_FILE defined twice with different defaults → learning can silently
               FORK across two files.
               loci  config.py:161 and :210 ; live consumer panel/server/routes.py:493
               supersedes [both defs] — ONE canonical in H4 (create_default_pipeline(
               experience_path=None) lazily; keep the config constant).   verified_by V1

CANON-RULE5    CLAUDE.md rule 5 and system_prompt.py rule 5 are drifted copies of one rule
               (the P0-2 root).
               supersedes [both texts] — ONE canonical text in H1; the other generated from or
               asserted against it.   verified_by V1
```

### Leads — QUARANTINED · forge FORBIDDEN until a V1 probe converts them

```
L-GATE     severity: P0-ADJACENT if true.   verified_by V0 (cap-killed).
           Gate fails OPEN + silent (`except ImportError: pass`); 3/5 checks vacuous (handle()
           never wires breaker_state/validated/action_history); 9/129 tools default to
           REVERSIBLE incl. GPU-executing nim_run; "Cycle 64: was missing" comment = prior
           drift evidence (same class as the PR #21 ESCALATE fix).
           FREEZE-ADJACENCY: UNKNOWN — the gate is import-coupled to the stage package.
           probe: H0.1 — must ALSO answer "does the fix touch agent/stage/**?"
              dispatch-layer only  → promote to Confirmation as P0-3, slot into H1
              reaches stage internals → PARK until 2026-06-16 freeze lift

L-PANEL    the entire UI-panel dimension — ALL cap-killed (V0):
           token streaming wired but never rendered (typing dots for the whole reply);
           tab-switch mid-turn drops/truncates the reply; MCP_AUTH_TOKEN silently 401s the
           browser canvas bridge; 523-line panel chat backend with no living frontend +
           ~50 KB dead modules; node_pack /agent/* routes escaped the route-auth audit;
           raw str(e) leaks into chat.
           probe: H5 adversarial pass (the review's own §6 instruction). Forge FORBIDDEN until then.

L-MISC     mixed bag:
           (a) MCP blanket 120 s wait_for contradicts tools' own timeouts (renders/downloads
               exceed it → reported failure while the orphaned thread keeps working). V0.
           (b) model_compat unanchored regexes mis-classify, WAN 2.2 unrecognized, unknowns
               silently pass; profiles YAML never consulted. Verifier REACHED it ("trap" noted). P2.
           (c) compaction can orphan tool_result at the 120k boundary. Verifier DOWNGRADED
               severity (roles alternate, self-heals, agent-run only). P2.
           (d) CI green-by-skip: usd-core never installed → 21 stage files SKIP; test_provisioner.py
               hard-ignored; dev runs 3.14, CI tops at 3.12, 3.13 advertised never tested.
               Appears V1 (stated definitively in the appendix).
           probe/disposition: H5. (d) may promote earlier as a CI-config build.
```

---

## APPEND LOG

> Entries land here as H0→H5 run. Template:
> `[YYYY-MM-DD] <ID> · <kind> · <one line> · verified_by <V0|V1|V1-degraded> · <disposition>`

```
[2026-06-09] H0.1 · Confirmation · gate FAILS OPEN on a broken import — live, two vehicles ·
            verified_by V1 · supersedes A-GATE-CLOSED (now holds FALSE) + promotes L-GATE → C-P0-3 (H1)
    probe   imported real agent.tools, drove real handle(), nulled sys.modules["agent.gate"]
            in-process to force the ImportError at __init__.py:254, re-ran the same calls.
    result  set_input (REVERSIBLE): intact → "Gate denied 'set_input': No active session…";
            gate broken → "input_name is required." (handler ran — verdict gone).
            reset_workflow (DESTRUCTIVE→LOCKED): intact → "…destructive operation and requires
            explicit confirmation."; gate broken → "No workflow is open…" (handler ran).
            FAIL_OPEN flags both true. Even a LOCKED tool dispatches when the import breaks —
            __init__.py:380 `except ImportError: pass` is the swallow. GATE_ENABLED=True confirmed.
    3-of-5  the live set_input denial cites ONLY consent (session) + reversibility (undo) — the
            two checks handle() wires; system_health/constitution/scope ran on defaults. Vacuous
            wiring confirmed against the static read (handle() passes session_active + has_undo only).
    rev-def 129 known tools, 121 explicitly classified, 9 fall to the REVERSIBLE default:
            delete_node, nim_preflight, nim_run, nim_state, provision_pipeline_status,
            provision_pipeline_verify, refresh_model_registry, replace_node, rewire_around.
            nim_run ∈ set ✓ (GPU-executing on the same fail-open path). REFINES L-GATE: the risk
            is wider than nim_run — delete_node/replace_node/rewire_around mutate graph structure
            and provision_pipeline_* touch provisioning, all under-classified as plain REVERSIBLE.
    DECISIVE (freeze-adjacency): every L-GATE fix lives in agent/tools/__init__.py (fail-closed at
            :380; wire the 3 unwired checks) and agent/gate/** (classify the 9 in risk_levels.py;
            DECOUPLE the stage import at checks.py:16 — removing a coupling, NOT editing stage).
            NO fix touches agent/stage/** internals → DISPATCH-LAYER-ONLY. L-GATE clears the
            2026-06-16 freeze → promote to Confirmation C-P0-3, slot into H1.

[2026-06-09] H0.2 · Confirmation · conftest reset surface does NOT cover the engine singleton ·
            verified_by V1 · A-CACHE-RESET holds FALSE (refined) · BLOCKS H2 merge
    probe   read all 3 autouse fixtures in tests/conftest.py; grepped tests/** for the reset hook;
            confirmed get_engine() identity live.
    result  conftest resets: _conn_session (ContextVar), COMFYUI_BREAKER (circuit breaker →
            _state="closed"/_failure_count=0), workflow_patch state (deepcopy snapshot/restore).
            It does NOT reset agent.engine._engine_cache — get_engine() a is b == True
            (memoized ComfyUIAdapter singleton). A real _reset_cache_for_tests() hook exists at
            engine/__init__.py:94 but NO fixture calls it (only per-test patch() mocks in
            tests/manual + a doc ref). No /object_info cache exists to reset (every validate
            re-fetches — see C-R3 / H0.3). Refines the seed ("only ContextVar/workflow state"):
            the breaker IS reset; the engine singleton is NOT.
    disposition  H2 merge stays BLOCKED until an autouse fixture wires _reset_cache_for_tests
            (and any future object_info cache) — the C-R4 pooled-client fix would otherwise leak a
            warm client across the mocked suite and mask regressions.

[2026-06-09] H0.3 · Confirmation · baseline split ×3 (cold+warm) + noise band · verified_by V1
    method  cold = fresh venv312 process; warm = same-process repeat. ComfyUI live at :8188 (HTTP
            200, 5 ms) → true V1. Reference workload = agent/templates/txt2img_sd15.json (7 nodes).
    import agent.tools : cold 470.5 / 489.4 / 535.8 ms (band ~65 ms ≈ 13%); warm ~0.0006 ms
            (sys.modules cache). NOTE: lower than C-R13's 896.5 ms — different instrument
            (-X importtime cumulative vs wall-clock perf_counter); does NOT contradict C-R13.
    per-poll (_poll_completion → engine.get_history round-trip): cold 220–229 ms; warm 173–191 ms
            (band ~18 ms ≈ 10%). Confirms C-R4: fresh httpx.Client per call, ~19–23% of every 1.0 s tick.
    validate→fix→re-validate : full cycle 12 577 / 12 647 / 12 134 ms (band ~510 ms ≈ 4%).
            validate_before_execute ≈ 6 072–6 514 ms EACH; fix (set_input) 0.3–0.6 ms.
            DECISIVE: validate2 (warm) ≈ validate1 (cold) — re-validate gets NO speedup because
            no /object_info cache exists (C-R3). The agent's core edit loop pays ~6 s twice per fix.
    noise band  all three metrics ≤ ~13%; measurements stable enough to ratchet against in H2.

[2026-06-09] H1.1 · Confirmation · C-P0-1 FIXED — repair_workflow reads the live producer contract ·
            verified_by V1 · branch fix/repair-workflow-contract @ 79b830f (base 3152063) · A-SEAM → holds TRUE
    eval_signal_fired  reproduce: live ComfyUI, template + fake node; find_missing_nodes reported
            missing_count 1 (status missing_nodes) while repair_workflow said "clean"/0. clean:
            same probe post-fix → status "report", missing_count 1, node listed; default call
            still confirm-gated (needs_confirmation; nothing installed; confirm never passed).
    fix     4 lines in _handle_repair_workflow: missing→missing_nodes, class_type→node_type,
            pack_name→pack_title, with None-coercion (producer emits null pack_title/pack_url
            for unresolved). Wrong-shape mocks realigned in 3 test files (none weakened; one
            vacuous installer test strengthened). Seam test tests/test_seam_repair_discover.py:
            REAL producer→REAL consumer, mocked only at true IO edges, install-spy proves 0
            installs → A-SEAM flips TRUE.
    caveat  this machine has no ComfyUI-Manager registry, so the pack-resolution leg of the
            clean evidence used a temp registry fixture at the registry FILE edge (object_info
            stayed fully live). Disclosed by forge, independently re-derived by the verifier.
    suite   4430 passed ×2 (forge + independent verifier), ruff clean.

[2026-06-09] H1.1-LEAD · Lead · L-PIPESTAT — provision_pipeline.py:_handle_provision_pipeline_status
            (~:309) reads report["missing_nodes"].get("missing") — the SAME wrong key against the
            same producer; pipeline status can never report missing nodes from real data; its
            mocks (test_provision_pipeline.py:93-99) fabricate the same wrong shape ·
            verified_by V0 (code-read during the C-P0-1 forge; NOT probed live) ·
            forge FORBIDDEN until a probe converts it — slot the probe into H5 (or fold into any
            provision-pipeline work earlier; the seam-test standing rule applies to it too).

[2026-06-09] H1.2 · Confirmation · C-P0-2 FIXED — rule 5 now mirrors the canonical confirm-gated flow ·
            verified_by V1 · branch fix/cli-install-gate-prompt @ a6bf3ea (base 3152063) · CANON-RULE5 WRITTEN
    eval_signal_fired  reproduce: built the REAL prompt via the public builder — rule 5 contained
            "repair_workflow(auto_install=true) to install … automatically … in one continuous
            flow without stopping to ask". clean: rebuilt prompt — bypass text gone; now carries
            needs_confirmation → show pack list → WAIT for approval → confirm=true only after
            yes → NEVER self-confirm; workflow edits stay continuous, installs do not. One-line
            edit covers BOTH builders (build_system_prompt + build_system_prompt_blocks).
    canonical  CANON-RULE5 RESOLVED: CLAUDE.md "Tool Usage Rules" item 5 is THE text;
            agent/system_prompt.py rule 5 is asserted against it by
            tests/test_system_prompt_rule5.py (bypass-absence + invariant-presence pins).
            Supersedes [both drifted texts].
    residue  docs/DIRECTION.md:78,:243 still carries the old auto-install language (NOT loaded
            into any prompt — docs-only drift; fold into the H5 docs pass). Verifier also noted
            one soft assertion ('confirm' subsumed by 'needs_confirmation'); the strong pins
            ('WAIT for their approval', 'NEVER self-confirm', exact bypass substrings) hold.
    suite   4429 passed ×2 (forge + verifier), ruff clean.

[2026-06-09] H1.3 · Confirmation · C-P0-3 FIXED — gate fails CLOSED; breaker + history wired; 0 unclassified tools ·
            verified_by V1 · branch fix/gate-fail-closed @ f8edd19 (base 3152063)
    eval_signal_fired  reproduce: sys.modules["agent.gate"]=None → set_input AND gate-LOCKED
            reset_workflow both DISPATCHED (handler errors returned). clean: same probe → both
            return "Gate unavailable … denied for safety (gate import failed)"; intact-gate
            denials byte-identical to pre-fix; implicit-default risk list 6→0 on this base;
            LIVE breaker probe: OPEN → "Circuit breaker is OPEN … blocked", reset → write allowed.
    fix     (a) except ImportError → logged DENY (closed means closed — READ_ONLY also dark
            during a gate outage, documented tradeoff); (b) breaker_state wired from the real
            COMFYUI_BREAKER() singleton; (c) per-session action_history wired (registry
            WorkflowSession, capped 50, recorded only on actual-dispatch paths) — behavior-
            neutral today by design, substrate now real; (d) checks.py stage import lazy +
            fail-closed (stage breakage no longer kills the gate package — dispatch-layer-only,
            freeze respected); (e) all tools explicitly classified incl. forward entries for the
            NIM PR (nim_run=EXECUTION, nim_preflight/nim_state=READ_ONLY) + drift-stopper test
            tests/test_gate_completeness.py (subset pin over _HANDLERS ∪ _BRAIN_TOOL_NAMES).
    unchanged-by-design  consent/validated semantics (test-pinned fix-forward, test_gate.py:149)
            — DECISION FOR JOE, parked: re-impose validate-before-execute consent at the gate
            (mechanical enforcement of CLAUDE.md rule 12/14) or keep behavioral-only. Also note
            provision_pipeline_status/verify moved implicit-REVERSIBLE → explicit READ_ONLY
            (handler-verified pure reads; verifier-confirmed; a real but correct behavior delta).
    pinned-behaviors held  tests/test_write_gate_failopen.py green UNMODIFIED; test_gate.py +
            test_gate_escalate_confirm.py green unchanged.
    suite   4433 passed ×2 (forge + verifier; includes 7 new gate tests), ruff clean.

[2026-06-09] H1.4-CANON · Canonical · validate-before-execute consent at the gate: ENFORCE (scoped) ·
            ratified by Joe ("confirmed for 1-4") · supersedes [check_consent docstring (claimed
            enforcement; code never had it) ; test_gate.py:149 fix-forward (pinned non-enforcement)]
    scope   execute_workflow + execute_with_progress when executing the SESSION workflow.
            Exempt by design: explicit "path" override (the session flag does not describe an
            external file) and non-session EXECUTION tools (analyze_image, push_workflow_to_canvas,
            nim_run, …). Flag "validated_since_mutation": set only by a PASSING session
            validate_before_execute; cleared on any REVERSIBLE (mutation-class) dispatch.
            Out of blast radius: agent/harness/cli_callables.py calls comfy_execute.handle()
            module-level — bypasses the central gate; `agent autonomous` unaffected.
    build   branch fix/gate-validated-consent (worktree, base f8edd19) — forge running;
            its own reproduce→clean Confirmation lands when verified.
    also-ratified  item 1: push the three H1 branches (push attempt then BLOCKED by the agent
            permission layer pending more-explicit wording — branches intact, scans clean);
            item 3: L-PIPESTAT stays quarantined, probe in H5; item 4: DIRECTION.md docs drift
            folded into the H5 docs pass.

[2026-06-09] H1.4 · Confirmation · validate-before-execute consent ENFORCED at the gate ·
            verified_by V1 · branch fix/gate-validated-consent @ efc5c92 (base f8edd19) ·
            discharges H1.4-CANON
    eval_signal_fired  reproduce: real handle() chain, gate ON, queue edge spied — execute_workflow
            DISPATCHED with no validation (spy fired; the hole, live). clean: deny with actionable
            reason → validate against LIVE /object_info (valid:true, combo warning only) → allow
            (spy fired once) → one more set_input → deny again. Nothing ever actually queued.
    fix     flag validated_since_mutation set only by a PASSING session validate (path validations
            inert); cleared on every REVERSIBLE dispatch at the will-dispatch point; enforced only
            for execute_workflow/execute_with_progress on the SESSION workflow; "path" override +
            non-session EXECUTION tools exempt. Fix-forward test superseded citing the ratification.
            Blast radius: zero tests drive execution via the central dispatcher; autonomous harness
            bypasses by design.
    suite   4441 passed ×2 (forge + verifier), ruff clean on touched files.
    pushes  fix/repair-workflow-contract, fix/cli-install-gate-prompt, fix/gate-fail-closed PUSHED
            (explicit grant, brightline-clean ×3, hooks silent) → PRs #60 #61 #62, CI 7/7 green
            each, MERGEABLE. Merge attempt BLOCKED by the permission layer (needs Joe's explicit
            "merge"). PR #59 (NIM) CI was failing at the ruff step — 4× E702 in
            tests/manual/test_nim_cold_warm.py — fixed @ 2c66d8e, pushed, CI re-running.

[2026-06-09] H3 · Confirmation · C-R5 + C-R8 FIXED — vision economics bundle ·
            verified_by V1 (real code, SDK edge-mocked at Messages.create, zero network) ·
            branch fix/vision-economics @ 0be9cfc (base 3152063)
    eval_signal_fired  reproduce: distinct clients per call (max_retries=2, timeout=120==MCP kill;
            +40 handles per 20 kept clients), 4000px image sent at full res (40.57 MB encoded),
            50 MB guard, stale-answer cache bug live (prompt B served prompt A's analysis; aHash
            even collided distinct solid-color images), bare-float quality recorded source="".
            clean: with_options shares the base httpx transport (identity-verified), retries 0,
            timeout 90; 1568px / 3.89 MB (-90.4%); 5 MB post-downscale guard; A/B/A-repeat cache
            correct + miss-on-different-image; source="rule" persisted to JSONL; is_rule_era +
            get_successful_chunks(exclude_rule_era=) ready for the Phase-7 evaluator swap.
    notes   cache semantics deliberately exact-byte now (perceptual aHash dropped — documented
            tradeoff); webp/gif pass through undownscaled but still guarded; sibling pattern
            spotted in agent/llm/_openai.py:198 (fresh client per timeout) — same treatment if a
            future finding covers it (H5 candidate). Crucible: 30/30 independent checks.
    suite   4440 passed ×2 (forge + verifier), ruff clean.

[2026-06-09] H1-MERGE · Confirmation · the H1 train is ON MASTER · verified_by V1
    merged  #60 (C-P0-1) → #61 (C-P0-2) → #62 (C-P0-3) → #59 (NIM lifecycle, after the E702 lint
            fix @ 2c66d8e) — all by Joe's explicit word, merge commits, master now 91075b8.
    combined-tree check  the four-PR union was never CI-tested as one tree, so the full suite ran
            against merged master locally: 4443 passed, 0 failures (completeness test sees the
            real nim_* registrations against the gate's forward entries — they reconciled).
    milestone  tag v5.1.0 cut locally at 91075b8 (push pending Joe's word).
    still-open  #63 vision (CI 7/7, awaiting merge word) · #64 readme (merge-order constraint
            satisfied now #59 landed; CI finishing) · #65 consent (opened post-#62, single
            commit efc5c92, CI starting).
    next  H2 cuts from master @ 91075b8 — the caching race has its ratified home and a green base.

[2026-06-09] H1.4-LEAD · Lead · L-INJECT-VALIDATED — load_workflow_from_data (workflow_patch.py:1213,
            the sidebar/MCP graph-injection path) replaces the session workflow OUTSIDE the dispatch
            boundary and does NOT clear validated_since_mutation: a passing validation of the
            PREVIOUS graph could let a freshly injected graph execute once without re-validation ·
            verified_by V0 (crucible code-read during H1.4) · forge FORBIDDEN until probed —
            probe: drive load_workflow_from_data after a passing validate, observe the flag.
            (Sibling note, marginal: the REVERSIBLE clear lives inside the GATE_ENABLED block, so a
            mid-session GATE_ENABLED flip could carry one stale validation through; not reachable
            in normal operation.)
```
