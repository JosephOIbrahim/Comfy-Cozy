# Inside-Out Architecture Package — README

**Package:** Comfy-Cozy × Moneta — Inside-Out Substrate Migration
**Created:** 2026-04-30
**Status:** POST-COUNCIL — binding decisions in `COUNCIL_DECISIONS.md` at repo root (council session 2026-05-01). The brief recommendations in this package are preserved as the input artifact going *into* council; council outcomes override them where they differ.
**Author:** Joe Ibrahim (Architect), Claude (translation)

---

## 0. What This Is

Seven documents covering a MOE council decision session on whether Comfy-Cozy should migrate from outside-in (REST/WebSocket to ComfyUI) to inside-out (custom node package, Moneta in-process, workflow graph as composition substrate). Council ran 2026-05-01; binding outcomes are in `COUNCIL_DECISIONS.md` at repo root and the run is operationalized via `INSIDE_OUT_RUN_PLAYBOOK.md` + `RUN_INSIDE_OUT_PASS.md`.

**This is decision work only. No code. No forge. No commits.** Building tasks happen in Claude Code after council approval.

---

## 1. Read Order

Read in this order. Each document builds on the previous.

| # | Document | Purpose | Required reading? |
|---|---|---|---|
| 0 | `00_INSIDE_OUT_EXPLORATION_PLAN.md` | Strategic frame — why now, the three questions, decision sequence | YES — start here |
| 1 | `01_SCOUT_INSIDE_OUT_v0_1.md` | Claude Code scout pass — execution spec consumed by `RUN_INSIDE_OUT_PASS.md` | NO — for Claude Code at run time |
| 2 | `02_ARCH-1_INSIDE_OUT_BRIEF.md` | Council brief — outside-in vs inside-out (the transport decision) | YES |
| 3 | `03_ARCH-2_MONETA_EVOLUTION_BRIEF.md` | Council brief — Moneta v1.3 (state-machine absorption) | YES |
| 4 | `04_ARCH-5_WORKFLOW_LIVRPS_BRIEF.md` | Council brief — workflow graph as LIVRPS substrate (patent extension) | YES |
| 5 | `INSIDE_OUT_RUN_PLAYBOOK.md` | Joe's pre-flight + gate-review playbook — the operational companion to `RUN_INSIDE_OUT_PASS.md` | YES — required during execution |
| 6 | `../../COUNCIL_DECISIONS.md` (repo root) | Binding council outcomes — overrides brief recommendations where they differ | YES — read before acting on briefs |
| 7 | `README.md` | This file (index, council session protocol) | Reference as needed |

---

## 2. Council Session Protocol

### 2.1 Pre-session

