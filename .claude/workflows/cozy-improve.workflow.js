// cozy-improve — the Comfy-Cozy self-improvement harness (ONE EPOCH per invocation).
//
// JOB: port verified architectural improvements into Comfy-Cozy, one ratcheted,
//      human-mergeable unit per item. Fuses SYNAPSE's FORGE 6-phase cycle (agent
//      roles + builder!=breaker isolation) with Comfy-Cozy's science harness
//      (LEDGER taxonomy + champion ratchet + cozy_loop durability semantics).
//
// SHAPE: one Workflow invocation = one epoch = one WAVE of independent improvements.
//   - Durable cross-epoch state lives in tooling/harness/LEDGER.md (+ champion.json),
//     read/written ONLY inside agents (this JS sandbox has no filesystem).
//   - Outer driver (/loop self-paced, or ScheduleWakeup overnight) re-invokes per epoch.
//   - Re-invocation is idempotent: Confirmed/DeadEnd items are skipped.
//
// PARAMETERS (Workflow `args`):
//   args.items : [{id, title, summary, kind, grounding}]  seed backlog (Phase-1 MVP, no discovery)
//   args.wave  : max items this epoch (default 1; >1 enables worktree isolation)
//   args.epoch : epoch number for reports (default 1)
//
// SAFETY: agents NEVER push/reset/rebase/force. Scribe's only git verbs are add|commit|tag
//   on the item branch. The benchmark ratchet (pure fn below) is the sole accept authority.

export const meta = {
  name: 'cozy-improve',
  description: 'Self-improvement harness: port a verified architectural improvement into Comfy-Cozy as one ratcheted, human-mergeable branch.',
  phases: [
    { title: 'select',     detail: 'read LEDGER + champion baseline; pick ready items' },
    { title: 'research',   detail: 'Cartographer: probe -> diff-level spec (V1 floor)' },
    { title: 'design',     detail: 'Architect: minimal surgical design + tests' },
    { title: 'build',      detail: 'Forge: implement on branch forge/<id>' },
    { title: 'verify',     detail: 'Crucible: pytest vs baseline, ruff, bench, determinism' },
    { title: 'refute',     detail: '3 Skeptics adversarially try to refute (majority gate)' },
    { title: 'ledger',     detail: 'Scribe: LEDGER append + champion + PR body (NO push)' },
    { title: 'checkpoint', detail: 'epoch summary + READY-FOR-MERGE surfacing' },
  ],
};

// ---------------------------------------------------------------------------
// Shared floor preamble — every agent inherits this contract.
// ---------------------------------------------------------------------------
const FLOOR = [
  'FLOOR (every artifact, non-negotiable):',
  '- Assert ONLY what you verified. "verified" = V1 reproduce -> clean. Mocked/green-by-default is V0 and discharges nothing.',
  '- Provenance: every claim names a file:line or a command you ran.',
  '- You operate under the Comfy-Cozy Git Authority Map: you may NEVER run git push / reset / rebase / --force / any remote op.',
  '- Builder != breaker: if you build, you do not judge your own work; if you judge, you do not edit.',
  '- Surgical changes only: touch only what the spec names. No drive-by refactors, no scope creep.',
  '- The frozen zone (agent/stage/**, agent/stage/moe_dispatcher.py, and any owner-gated proprietary files the brightline guard flags) is READ-ONLY. A write there is a TERMINAL violation — surface it, never force it.',
].join('\n');

const WAVE  = (typeof args === 'object' && args && args.wave)  ? args.wave  : 1;
const EPOCH = (typeof args === 'object' && args && args.epoch) ? args.epoch : 1;
const SEED  = (typeof args === 'object' && args && Array.isArray(args.items)) ? args.items : [];
const NOISE = 0.0; // bench tolerance band; raise only for stochastic benches

// ---------------------------------------------------------------------------
// Structured-output schemas
// ---------------------------------------------------------------------------
const BaselineSchema = {
  type: 'object', additionalProperties: false,
  required: ['tests_passed', 'tests_baseline_failed', 'ruff_clean', 'champion_file', 'ready_item_ids'],
  properties: {
    tests_passed:          { type: 'integer' },
    tests_baseline_failed: { type: 'integer' },
    ruff_clean:            { type: 'boolean' },
    champion_file:         { type: 'string' },
    ready_item_ids:        { type: 'array', items: { type: 'string' } },
    notes:                 { type: 'string' },
  },
};

const SpecSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'kind', 'target_loci', 'verified_by', 'frozen_zone_contact', 'blast_radius_files'],
  properties: {
    item_id:             { type: 'string' },
    kind:                { type: 'string', enum: ['feature', 'fix', 'perf', 'refactor', 'doc'] },
    synapse_ref:         { type: 'string' },
    target_loci:         { type: 'array', items: { type: 'object', additionalProperties: true } },
    probe:               { type: 'object', additionalProperties: true },
    verified_by:         { type: 'string', enum: ['V1', 'V1-degraded', 'V0'] },
    targeted_benchmark:  { type: ['string', 'null'] },
    blast_radius_files:  { type: 'array', items: { type: 'string' } },
    frozen_zone_contact: { type: 'boolean' },
    spec_summary:        { type: 'string' },
  },
};

const DesignSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'files_to_touch', 'new_tests', 'risk'],
  properties: {
    item_id:        { type: 'string' },
    design_summary: { type: 'string' },
    files_to_touch: { type: 'array', items: { type: 'string' } },
    new_tests:      { type: 'array', items: { type: 'string' } },
    seam_test_required: { type: 'boolean' },
    predicted_delta:    { type: 'string' },
    rollback_handle:    { type: 'string' },
    risk:           { type: 'string', enum: ['low', 'medium', 'high'] },
  },
};

const BuildSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'branch', 'files_changed', 'committed', 'validation_passed'],
  properties: {
    item_id:           { type: 'string' },
    branch:            { type: 'string' },
    commit_sha:        { type: 'string' },
    files_changed:     { type: 'array', items: { type: 'string' } },
    diff_stat:         { type: 'string' },
    committed:         { type: 'boolean' },
    validation_passed: { type: 'boolean' },
    notes:             { type: 'string' },
  },
};

const MeasureSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'branch', 'tests_passed', 'tests_failed', 'new_failures', 'ruff_clean', 'determinism_ok', 'within_blast_radius', 'frozen_zone_touch'],
  properties: {
    item_id:             { type: 'string' },
    branch:              { type: 'string' },
    tests_passed:        { type: 'integer' },
    tests_failed:        { type: 'integer' },
    new_failures:        { type: 'array', items: { type: 'string' } },
    ruff_clean:          { type: 'boolean' },
    bench:               { type: ['object', 'null'], additionalProperties: true },
    determinism_ok:      { type: 'boolean' },
    within_blast_radius: { type: 'boolean' },
    frozen_zone_touch:   { type: 'boolean' },
    measure_log:         { type: 'string' },
  },
};

const RefuteSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'refuted', 'class', 'reasons'],
  properties: {
    item_id: { type: 'string' },
    refuted: { type: 'boolean' },
    class:   { type: 'string', enum: ['regression', 'scope_creep', 'determinism', 'false_verified', 'frozen_zone', 'none'] },
    reasons: { type: 'array', items: { type: 'string' } },
  },
};

const ReceiptSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'kind', 'awaiting_human_merge'],
  properties: {
    item_id:              { type: 'string' },
    ledger_entry_id:      { type: 'string' },
    kind:                 { type: 'string', enum: ['Confirmation', 'DeadEnd'] },
    champion_promoted:    { type: 'boolean' },
    replicate_pending:    { type: 'boolean' },
    pr_body_path:         { type: 'string' },
    branch:               { type: 'string' },
    awaiting_human_merge: { type: 'boolean' },
    summary:              { type: 'string' },
  },
};

// ---------------------------------------------------------------------------
// THE RATCHET — pure function, the sole accept authority. No agent judgment here.
// ---------------------------------------------------------------------------
function ratchet(m, refutals, baseline) {
  const testsGreen = m.tests_passed >= baseline.tests_passed
                  && (m.new_failures || []).length === 0
                  && m.tests_failed <= baseline.tests_baseline_failed;
  const lintClean  = m.ruff_clean === true;
  const benchOk    = (m.bench == null)
                  ? true
                  : (Number(m.bench.delta_median) <= NOISE && Number(m.bench.delta_p95) <= NOISE);
  const noRegress  = m.determinism_ok === true && m.within_blast_radius === true && m.frozen_zone_touch === false;
  const notRefuted = (refutals || []).length < 2; // majority of 3 must NOT refute
  const accept = testsGreen && lintClean && benchOk && noRegress && notRefuted;
  return {
    accept,
    replicate_pending: accept && m.bench != null, // bench-driven wins replicate before champion promotion
    reasons: { testsGreen, lintClean, benchOk, noRegress, notRefuted },
  };
}

