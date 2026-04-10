## [GRAPH × FORGE] Fix test_health.py mock leak

**Status:** QUEUED
**Priority:** MEDIUM
**Baseline:** 2713 passing, 5 failures
**Target:** 2717 passing, 1 failure

### Problem

Four tests in `tests/test_health.py` fail with `'PromptServer not initialized'`
despite mocking `agent.health.httpx.Client` and `agent.health._check_llm`.
The mocks are not intercepting — a real ComfyUI check is leaking through.

Failing tests:
- TestHealthAllOk::test_health_all_ok
- TestHealthComfyUIDown::test_health_comfyui_down
- TestHealthComfyUITimeout::test_health_comfyui_timeout
- TestHealthGPUInfo::test_health_gpu_info

### Investigation path

1. Read `agent/health.py` — identify the actual httpx call site and import path
2. Check whether `check_health()` imports httpx.Client at call time vs module time
3. The `'PromptServer not initialized'` string suggests a ComfyUI-internal error —
   find where that's raised and trace how it's reaching the test
4. Fix the mock target path OR refactor health.py to make it mockable

### Acceptance criteria

- All 4 test_health.py tests pass
- No changes to test_health.py test logic (fix the source, not the test)
- No new test failures introduced
- Baseline: 2717 passing

### Constraints

- Do NOT skip or xfail the tests
- Do NOT mock at a higher level to paper over the real issue
- If the root cause is that health.py has grown a hard ComfyUI dependency
  since these tests were written, surface that in the commit message