- [ ] All council readers complete documents 0, 2, 3, 4 (skip 1 — that's for Claude Code post-council)
- [ ] Patent posture file accessible (referenced by ARCH-2 and ARCH-5)
- [ ] Three-isolated-experience-stores problem written up separately if not already documented (referenced by ARCH-2)

### 2.2 Session order

The three decisions have dependency ordering:

```
1. ARCH-1 first  — gates ARCH-5
2. ARCH-5 second — patent extension decision (conditional on ARCH-1)
3. ARCH-2 last   — independent, but informed by ARCH-1 outcome
```

**Estimated session length:** 60-90 minutes if council runs decisively. Each brief includes a vote sheet at the end — fill it in during the session.

### 2.3 Post-session

If ANY decision is 🟢 or 🟡:

- [ ] Vote sheets archived to BLOCKERS or DECISIONS log
- [ ] Tier 1-2 hardening continues unaffected
- [ ] Scout pass scheduled for post-Tier-2 closeout
- [ ] Patent counsel review scheduled for ARCH-5 (and ARCH-2 if 🟢)

If ALL decisions are 🔴:

- [ ] Architecture stays as-is
- [ ] Comfy-Cozy continues outside-in
- [ ] Phase 7 reframes around current architecture
- [ ] Three-isolated-stores problem becomes urgent (separate brief)

---

## 3. The Three Questions in One Page

### ARCH-1 — Transport
**Outside-in vs inside-out for Comfy-Cozy?**

Recommendation: 🟢 GREEN with timing constraint (Tier 1-2 hardens first, scout pass after, Phase 2 inside-out work after that).

### ARCH-2 — Substrate Evolution
**Should Moneta v1.3 absorb Harlo's state-machine pattern?**

Brief recommendation: 🟡 YELLOW — start with thin telemetry component; defer full absorption pending three-isolated-stores resolution and patent counsel review.

**Council decision (2026-05-01): 🟢 GREEN — full absorption, override of CRUCIBLE 🔴 RED-DEFER recommendation. See `COUNCIL_DECISIONS.md` for binding outcome and the override rationale.**

### ARCH-5 — Patent Extension
**ComfyUI workflow graph as LIVRPS substrate; CIP patent filing?**

Recommendation: 🟢 GREEN, conditional on ARCH-1 = 🟢 and patent counsel review.

---

## 4. Critical Path

All three landed GREEN at the 2026-05-01 council. Authoritative path is in `COUNCIL_DECISIONS.md` "Critical Path"; reproduced here for navigation:

```
Now              →  Tier 1-2 hardening continues on outside-in (parallel track,
                    not gated by inside-out work)
                    Inside-out scout/architect/forge run via RUN_INSIDE_OUT_PASS.md
                    in Claude Code (read-only scout, then plan, then forge)

Parallel tracks  →  Three-isolated-stores brief drafted (Joe)
                    Patent counsel meeting scheduled (ARCH-5 CIP, ARCH-2 partition)
                    ARCH-2 thin component scoping begins after three-stores brief

Phase 2 ship     →  CIP filing (if counsel approved)
                    SuperDuper Panel + GRAPH mode lands inside-out
                    Cozy Shadow Graph operational
                    Moneta v1.3 absorption first milestones land
```

Wall-clock estimate: ~3–5 months from council session to inside-out shipping (per `COUNCIL_DECISIONS.md`), longer if ARCH-2 work surfaces three-stores complications. **This estimate is not committed; it's directional.**

---

## 5. What This Package Does NOT Decide

- Implementation timeline (decided in Phase 2 plan post-scout)
- Specific patent claim language (decided by counsel)
- ComfyUI version compatibility matrix (decided in scout pass)
- Three-isolated-experience-stores resolution (separate brief required)
- Vision evaluator (parallel track, not in this package)
- Path A vs Path B sequencing (parallel track, not in this package)

---

## 6. Open Questions Surfaced

These are issues the briefs flagged that need resolution but are out of scope for council:

1. **Three-isolated-experience-stores problem** — flagged by ARCH-2 as upstream. Needs its own brief before ARCH-2 forge work.
2. **Patent counsel availability** — gates ARCH-5 filing and ARCH-2 IP partition.
3. **ComfyUI dependency conflict surface** — quantified in scout pass; if HARD, may force ARCH-1 re-decision.
4. **Phase 7 GRAPH mode actual usage** — empirical question that affects ARCH-5's enablement strength.

---

## 7. Council Sign-off — RECORDED

Council session ran 2026-05-01. The binding record (with CRUCIBLE objections, override rationale for ARCH-2, and Critical Path) lives in `COUNCIL_DECISIONS.md` at repo root. Recorded outcomes:

```
ARCH-1: 🟢 GREEN   (timing constraint relaxed: parallel-track approved)
ARCH-5: 🟢 GREEN
ARCH-2: 🟢 GREEN   (override of CRUCIBLE 🔴 RED-DEFER recommendation)

Signed: Joe Ibrahim                  Date: 2026-05-01
Next action: pre-flight per INSIDE_OUT_RUN_PLAYBOOK.md, then RUN_INSIDE_OUT_PASS.md
```

---

## 8. Where This Package Lives

Recommended placement:

```
G:\Comfy-Cozy\docs\inside-out-package\
  README.md
  00_INSIDE_OUT_EXPLORATION_PLAN.md
  01_SCOUT_INSIDE_OUT_v0_1.md
  02_ARCH-1_INSIDE_OUT_BRIEF.md
  03_ARCH-2_MONETA_EVOLUTION_BRIEF.md
  04_ARCH-5_WORKFLOW_LIVRPS_BRIEF.md
  INSIDE_OUT_RUN_PLAYBOOK.md

G:\Comfy-Cozy\
  COUNCIL_DECISIONS.md      (binding council outcomes, repo root)
  RUN_INSIDE_OUT_PASS.md    (Claude Code drop-in execution prompt, repo root)
```

Commit as a single PR:
```
git checkout -b docs/inside-out-package
git add docs/inside-out-package/
git commit -m "docs: inside-out architecture exploration package"
git push origin docs/inside-out-package
```

Branch can stay open until council session concludes; merge to master after vote sheets are archived.

---

## 9. Acknowledgments

The package draws on:

- **SYNAPSE_HARLO_BRIDGE_INTEGRATION_v1.1.md** — substrate isomorphism principle (§2), Frame B / Frame F definitions (§9, §10), composition substrate ownership rules (§5.1)
- **AGENT_CONSTITUTION_v2.md** — handoff artifact patterns, MOE role definitions (Architect/Implementer/Verifier), patent boundary frozen list (§5)
- **userMemories** — Moneta architectural divergence from Harlo, three-isolated-stores problem, patent claim structure, hardening track status, Path A/B sequencing
- **Conversation lineage** — 4.27 (Moneta closeout), 4.28 (Harlo schema surgery), 4.29 (comfy-moneta-bridge v0.1.0 ship), 4.30 (this exploration session)

---

**End of package README.** Council reads in the order listed above.