// ---------------------------------------------------------------------------
// Prompt builders
// ---------------------------------------------------------------------------
function selectPrompt() {
  return `${FLOOR}

ROLE: Select/baseline reader for the cozy-improve harness. READ-ONLY.

Do exactly this and return the schema:
1. Read tooling/harness/champion.json. If it exists, read baseline {tests_passed, tests_baseline_failed} and the canonical champion_file. If it does NOT exist yet, set tests_passed=4540, tests_baseline_failed=1 (the known Windows SIGKILL test_cozy_persistence::test_kill_after_flush_resumes_cleanly), champion_file="tooling/harness/champion.json".
2. Read tooling/harness/LEDGER.md. List the entry IDs of Confirmations that are forge-eligible and NOT yet marked Done/DeadEnd in the APPEND LOG (ready_item_ids). Leads are NOT ready.
3. Do NOT run pytest here (Crucible runs it once on the built branch). Report ruff_clean=true unless you already know otherwise.

Return BaselineSchema.`;
}

function cartographerPrompt(item) {
  return `${FLOOR}

ROLE: Cartographer (researcher x scout). READ-ONLY. Produce a diff-level spec for ONE improvement.

ITEM: ${JSON.stringify(item)}

Steps:
1. Read the Comfy-Cozy target loci named in the item. Read the SYNAPSE reference at C:\\Users\\User\\SYNAPSE if the item cites one.
2. PROBE the claim to the V1 floor: actually open the files / run the read-only probe command and confirm the gap is real. Record verified_by=V1 (or V1-degraded if a live dependency is unreachable, V0 only if you truly could not probe).
3. Map the blast radius: every file a minimal fix would touch. Set frozen_zone_contact=true if ANY locus is under agent/stage/** or an owner-gated proprietary file flagged by the brightline guard.
4. Name the targeted_benchmark (a harness/bench_*.py target) if this is a perf item, else null.

If the item carries a "grounding" field, treat it as verified seams (real signatures/insertion points) and fold it into target_loci.

Return SpecSchema. Do NOT edit anything.`;
}

function architectPrompt(spec) {
  return `${FLOOR}

ROLE: Architect. READ-ONLY. Design the MINIMAL surgical implementation for this spec.

SPEC: ${JSON.stringify(spec)}

Produce: the smallest change that satisfies the spec (simplest-thing-that-works), the exact files_to_touch, the new tests to add (name them), whether a seam test is required (a test driving the real producer through the real consumer), the predicted bench/behavior delta, and a rollback_handle (branch/undo). Reuse existing utilities; do not introduce speculative abstractions.

Return DesignSchema. Do NOT edit anything.`;
}

function forgePrompt(design) {
  return `${FLOOR}

ROLE: Forge (engineer x forge). You MAY edit. Implement EXACTLY this design, nothing more.

DESIGN: ${JSON.stringify(design)}

Procedure:
1. From the repo root (G:/Comfy-Cozy), create the item branch: git checkout -b forge/${design.item_id} (if it exists, check it out). Record the original branch name so it can be restored.
2. Implement only the files_to_touch. Add the new_tests. Match surrounding code style (99-char lines, type hints, deterministic to_json with sort_keys). Translate errors to human language — no raw tracebacks.
3. Run a quick local import/compile sanity check (python -c "import agent" or compile the changed module). Set validation_passed accordingly.
4. Stage ONLY the files you changed (never git add -A). Commit with message: "[FORGE ${design.item_id}] <one-line>\\n\\nLEDGER: pending\\nProvenance: cozy-improve epoch". Do NOT push. Do NOT touch master. Capture the commit_sha and a git diff --stat.
5. Leave the branch checked out for Crucible.

Return BuildSchema.`;
}

