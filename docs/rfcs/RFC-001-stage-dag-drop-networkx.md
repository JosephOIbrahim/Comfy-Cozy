# RFC-001 — Drop networkx from the Workflow-Intelligence DAG

**Status:** DRAFT · freeze-legal (DESIGN) · **forge gated until 2026-06-16** (Mike Gold `agent/stage/**` freeze)
**Author:** CTO · 2026-06-11
**Tracks:** H2 / C-R13 `[RFC-stage]` follow-up — the in-module stage-import cost the caching wave deferred.
**Touches (frozen):** `agent/stage/dag/engine.py`. **Touches (non-frozen):** `pyproject.toml`, `tests/`.

---

## 1. Problem

`from agent.stage.dag import build_dag` pulls **networkx — 323 ms cold** (measured, `python -X importtime`). The validate path imports it (`agent/tools/comfy_execute.py:664-666`, gated by `DAG_ENABLED`), so the **first `validate_before_execute` in a process pays ~323 ms** of import it does not need. H2 made the stage layer *importer-side* lazy (`_ensure_stage()` in `agent/tools/__init__.py`) but explicitly parked the *in-module* import move as `[RFC-stage]` because it mutates frozen `agent/stage/**`.

What networkx is actually used for (`agent/stage/dag/engine.py`):

| Site | Call | Reality |
|---|---|---|
| `:78` | `nx.DiGraph()` + 6×`add_node` + 6×`add_edge` | a **fixed** 6-node graph, hardcoded |
| `:97` | `nx.is_directed_acyclic_graph(dag)` | an assert that is **always true** for a hardcoded acyclic graph |
| `:138` | `nx.topological_sort(dag)` | a **compile-time-constant** order |

The graph never varies: 6 nodes (`complexity, model_reqs, optimization, risk, readiness, tool_scope`), 6 edges, all literal. Its topological order is the constant `(complexity, model_reqs, optimization, risk, readiness, tool_scope)`. `evaluate_dag` already drives execution with an `if/elif` chain keyed on node name (`:138+`) — it uses the graph **only** to obtain that iteration order.

**networkx is a core dependency (`pyproject.toml:35`, `networkx>=3.0`) and `agent/stage/dag/engine.py` is its only consumer in the entire repo** (`grep -rln "import networkx\|networkx\." agent/ cognitive/` → one file). Every install carries a 323 ms graph library to topologically sort a 6-element list whose order is known at authoring time.

## 2. ENHANCE-target

Extends the existing `build_dag()` / `evaluate_dag()` pair — **not** a rewrite. The `WorkflowIntelligence` output, the six `compute_*` functions, the `DAG_ENABLED` switch, and every field surfaced by validate are unchanged. Only the iteration-order *mechanism* changes.

## 3. Proposed change (primary)

Replace the networkx DiGraph with the static order it always produces.

- `engine.py:26-31` — delete the `try: import networkx as nx / HAS_NX` block.
- `engine.py:62-99` `build_dag()` — return a frozen, dependency-checked static plan instead of an `nx.DiGraph`:

  ```python
  # Topological order is constant — the dependency edges below are encoded
  # once, here, and asserted by test_dag_order_matches_edges (RFC-001).
  _DAG_ORDER = (_COMPLEXITY, _MODEL_REQS, _OPTIMIZATION, _RISK, _READINESS, _TOOL_SCOPE)
  _DAG_EDGES = (
      (_COMPLEXITY, _OPTIMIZATION), (_MODEL_REQS, _OPTIMIZATION),
      (_MODEL_REQS, _RISK), (_RISK, _READINESS),
      (_RISK, _TOOL_SCOPE), (_READINESS, _TOOL_SCOPE),
  )

  def build_dag() -> tuple[str, ...]:
      """Return the intelligence compute order (static topological sort)."""
      return _DAG_ORDER
  ```

- `engine.py:106-138` `evaluate_dag()` — iterate `dag` directly (it is now the order tuple); drop the `import networkx` at `:134` and the `nx.topological_sort` at `:138`. The `if not HAS_NX` guards at `:72` and `:131` are deleted (the capability no longer depends on an optional import).
- `pyproject.toml:35` — remove `"networkx>=3.0"` from core `dependencies`.

**Why a tuple, not a hand-rolled DiGraph shim:** `evaluate_dag` never reads node attributes or edges at runtime — only the order. The `compute=` attributes attached at `:82-87` are introspection-only (the docstring says so) and unused by the evaluator. A tuple is the whole contract.

## 4. Reversibility

Single-file logic change plus a one-line dependency removal. Revert = `git revert`. No data migration, no persisted artifact, no API surface change (`build_dag`/`evaluate_dag` names and call sites unchanged; the return *type* of `build_dag` changes from `nx.DiGraph` to `tuple[str, ...]`, consumed only by `evaluate_dag` and the validate handler which passes it straight back — verified: `grep -rn "build_dag" agent/` shows `comfy_execute.py` and `engine.py` as the only callers).

## 5. Acceptance test (forge-time, `tests/`)

1. **Order-preservation oracle (the safety net):** a test that *does* import networkx (dev-only), builds the old-style DiGraph from `_DAG_EDGES`, and asserts `tuple(nx.topological_sort(g))` equals `_DAG_ORDER` — proving the hardcoded order is a valid topological sort of the declared edges. This pins the constant against future edge edits. (networkx stays a **dev** dependency for this one test, or the test is skipped when absent.)
2. **Output parity:** `evaluate_dag(build_dag(), wf)` produces a `WorkflowIntelligence` field-identical to `master` for a fixture set (the SD1.5 template + a ControlNet workflow + an empty graph).
3. **Cost regression:** `python -X importtime -c "from agent.stage.dag import build_dag"` shows **no networkx** in the trace.
4. **Full suite green**, including the 21 stage-layer files (now CI-tested per item #3).

## 6. Blast radius

- Removing networkx from core deps changes the install footprint. Verified single-consumer, so nothing else breaks — but the forge PR must re-run the full suite *after* an `pip install -e .` that no longer pulls networkx, to prove no hidden transitive importer. CI (post #68) installs `.[dev,stage]`; keep networkx under `dev` for acceptance test #1, or guard that test with `importorskip`.
- `build_dag()` return type changes `nx.DiGraph → tuple`. Only `evaluate_dag` and the validate handler consume it; both pass it opaquely. No external caller.
- Measured win: −323 ms on first validate; −1 core dependency for every install; faster cold import for any future path that touches the dag package.

## 7. Invariants touched

- **I2 FREEZE-RESPECT** — this RFC is the freeze-legal artifact; **the forge waits for 2026-06-16.** No `agent/stage/**` mutation lands before then.
- **I5 DO-NOT-TOUCH** — the load-bearing IP (delta-layer priority, the safety gate, the memory substrate) is untouched; the DAG is intelligence, not the delta substrate. This *extends* (mechanism swap), it does not rewrite semantics.
- **I8 TEST-AS-ORACLE** — acceptance test #1 is the hostile oracle: it keeps networkx around purely to prove the static order stays correct, so a future edge change that breaks the order fails loudly.

## 8. Alternative considered (rejected)

*Lazy-import networkx inside `build_dag()`* (the literal "in-module import move"). Rejected: the validate path calls `build_dag()` immediately after importing it, so the lazy move pays the 323 ms on the first validate anyway — it would help only stage-import paths that never build the DAG. Dropping networkx outright helps **every** path including the validate one, for strictly less long-term cost. The lazy move is the smaller diff but the worse outcome.

---

*Forge trigger: 2026-06-16 freeze lift. This RFC is forge-ready — §3 is the diff, §5 is the gate.*
