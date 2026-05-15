---
description: Run one full Cozy chain (scout → architect → ... → scribe) with self-healing.
argument-hint: "[intent description]"
---

# /cozy-cycle — One MoE chain pass with self-healing

You are about to drive one full MoE chain pass governed by
`.claude/COZY_CONSTITUTION.md` and the 10 commandments in
`agent/stage/constitution.py`.

## User Intent

$ARGUMENTS

## Protocol

1. **Classify the intent** using the keyword sets in
   `agent/stage/moe_dispatcher.py:_TASK_KEYWORDS`. Pick the matching
   `TaskType` and resolve its chain via `TASK_CHAINS`.

2. **Dispatch each specialist in order**, using the Agent tool with
   `subagent_type` set to the matching `cozy-*` subagent
   (e.g. `cozy-scout`, `cozy-architect`, ...). Pass the prior
   specialist's typed handoff artifact as input.

3. **After each specialist returns**, validate:
   - Artifact `artifact_type` matches the expected type for that
     specialist (commandment 6, `explicit_handoffs`).
   - No constitutional violations were emitted in the result.
   - If a TERMINAL was raised, halt and emit a BLOCKER summary.

4. **The chain MUST end with `cozy-scribe`** if any specialist mutated
   state (Article II). The Scribe produces the final
   `persistence_receipt` confirming the flush.

5. **Self-healing ladder** (Article III):
   - TRANSIENT: backoff and retry up to 3 times within the same
     specialist invocation.
   - RECOVERABLE: re-dispatch the appropriate specialist
     (FORGE for build errors, PROVISIONER for missing assets,
     ARCHITECT for plan errors).
   - TERMINAL: halt the chain, summarize, exit.

## Output

Produce a single chain-summary block at the end:

```
Chain: <task_type>
Specialists: <names in order>
Halt reason: <budget|completed|TERMINAL:reason>
Artifacts produced: <list of artifact_types>
Persistence: <flushed_at from persistence_receipt | NOT_FLUSHED>
```

Do NOT push to remote. Do NOT run destructive git operations.
Do NOT bypass commandment gates.
