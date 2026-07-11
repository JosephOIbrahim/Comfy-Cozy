export const meta = {
  name: 'refinement-pass',
  description: 'One constitution-governed refinement pass: 3 scout lenses -> adjudicate -> disjoint forge -> crucible. Loop <=3x with commits between passes.',
  whenToUse: 'Invoke via Workflow({name:"refinement-pass", args:{pass_n, focus_hints, baseline_tests}}) once per pass; conductor commits between passes. Constitution: tooling/harness/refinement3x/CONSTITUTION.md',
  phases: [
    { title: 'Scout', detail: 'robustness / simplification / truth lenses, parallel' },
    { title: 'Adjudicate', detail: 're-read citations, kill, rank, cap 4, assign disjoint ownership' },
    { title: 'Forge', detail: 'one agent per approved cluster' },
    { title: 'Crucible', detail: 'full suite + ruff verdict' },
  ],
}

const passN = (args && args.pass_n) || 1
const hints = (args && args.focus_hints) || []
const baseline = (args && args.baseline_tests) || 0

const LAW = `You are one agent in refinement pass ${passN}/3 at G:\\Comfy-Cozy (Windows 11). Constitution (binding, see tooling/harness/refinement3x/CONSTITUTION.md):
- READ the code before claiming anything; every finding carries file:line you personally verified this session.
- FORBIDDEN: agent/stage/** ; public tool schemas / CLI surfaces / MCP behavior; new features; repo-wide mechanical churn (format normalization is parked); anything touching the tokens the brightline guard flags.
- No git commands, no installs, no network. Style: 99-char ruff lines, match surroundings, no reviewer-facing comments.
- Your final message is machine-parsed.`

const CAND = {
  type: 'object', required: ['candidates'],
  properties: {
    candidates: { type: 'array', maxItems: 6, items: {
      type: 'object', required: ['site', 'problem', 'fix', 'leverage', 'risk'],
      properties: {
        site: { type: 'string', description: 'file:line' },
        problem: { type: 'string' },
        fix: { type: 'string', description: 'surgical fix shape, <=3 files' },
        leverage: { type: 'integer', minimum: 1, maximum: 5 },
        risk: { type: 'integer', minimum: 1, maximum: 5 },
      } } },
  },
}

const LENSES = [
  { key: 'robustness', prompt: `LENS robustness: hunt real defects-in-waiting in agent/ (minus stage) and cognitive/: swallowed exceptions that hide actionable errors, mutable default arguments, unclosed resources, race-prone lazy init, error messages that lie about the actual failure. Only sites where the failure path is REACHABLE.` },
  { key: 'simplification', prompt: `LENS simplification: dead code with zero callers (grep-verified), duplicated logic that one helper should own (e.g. twin template loaders in agent/tools/pipeline.py:276 vs workflow_templates.py:22), single-use abstractions, code a senior reviewer would call overcomplicated. Surgical only — no architecture rewrites.` },
  { key: 'truth', prompt: `LENS truth/consistency: docstrings and comments that now CONTRADICT the code after today's changes (state dirs moved to ~/.comfy-cozy, distribution renamed comfy-cozy, probe caching in mcp_server), stale internal paths/names, validate_project warnings (README tool-count marker missing; test-step timeout warning), error strings referencing old behavior. Internal truth only — public docs were swept today.` },
]

phase('Scout')
const hintText = hints.length ? `\nKNOWN PARKED ITEMS to evaluate alongside your own findings (verify before adopting): ${hints.join(' | ')}` : ''
const scouts = await parallel(LENSES.map(l => () =>
  agent(`${LAW}\n\n${l.prompt}${hintText}\n\nReturn <=6 candidates, deduplicated, each with the exact surgical fix.`,
    { label: `scout:${l.key}`, phase: 'Scout', schema: CAND, effort: 'high' })))

const pool = scouts.filter(Boolean).flatMap((s, i) => s.candidates.map(c => ({ ...c, lens: LENSES[i].key })))
log(`scouts returned ${pool.length} candidates`)

