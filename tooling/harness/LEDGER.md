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

[2026-06-10] H2 · Confirmation · C-R3 + C-R4 + C-R11 + C-R13 FIXED — caching wave BUILT; race won
            by the class-scoped fetch · verified_by V1 (live ComfyUI :8188 throughout) ·
            branch perf/h2-caching-bundle @ ea7237f (worktree G:\Comfy-Cozy-h2, base master 3a939bc) ·
            A-CACHE-RESET → holds TRUE (autouse _reset_shared_caches: engine cache + object_info
            cache + discover memo)
    baseline  re-measured same-day ×3 with the committed instrument (tooling/harness/latency/
            bench_h2.py @ f9d1465): cycle 7191/7241/7524 ms (validate1 med 3707, validate2 med
            3533 — zero reuse), poll warm 158–179 ms, import 433–545 ms. (Absolute numbers below
            the Jun-09 12.6 s record — different ComfyUI session state; race scored against THIS
            baseline, same instrument, band ≈4.6%.)
    race    two legs per §4b, one commit each. Leg A (TTL full-payload cache, 90eebe9):
            cycle 3562 ms med (re-validate 0.2 ms; validate1 unchanged). Leg B (class-scoped
            per-class GETs over the same TTL cache, 100fe80): cycle 238.6 ms med. B promoted.
    champion  final tree ×3 fresh processes: cycle 461–491 ms (−93.4% vs baseline; first
            validate carries the DEFERRED stage import ~250 ms after C-R13 — honest
            redistribution, total still −93%), re-validate 0.1–0.2 ms, poll warm 0.29–0.33 ms
            (−99.8%, C-R4 pooled adapter client), cold import 188–199 ms (−59%, C-R13
            importer-side lazy stage; agent/stage/** untouched — freeze respected, git diff
            master -- agent/stage/ EMPTY). discover legs concurrent + 120 s memo (C-R11; live:
            first 0.44 s both sources, repeat ~0 s). install/uninstall invalidate the cache.
    eval_signal_fired  reproduce: validate2 ≈ validate1 (no cache, ×3); poll pays fresh-client
            setup every call. clean: probes above. Output-equivalence probe: validate JSON
            byte-identical master-vs-branch (sorted), clean template AND injected-missing-node
            case; invalidation probe cold2/warm+0/invalidate+1.
    suite   4464 passed / 0 failed ×2 (forge + independent verifier run), ruff clean agent/+tests/.
            38 tests realigned to the new true edge (comfy_api._get / pooled adapter client) —
            assertions unchanged; 8 prior accidental-passers now pass for the right reason;
            seam test still real-producer→real-consumer.
    targets  doc §5: first-pass validate <7 s → 0.47 s ✓ · re-validate <0.5 s → 0.0002 s ✓ ·
            per-poll <5 ms → 0.3 ms ✓ · cold import ≈200 ms → ~195 ms ✓.
    push    NOT pushed — RED tier, awaiting Joe's word. 9 commits f9d1465..ea7237f.

[2026-06-11] H4 · Confirmation · C-R10 + C-R12 FIXED — persistence wave BUILT · verified_by V1 ·
            branch fix/h4-persistence @ eb798d3 (worktree G:\Comfy-Cozy-h4, base master 3a939bc) ·
            3 commits: 0060c6e (C-R10a+CANON) · 003fc10 (C-R10b) · eb798d3 (C-R12, incl. the
            cross-group metrics-test fix: __name__-less test-double tolerance in the dispatcher)
    C-R10a  experience JSONL: append_to() writes ONE fsync'd line per run (probe: 407 B/run,
            O(1)) instead of the full-snapshot rewrite (10.9 MB/run); save() gains fsync and
            doubles as compaction every max_chunks appends (file bounded ~2x max_chunks; load()
            already truncates). quality.source / is_rule_era / exclude_rule_era round-trip
            verified. Torn-tail appends are safe (load skips malformed lines — pre-existing).
    C-R10b  NIM warm-state: _STATE_LOCK spans read-prune-rewrite (probe: 4 threads x 10 writes
            = 40/40 records, lost-update closed); prune via the existing WARM_MAX_AGE_S
            predicate, WRITE PATH ONLY (read-purity pin tests/manual/test_nim_lifecycle_unit.py
            :136-147 green unmodified); flush+fsync before os.replace (session.py:286-288
            pattern); transient read failure now RAISES instead of silently truncating history
            (the un-ledgered wipe hazard found by scout). 5 new write-path tests.
    CANON-EXPFILE  RESOLVED. Real fork was autonomous.py:38 (~/.comfy-cozy) vs config.py:210
            (~/ComfyUI) — the ledger's "config.py:161 and :210" loci were WRONG (161 is
            COMFYUI_DATABASE). Canon: agent/config.py EXPERIENCE_FILE is THE constant;
            cognitive resolves lazily via _default_experience_file() with the fallback ALIGNED
            to ~/ComfyUI (no agent.* import — boundary held); create_default_pipeline(
            experience_path=None) + AutonomousPipeline carries the path (save/load asymmetry
            closed); session_context injects str(EXPERIENCE_FILE); drift-stopper test pins
            convergence. supersedes [autonomous.py import-time constant ; pipeline/__init__
            EXPERIENCE_FILE re-export (dropped, zero external importers)].
            Residual (documented): COMFYUI_DATABASE="" (empty string) still diverges
            (config Path("") vs resolver or-fallback) — pathological, not scheduled.
    C-R12   download_model: Range resume from the .download partial (header rides every hop of
            the re-validated redirect walk; 206 appends with the SHA hasher seeded from the
            partial — provisioner.py:271-359 pattern ported inline, frozen path untouched; 200
            restarts; 20 GB cap counts offset+new). Transient failures (Timeout/ConnectError)
            KEEP the partial; security/integrity failures still unlink. Progress emitted per
            1 MB chunk via ProgressReporter (schema promise now true). Informed confirm with
            ZERO pre-consent network: host/destination/model_type/resume state in the payload;
            exists-check hoisted above the gate. DESIGN TRADEOFF: no pre-confirm size probe —
            the no-network-before-consent pin (test_provision_confirm_defense
            stream.assert_not_called) outranks informed-size; size surfaces via progress
            post-approval. Dispatcher: signature-aware progress forwarding (per-module cache,
            tolerates __name__-less test doubles) replaces try/except-TypeError — the
            re-execution hazard (a TypeError from INSIDE a confirmed download would have
            re-run the full fetch) is gone. ESCALATE auto-block now echoes safe identifying
            inputs (url/filename/name, 120-char cap); "auto-blocked" pin intact.
    suite   4492 passed / 0 failed x2 on the identical final tree (master baseline 4464; +28 net
            new tests incl. 13 download-resume, 5 nim write-path, 5 append_to, 3 canon).
            Scoped ruff clean. Freeze: git diff master -- agent/stage/ EMPTY.
    test-pollution fix  the suite previously WROTE THE DEVELOPER'S REAL experience store on
            every run (~56 pipeline.run() sites, scout finding) — autouse _isolate_experience_file
            fixture redirects the resolver to tmp_path; canon test opts out via an import-time
            real-function reference.
    leads   L-VERIFYSHA (V0, code-read): _verify_sha256 comfy_provision.py:243 orphaned by the
            incremental hasher — delete or re-point in H5 docs/cleanup pass, probe-first rule
            applies. L-CONFIRM-ENVDEP (V0): test_provision_confirm_defense destination assert
            depends on the real MODELS_DIR not containing example.safetensors (pre-existing
            pattern, now slightly extended; hermetic twins exist in test_download_resume.py).
    push    NOT pushed — RED tier; H2's "push it" word covered PR #66 only. Awaiting Joe's word
            for fix/h4-persistence.

[2026-06-11] H2-MERGE+H4-PUSH · Confirmation · H2 is ON MASTER; H4 is PUBLIC · verified_by V1
    merged  PR #66 (H2 caching wave) by Joe's explicit word — merge commit, master now ac841cb.
    union   origin/master (ac841cb) merged INTO fix/h4-persistence @ a6aa26a; one conflict
            (tests/conftest.py — both waves added an autouse fixture at the same anchor; both
            kept). Union suite: 4492 passed / 0 failed. Scoped ruff clean.
    pushed  fix/h4-persistence (4 commits incl. the union merge) on Joe's "keep going on H4"
            (interpretation stated aloud: the named blocker was the push word) — brightline
            scan read clean PRE-push (run from the main checkout: the scanner + pre-push hook
            are git-excluded and DO NOT EXIST in worktrees; pushing from a worktree would
            silently skip the guard — standing rule, also hit in H2). PR #67 opened.
    supersedes [H4 entry "push NOT pushed" line]

[2026-06-11] H4-MERGE · Confirmation · H4 is ON MASTER · verified_by V1
    merged  PR #67 (persistence wave) by Joe's explicit word — merge commit, master now 0b1a37a
            (carries H2 + H4 + the conftest both-fixtures union). PR CI was 7/7 green pre-merge.

[2026-06-11] CI-HONESTY · Confirmation (CI evidence PENDING the #68 run) · doc-3.4 build PUSHED ·
            branch ci/stage-layer-honesty @ f6da63e · PR #68 · L-MISC-d PROMOTED to build
    change  one file (.github/workflows/ci.yml): install .[dev,stage] (stage extra existed,
            CI never used it; usd-core 26.5 ships cp310-cp314 wheels both platforms — verified
            on PyPI pre-build); explicit "from pxr import Usd" step (no relapse to
            green-by-skip); 3.13 added to the matrix (advertised-never-tested); 
            test_provisioner.py un-ignored (probe: 33/33 with usd-core; the ignore existed
            because collection ERRORED without it).
    caveat  ubuntu legs execute the 21 stage test files for the FIRST TIME in #68's checks —
            a red leg there is the purchase working, fix-forward.
    lead    L-STALE-DISCOVERY (V1, reproduced locally): tests/integration/test_discovery.py
            patches comfy_discover._search_civitai which no longer exists — skips in CI
            (comfyui_available fixture, no server) and FAILS locally with ComfyUI running.
            Stale since the discover refactor; fold into H5.

[2026-06-11] CI-HONESTY-2 · Confirmation · #68's first run DID ITS JOB — 4 ubuntu legs green
            (21 stage files + 3.13 executed for the first time ever), 4 windows legs red on two
            surfaced-not-caused failures · verified_by V1 (CI logs + local reproduce)
    root    ONE root, two symptoms: installing usd-core un-skipped the POSIX-only subprocess
            e2e test of the file-watch memory adapter (tests/integration/ — exact file in PR
            #68's CI logs; os.kill with signal.SIGKILL at :161 — AttributeError on Windows,
            reproduced locally); its mid-test crash left the adapter armed, which intercepted
            a later test's mocked knowledge-file read ("delta ingest failed ... MagicMock/...")
            so the expected debug log never fired (test_system_prompt_metadata caplog assert).
    fix     CI test step now runs -m "not integration" — the pyproject marker definition's OWN
            prescription; CI's previous green relied on every integration test happening to
            skip. Local scoped suite 4464/0. Commit 32ba81b (amended from a flagged local-only
            commit — see incident below). Stage tests are not integration-marked; the honesty
            purchase stands.
    incident  the brightline guard FLAGGED MY OWN ci.yml comment (it named the e2e subsystem
            while narrating the failure). Per the standing relabel-is-bypass rule: HALTED,
            handed to Joe with options; Joe ratified (c) = drop the narrative from public
            artifacts, keep the mechanical fact, story lives HERE. The flagged commit was
            local-only/unpushed → amended (no published history touched), full-range re-scan
            clean, pushed with hook silent. RULE REFINED: agent-authored prose in public
            artifacts must not name bright-line subsystems even when describing failures —
            cite the ledger entry instead.
    leads   L-SIGKILL-E2E (V1, reproduced local+CI): the adapter e2e test's :161 os.kill(pid,
            signal.SIGKILL) is POSIX-only — fix is proc.kill() (cross-platform); also the
            crashed test leaves the adapter armed (missing try/finally teardown) — that state
            leak is what broke the bystander. Both forge-eligible in H5; the file is a manual
            pre-ship test per CLAUDE.md so master is not blocked.

[2026-06-11] CI-HONESTY-MERGE · Confirmation · the CI-honesty build is ON MASTER · verified_by V1
    merged  PR #68 by Joe's explicit word after 9/9 green (8 matrix legs + review bot) — master
            now 79a6fa5. The stage layer is no longer green-by-skip: 21 stage test files +
            test_provisioner (33) execute on every leg, with an explicit pxr import step; 3.13
            tested on both platforms; integration tests excluded explicitly per the marker
            definition. Hardening doc §4 item 3 CLOSED. Residual husk: G:/Comfy-Cozy-ci
            directory held by a file lock post-deregistration — inert, delete when released.

[2026-06-11] TC · Confirmation · L-MISC-a PROBED TRUE then FIXED + C-R6 FIXED — timeout-coherence
            wave BUILT and PUSHED (standing word: "when ready commit & push") · verified_by V1 ·
            branch fix/timeout-coherence @ e1a6cbb (base 79a6fa5) · PR #69 · doc §4 item 4
    L-MISC-a→V1  blanket wait_for(120.0) at mcp_server.py:356-359, worker thread ORPHANED on
            expiry (uncancellable; side effects land after the client is told failure). WORSE
            than recorded: execute_with_progress 300 s / install 245 s worst / nim_run ~1200 s
            cold all unreachable; execute_workflow's 120 s default TIES the kill so its graceful
            status:"timeout"+prompt_id payload could never surface; the :353-355 comment claiming
            downloads "handled separately" was FALSE (time-unbounded by design, byte-bounded).
    fix-a   _tool_time_budget(name, args): dynamic budgets honor caller timeouts (clamp 24 h),
            download_model=None (unbounded; 30 s per-read liveness), vision stays 120 (inner 90
            must keep winning — pinned), default 120 retained. Budget is a WAIT not a kill —
            documented. Message states budget + background-completion caveat. Source-grep test
            → 9 behavior tests. 12-case probe all-OK.
    fix-b   C-R6: connect gains max_size=16 MiB (1 MiB default closed 1009 on big previews;
            recv_bufsize was a read-chunk knob — no-op for the cap, verified) + ping_timeout=60;
            mid-stream ConnectionClosed/OSError → EngineConnectionError (TimeoutError stays
            first in the chain — OSError subclass since 3.10, sentinel contract pinned);
            nim_run polls /history under the SAME phase deadline on WS death instead of failing
            a queued run (monitoring="polling_fallback" + ws_error, mirroring comfy_execute);
            warm-state in fallback recorded ONLY when the WARMUP→COOKING flip was observed
            (fabricated warm times could false-fail later cold pulls).
    refinements  comfy_execute ALREADY had the mid-stream polling fallback (C-R6's "no polling
            fallback" applies to nim_run only — record corrected); connect-TIME failures were
            already translated; installed websockets is 16.0.
    suite   4507 passed / 0 failed ×2 (master baseline 4492; +15 net new). Ruff clean. Freeze
            diff empty. Scan clean pre-push; hook silent.
    leads   L-COG-WS-FALLBACK (V1, test-pinned): cognitive/tools/execute.py has the same
            no-fallback WS behavior, PINNED by test_execute_websocket_unreachable — changing it
            is a deliberate contract change, H5 candidate. L-MANUAL-COLLECTED (V1): tests/manual/
            IS collected by default runs (testpaths=["tests"], no collect_ignore) — the "manual"
            label is aspirational; tidy in H5. L-FALSE-COVERAGE (V1): TestToolErrorProtocol's
            _direct() coroutine is never awaited — vacuous test, H5.

[2026-06-11] TC-CI · Confirmation · PR #69 (timeout coherence) 9/9 GREEN · verified_by V1 ·
            merge awaiting Joe's word.

[2026-06-11] EXR · Confirmation · doc-3.7 EXR ingestion BUILT and PUSHED (standing word) ·
            verified_by V1 · branch feat/exr-vision @ d05f5b3 (base 79a6fa5) · PR #70
    finding-refined  the doc's failure model was incomplete: big EXRs hit the 5 MB guard with
            wrong advice, but SMALL EXRs sailed to the API mislabeled image/png (suffix map
            defaulted unknowns, vision.py:180) and failed opaquely; the "deliberate pass-
            through" branch actually served gif/webp only. verify_execution auto-feeds the
            first history image into analyze_image with NO extension filter — a SaveEXR node
            triggered the failure every verified run.
    build   agent/brain/exr_ingest.py: exposure → AP1→Rec.709 (header chromaticities ≈ ACEScg,
            1e-3 tol; absent = Rec.709 per spec) → clip → sRGB EOTF → PNG; flows through the
            EXISTING downscale+guard. Data-pass refusal (channel-naming message). Unknown
            suffixes error actionably (closes the mislabel class). hash_compare converts too.
            vision_cache sandbox-validates cache-key reads (scout-found gap, fixed in-wave).
            New extra exr=[openexr>=3.3] (wheels VERIFIED cp310-313 win+linux; numpy
            transitive — NOT core); CI installs .[dev,stage,exr].
    probed-API  OpenEXR 3.4 probed by execution pre-forge: File(header, {"RGB": Channel(arr)});
            channels() groups RGB by default; header() is LIVE-BOUND to the open handle (the
            AP1 decision must happen inside the context — forge's test caught the silent-skip).
    suite   4504 passed / 0 failed ×2 (+12 new); independent probes: sRGB 0.5→188 exact, clip,
            data-refusal, AP1-tagged vs untagged diverge. Ruff clean; freeze diff empty; scan
            clean; hook silent.
    leads   L-EXR-CP314 (V1, PyPI): openexr has NO cp314 wheel (3.4.12 stops at cp313) — re-
            check before any 3.14 matrix entry; openimageio/opencolorio already ship cp314.
            L-OCIO-STRETCH (V1, PyPI): opencolorio 2.5.2 wheels cp39-cp314 both platforms,
            builtin ACES configs since 2.2 — the show-config transform is buildable when
            wanted. L-METADATA-EXR (V0): write_image_metadata is PNG-only (image_metadata.py
            :266) — EXR metadata embedding is T0.1 manifest territory, post-freeze.

[2026-06-11] EXR-CI · Confirmation · PR #70 9/9 GREEN (exr extra installed on all 8 legs) ·
            merge awaiting Joe's word. PR #69 also 9/9 green, same state.

[2026-06-11] SPEND-LIMIT · DeadEnd · the lock-wave scout workflow died on the monthly subagent
            spend limit — BOTH scouts refused before reading a byte. Continued SOLO inline
            (scout+forge+crucible by the orchestrator directly); quality gates unchanged.
            RULE: when delegation is unavailable, the wave slows but the Floor does not bend.

[2026-06-11] LOCK · Confirmation · doc-3.8 workflow.lock BUILT and PUSHED (standing word) ·
            verified_by V1 · branch feat/workflow-lock @ 00a36b6 (base 79a6fa5) · PR #71 ·
            built SOLO (spend limit — no subagents)
    build   agent/tools/workflow_lock.py (no new MCP tool → no gate surface): save_workflow
            writes <name>.lock.json pinning model SHA-256s (resolution under MODELS_DIR;
            field knowledge REUSED from model_compat._extract_models_from_workflow), installed
            pack git commits (pure .git/HEAD reads incl. detached + packed-refs), live
            comfyui_version (system_stats field verified live = 0.24.0), workflow sha256.
            validate_before_execute appends drifted-since-lock WARNINGS (explicit path or the
            session's loaded_path); no sidecar = silence — provenance, not a gate. Hash cost:
            (path,size,mtime_ns) in-process cache + prior-sidecar reuse (re-save never
            re-hashes — test pins ONE sha256 call); validate re-hashes only on stat change
            (touched-but-identical stays quiet). Lock failure never fails the save.
            conftest _reset_shared_caches clears the hash cache (A-CACHE-RESET house rule).
    suite   4505 passed / 0 failed ×2 (+12 new). Ruff clean; freeze diff empty; scan clean;
            hook silent.
    deferred  save_session integration (own store shape; same helper callable later).
            Model-dir rglob fallback on network shares is per-save, first-save only — if a
            floor hits it, an index cache is the known next step.

[2026-06-11] LOCK-CI · Confirmation · PR #71 9/9 GREEN · three PRs now merge-ready on Joe's
            word: #69 (item 4), #70 (item 5), #71 (item 6).

[2026-06-11] POOL-DESIGN · Confirmation (design; forge PARKED on #69 merge — same engine files,
            no unauthorized PR stacking) · doc §4 item 7 scouted SOLO · verified_by V1
    finding  friendlier than recorded: circuit_breaker.py ALREADY has a named registry
            (get_breaker(name), :127-141; COMFYUI_BREAKER() = get_breaker("comfyui"), :150) —
            per-host breakers are a KEYING change. get_engine caches per name
            (engine/__init__.py:51-81); adapter reads config at construction (the documented
            seam for a url override).
    design  COMFYUI_ENDPOINTS env (empty default = single-endpoint, byte-identical);
            COMFYUI_BREAKER(url=None) keys per host; ComfyUIAdapter(url=None); EndpointPool
            (agent/engine/pool.py) as an IAIEngine delegating to the first endpoint whose
            breaker allows, failing over on EngineConnectionError/Unavailable — the breaker's
            OPEN/HALF_OPEN/recovery_timeout IS the health check (no new prober). Farm
            adapters (Deadline-class) stay a Lead per the doc's own ordering.
    test-plan  failover A→B; per-host breaker isolation; HALF_OPEN recovery re-admits A;
            single-endpoint a-is-b identity pin holds; conftest breaker reset extended to the
            registry without breaking the existing attr-reset fixture.

[2026-06-11] POOL · Confirmation · doc-3.5 endpoint pool BUILT and PUSHED (standing word) ·
            verified_by V1 · branch feat/engine-pool @ 53f04a0 (base 79a6fa5) · PR #72 ·
            built SOLO · supersedes [POOL-DESIGN "parked on #69" — revised: #69's adapter
            hunks (connect/_events) are textually disjoint from the pool's (__init__/_breaker);
            union merge-down at merge time, H4 precedent]
    build   COMFYUI_ENDPOINTS (empty default = byte-identical single-endpoint);
            COMFYUI_BREAKER(url) keys the EXISTING registry per host (a keying change, as
            scouted); ComfyUIAdapter(url=None) — default keeps the SHARED breaker so gate
            wiring + conftest resets see what they always did; EndpointPool (IAIEngine):
            failover on EngineConnectionError/Unavailable, breaker cycle IS the health check
            (OPEN endpoints fast-fail with zero network — spy-proven), HALF_OPEN re-admits.
            JOB AFFINITY: prompt_id+client_id pinned (FIFO 256) at queue; history/ws/interrupt
            route to the queueing worker; pinned calls authoritative (never silently ask the
            wrong worker). Aggregate mirror into the shared breaker keeps the gate's
            system-health meaning in pool mode. Farm adapters stay a Lead (doc's own ordering).
            conftest breaker reset extended in place to comfyui:* names (identity preserved).
    suite   4504 passed / 0 failed ×2 (+12 new). Ruff clean; freeze diff empty; scan clean;
            hook silent.
    note    doc §4 order: ALL EIGHT ITEMS now either merged (1-3) or green-in-review
            (4=#69, 5=#70, 6=#71, 7=#72 pending CI) except item 8 (H5 lead conversion),
            which is the closing round over the banked leads.

[2026-06-11] RELEASE-5.2.0 · Confirmation · v5.2.0 "The Production Floor" PUBLISHED (Joe's
            explicit release instruction) · verified_by V1
    shipped  master fa4a970 (release-prep commit, scan clean, hook silent): README diagrams
            now show the object_info TTL cache node, class-scoped GETs, pooled engine client,
            append-only fsync'd experience store, ~1 ms cached re-validate in the fix loop;
            TL;DR gains measured edit-loop + durable-learning bullets; test counts 4,490+;
            CI-matrix honesty sentence; CHANGELOG gains 5.2.0 AND a backfilled 5.1.0 (the
            GitHub release existed with no changelog entry); pyproject+__init__ 5.0.0→5.2.0;
            description 113→129 tools. Tag v5.2.0 pushed; GitHub release created (notes =
            measured claims only, merged-work only; the four green PRs listed as in-review).
            Repo description refreshed (126→129 tools + the new headline capabilities).
            Docs branch (this ledger) pushed through the per-commit guard — the evidence
            trail the PR bodies cite is now publicly reachable.
    scope-discipline  #69-#72 stay OUT of the release/diagrams — not merged, not claimed.
            Untracked local scratch (logs, quarantine, RSI/harness working files) deliberately
            NOT committed.

[2026-06-11] MERGE-TRAIN-2 · Confirmation · #69→#70→#71→#72 ALL MERGED by Joe's explicit word ·
            verified_by V1 · master dbf1349 · combined-tree check (H1-MERGE precedent): the
            four-wave union was never CI'd as one tree → full suite locally on merged master:
            4544 passed / 0 failed. Doc §4 items 1-7 ALL ON MASTER.

[2026-06-11] H5 · Confirmation · LEAD-CONVERSION ROUND COMPLETE — every banked lead probed,
            fixed, or parked with disposition · verified_by V1 · branch fix/h5-lead-conversion
            @ 85537f2 (base dbf1349) · PR #73 · built SOLO
    fixed (all reproduced live first)
      L-PIPESTAT     wrong producer key (C-P0-1 class): producer missing_count=1 while status
                     said "ready"; key fixed + fabricated mocks realigned. 51 tests green.
      L-INJECT-VALIDATED  injected graph inherited prior consent (flag True after injection,
                     live); loader clears unconditionally (sibling GATE-flip hazard closed);
                     regression pin added.
      L-MISC-b       three defects reproduced: WAN 2.2 (2.1-only pattern → generalized);
                     mysd15_style_sdxl→sd15 (boundary check + latest-position-wins replaces
                     alphabetical first-match); unknown-family silent pass → surfaced via
                     unknown_models+message. Verdict stays compatible:true for unknowns —
                     full fail-closed would false-block community models; RATIFIABLE OPTION
                     left to the board, recorded here.
      L-SIGKILL-E2E  REFINED: the SIGKILL AttributeError fired INSIDE the teardown finally,
                     aborting adapter.stop() — that abort WAS the bystander-breaking state
                     leak. proc.kill() fix; the e2e test now passes ON WINDOWS (1 passed).
      L-FALSE-COVERAGE  rewritten to drive the REAL CallToolRequest handler (the old version
                     targeted an attribute that never existed — vacuous from birth);
                     SDK-side input validation discovered+documented in the test.
      L-STALE-DISCOVERY  four rotten patch targets + a response-object _get mock (parsed-JSON
                     since H2) realigned; models-summary hermetic (tmp MODELS_DIR).
      L-CONFIRM-ENVDEP  hermetic via patched MODELS_DIR.
      L-VERIFYSHA    orphan deleted + its direct unit test (behavior covered by the seeded-
                     hasher tests in test_download_resume.py).
      DIRECTION.md drift (H1.2 residue, :78 + :243 region) → confirm-gated canon text.
      L-MANUAL-COLLECTED  docstring now states the truth (collected by the default suite).
    parked (disposition recorded; probe named)
      L-PANEL        needs a live browser session — its own adversarial run, not half-done
                     solo; the four named symptoms stand as the probe list.
      L-COG-WS-FALLBACK  test-pinned contract; change requires ratification.
      profiles-consult (doc 3.10 second half)  loader is a parameter-profile system keyed by
                     exact model id, not a filename→family registry — design change, not a
                     defect; pairs with a future family-registry if wanted.
      L-MISC-c compaction orphan (self-heals, agent-run only) · L-EXR-CP314 · L-OCIO-STRETCH
                     · L-METADATA-EXR (stretch/informational).
    suite   4544 passed / 0 failed ×2 on the freshly merged base; realigned integration tests
            pass LIVE; ruff clean; freeze diff empty; scan clean; hook silent.
    DONE    per the science harness §8 finish line: A-SEAM true · A-CACHE-RESET true · caching
            champion promoted · vision + persistence Confirmations on master · every Lead
            converted or parked-with-probe. The hardening doc's §4 order: items 1-7 merged,
            item 8 = PR #73 in review.

[2026-06-11] CLOSE-THE-LOOP · Confirmation · THE HARDENING ORDER IS COMPLETE AND SHIPPED ·
            verified_by V1 · pre-approved capsule executed by Joe's word
    #73     one windows-3.11 leg failed on the file-watch adapter's malformed-delta unit test
            in tests/test_cozy_persistence.py (exact id in the #73 CI logs) — adjudicated
            FLAKE before merging: file untouched by H5 (only adapter-adjacent change is the
            integration-deselected e2e teardown, which cannot execute in CI), 3 sibling
            windows legs green same run, 20/20 local stress, rerun 9/9. MERGED → master
            11c4ea0. Lead L-FLAKY-DELTA (V1, one observed CI failure): timing-sensitive
            poll-interval test on slow runners — probe = stress on a throttled runner;
            candidate fix = marker-wait with generous deadline instead of fixed sleeps.
    shipped v5.3.0 "Shot-Ready" @ 23e1319: README/TL;DR + architecture diagram (EndpointPool,
            per-host breakers, 1..N workers, workflow.lock store) + validate-flow drift label +
            counts 4,540+ + CHANGELOG 5.3.0 + version/description bumps; tag + GitHub release
            (notes: merged-work only, evidence-trail pointer); repo description refreshed.
            Scans clean; hooks silent throughout.
    cleanup worktrees -tc/-exr/-lock/-pool/-h5 removed (merged); -rel removed post-release;
            -ci husk STILL file-locked (deregistered, inert — delete when the handle drops).
            ComfyUI left RUNNING (Joe's dev server — not mine to stop).
    state   doc §4: ALL EIGHT ITEMS MERGED. Science-harness finish line crossed (H5 entry).
            Open horizons, banked: L-PANEL adversarial pass (own session, probe list named);
            post-2026-06-16 stage-freeze lift opens [RFC-stage] (in-module lazy imports — the
            ~250 ms first-validate stage-import cost noted at H2 is its first customer);
            L-COG-WS-FALLBACK awaits ratification; model_compat full fail-closed is a board
            option; L-FLAKY-DELTA above. Mile 8 of 8.

[2026-06-11] L-PANEL · Confirmation · the banked UI-panel dimension PROBED + partially FORGED ·
            verified_by V1 · branch fix/l-panel-hardening @ b3991ea (base master 3ac78e9, after
            amend for a disclosure reword) · COMMITTED, push pending Joe's per-call word
    probe   5-way adversarial fan-out (no spend-limit this run, Opus 4.8). Converted 6 cap-killed
            V0 findings into precise verdicts.
    forged (V1, tested)
      A  /agent/* bridge routes were UNAUTHENTICATED mutation surface (push_workflow replaces
         every tab's canvas; canvas_changed seeds the buffer the agent trusts) while every
         /comfy-cozy/* route was gated. bridge_auth_failure() = the audited Origin-first gate
         (browser same-origin; non-browser Bearer when token set), lifted to module level so it
         is pure-unit-testable; agent httpx clients send the token. 6 tests, no live ComfyUI.
      B  raw str(e) reached the rendered chat at 5 chat/WS sites (the "~30 leaks" framing was
         WRONG — panel REST already clean). safe_error_message() keeps exc_info server-side.
         The panel-chat test that PINNED the leak ("API down" in message) now pins the FIX
         (raw text absent) — a real site-level reproduce→clean for B, not just the helper.
    refuted "MCP_AUTH_TOKEN 401s the bridge" — FALSE (routes were never gated; defect was the
            opposite). Recorded so it is not re-litigated.
    parked forge-ready (NOT blind-forged — Floor)
      C streaming-not-rendered + D tab-switch-drop: real, both in the LIVING sidebar.js, both
        browser-render-bound; exact diffs recorded. E ~60KB dead modules: real but the flagged
        appMode.js is the half-built CORRECT streaming path (entangled with C) and is documented
        — deleting it would foreclose C's cleaner fix, so NOT deleted. All in
        docs/L-PANEL_ADVERSARIAL_PASS_JUNE_2026.md. Probe = a browser session + the sidebar-vs-
        appMode architecture call (named).
    suite   4550 passed / 0 failed. Ruff clean on touched files (one pre-existing E401 in
            panel/__init__.py left untouched — not in the CI lint path, surgical-changes rule).
    incident  the brightline guard flagged MY OWN RFC prose naming a bright-line subsystem in a
            tracked doc (the I5 invariants line). NOT a relabel-to-bypass: removed the
            unnecessary codename from generic design prose (neutral seam language — the
            sanctioned tracked-artifact rule), amended the LOCAL-ONLY commit, range re-scan clean.
            ALSO: the worktree's pre-COMMIT hook did not fire (let the flagged commit land
            locally); the pre-PUSH hook + manual --range scan are the backstop that caught it.
            Lead L-WORKTREE-HOOK: confirm core.hooksPath pre-commit fires from worktrees, or the
            pre-push hook is the sole guard there.

[2026-06-11] L-PANEL-MERGE+LIVE · Confirmation · PR #74 MERGED + live bridge V1 · verified_by V1
    merged  PR #74 (L-PANEL auth+errors + RFC-001) by Joe's word, master dd73543. CI: prior
            commit 9/9 green; harness-commit re-run still in-flight at merge (only added a
            non-collected tooling script + a doc) — tag/release GATED on its green conclusion.
    live    bridge_live_verify.py drove the three canvas-bridge capabilities through the
            AUTH-GATED tools against live ComfyUI 0.24 (the real risk of an auth change is the
            agent 401-ing ITSELF — disproven): push_workflow_to_canvas reloads the canvas ✓;
            an edited seed (13371337) round-trips canvas_changed→get_canvas_state ✓; the
            no-token default path confirms bridge_auth_headers()=={} is non-breaking. Capability
            3 (per-node timing): route works (clean 404), but the capture was EMPTY on the STALE
            installed node pack. A /ws probe proved ComfyUI 0.24 emits the exact events the
            bridge observes (execution_start/executing/execution_success, all with prompt_id),
            so it is a stale-install/observer issue, NOT PR #74 (which never touched
            profiling.py). Installed node pack REFRESHED to the auth-gated version (active on
            the next ComfyUI restart). Lead L-BRIDGE-PROFILE: re-run after restart; if still
            empty, the send_sync observer must intercept 0.24's actual broadcast path.
    release v5.3.1 "Panel Hardening" SHIPPED: merged-CI concluded success (9/9); master 183a611,
            tag v5.3.1, GitHub release live, description gains "Origin-gated canvas bridge".
            README bridge diagram + Origin/Bearer gate node + security note; counts 4,550+.
            Worktrees -panel/-rel2 removed; only the main checkout remains. ComfyUI left running
            (installed node pack refreshed; restart activates the gate + L-BRIDGE-PROFILE probe).

[2026-06-11] RFC-001 · Confirmation · stage-freeze pass = DESIGN, forge GATED to 2026-06-16 ·
            freeze-legal · docs/rfcs/RFC-001-stage-dag-drop-networkx.md (on fix/l-panel-hardening)
    finding networkx is a 323ms (measured, -X importtime) CORE dependency with EXACTLY ONE
            consumer repo-wide — agent/stage/dag/engine.py, a 6-node graph whose topology is
            hardcoded and whose topological order is a compile-time constant. The validate path
            pays it on first validate (the cost H2/C-R13 deferred as [RFC-stage]).
    proposal drop networkx entirely (replace the DiGraph with the static order tuple it always
            returns) → −323ms first-validate, −1 core dep for every install, ZERO behavior
            change. §3 is the diff, §5 is the gate. Lazy-import alternative REJECTED (build_dag
            is called right after import, so it helps nothing on the validate path).
    freeze  agent/stage/** is FROZEN until 2026-06-16 (today is 06-11) → RFC only; NO forge.
            git diff master -- agent/stage/ EMPTY. The RFC is forge-ready for the lift.

[2026-06-10] H2-DEADEND · DeadEnd · reflexive `git stash` in the FORGE worktree mid-CRUCIBLE
            stashed the uncommitted test realignments and invalidated an in-flight suite run ·
            caught same-minute, `git stash pop` restored the identical 7-file diff, realignments
            committed (ea7237f), suite re-run clean. RULE: in a harness worktree, commit before
            any state-mutating git side-step; never run bare `git stash` as a scratch no-op.

[2026-06-27] HARNESS-BOOT · Confirmation · cozy-improve self-improvement harness scaffolded ·
            verified_by V1 · .claude/workflows/cozy-improve.workflow.js
    what    A Workflow-tool epoch script that ports SYNAPSE-derived architectural improvements
            into Comfy-Cozy, one ratcheted human-mergeable branch per item. Fuses SYNAPSE's
            FORGE 6-phase cycle (Cartographer→Architect→Forge→Crucible→3×Skeptic→Scribe, with
            builder≠breaker tool boundaries: read-only roles run agentType Explore) with this
            harness's LEDGER + champion ratchet + cozy_loop durability semantics.
    ratchet pure JS predicate (sole accept authority): tests≥baseline AND no new failures AND
            failed≤baseline_failed; ruff clean; bench null→neutral else delta_median AND
            delta_p95 ≤ NOISE; determinism_ok AND within_blast_radius AND ¬frozen_zone_touch;
            <2 of 3 skeptics refute. Bench-driven ACCEPTs replicate before champion promotion.
    safety  agents have NO push/reset/rebase capability; Scribe git verbs = add|commit|tag on
            forge/<id> only. .githooks/pre-rebase added (COZY_HARNESS-gated); the pre-existing
            brightline pre-push guard is untouched. Frozen agent/stage/** → RFC-only, surface not halt.
    note    WAVE=1 epochs run in-tree on a dedicated branch (no worktree) to dodge the
            editable-install resolution pitfall; worktree isolation engages only at WAVE>1.

[2026-06-27] CANON-CHAMPION · Canonical · single source of champion truth · supersedes: [fork]
    question  two champion artifacts exist: harness/champion.json (latency baselines, warm-BGE
              ~50× first-recall win) and tooling/harness/CHAMPION.md (per-track narrative). A
              third, tooling/harness/champion.json, did NOT exist — risking a silent fork.
    answer    harness/champion.json is the READ-ONLY latency baseline ORACLE. Architectural-
              improvement champions live in tooling/harness/champion.json (created this epoch,
              baseline tests_passed=4540 / tests_baseline_failed=1). The Scribe stage writes
              ONLY the latter. The CHAMPION.md narrative remains human-readable commentary.

[2026-06-27] L-RECIPE-SYSTEM · Lead · zero-LLM Recipe layer (SYNAPSE routing/recipes port) ·
            forge-FORBIDDEN until the Cartographer probes it to a Confirmation
    claim   Comfy-Cozy has no deterministic pre-LLM macro layer. The CLAUDE.md "Artistic Intent
            Translation" table (8 rows) and agent/knowledge/common_recipes.md (~6 graphs) are
            de-facto recipe specs the LLM re-derives every turn. SYNAPSE routing/recipes/base.py
            (Recipe/RecipeStep + $var dataflow) is the missing deterministic producer of the
            EXISTING agent/schemas/intent/default.yaml IntentSpecification.
    grounding (V1 seams, this session) set_input(node_id, input_name, value);
            connect_nodes(from_node, from_output:int, to_node, to_input); add_node(class_type,
            inputs)→node_id; CLI insertion after agent/main.py:351; @find source =
            workflow_patch._get_state()["current_workflow"]. Every recipe step routes through
            tools.handle() so the existing pre_dispatch_check gate vets it — no second gate path.
    probe   the Cartographer reads these loci + SYNAPSE routing/recipes/base.py and flips this
            Lead to a Confirmation; epoch-1 then forges agent/recipes/ + apply_recipe + the wire.

[2026-06-27] C-RECIPE-SYSTEM · Confirmation · L-RECIPE-SYSTEM forged + verified · verified_by V1
            supersedes: [L-RECIPE-SYSTEM] · branch forge/recipe-system-epoch1 (commit pending)
    built   agent/recipes/{base,builtin,__init__}.py (engine: ParamMutation/ToolStep/$var/@find,
            never-hard-fail fall-through), agent/tools/recipes_tool.py (apply_recipe + list_recipes
            MCP tools), registered in agent/tools/__init__.py, classified READ_ONLY in
            agent/gate/risk_levels.py (dispatcher — inner steps re-enter handle() and self-gate),
            CLI pre-check wired in agent/main.py behind config.RECIPES_ENABLED (default OFF —
            purely additive). 7 built-in recipes from the CLAUDE.md intent table + common_recipes.md.
    gate    reproduce→clean V1: 16 new tests in tests/test_recipes.py (engine + gated MCP surface)
            all green; FULL suite `pytest -m "not integration"` = 4568 passed / 0 failed / 2 skipped
            (the one known Windows SIGKILL baseline test did not fire this run); ruff clean on
            touched files. Tool count 131→133: both assertions updated (test_tools_registry,
            test_mcp_server) + CLAUDE.md count/table. bench=null (feature port) → ratchet neutral.
    safety  every recipe step dispatches through tools.handle() so the EXISTING pre_dispatch gate
            vets it — no second gate path, no bypass. Every change reversible (undo_workflow_patch).
            Frozen agent/stage/** untouched; moe_dispatcher untouched.
    ratchet ACCEPT (testsGreen ✓ lintClean ✓ benchOk ✓[null] noRegress ✓ notRefuted ✓). champion
            track recipe-system promoted (deterministic feature → no replicate needed). PR body at
            tooling/harness/forge/PR_recipe-system.md. awaiting_human_merge — harness never pushes.

[2026-06-27] C-R7-DEADEND · DeadEnd · forge/C-R7 fix for C-R7 (install into ComfyUI
            python_embedded, not the agent venv) REFUTED despite an all-green suite — the ratchet
            notRefuted gate FAILED · verified_by V1 (Crucible measured a62dd66; ratchet input) ·
            C-R7 stays OPEN, fix PENDING (supersedes nothing)
    direction  C-R7 = install_node_pack runs bare `pip` from PATH → agent venv, not ComfyUI
            python_embeded (comfy_provision.py:552-567). Forge a62dd66 [FORGE C-R7] routed the
            install into ComfyUI's python_embedded on Windows ([python,-m,pip,...] pattern).
            Touched ONLY agent/tools/comfy_provision.py + tests/test_comfy_provision.py
            (+155/-11, 2 files — git show --stat a62dd66).
    measured  Crucible on a62dd66: pytest -m "not integration" → 4571 passed / 0 failed / 2 skipped
            (baseline 4568 @ recipe-system; +3 new tests, NO regression); ruff clean on both
            touched files; determinism_ok; within_blast_radius; frozen_zone_touch=false; bench=null.
    ratchet   REJECT — testsGreen ✓ lintClean ✓ benchOk ✓[null] noRegress ✓ but notRefuted ✗.
            Per the ratchet predicate (HARNESS-BOOT entry, this log: "<2 of 3 skeptics refute" to
            pass), notRefuted=false ⇒ ≥2 of 3 skeptics refuted. Refutation class = ADVERSARIAL
            (skeptic) refutation, NOT a mechanical gate — green on tests/lint/bench yet refuted on
            the merits.
    disposition  build DISCARDED. Branch forge/C-R7 @ a62dd66 LEFT IN PLACE for human inspection
            (not deleted; master @ 183a611 not reset). Champion NOT promoted —
            tooling/harness/champion.json UNTOUCHED. C-R7 remains an OPEN finding; THIS approach is
            closed. awaiting_human_merge=false.
```

[2026-07-02] V2-E0A · Confirmation · E0a closed: permission scrub + PR #76 merged @ a74b4c1
            after TWO H4 union rounds · verified_by V1 (local suites + merged CI 9/9)
    scope   v2 program green-lit 2026-07-01 (plan + budget defaults + mechanical auto-merge
            grant; plan file external — see v2/STATE.json plan_file). E0a: owner scrubbed
            .claude/settings.local.json (egress allows removed; deny layer added for
            push/remote/reset/rebase/release/api/auth/curl/wget) — deny layer live-verified.
            Untracked triage: 20 flagged + 7 noise -> .git/info/exclude (never commit, never
            delete; deletions queued as owner gate). Stale v2/main archive-tagged @ 93a94af.
    unions  master moved TWICE mid-flight. Round 1: v5.3.1 merged @ 61fe043 (1 conflict —
            CLAUDE.md count headline -> measured union 133 = 84+22+27; suite 4686/0).
            Round 2: v5.4.0 Brain Swap (PR #75) merged @ a0c3b25 (5 conflicts, all the
            same-content-different-commits class; suite 4686/0). Both push ranges scan-clean;
            CI 9/9 green; PR #76 merged on owner word.
    process per-commit + pre-push guard fired silently throughout; scan-clean recorded per
            standing rule; owner executed all pushes.

[2026-07-02] V2-E0B · Confirmation · E0b runway artifacts complete on v6/e0b-runway
            (base a74b4c1) · verified_by V1 (measured locally; CI recomputes on the PR)
    scope   verify_ratchet.py — 7-check mechanical accept authority; known-flake tolerance
            BY NAME (subset check), never by count; baseline decreases only via
            baseline_deltas.jsonl rows citing LEDGER IDs. Hooks hardened: pre-push
            default-deny remote classifier (spoof-tested: lookalike-named public repos still
            scanned); pre-commit fail-closed on absent scanner; bypass advice removed from
            hook text. Strict partition census (v2/census.json BINDING; make_census.py
            asserts it): 133 = 69 keep + 21 merge-away + 25 delete + 11 provisioning +
            4 scene + 3 nim -> 75 core (+ping), 28 aliases, 25 tombstones, 2 new names.
            ORCHESTRATOR_v2.md constitution §1-§10 incl. §10 recursion contract (Utility
            Track: Tier A/B/C — recursion stops at the judge). v2/ state files seeded.
            .claude/settings.local.json UNTRACKED from index + gitignored (machine-personal
            permission state; its pre-scrub history remains public — accepted, documented).
    measured baselines re-pinned @ a74b4c1: floor 4685 (4686 measured − 1 named-flake
            allowance) / collected 4687 / import 334.0 ms median-of-3 / registry 133.
            Identical content measured twice: 4686/0 (union-2 run) + 4686/0 (--baseline run).
    leads   L-IMPORT-DELTA partially resolved: pre-union branch 553.5 ms (lacked the H2 perf
            wave); union restored lazy-stage registration -> 334.0 ms; residual vs the
            188-199 ms champion methodology stays open. Collected-vs-executed off-by-one
            (4687 vs 4688) consistent across trees — parked.
    disposition PR_E0b teed; standing push grant recorded 2026-07-02 (owner pre-approved
            "push it"; the keystroke stays owner's via the deny layer — by design).

[2026-07-02] V2-E0B-R1 · Confirmation · E0b skeptic round 1 REFUTED 3/3 (proper function
            of the panel: it refused the accept authority's own birth certificate);
            re-plan bounce executed per §7 · verified_by V1 (all fixes measured locally)
    refutations (18 findings: 2 BLOCKER, 6 MAJOR, 10 MINOR — highlights)
            B1 judge lens: thresholds were branch-writable — verify_ratchet ran from
            master's copy but read baselines/known-flakes from the CANDIDATE tree;
            check_deltas failed open when 'original' absent; --baseline reset the
            reconciliation anchor (self-laundering). B2 correctness lens: the pinned
            flake node id was WRONG (missing ::TestCrashResume::) — the name-based
            tolerance could never fire; every flake day would have halted the program.
            M: disclosure scan silently SKIPPED=ok on plain --check while the
            constitution prescribed plain --check; pytest ERRORS never checked;
            counts parsed from injectable stdout; standing push grant recorded in
            agent-readable files contradicting the constitution's own no-grants-from-
            files rule, with three files disagreeing about G2.
    fixes   ratchet v2: thresholds read from origin/master's baselines copy with
            byte-integrity check (divergence must reconcile via delta rows, else
            refuse; bootstrap labeled); flake authority = in-script constant with
            collect-time existence assertion; counts from pytest junit XML (uuid
            scratch path) — errors==0 required, error/failure node ids matched
            against flakes; scan range auto-derived origin/master..HEAD, fail-closed;
            --brightline skip reserved for CI with disclosure_certified=false in the
            verdict; --baseline preserves 'original' (re-seed = --reset-original,
            Joe-reviewed); sentinel-guard refuses writing garbage baselines; ruff via
            interpreter module; import budget enforced same-node only (reported
            elsewhere). Constitution §4 rewritten (authority model; baselines.json
            added to frozen set; hooks untracked-by-design honesty; CI-green-does-
            not-certify-disclosure), §6 G2/G3 defined precisely (executor always
            owner's keystroke; grants-in-files descriptive never operative; auto-merge
            pinned to enumerated ids; threshold-touching commits disqualified).
            STATE.json: statuses derived honestly (E1/E2 blocked on E0c), E8 depends
            enumerated, plan referenced by sha256 not machine path. Filename-level
            disclosure hygiene in GATES/BACKLOG prose per the composition rule.
    process the panel consumed ~240k tokens and returned in 12 minutes; the two
            BLOCKERs were real, mechanically verified, and pre-merge — the cost of
            NOT running it would have been an autonomous program governed by a
            gameable gate with an inert flake tolerance.
