---
candidate: flip-library-default-behind-env-switch
goal: Flip a package's default mode (synthetic→bge) when the test suite strips the controlling env var
verifier_outcome: PASS (full suite 282→289 green both modes)
similar_to: []
created: 2026-05-27
consolidated_from: 1
---

## Goal
Change `DEFAULT_MODE` for an embedder selected via `BRIDGE_EMBEDDER_MODE`, where
an autouse `conftest` fixture `delenv`s that var before every test.

## Approach
1. Recognize the trap: a shell-level `ENV=value` is **deleted per-test** by
   `conftest.delenv`, so "run suite with ENV set" does NOT exercise that mode.
   True default-mode coverage only comes from changing the constant.
2. Flip the constant; run the full suite to surface the real ripple empirically
   rather than guessing.
3. Triage failures into buckets: (a) tests asserting the old default → update
   expectation; (b) synthetic-path unit tests with mode-specific fixtures → pin
   the old mode explicitly in the fixture (`monkeypatch.setenv`); (c) mock
   signatures broken by an unrelated change (local_files_only kwarg) → widen mock.
4. Keep the new default's coverage in the real e2e/integration tests; pin the
   legacy mode only where the test's *intent* is the legacy path.

## Verifier
L0 ruff + L1 full suite, run in default mode AND with explicit legacy-mode pins.

## Anti-patterns
- Trusting a shell-level env override when conftest strips it (false baseline).
- Pinning the whole suite to the legacy mode (loses new-default coverage).
