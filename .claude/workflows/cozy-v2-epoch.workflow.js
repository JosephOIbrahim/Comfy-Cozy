// cozy-v2-epoch — the v2 build-harness epoch unit (ONE EPOCH per invocation).
//
// Evolved from cozy-improve.workflow.js (~the proven skeleton) per ORCHESTRATOR_v2.md.
// New over cozy-improve (skeptic-hardened, LEDGER V2-E0B-R1):
//   1. verify_ratchet.py --check is the measurement authority (thresholds from
//      MASTER's baselines; junit-sourced counts; fail-closed disclosure range).
//      The JS accept is a thin wrapper: verdict.all_green && refutations < 2.
//   2. MULTI-SHA review: Crucible + every skeptic judge ALL [FORGE] commits in
//      base_sha..HEAD; blast-radius and frozen-zone AND-fold across commits; the
//      run asserts no commit in the range escaped review.
//   3. MECHANICAL budget: agent() invocations counted in-script; cap exceeded =>
//      terminal budget_exceeded (never judgment).
//   4. Judge panel on design alternatives: unanimous proceeds, split => G7 gate.
//   5. One RE-PLAN BOUNCE: first refutation/ratchet-fail sends evidence back to
//      the Architect; the Forge retries ONCE on the same branch.
//   6. Scribe writes the v2 durable state set (LEDGER + STATE/STATUS/GATES/RESUME).
//   7. Sweep mode (args.mode='sweep'): loop-until-dry, max 5 iterations.
//
// PARAMETERS (Workflow `args`):
//   args.items  : [{id, title, summary, kind, grounding}]  seed backlog
//   args.wave   : max parallel items (default 1; >1 => worktree isolation)
//   args.epoch  : epoch id string, e.g. "E1" (required for real epochs)
//   args.mode   : 'single' (default) | 'sweep'
//   args.budget : max agent invocations this run (default 30, per STATE.json)
//
// SAFETY: no agent pushes/resets/rebases/touches remotes — structurally denied
// (settings deny list) and constitutionally forbidden. Scribe's git verbs are
// add|commit|lightweight-tag only. Frozen accept-authority is READ-ONLY here.

export const meta = {
  name: 'cozy-v2-epoch',
  description: 'v2 build-harness epoch: scout -> design(±judges) -> forge -> ratchet -> 3 skeptics -> scribe; one ratcheted human-mergeable unit.',
  phases: [
    { title: 'select',   detail: 'read v2 state + ratchet baseline; pick ready items' },
    { title: 'scout',    detail: 'probe every seam to the V1 floor -> diff-level spec' },
    { title: 'design',   detail: 'minimal surgical design; judge panel on alternatives' },
    { title: 'build',    detail: 'Forge implements on v6/<id>; commits per coherent unit' },
    { title: 'verify',   detail: 'Crucible: verify_ratchet.py --check (measure only)' },
    { title: 'refute',   detail: '3 skeptics over EVERY forge commit; majority gate' },
    { title: 'ledger',   detail: 'Scribe: LEDGER + v2 state + PR body (NO push)' },
    { title: 'checkpoint', detail: 'epoch summary + gates queued' },
  ],
};

