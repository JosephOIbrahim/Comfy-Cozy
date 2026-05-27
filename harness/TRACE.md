# TRACE — Real Semantic Embeddings for comfy-moneta-bridge

Append-only causal log. `parent_id` is the causal predecessor, not wall-clock predecessor.

---

```
span_id:       s0
parent_id:     null
pass:          0
step_type:     plan
input_state:   operator brief B (semantic embeddings, first-run harness validation)
action:        Draft + ratify SPEC.md (harness/SPEC.md)
output_state:  SPEC ratified; predicates P1-P7, falsifiers F1-F5, assumptions A1-A5
verifier:      operator acceptance — PASS
outcome:       success
external_calls: []
```

```
span_id:       s1
parent_id:     s0
pass:          1
step_type:     verify
input_state:   SPEC scout targets reference sibling repos by name
action:        Locate Moneta / comfy-moneta-bridge / comfy-cozy-app on filesystem
output_state:  ABSENT — no vector_index.py, no bridge dir, no outcomes.jsonl under ~
verifier:      L1 (file existence) — A1/A2 BLOCKED (substrate off-machine, likely Threadripper)
outcome:       escalation
external_calls: [find, ls]
```

```
span_id:       s2
parent_id:     s1
pass:          1
step_type:     execute
input_state:   operator supplied 3 GitHub URLs (JosephOIbrahim/{Moneta,comfy-moneta-bridge,comfy-cozy-app})
action:        gh repo clone all three into /Users/rustybeard/Code
output_state:  3 repos present; scout targets resolved (Moneta/src/moneta/vector_index.py, bridge/comfy_moneta_bridge/{vector,ingest,cli}.py)
verifier:      L1 (file existence) — PASS
outcome:       success
external_calls: [gh repo clone x3]
```

```
span_id:       s3
parent_id:     s2
pass:          1
step_type:     verify
leaf_id:       A1
input_state:   Moneta/src/moneta/vector_index.py
action:        Read; inspect dim-handling for F1 trigger
output_state:  Index dim-agnostic at construction (embedding_dim=None default :71-74); first upsert
               sets _dim (:108-109); later mismatch raises (:110-113). Dim fixed-at-first-deposit but
               synthetic+BGE+MiniLM all 384 -> no mismatch on swap. F1 NOT triggered.
verifier:      L3 (semantic, SPEC-fit) — A1 HOLDS
outcome:       success
external_calls: [Read]
```

```
span_id:       s4
parent_id:     s2
pass:          1
step_type:     verify
leaf_id:       A2,A5
input_state:   comfy-moneta-bridge repo
action:        Explore subagent — trace ingest/hydrate x-session mechanics + Comfy-Cozy consumer wire
output_state:  A2: shared storage_uri (moneta_config.py:33), Moneta query unfiltered (recall.py:71-72),
               post-query session payload guard; tests/test_integration_bge.py:57-138 already proves
               two-session same-URI semantic recall in bge mode. A5: consumer wire COMPLETE —
               capsule.py:229-238 writes sessions/{name}.json -> Cozy-Comfy/agent/startup.py:74-75 reads
               AUTO_LOAD_SESSION -> launch.py:44 + cli.py:158-173 (bridge hydrate --launch).
verifier:      L1 (test existence) + L3 (SPEC-fit) — A2 HOLDS, A5 HOLDS (F5 dissolved)
outcome:       success
external_calls: [Agent/Explore]
```

```
span_id:       s5
parent_id:     s4
pass:          1
step_type:     verify
input_state:   bridge vector.py + ingest.py (central reuse claim)
action:        Read both directly to confirm embedder already built
output_state:  vector.py encode_outcome() = real BGE-small 384-dim L2-norm (:125-135); from_env() mode
               switch default synthetic (:30,:61-68); current_embedder_version() tagging (:71-78).
               ingest.py _prepare() routes bge->encode_outcome else synthesize_vector (:62-65), tags
               _embedder on payload (:69). P1/P3 BUILT; P2 default inverted; P4 network conflict;
               P5 query-side tag-rejection unconfirmed.
verifier:      L0 (read) — reuse confirmed
outcome:       success
external_calls: [Read x2]
```

