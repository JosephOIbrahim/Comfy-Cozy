## [GRAPH × FORGE] Windows portability — replace grep with pathlib in test_workflow_patch_engine_live.py

**Status:** QUEUED
**Priority:** LOW
**Baseline:** 2717 passing (after GRAPH×FORGE health fix lands), 1 failure
**Target:** 2718 passing, 0 failures

### Problem

`tests/test_workflow_patch_engine_live.py::test_no_legacy_src_cognitive_imports_remain`
shells out to `grep` via subprocess, which doesn't exist on Windows.

```python
result = subprocess.run(
    ["grep", "-rln", "from src.cognitive", "agent/", "panel/", "cognitive/"],
    capture_output=True, text=True,
)
```

Fails with `FileNotFoundError: [WinError 2]`.

### Fix

Replace subprocess+grep with pure Python using `pathlib.Path.rglob`:

```python
from pathlib import Path

def test_no_legacy_src_cognitive_imports_remain():
    offenders = []
    for root in ("agent", "panel", "cognitive"):
        for py_file in Path(root).rglob("*.py"):
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            if "from src.cognitive" in text:
                offenders.append(str(py_file))
    assert not offenders, f"Legacy src.cognitive imports found: {offenders}"
```

### Acceptance criteria

- Test passes on Windows and Linux
- Same semantic check (no `from src.cognitive` in agent/, panel/, cognitive/)
- Baseline: 2718 passing, 0 failures

### Constraints

- Pure stdlib — no new dependencies
- No subprocess calls