// ---------------------------------------------------------------------------
// FLOOR — every agent inherits this contract.
// ---------------------------------------------------------------------------
const FROZEN = [
  'agent/stage/**',
  'tooling/harness/verify_ratchet.py',
  'tooling/harness/v2/baselines.json',
  'tooling/harness/v2/baseline_deltas.jsonl',
  'tooling/harness/champion.json',
  'harness/champion.json',
  '.claude/workflows/**',
  '.githooks/**',
];
const FLOOR = [
  'FLOOR (every artifact, non-negotiable):',
  '- Assert ONLY what you verified. "verified" = V1 reproduce -> clean. Mocked/green-by-default is V0 and discharges nothing.',
  '- Provenance: every claim names a file:line or a command you ran.',
  '- Git Authority Map: you may NEVER run git push / reset / rebase / --force / branch -D / any remote-mutating op. Fetch/show are reads and fine.',
  '- Builder != breaker: if you build, you do not judge your own work; if you judge, you do not edit.',
  '- Surgical changes only: touch only what the spec names. No drive-by refactors.',
  `- FROZEN (READ-ONLY; a write is a TERMINAL violation — surface it, never work around it): ${FROZEN.join(', ')}. Files flagged by the local disclosure guard are frozen too.`,
  '- Never use git commit --no-verify. A guard flag = STOP and surface to the owner.',
  '- Public prose never names guarded subsystems; cite LEDGER entry IDs.',
].join('\n');

// args may arrive as object OR JSON string — handle both (LEDGER: seed-injection fix).
let _A = args;
if (typeof _A === 'string') { try { _A = JSON.parse(_A); } catch (_e) { _A = null; } }
_A = (_A && typeof _A === 'object') ? _A : {};
const WAVE   = _A.wave || 1;
const EPOCH  = _A.epoch || 'adhoc';
const MODE   = _A.mode === 'sweep' ? 'sweep' : 'single';
const BUDGET = Number(_A.budget) || 30;
const SEED   = Array.isArray(_A.items) ? _A.items : [];

// ---------------------------------------------------------------------------
// MECHANICAL budget — counted here, not judged by any agent.
// ---------------------------------------------------------------------------
let INVOKED = 0;
async function call(prompt, opts) {
  if (INVOKED >= BUDGET) return { halt: 'budget_exceeded', invoked: INVOKED };
  INVOKED += 1;
  return agent(prompt, opts);
}
function isTerminal(x) { return x && (x.rfc_only || x.halt); }

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------
const SelectSchema = {
  type: 'object', additionalProperties: false,
  required: ['ratchet_green', 'ready_item_ids'],
  properties: {
    ratchet_green:  { type: 'boolean' },
    ratchet_notes:  { type: 'string' },
    ready_item_ids: { type: 'array', items: { type: 'string' } },
    notes:          { type: 'string' },
  },
};
const SpecSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'kind', 'target_loci', 'verified_by', 'frozen_zone_contact', 'blast_radius_files'],
  properties: {
    item_id: { type: 'string' },
    kind: { type: 'string', enum: ['feature', 'fix', 'perf', 'refactor', 'doc'] },
    target_loci: { type: 'array', items: { type: 'object', additionalProperties: true } },
    verified_by: { type: 'string', enum: ['V1', 'V1-degraded', 'V0'] },
    blast_radius_files: { type: 'array', items: { type: 'string' } },
    frozen_zone_contact: { type: 'boolean' },
    spec_summary: { type: 'string' },
  },
};
const DesignSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'files_to_touch', 'new_tests', 'risk', 'alternatives'],
  properties: {
    item_id: { type: 'string' },
    design_summary: { type: 'string' },
    files_to_touch: { type: 'array', items: { type: 'string' } },
    new_tests: { type: 'array', items: { type: 'string' } },
    rollback_handle: { type: 'string' },
    risk: { type: 'string', enum: ['low', 'medium', 'high'] },
    alternatives: {
      type: 'array', description: 'other viable designs (empty when one obvious approach)',
      items: { type: 'object', additionalProperties: true },
    },
  },
};
const JudgeSchema = {
  type: 'object', additionalProperties: false,
  required: ['winner', 'reason'],
  properties: { winner: { type: 'integer' }, reason: { type: 'string' } },
};
const BuildSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'branch', 'base_sha', 'forge_shas', 'files_changed', 'committed'],
  properties: {
    item_id: { type: 'string' },
    branch: { type: 'string' },
    base_sha: { type: 'string', description: 'sha the branch was cut from (recorded at cut time)' },
    forge_shas: { type: 'array', items: { type: 'string' }, description: 'ordered [FORGE]-trailered commits' },
    files_changed: { type: 'array', items: { type: 'string' } },
    committed: { type: 'boolean' },
    notes: { type: 'string' },
  },
};
const MeasureSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'branch', 'ratchet_all_green', 'range_fully_reviewed', 'within_blast_radius', 'frozen_zone_touch'],
  properties: {
    item_id: { type: 'string' },
    branch: { type: 'string' },
    ratchet_all_green: { type: 'boolean' },
    ratchet_verdict: { type: 'object', additionalProperties: true },
    range_fully_reviewed: { type: 'boolean', description: 'every commit in base..HEAD carries the [FORGE] trailer and was inspected' },
    within_blast_radius: { type: 'boolean', description: 'AND-fold over ALL forge commits' },
    frozen_zone_touch: { type: 'boolean', description: 'OR-fold over ALL forge commits' },
    measure_log: { type: 'string' },
  },
};
const RefuteSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'refuted', 'class', 'reasons'],
  properties: {
    item_id: { type: 'string' },
    refuted: { type: 'boolean' },
    class: { type: 'string', enum: ['regression', 'scope_creep', 'determinism', 'false_verified', 'frozen_zone', 'none'] },
    reasons: { type: 'array', items: { type: 'string' } },
  },
};
const ReceiptSchema = {
  type: 'object', additionalProperties: false,
  required: ['item_id', 'kind', 'awaiting_human_merge'],
  properties: {
    item_id: { type: 'string' },
    ledger_entry_id: { type: 'string' },
    kind: { type: 'string', enum: ['Confirmation', 'DeadEnd'] },
    pr_body_path: { type: 'string' },
    branch: { type: 'string' },
    awaiting_human_merge: { type: 'boolean' },
    summary: { type: 'string' },
  },
};