```
span_id:       s6
parent_id:     s5
pass:          1
step_type:     reflect
input_state:   A1/A2/A5 all hold; reuse map established
action:        Produce PASS 1 sketch + confidence per predicate (CAPSULE.md)
output_state:  Gate met — every SPEC predicate scored. Sketch = finish-and-flip, not build-from-zero.
verifier:      PASS 1 gate (confidence per predicate) — PASS
outcome:       success
external_calls: []
```

```
span_id:       s-correction
parent_id:     s4
pass:          1
step_type:     reflect
input_state:   earlier first-cut A5 verdict (Comfy-Cozy-only scout) = "bridge embeddings orphaned -> F5"
action:        Correction logged: that verdict was made with the bridge repo ABSENT (half the system).
               With bridge present, consumer wire is real. F5 dissolved. Recorded to prevent the
               retracted conclusion from leaking downstream.
verifier:      n/a
outcome:       success
external_calls: []
```

```
span_id:       s7
parent_id:     s5
pass:          2
step_type:     verify
input_state:   PASS 1 claim "_embedder query-side rejection unconfirmed (P5)"
action:        Read recall.py; grep _embedder usage across bridge
output_state:  Query-side rejection IS implemented (recall.py:83-85, capsule.py:178). PASS 1 unknown
               resolved. But this REJECTION is the mechanism that orphans legacy synthetic data on flip.
verifier:      L0 (read) — claim confirmed, weaponized into F-MIGRATE
outcome:       success
external_calls: [Read, grep]
```

```
span_id:       s8
parent_id:     s7
pass:          2
step_type:     verify
input_state:   suspicion: cross-session path != consumer path
action:        grep callers of recall() vs write_capsule(); read cli.py command surface
output_state:  CONFIRMED. write_capsule (AUTO_LOAD_SESSION artifact) filters same-session
               (capsule.py:11-13,146). recall() exposed only via `bridge recall` stdout (cli.py:177)
               + internal agent tool (tools.py:38). No automated cross-session consumer in Comfy-Cozy.
verifier:      L3 (SPEC-fit) — SPEC Outcome NOT wired end-to-end -> F-CROSS / narrow F5
outcome:       escalation
external_calls: [grep, Read]
```

```
span_id:       s9
parent_id:     s8
pass:          2
step_type:     reflect
input_state:   12 red-team findings; 4 NOT-OK (S×L>=12); 2 sev-5 trip F2/F5
action:        Write PASS 2 CAPSULE (findings + required mitigations M1-M6). Halt at gate per
               Operating Principle 9: F2 (F-MIGRATE) + F5 (F-CROSS) require operator adjudication
               before DECOMPOSE.
verifier:      PASS 2 gate (>=1 sev4 finding) — PASS; SPEC-invalidation check -> surface to operator
outcome:       escalation
external_calls: []
```

```
span_id:       s10
parent_id:     s9
pass:          2
step_type:     execute
input_state:   operator answers Q1(P6 defer)/Q2(P4 amend)/Q3(P5 storage check)
action:        Q3 empirical — find Moneta storage (default ~/.comfy-moneta-bridge/moneta, cli.py:42).
               No snapshot.json/wal.jsonl under ~ -> empty -> P5 fixture-only on this Mac
               (Threadripper runtime unverified caveat). Apply SPEC Amendment A1 (P4 wording, P6
               PENDING+gate-PASS-6).
verifier:      L1 (file existence: storage empty) — PASS; SPEC re-ratified (Amendment A1)
outcome:       success
external_calls: [Bash find/grep, Edit SPEC x3]
```