function cruciblePrompt(build, baseline) {
  return `${FLOOR}

ROLE: Crucible (producer-CI x crucible). MEASURE ONLY — you may run Bash + Read, you may NOT edit.

BUILD: ${JSON.stringify(build)}
BASELINE: tests_passed=${baseline.tests_passed}, tests_baseline_failed=${baseline.tests_baseline_failed}

On branch ${build.branch} from G:/Comfy-Cozy:
1. Run: python -m pytest tests/ -m "not integration" -q  -> parse the final summary into tests_passed and tests_failed. List any test ids that fail which are NOT the known baseline failure (new_failures).
2. Run: ruff check agent/ tests/  -> ruff_clean = (exit 0).
3. If the spec named a targeted_benchmark, run it on baseline (origin) and on this branch; report bench={name, median, p95, baseline_median, baseline_p95, delta_median, delta_p95}. Else bench=null.
4. determinism_ok: confirm no new non-sorted JSON / random-seed / wallclock-in-output was introduced (grep the diff). within_blast_radius: every changed file is in the design's files_to_touch. frozen_zone_touch: any changed file under agent/stage/** or an owner-gated proprietary file.
5. Do NOT fix anything. Report numbers only.

Return MeasureSchema.`;
}

function skepticPrompt(measure, lens) {
  return `${FLOOR}

ROLE: Skeptic (adversarial verifier). READ-ONLY. Your job is to REFUTE this change. Default to refuted=true if you find a real problem.

LENS: ${lens}
MEASUREMENT: ${JSON.stringify(measure)}

Inspect the diff on branch ${measure.branch} (git diff origin...${measure.branch} or against the base). Through your lens, look for: a weakened/deleted test assertion to force green (false_verified); a regression the suite didn't catch; scope creep beyond the spec; a determinism break; a frozen-zone touch. If you find one, refuted=true with the class and concrete file:line reasons. If the change is honest and within scope, refuted=false, class="none".

Return RefuteSchema.`;
}

function scribePrompt(measure, decision, item) {
  return `${FLOOR}

ROLE: Scribe (producer-record x scribe). The ONLY durable-state writer and the ONLY git-mutating role. You may Write + run git add|commit|tag. You may NEVER push/reset/rebase.

ITEM: ${JSON.stringify(item)}
MEASUREMENT: ${JSON.stringify(measure)}
RATCHET DECISION: ${JSON.stringify(decision)}

If decision.accept == true:
1. Append a Confirmation to tooling/harness/LEDGER.md APPEND LOG (date 2026-06-27, entry id like C-${item.id}): the reproduce->clean result, test delta, bench delta, branch name. kind="Confirmation".
2. Update tooling/harness/champion.json: add/replace the track for ${item.id} with the measured result. If decision.replicate_pending, set replicate_pending:true and do NOT mark the champion promoted yet.
3. Write a PR body to tooling/harness/forge/PR_${item.id}.md: title, summary, the gate evidence (tests passed/failed vs baseline, ruff, bench median/p95, the 3 skeptic verdicts), files changed, branch forge/${item.id}, and "Merge is reserved for Joe — this harness never pushes."
4. Amend nothing; create a fresh commit on branch forge/${item.id} staging ONLY the LEDGER/champion/PR files: git add those three; git commit -m "[SCRIBE ${item.id}] record epoch result + PR body". Tag lightweight: git tag cozy-improve/${item.id}. Do NOT push. awaiting_human_merge=true.

If decision.accept == false:
1. Append a DeadEnd to the LEDGER (direction + measured delta + the failing ratchet reason / refutation class). kind="DeadEnd".
2. Discard the build: inside the repo, git checkout the original branch, then leave branch forge/${item.id} in place for human inspection (do NOT delete it, do NOT reset master). awaiting_human_merge=false.

Return ReceiptSchema.`;
}

// ---------------------------------------------------------------------------
// Pass-through guard: a stage may emit a terminal marker (rfc_only / halt) that
// later stages must forward untouched instead of treating as their input.
// ---------------------------------------------------------------------------
function isTerminal(x) { return x && (x.rfc_only || x.halt); }

// ===========================================================================
// EPOCH
// ===========================================================================
phase('select');
const baseline = await agent(selectPrompt(), { schema: BaselineSchema, label: 'select' });