// ---------------------------------------------------------------------------
// ACCEPT — thin wrapper; verify_ratchet.py (master's copy) is the authority.
// ---------------------------------------------------------------------------
function accept(measure, refutals) {
  const verdict = measure.ratchet_verdict || {};
  const mechanical = measure.ratchet_all_green === true
    && verdict.disclosure_certified === true   // CI --brightline skip can NEVER accept (§2, R2)
    && measure.range_fully_reviewed === true
    && measure.within_blast_radius === true
    && measure.frozen_zone_touch === false;
  const notRefuted = (refutals || []).length < 2;
  return { accept: mechanical && notRefuted, mechanical, notRefuted };
}

// ---------------------------------------------------------------------------
// Prompts
// ---------------------------------------------------------------------------
const selectPrompt = () => `${FLOOR}

ROLE: Select/boot reader. READ-ONLY.
1. Read tooling/harness/ORCHESTRATOR_v2.md, tooling/harness/v2/STATE.json,
   tooling/harness/v2/GATES.md, tooling/harness/DEADENDS.md.
2. Re-establish truth: run python tooling/harness/verify_ratchet.py --check --json %TEMP%/ratchet_boot.json
   (this reads thresholds from origin/master; report ratchet_green = all_green, and
   summarize any red check in ratchet_notes).
3. ready_item_ids: items for epoch ${EPOCH} from STATE.json/BACKLOG.md that are not
   Confirmed/DeadEnd in the LEDGER.
Return SelectSchema.`;

const scoutPrompt = (item) => `${FLOOR}

ROLE: Scout. READ-ONLY. Diff-level spec for ONE item.
ITEM: ${JSON.stringify(item)}
1. Probe every claimed seam to the V1 floor (open the files, run read-only commands).
2. blast_radius_files: every file a minimal fix touches — include tests/conftest and
   shared fixtures if touched. frozen_zone_contact=true if ANY locus is FROZEN.
Return SpecSchema.`;

