"""The completeness pin (DIAG.C9 as amended): an undeclared checker cannot ship.

Pins the CHECKS list by name, ties DESIGNATED_CODES to it, proves every designated
code is a citizen of the schema's finding-code enum, and exercises the invariant's
floor (guard_unknown_gap) plus deterministic trigger evaluation.
"""

import json
from pathlib import Path

from agent.diagnosis.checks import CHECKS, DESIGNATED_CODES
from agent.diagnosis.diagnosis import Finding, evaluate_triggers, guard_unknown_gap

SCHEMA_PATH = Path(__file__).parents[2] / "schema" / "diagnosis.schema.json"

PINNED_CHECKER_NAMES = [
    "check_vram_pressure",
    "check_env_torch_cuda_mismatch",
    "map_execution_error",
]

EMPTY_BASELINE = {"runCount": 0, "durationMedianS": None, "stageMediansMs": {}}


class TestCompletenessPin:
    def test_checks_list_is_pinned_by_name(self):
        """THE PIN: adding, removing, or reordering a checker fails this test."""
        assert [c.__name__ for c in CHECKS] == PINNED_CHECKER_NAMES

    def test_designated_codes_cover_exactly_the_pinned_checkers(self):
        assert set(DESIGNATED_CODES) == set(PINNED_CHECKER_NAMES)

    def test_every_designated_code_is_in_the_schema_enum(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        enum = set(schema["properties"]["findings"]["items"]["properties"]["code"]["enum"])
        for name, codes in DESIGNATED_CODES.items():
            undeclared = codes - enum
            assert not undeclared, (
                f"{name} designates codes outside the schema enum: {sorted(undeclared)}"
            )


class TestGuardUnknownGap:
    def test_trigger_with_checker_silence_produces_one_unknown_gap(self):
        findings = guard_unknown_gap(["vram_threshold"], [])
        assert len(findings) == 1
        f = findings[0]
        assert f.code == "unknown_gap"
        assert f.severity == "warn"
        assert f.actionable is False
        assert f.context["trigger"] == "vram_threshold"

    def test_existing_findings_pass_through_unchanged(self):
        existing = Finding(
            code="vram_pressure",
            severity="warn",
            actionable=True,
            explanation="VRAM peak breached the pressure threshold on a completed run.",
        )
        result = guard_unknown_gap(["vram_threshold"], [existing])
        assert result == [existing]
        assert result[0] is existing

    def test_no_triggers_no_findings_stays_empty(self):
        assert guard_unknown_gap([], []) == []


class TestEvaluateTriggers:
    def test_error_status_with_oom_text_fires_both(self, sample_run):
        run = {**sample_run, "status": "error"}
        triggers = evaluate_triggers(
            run, EMPTY_BASELINE, "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB"
        )
        assert triggers == ["execution_error", "oom"]

    def test_clean_run_with_no_baseline_stays_dormant(self, sample_run):
        assert evaluate_triggers(sample_run, EMPTY_BASELINE) == []

    def test_duration_regression_needs_history_and_ratio(self, sample_run):
        baseline = {"runCount": 3, "durationMedianS": 30.0, "stageMediansMs": {}}
        slow = {**sample_run, "durationS": 40.0}  # > 1.25 x 30.0
        assert "duration_regression" in evaluate_triggers(slow, baseline)
        within = {**sample_run, "durationS": 35.0}  # <= 1.25 x 30.0
        assert "duration_regression" not in evaluate_triggers(within, baseline)

    def test_vram_threshold_fires_at_ratio(self, sample_run):
        hot = {**sample_run, "vramPeakGb": 23.5}  # 23.5 / 24.0 >= 0.92
        assert "vram_threshold" in evaluate_triggers(hot, EMPTY_BASELINE, vram_total_gb=24.0)
        cool = {**sample_run, "vramPeakGb": 12.0}
        assert "vram_threshold" not in evaluate_triggers(cool, EMPTY_BASELINE, vram_total_gb=24.0)