```
span_id:       s11
parent_id:     s10
pass:          3
step_type:     verify
input_state:   M1 (L5) would inject cross-session memory into capsule consumed by Comfy-Cozy (NO TOUCH)
action:        Compare capsule write schema vs session.py load schema for M1 fit / OP-9 risk
output_state:  write_capsule emits notes:list[dict]{text,type,added_at} (capsule.py:37-57);
               session.py loads notes generically, v2 types observation/preference/decision/tip
               (session.py:131-133,242-264). M1 fits as existing-type notes -> NO new field ->
               NO Comfy-Cozy edit -> NO escalation.
verifier:      L3 (schema-fit, OP-9 boundary) — PASS (NO-TOUCH holds)
outcome:       success
external_calls: [Bash grep/sed]
```

```
span_id:       s12
parent_id:     s11
pass:          3
step_type:     plan
input_state:   forks resolved (M1 build, P5 mode-matched); schema-fit clear
action:        Decompose into 6 leaves L1-L6 with contracts+verifiers+deps; write PLAN.md + CAPSULE
output_state:  Every SPEC predicate owned; no frozen-substrate mod; ledger empty (all novel).
verifier:      PASS 3 gate (predicate ownership + no-frozen-mod) — PASS
outcome:       success
external_calls: [Write PLAN.md, Write CAPSULE.md]
```

```
span_id:       s13
parent_id:     s12
pass:          4
step_type:     execute
input_state:   PASS 3 plan; bridge repo on master
action:        branch feat/bge-default-semantic; venv py3.12 (3.14 lacks torch wheel); install local
               Moneta rc1 + bridge[dev,embeddings,agents]; provision BGE (128M cache); baseline.
output_state:  282 passed baseline. CORRECTION: conftest.py:17 delenvs BRIDGE_EMBEDDER_MODE per-test,
               so the "both modes" baseline was synthetic-default twice — true bge-default needs L4.
verifier:      L1 baseline (282) — PASS; correction logged
outcome:       success
external_calls: [git checkout -b, venv, pip x3, provision_model]
```

```
span_id:       s14
parent_id:     s13
pass:          4
step_type:     verify
leaf_id:       L1,L2,L3
action:        L1 verify embedder via existing test_vector_bge (384/determinism). L2 add
               test_p5_synthetic_compat (synthetic round-trip, mode-matched). L3 vector.py
               local_files_only + provision_model; add test_p4_no_network (socket-patch, no env crutch).
output_state:  L1 verify-only PASS; L2 2/2 PASS; L3 2/2 PASS (zero socket egress during bge ingest).
verifier:      L0+L1 (L1,L2) + L2 property (L3) — PASS
outcome:       success
external_calls: [Edit vector.py, Write test_p5/test_p4, pytest]
```

```
span_id:       s15
parent_id:     s14
pass:          4
step_type:     verify
leaf_id:       L4
action:        Flip DEFAULT_MODE=bge + docstrings. Full suite -> 21 failures (expected ripple).
               Triage: 3 from_env default assertions -> bge; 14 synthetic-path unit tests -> pin
               synthetic in fixtures; 1 mock spy -> accept local_files_only; 3 ingest tests -> pin.
output_state:  Suite green both modes (286: 282 + 4 new). bge is now the real default.
verifier:      L0+L1 full suite — PASS
outcome:       success
external_calls: [Edit vector.py x3, Edit tests x10, pytest x2]
```

```
span_id:       s16
parent_id:     s15
pass:          4
step_type:     verify
leaf_id:       L5
action:        capsule.py: write_capsule(cross_session_top_k=3); _cross_session_notes injects
               other-session recall hits as observation notes (provenance in text, no new field,
               best-effort). Add test_p7_cross_session (3). Cross-repo: load capsule via Comfy-Cozy
               real session.load_session.
output_state:  3/3 PASS; full suite 289. Cross-repo load: schema_v2, session-A memory visible in
               session-B's loaded session. SPEC Outcome proven e2e; NO-TOUCH intact (no escalation).
verifier:      L1 e2e + L3 (real consumer load) — PASS
outcome:       success
external_calls: [Edit capsule.py x3, Write test_p7, pytest, cross-repo python load]
```