const architectPrompt = (spec, bounceEvidence) => `${FLOOR}

ROLE: Architect. READ-ONLY. MINIMAL surgical design.
SPEC: ${JSON.stringify(spec)}
${bounceEvidence ? `RE-PLAN BOUNCE (attempt 2 of 2 — revise the design to answer this evidence, then the Forge retries ONCE): ${JSON.stringify(bounceEvidence)}` : ''}
Design the smallest change satisfying the spec; name exact files_to_touch and new_tests;
reuse existing utilities; no speculative abstractions. If more than one approach is
genuinely viable, list them in alternatives (the panel will judge); else alternatives=[].
Return DesignSchema.`;

const judgePrompt = (design, lens, i) => `${FLOOR}

ROLE: Design judge #${i}. READ-ONLY. LENS: ${lens}.
ALTERNATIVES (0 = the primary design, 1.. = design.alternatives):
${JSON.stringify({ primary: design.design_summary, files: design.files_to_touch, alternatives: design.alternatives })}
Pick the winner by index through your lens. Return JudgeSchema.`;

const forgePrompt = (design, epoch) => `${FLOOR}

ROLE: Forge. You MAY edit. Implement EXACTLY this design.
DESIGN: ${JSON.stringify(design)}
1. From G:/Comfy-Cozy: record base_sha = git rev-parse HEAD of the branch point, then
   git checkout -b v6/${design.item_id} (or check it out if it exists; base_sha then =
   the recorded value in the prior BuildSchema — never re-derive from origin diffs).
   IF you are in a worktree (isolation): FIRST copy the disclosure scanner from the
   main checkout to exactly <worktree>/scripts/brightline_scan.py, else your commits
   will be refused (fail-closed pre-commit). Verify with git status --porcelain that
   the copy is untracked.
2. Implement ONLY files_to_touch + new_tests. Match style (99-char, type hints,
   deterministic to_json). Commit after EACH coherent unit with trailer
   "[FORGE ${design.item_id}] <one-line>" — never git add -A, name files explicitly.
3. Report base_sha and the ORDERED list of your commit shas (forge_shas). Leave the
   branch checked out.
Return BuildSchema.`;

const cruciblePrompt = (build) => `${FLOOR}

ROLE: Crucible. MEASURE ONLY (Bash + Read; no edits, no judgment).
BUILD: ${JSON.stringify(build)}
On branch ${build.branch}:
1. AUTHORITY: fetch master's copies first —
   git show origin/master:tooling/harness/verify_ratchet.py > %TEMP%/vr_master.py
   If that succeeds, run: python %TEMP%/vr_master.py --check --json %TEMP%/ratchet_${build.item_id}.json
   (master's script reads master's baselines itself). If master does not yet have the
   script (bootstrap), run the in-tree copy and say so in measure_log.
   ratchet_all_green = verdict.all_green; embed the verdict object.
2. RANGE COVERAGE: list git rev-list ${build.base_sha}..HEAD. range_fully_reviewed =
   (every sha in that list is in build.forge_shas AND every listed sha's message
   carries the [FORGE ${build.item_id}] trailer). Any stranger commit => false.
3. For EVERY sha in the range: git show <sha> --stat. within_blast_radius = AND-fold
   (every touched file within the design blast radius). frozen_zone_touch = OR-fold
   (any touched file in the FROZEN list).
4. Report numbers only; fix nothing.
Return MeasureSchema.`;

const skepticPrompt = (measure, build, lens) => `${FLOOR}

ROLE: Skeptic. READ-ONLY. REFUTE this change if you can. LENS: ${lens}.
MEASUREMENT: ${JSON.stringify(measure)}
COMMITS: ${JSON.stringify(build.forge_shas)} (base ${build.base_sha})
Inspect EVERY listed commit: git show <sha> for each — the epoch is multi-commit and
an earlier commit can hide what a later one exploits (weakened assertion in commit 1,
feature in commit 2). Judge ONLY commits in this list against the design; do not
penalize pre-existing code. refuted=true needs concrete file:line reasons.
Return RefuteSchema.`;