let items = SEED.slice();
if (items.length === 0) {
  // Phase-1 MVP has no discovery: fall back to ready LEDGER items by id.
  items = (baseline.ready_item_ids || []).map((id) => ({ id, title: id, summary: 'from LEDGER', kind: 'fix' }));
}
items = items.slice(0, WAVE);
if (items.length === 0) {
  log('backlog dry — nothing ready. Epoch ends.');
  return { epoch: EPOCH, halt: 'backlog_dry', results: [] };
}
log(`epoch ${EPOCH}: ${items.length} item(s) this wave -> ${items.map((i) => i.id).join(', ')}`);

const useWorktree = WAVE > 1; // collision isolation only matters with parallel forges

const results = await pipeline(
  items,

  // 1 — Cartographer: probe -> spec (V1 floor)
  (item) => agent(cartographerPrompt(item), {
    schema: SpecSchema, agentType: 'Explore', phase: 'research', label: `carto:${item.id}`,
  }).then((spec) => ({ ...spec, _item: item })),

  // 2 — Architect: minimal design (frozen zone -> RFC-only, surface not halt)
  (spec) => spec.frozen_zone_contact
    ? { rfc_only: true, item_id: spec.item_id, _item: spec._item, reason: 'frozen_zone_contact -> RFC only, no forge' }
    : agent(architectPrompt(spec), {
        schema: DesignSchema, agentType: 'Explore', phase: 'design', label: `arch:${spec.item_id}`,
      }).then((d) => ({ ...d, _item: spec._item })),

  // 3 — Forge: implement on branch forge/<id>
  (design) => isTerminal(design) ? design : agent(forgePrompt(design), {
    schema: BuildSchema, phase: 'build', label: `forge:${design.item_id}`,
    ...(useWorktree ? { isolation: 'worktree' } : {}),
  }).then((b) => ({ ...b, _item: design._item })),

  // 4 — Crucible: measure only
  (build) => isTerminal(build) ? build : agent(cruciblePrompt(build, baseline), {
    schema: MeasureSchema, agentType: 'Explore', phase: 'verify', label: `crucible:${build.item_id}`,
    ...(useWorktree ? { isolation: 'worktree' } : {}),
  }).then((m) => ({ ...m, _item: build._item })),

  // 5 — Adversarial refute: 3 independent skeptics, majority must NOT refute
  async (m) => {
    if (isTerminal(m)) return m;
    const verdicts = await parallel([
      () => agent(skepticPrompt(m, 'weakened/deleted test assertion, false-verified'), { schema: RefuteSchema, agentType: 'Explore', phase: 'refute', label: `skeptic-A:${m.item_id}` }),
      () => agent(skepticPrompt(m, 'silent regression / scope creep beyond spec'),     { schema: RefuteSchema, agentType: 'Explore', phase: 'refute', label: `skeptic-B:${m.item_id}` }),
      () => agent(skepticPrompt(m, 'determinism break / frozen-zone touch'),           { schema: RefuteSchema, agentType: 'Explore', phase: 'refute', label: `skeptic-C:${m.item_id}` }),
    ]);
    return { m, refutals: verdicts.filter((v) => v && v.refuted) };
  },

  // 6 — Ratchet (pure) + Scribe (record; commit; NO push)
  async (r) => {
    if (isTerminal(r)) {
      // RFC-only / halt: surface, do not score. Scribe records a Lead->RFC note.
      return agent(scribePrompt(r, { accept: false, replicate_pending: false, reasons: { frozen: true } }, r._item), {
        schema: ReceiptSchema, phase: 'ledger', label: `scribe:${r.item_id}`,
      });
    }
    const decision = ratchet(r.m, r.refutals, baseline);
    log(`${r.m.item_id}: ratchet ${decision.accept ? 'ACCEPT' : 'REJECT'} (${JSON.stringify(decision.reasons)})`);
    return agent(scribePrompt(r.m, decision, r.m._item), {
      schema: ReceiptSchema, phase: 'ledger', label: `scribe:${r.m.item_id}`,
    });
  },
);

phase('checkpoint');
const receipts = (results || []).filter(Boolean);
const ready = receipts.filter((r) => r.awaiting_human_merge);
log(`epoch ${EPOCH} done — ${ready.length} ready for merge: ${ready.map((r) => r.branch).join(', ') || 'none'}`);
return { epoch: EPOCH, ready: ready.map((r) => ({ item: r.item_id, branch: r.branch, pr: r.pr_body_path })), receipts };
