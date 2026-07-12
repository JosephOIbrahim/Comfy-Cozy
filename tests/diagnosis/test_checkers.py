"""Checker behavior: purity, designated codes, fail-soft (DIAG.C9 as amended).

A checker is a pure function (env, run, baseline, triggers, error_text) -> list[Finding].
Same inputs, same findings; absent signal -> []; the emit path never raises.
"""

import pytest

from agent.diagnosis.checks import (
    CHECKS,
    DESIGNATED_CODES,
    check_env_torch_cuda_mismatch,
    check_vram_pressure,
    map_execution_error,
    run_checks,
)

EMPTY_BASELINE = {"runCount": 0, "durationMedianS": None, "stageMediansMs": {}}

OOM_TEXT = "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB"
SHAPE_ERROR_TEXT = "RuntimeError: mat1 and mat2 shapes cannot be multiplied"


def _scenarios(env: dict, run: dict) -> dict[str, tuple]:
    """A spread of (env, run, baseline, triggers, error_text) inputs per checker branch."""
    return {
        "clean": (env, run, EMPTY_BASELINE, [], ""),
        "oom": (
            {**env},
            {**run, "status": "error"},
            EMPTY_BASELINE,
            ["execution_error", "oom"],
            OOM_TEXT,
        ),
        "vram_threshold": (
            {**env},
            {**run, "vramPeakGb": 23.5},
            EMPTY_BASELINE,
            ["vram_threshold"],
            "",
        ),
        "mismatch_env": (
            {**env, "torch": "2.7.1", "torchCuda": "unknown"},
            {**run},
            EMPTY_BASELINE,
            [],
            "",
        ),
        "execution_error": (
            {**env},
            {**run, "status": "error"},
            EMPTY_BASELINE,
            ["execution_error"],
            SHAPE_ERROR_TEXT,
        ),
    }


class TestPurity:
    @pytest.mark.parametrize("checker", CHECKS, ids=lambda c: c.__name__)
    def test_same_inputs_yield_same_findings(self, checker, sample_env, sample_run):
        """Calling a checker twice with identical inputs is byte-for-byte equal."""
        for name, (env, run, baseline, triggers, error_text) in _scenarios(
            sample_env, sample_run
        ).items():
            first = [
                f.model_dump() for f in checker(env, run, baseline, list(triggers), error_text)
            ]
            second = [
                f.model_dump() for f in checker(env, run, baseline, list(triggers), error_text)
            ]
            assert first == second, f"{checker.__name__} is impure on scenario {name!r}"


class TestDesignatedCodes:
    @pytest.mark.parametrize("checker", CHECKS, ids=lambda c: c.__name__)
    def test_every_finding_stays_within_designated_codes(self, checker, sample_env, sample_run):
        """No checker emits a code outside its DESIGNATED_CODES entry, on any input."""
        allowed = DESIGNATED_CODES[checker.__name__]
        for name, (env, run, baseline, triggers, error_text) in _scenarios(
            sample_env, sample_run
        ).items():
            for finding in checker(env, run, baseline, list(triggers), error_text):
                assert finding.code in allowed, (
                    f"{checker.__name__} emitted undesignated code {finding.code!r} "
                    f"on scenario {name!r}"
                )


class TestNeverRaises:
    """run_checks is fail-soft: malformed input -> a list, never an exception (DIAG.C1)."""

    def test_env_with_none_fields(self, sample_run):
        env = {k: None for k in ("os", "python", "torch", "torchCuda", "driver", "comfyuiVersion")}
        result = run_checks(env, sample_run, EMPTY_BASELINE, [], "")
        assert isinstance(result, list)

    def test_run_missing_keys(self, sample_env):
        result = run_checks(sample_env, {}, EMPTY_BASELINE, ["vram_threshold"], "")
        assert isinstance(result, list)

    def test_triggers_containing_junk(self, sample_env, sample_run):
        result = run_checks(sample_env, sample_run, EMPTY_BASELINE, ["banana", 42, None, ""], "")
        assert isinstance(result, list)

    def test_error_text_none(self, sample_env, sample_run):
        run = {**sample_run, "status": "error"}
        result = run_checks(sample_env, run, EMPTY_BASELINE, ["execution_error", "oom"], None)
        assert isinstance(result, list)

    def test_everything_malformed_at_once(self):
        result = run_checks({"driver": None}, {}, {}, ["oom", object()], None)
        assert isinstance(result, list)


class TestCheckVramPressure:
    def test_oom_trigger_yields_exactly_one_critical_with_fix_hint(self, sample_env, sample_run):
        run = {**sample_run, "status": "error"}
        findings = check_vram_pressure(
            sample_env, run, EMPTY_BASELINE, ["execution_error", "oom"], OOM_TEXT
        )
        assert len(findings) == 1
        f = findings[0]
        assert f.code == "vram_pressure"
        assert f.severity == "critical"
        assert f.actionable is True
        assert f.fixHint

    def test_vram_threshold_without_oom_yields_one_warn(self, sample_env, sample_run):
        run = {**sample_run, "vramPeakGb": 23.5}
        findings = check_vram_pressure(sample_env, run, EMPTY_BASELINE, ["vram_threshold"], "")
        assert len(findings) == 1
        assert findings[0].code == "vram_pressure"
        assert findings[0].severity == "warn"

    def test_neither_trigger_stays_dormant(self, sample_env, sample_run):
        assert check_vram_pressure(sample_env, sample_run, EMPTY_BASELINE, [], "") == []


class TestCheckEnvTorchCudaMismatch:
    def test_driver_known_torch_cuda_unknown_is_critical(self, sample_env, sample_run):
        env = {**sample_env, "torch": "2.7.1", "torchCuda": "unknown"}
        findings = check_env_torch_cuda_mismatch(env, sample_run, EMPTY_BASELINE, [], "")
        assert len(findings) == 1
        assert findings[0].code == "env_torch_cuda_mismatch"
        assert findings[0].severity == "critical"

    def test_driver_and_torch_cuda_both_known_is_dormant(self, sample_env, sample_run):
        assert check_env_torch_cuda_mismatch(sample_env, sample_run, EMPTY_BASELINE, [], "") == []

    def test_both_unknown_is_dormant_absent_signal(self, sample_env, sample_run):
        env = {**sample_env, "driver": "unknown", "torchCuda": "unknown"}
        assert check_env_torch_cuda_mismatch(env, sample_run, EMPTY_BASELINE, [], "") == []


class TestMapExecutionError:
    def test_execution_error_without_oom_maps_to_unknown_gap(self, sample_env, sample_run):
        run = {**sample_run, "status": "error"}
        findings = map_execution_error(
            sample_env, run, EMPTY_BASELINE, ["execution_error"], SHAPE_ERROR_TEXT
        )
        assert len(findings) == 1
        f = findings[0]
        assert f.code == "unknown_gap"
        assert f.context["trigger"] == "execution_error"

    def test_execution_error_with_oom_defers_to_vram_checker(self, sample_env, sample_run):
        run = {**sample_run, "status": "error"}
        findings = map_execution_error(
            sample_env, run, EMPTY_BASELINE, ["execution_error", "oom"], OOM_TEXT
        )
        assert findings == []

    def test_no_triggers_stays_dormant(self, sample_env, sample_run):
        assert map_execution_error(sample_env, sample_run, EMPTY_BASELINE, [], "") == []