const scribePrompt = (measure, decision, item, build) => `${FLOOR}

ROLE: Scribe. The ONLY durable-state writer; git verbs: add|commit|lightweight tag. NEVER push.
ITEM: ${JSON.stringify(item)}
MEASUREMENT: ${JSON.stringify(measure)}
DECISION: ${JSON.stringify(decision)}
If accept: (1) LEDGER Confirmation (entry id C-${item.id}, today's date, evidence incl.
ratchet verdict + skeptic verdicts); (2) refresh tooling/harness/v2/{STATE.json,
STATUS.md,GATES.md} + RESUME_${EPOCH}.md (epoch phase, gates queued: push word);
(3) PR body at tooling/harness/forge/PR_${item.id}.md ending "Merge is reserved for
Joe — this harness never pushes."; (4) fresh commit staging ONLY those named files:
"[SCRIBE ${item.id}] record epoch result"; lightweight tag v6/${item.id}/done.
If reject: LEDGER DeadEnd + DEADENDS.md row; branch LEFT in place; update state files;
awaiting_human_merge=false.
Public prose cites LEDGER IDs, never guarded subsystem names.
Return ReceiptSchema.`;

// ---------------------------------------------------------------------------
// Per-item runner with ONE re-plan bounce.
// ---------------------------------------------------------------------------
async function runItem(item, useWorktree) {
  const spec = await call(scoutPrompt(item), {
    schema: SpecSchema, agentType: 'Explore', phase: 'scout', label: `scout:${item.id}`,
  });
  if (!spec || isTerminal(spec)) return spec;
  if (spec.frozen_zone_contact) {
    return { rfc_only: true, item_id: item.id, reason: 'frozen_zone_contact -> RFC only (G8/harness-maintenance territory)' };
  }

  let bounceEvidence = null;
  for (let attempt = 1; attempt <= 2; attempt++) {
    let design = await call(architectPrompt({ ...spec, _attempt: attempt }, bounceEvidence), {
      schema: DesignSchema, agentType: 'Explore', phase: 'design', label: `arch:${item.id}#${attempt}`, model: 'fable',
    });
    if (!design || isTerminal(design)) return design;

    if ((design.alternatives || []).length > 0) {
      const lenses = ['artist/user impact', 'maintenance cost', 'ecosystem forward-compat'];
      const votes = (await parallel(lenses.map((lens, i) => () => call(judgePrompt(design, lens, i + 1), {
        schema: JudgeSchema, agentType: 'Explore', phase: 'design', label: `judge${i + 1}:${item.id}`, model: 'fable',
      })))).filter(Boolean).filter((v) => !isTerminal(v));
      const winners = new Set(votes.map((v) => v.winner));
      if (winners.size !== 1) {
        return { halt: 'design_split', item_id: item.id, gate: 'G7', votes };
      }
      const w = votes[0].winner;
      if (w > 0) design = { ...design, ...design.alternatives[w - 1], item_id: design.item_id, alternatives: [] };
      log(`${item.id}: judge panel unanimous -> alternative ${w}`);
    }

    const build = await call(forgePrompt(design, EPOCH), {
      schema: BuildSchema, phase: 'build', label: `forge:${item.id}#${attempt}`, model: 'fable',
      ...(useWorktree ? { isolation: 'worktree' } : {}),
    });
    if (!build || isTerminal(build)) return build;

    const measure = await call(cruciblePrompt(build), {
      schema: MeasureSchema, agentType: 'Explore', phase: 'verify', label: `crucible:${item.id}#${attempt}`,
      ...(useWorktree ? { isolation: 'worktree' } : {}),
    });
    if (!measure || isTerminal(measure)) return measure;

    const lenses = [
      'weakened/deleted test assertion, false-verified, threshold tampering',
      'silent regression / scope creep beyond spec',
      'determinism break / frozen-zone touch / disclosure hygiene in prose',
    ];
    const verdicts = (await parallel(lenses.map((lens, i) => () => call(skepticPrompt(measure, build, lens), {
      schema: RefuteSchema, agentType: 'Explore', phase: 'refute', label: `skeptic-${'ABC'[i]}:${item.id}#${attempt}`, model: 'fable',
    })))).filter(Boolean).filter((v) => !isTerminal(v));
    const refutals = verdicts.filter((v) => v.refuted);
    const decision = accept(measure, refutals);
    log(`${item.id}#${attempt}: ${decision.accept ? 'ACCEPT' : 'REJECT'} (mechanical=${decision.mechanical}, refutals=${refutals.length}, invoked=${INVOKED}/${BUDGET})`);

    if (decision.accept) {
      return call(scribePrompt(measure, decision, item, build), {
        schema: ReceiptSchema, phase: 'ledger', label: `scribe:${item.id}`,
      });
    }
    if (attempt === 1) {
      bounceEvidence = { ratchet: measure.ratchet_verdict, refutals: refutals.map((r) => ({ class: r.class, reasons: r.reasons })) };
      log(`${item.id}: re-plan bounce — Architect revises once`);
      continue;
    }
    return call(scribePrompt(measure, decision, item, build), {
      schema: ReceiptSchema, phase: 'ledger', label: `scribe:${item.id}`,
    });
  }
  return null;
}

