# Authority Map — v2.0

## Scope Definitions

### Intent Scope
**Role:** Translate artistic language into parameter specifications.
**Can:** Read workflow state, inspect nodes, search models, capture intent, read memory.
**Cannot:** Execute workflows, mutate workflows, judge image quality.

### Execution Scope
**Role:** Apply workflow mutations and execute.
**Can:** Add/connect/set nodes, apply patches, execute workflows, save sessions, optimize.
**Cannot:** Analyze images, compare outputs, suggest improvements (verify's authority).

### Verify Scope
**Role:** Judge output quality and track refinement.
**Can:** Analyze images, compare outputs, read/write outcomes, track iterations, read metadata.
**Cannot:** Mutate workflows, execute workflows (can only recommend changes).

### Full Scope
**Role:** External MCP client (Claude Code / Claude Desktop).
**Can:** Everything. No restrictions.

## Enforcement

Authority is enforced at dispatch time by `ScopedDispatcher`. Unauthorized calls
return a structured JSON error with the scope name and hint text. The underlying
`handle()` function is never called for denied tools.

## All Scopes Share

Every scope has read access to: node info, all nodes, system stats, queue status,
history, custom nodes, models, workflows, templates, discovery, model compatibility,
CivitAI, GitHub releases, workflow classification, and intent classification.