```
span_id:       s17
parent_id:     s16
pass:          4
step_type:     verify
leaf_id:       L6
action:        Mac smoke: 15 bge full-ingests, median 16.9ms / p95 18.3ms. Labeled NOT the P6 record.
               Final L0 ruff (clean) + collect (289) + full suite (289 passed).
output_state:  All 6 leaves done & verified. 3 ledger candidates written. Not committed (branch).
verifier:      L0 ruff + L1 full suite — PASS; P6 catastrophic ceiling — PASS (non-gating)
outcome:       success
external_calls: [smoke script, ruff, pytest, Write candidates x3]
```

```
span_id:       s18
parent_id:     s17
pass:          4
step_type:     execute
input_state:   operator: "Commit, then PASS 5"
action:        Stage specific files (no -A); commit [PILOT] vector.py+capsule.py (aa0ae21),
               [VERIFY] 8 test files (bb1b32a). No push.
verifier:      git log + clean tree — PASS
outcome:       success
external_calls: [git add, git commit x2]
```

```
span_id:       s19
parent_id:     s18
pass:          5
step_type:     verify
input_state:   built system; new seams recall->capsule + tail->ingest(multi-session)
action:        Add test_integration_cross_session (full chain two-session + recall-failure isolation).
               System-level ruff + full suite. Commit [VERIFY] (3b23bc5).
output_state:  2/2 seam tests PASS; full suite 291; ruff clean. 5 seams healthy; 6/7 predicates
               verified at integration (P6 deferred). Error propagation: recall failure isolated.
verifier:      L0 + L1 (system) + L2 (seam: failure isolation) + L3 (predicate coverage) — PASS
outcome:       success
external_calls: [Write test, ruff, pytest, git commit]
```

```
span_id:       s20
parent_id:     s19
pass:          6
step_type:     verify
input_state:   PASS 2 findings; built artifact
action:        L4 stress — 5 safety-invariant attacks (test_stress_mixed_mode) + 2 informational
               measurements (cursor-loss replay, thintext cosine). Commit [VERIFY] (c0c26ef).
output_state:  5/5 invariants PASS (mixed-mode isolation holds — no synthetic leak; strong match
               not starved at 100-noise scale; coldstart empty; drift dropped; injection capped).
               BOUNDED: thintext clusters (0.984 vs 0.863 distinct), cursor-loss dup, offline-fail,
               bge similarity floor. OUT OF SCOPE: WAL>1k, PRNG collision. NO showstoppers.
verifier:      L4 stress — PASS; gate (no showstopper + bounded documented) — PASS
outcome:       success
external_calls: [Write test, ruff, pytest, measurement script, git commit]
```

```
span_id:       s21
parent_id:     s20
pass:          7
step_type:     reflect
input_state:   stressed system; 6/7 predicates met, P6 deferred
action:        Write SHIP_REPORT.md (SPEC compliance, limitations, verifier coverage, ledger deltas,
               next). Artifact: branch feat/bge-default-semantic +607/-20, 4 commits. Operator: SHIP.
output_state:  Run accepted. Branch stays local — push requires separate per-call approval (NOT done).
verifier:      operator decision recorded — SHIP
outcome:       success
external_calls: [Write SHIP_REPORT, git diff, AskUserQuestion]
```

```
span_id:       s22
parent_id:     s21
pass:          7
step_type:     reflect
input_state:   ledger after SHIP
action:        SLEEP — scan recipes (empty), candidates (3 @ consolidated_from=1).
output_state:  No promotions (need 3-shot), no archives, no overlap merges. 3 candidates held for
               future consolidation. Run CLOSED.
verifier:      SLEEP scan — complete
outcome:       success
external_calls: [ls, grep]
```

---

## RUN CLOSED — 2026-05-27

Brief B shipped. 6/7 SPEC predicates met (P6 PENDING, Threadripper). Outcome
proven end-to-end. Artifact: `comfy-moneta-bridge@feat/bge-default-semantic`,
4 commits, unpushed (push awaits separate per-call approval). 296 tests green.