// ===========================================================================
// EPOCH
// ===========================================================================
phase('select');
const boot = await call(selectPrompt(), { schema: SelectSchema, label: 'select' });
if (!boot || isTerminal(boot)) return { epoch: EPOCH, halt: (boot && boot.halt) || 'select_failed' };
if (!boot.ratchet_green) {
  log(`master baseline is RED (${boot.ratchet_notes}) — systemic halt per §7`);
  return { epoch: EPOCH, halt: 'master_baseline_red', notes: boot.ratchet_notes };
}

let backlog = SEED.length ? SEED.slice()
  : (boot.ready_item_ids || []).map((id) => ({ id, title: id, summary: 'from STATE/BACKLOG', kind: 'fix' }));
const receipts = [];
const maxIterations = MODE === 'sweep' ? 5 : 1;

for (let iter = 1; iter <= maxIterations; iter++) {
  const wave = backlog.slice(0, WAVE);
  if (wave.length === 0) { log('backlog dry — epoch ends'); break; }
  log(`epoch ${EPOCH} iter ${iter}: ${wave.map((i) => i.id).join(', ')} (wave=${WAVE}, budget ${INVOKED}/${BUDGET})`);
  const useWorktree = WAVE > 1;

  const batch = wave.length === 1
    ? [await runItem(wave[0], false)]
    : await parallel(wave.map((it) => () => runItem(it, useWorktree)));

  const done = (batch || []).filter(Boolean);
  receipts.push(...done);
  const progressed = done.filter((r) => r.kind === 'Confirmation').length;
  backlog = backlog.slice(wave.length);
  if (done.some((r) => r.halt === 'budget_exceeded')) { log('budget exceeded — pausing epoch (G7)'); break; }
  if (MODE === 'sweep' && progressed === 0) { log('zero-progress iteration — sweep ends (DeadEnd, not a loop)'); break; }
}

phase('checkpoint');
const ready = receipts.filter((r) => r.awaiting_human_merge);
const gates = receipts.filter((r) => isTerminal(r));
log(`epoch ${EPOCH} done — ${ready.length} ready for merge; ${gates.length} gates queued; ${INVOKED}/${BUDGET} invocations`);
return {
  epoch: EPOCH,
  invoked: INVOKED,
  ready: ready.map((r) => ({ item: r.item_id, branch: r.branch, pr: r.pr_body_path })),
  gates,
  receipts,
};
