# SCOUT PASS — Store 3 retrieval interface

**Repo:** Cozy
**Type:** Targeted scout. NOT a full repo inventory.
**Time:** 15–30 min
**Output:** One verdict — Case A or Case B — with supporting evidence.

---

## Context (locked premises — do not re-litigate)

- Moneta v1.1.0 is published. Handle architecture on `origin/main` (commit `bc65bf5`).
- Moneta's public API is **content-addressed only**:
  - `deposit(payload, embedding, protected_floor)` → UUID
  - `query(embedding, limit)` → `List[Memory]`
  - `signal_attention(weights)`
  - `get_consolidation_manifest()` → `List[Memory]`
  - `run_sleep_pass()` → harness operator
- **No cross-namespace traversal. No USD stage exposure. No path-based read API.** This is by design — the substrate's architectural novelty is content-addressed retrieval.
- Store 3 (the "Experience accumulator") in Cozy is the **retirement target** for the upcoming Moneta integration.
- This scout exists to answer **one question** so retirement implementation can begin.

---

## The question

**How does Store 3 currently retrieve "personal history" — by embedding similarity, or by USD path / namespace walk?**

| Case | Signal |
|---|---|
| **A** | Reads take an embedding / vector input (cosine search, k-NN, vector store query) |
| **B** | Reads take a USD path, `Sdf.Path`, prim hierarchy walk, or namespace string |
| **MIXED** | Both interfaces exist — flag and describe each |

---

## What to look at

1. **Find Store 3 in the Cozy repo.** Likely identifiers: `Store3`, `ExperienceStore`, `experience_accumulator`, `personal_history`, or similar. If naming is non-obvious, search for the concept of "experience" + "store" or "history" + "retrieve".

2. **Find the READ methods on Store 3.** Any method that returns historical experience to a caller. Ignore writes (deposit, append, accumulate) for this pass.

3. **For each read method, capture:**
   - Method signature (name, args with types, return type)
   - What the args represent (embedding? path? both?)
   - Where the implementation looks up the data (vector index? USD stage traversal? direct dict lookup?)

4. **Find every call site that uses Store 3's read methods.** List them.

5. **Quick look at writes too:** how does data *get into* Store 3? Are experience entries deposited with embeddings already attached, or do they come in as USD prims that get walked later?

---

## What NOT to do

- Do not do a full Cozy repo inventory. This scout is scoped to Store 3 only.
- Do not refactor anything.
- Do not propose alternatives, designs, or fixes.
- Do not speculate about what the interface *should* be — report what it *is*.
- Do not touch tests, build files, or unrelated modules.

---

## Output format

```
CASE: A | B | MIXED

STORE 3 LOCATION:
  file: <path/to/store3.py>
  class: <ClassName>

READ METHOD(S) FOUND:
  - ClassName.method_name(arg: ArgType) -> ReturnType
      args: <embedding | path | string | other — describe>
      lookup: <how the data is fetched internally>
  - ...

CALL SITES:
  - <file>:<line> — <what calls it, what it does with the result>
  - ...

WRITE PATH (one-line summary):
  - <how data enters Store 3 — embedding-attached or path-based>

NOTES:
  - <any wrinkle that matters for retirement: mixed interfaces,
     hidden coupling, anything that complicates the verdict>
```

---

## Why this matters (for the executing session — not for re-litigation)

- **Case A** means Store 3 retirement is straightforward: experience prims `deposit()` into Moneta, `query()` retrieves by embedding. Clean handoff. Demo wiring trivial.
- **Case B** means Store 3 used an interface Moneta no longer exposes. Real design choice required — translation layer, scope downgrade for v0.1, or substrate API addition. Not a blocker, but the path forks based on the answer.
- **MIXED** means the path forks per-call-site; the inventory will tell us which calls go which way.

The scout's job is the verdict + evidence. The fork decision happens after.