phase('Adjudicate')
const ADJ = {
  type: 'object', required: ['approved', 'killed', 'verdict'],
  properties: {
    approved: { type: 'array', maxItems: 4, items: {
      type: 'object', required: ['site', 'fix', 'owned_files', 'tests'],
      properties: {
        site: { type: 'string' }, fix: { type: 'string' },
        owned_files: { type: 'array', items: { type: 'string' }, description: 'disjoint across approved items' },
        tests: { type: 'string', description: 'targeted pytest files to run' },
      } } },
    killed: { type: 'array', items: { type: 'object', required: ['site', 'reason'], properties: { site: { type: 'string' }, reason: { type: 'string' } } } },
    verdict: { type: 'string', enum: ['proceed', 'diminishing-returns'], description: 'diminishing-returns when nothing scores leverage>=3 at risk<=2' },
  },
}
const adj = await agent(`${LAW}\n\nADJUDICATE pass ${passN}. Candidates below. For EACH: open the cited site, confirm the problem is real and the fix surgical; kill anything speculative, risky (risk>2 needs leverage 5), stage-touching, or duplicating another candidate. Approve AT MOST 4, ranked by leverage/risk, with DISJOINT owned_files sets (merge candidates sharing files into one item). If nothing clears leverage>=3 at risk<=2, verdict=diminishing-returns with empty approved.\n\nCANDIDATES:\n${JSON.stringify(pool, null, 1)}`,
  { label: 'adjudicator', phase: 'Adjudicate', schema: ADJ, effort: 'xhigh' })

if (!adj || adj.verdict === 'diminishing-returns' || !adj.approved.length) {
  return { pass: passN, verdict: 'diminishing-returns', pool_size: pool.length, killed: adj ? adj.killed : [], applied: [] }
}

phase('Forge')
const FORGE = {
  type: 'object', required: ['summary', 'files_changed', 'verification'],
  properties: { summary: { type: 'string' }, files_changed: { type: 'array', items: { type: 'string' } }, verification: { type: 'string' }, concerns: { type: 'array', items: { type: 'string' } } },
}
const forged = await parallel(adj.approved.map((a, i) => () =>
  agent(`${LAW}\n\nFORGE item ${i + 1}: ${a.site}\nFIX: ${a.fix}\nYOU OWN ONLY: ${a.owned_files.join(', ')} (plus test files those changes break — list them). Other agents edit other files NOW.\nVerify: ruff check on touched files + run: .venv312/Scripts/python.exe -m pytest ${a.tests} -q --tb=short | tail -5. Report honestly.`,
    { label: `forge:${a.site.split(':')[0].split('/').pop()}`, phase: 'Forge', schema: FORGE, effort: 'high' })))

phase('Crucible')
const CRU = {
  type: 'object', required: ['suite', 'ruff', 'verdict'],
  properties: { suite: { type: 'string' }, ruff: { type: 'string' }, verdict: { type: 'string', enum: ['green', 'regression'] }, detail: { type: 'string' } },
}
const cru = await agent(`${LAW}\n\nCRUCIBLE: run the FULL gate and report verbatim tails:\n1. .venv312/Scripts/python.exe -m pytest tests/ -m "not integration" -q --tb=short -p no:cacheprovider 2>&1 | tail -3\n2. .venv312/Scripts/python.exe -m ruff check agent/ tests/ 2>&1 | tail -2\nBaseline to beat-or-match: ${baseline} passed, 0 failed. verdict=green only if failures==0 AND passed>=${baseline} AND ruff clean. Otherwise verdict=regression with the failing test names in detail.`,
  { label: 'crucible', phase: 'Crucible', schema: CRU, effort: 'medium' })

return { pass: passN, verdict: cru ? cru.verdict : 'regression', crucible: cru, applied: adj.approved, forged: (forged || []).filter(Boolean), killed: adj.killed }
