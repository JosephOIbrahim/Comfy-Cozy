"""`agent diagnose --assert-env <hash>` — protect a frozen demo box (Gate cond 6):
exit 0 if the fingerprint is unchanged, 3 if it drifted, 2 if undeterminable. Keyless."""

import json
import unittest.mock as mock

from agent.diagnosis import diagnosis as diag
from agent.diagnosis.cli import run_diagnose

ENV = {"os": "win32", "python": "3.14.2", "torch": "2.9.1+cu130",
       "torchCuda": "cu130", "driver": "unknown", "comfyuiVersion": "0.27.0"}
HASH = diag.env_hash(ENV)


class TestAssertEnv:
    def test_match_exits_zero(self):
        with mock.patch.object(diag, "collect_env", return_value=dict(ENV)):
            assert run_diagnose(assert_env=HASH) == 0

    def test_drift_exits_three(self):
        drifted = {**ENV, "torch": "2.8.0+cu128", "torchCuda": "cu128"}
        with mock.patch.object(diag, "collect_env", return_value=drifted):
            assert run_diagnose(assert_env=HASH) == 3  # not 0, not 1, not 2 — its own code

    def test_case_insensitive_and_stripped(self):
        with mock.patch.object(diag, "collect_env", return_value=dict(ENV)):
            assert run_diagnose(assert_env=f"  {HASH.upper()}  ") == 0

    def test_worker_unreachable_falls_back_to_last_report(self):
        # Seed a real report, then simulate the worker being down at assert time.
        diag.emit(diag.build_diagnosis(ENV, {
            "promptId": "p", "workflowHash": "a" * 32, "status": "completed",
            "durationS": 1.0, "vramPeakGb": None, "stages": []}, "127.0.0.1:8188"))
        with mock.patch.object(diag, "collect_env", side_effect=OSError("refused")):
            assert run_diagnose(assert_env=HASH) == 0  # matched the on-disk report

    def test_unreachable_and_no_reports_exits_two(self):
        with mock.patch.object(diag, "collect_env", side_effect=OSError("refused")):
            assert run_diagnose(assert_env=HASH) == 2

    def test_json_output_shape(self, capsys):
        with mock.patch.object(diag, "collect_env", return_value=dict(ENV)):
            run_diagnose(assert_env=HASH, as_json=True)
        out = json.loads(capsys.readouterr().out)
        assert out["match"] is True and out["actual"] == HASH and out["source"] == "live worker"
