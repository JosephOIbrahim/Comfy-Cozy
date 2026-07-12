"""CLI + MCP surface tests for the keyless diagnosis subsystem (DISPATCH D1).

run_diagnose exit codes (0 rendered / 1 strict-critical / 2 no document), --json
output shape, the ONE MCP read surface (query via agent.tools.handle), and the
typer verb wiring. No API key exists anywhere in this path — proven by deleting
ANTHROPIC_API_KEY before the calls. The autouse isolated_diagnosis_dir fixture
keeps every test's document store in tmp_path.
"""

import json
import os
import time

import pytest

from agent.diagnosis.cli import query, run_diagnose
from agent.diagnosis.diagnosis import build_diagnosis, emit, env_hash

OOM_ERROR_TEXT = "RuntimeError: CUDA out of memory. Tried to allocate 2.50 GiB"


def _seed_clean(env, run, prompt_id="p-clean-1"):
    """Emit one completed run with no triggers and no findings."""
    return emit(build_diagnosis(env, dict(run, promptId=prompt_id), node_id="127.0.0.1:8188"))


def _seed_error(env, run, prompt_id="p-oom-1"):
    """Emit one error run whose OOM signature yields a critical vram_pressure finding."""
    run = dict(run, promptId=prompt_id, status="error", durationS=3.2, stages=[])
    return emit(build_diagnosis(env, run, node_id="127.0.0.1:8188", error_text=OOM_ERROR_TEXT))


@pytest.fixture
def seeded_store(sample_env, sample_run):
    """One clean run, then one OOM error run — the error doc is the newest."""
    clean_path = _seed_clean(sample_env, sample_run)
    backdated = time.time() - 3600
    os.utime(clean_path, (backdated, backdated))  # mtime tiebreak: error doc wins "latest"
    error_path = _seed_error(sample_env, sample_run)
    return {"clean": clean_path, "error": error_path}


class TestRunDiagnose:
    def test_last_renders_and_returns_zero(self, seeded_store, capsys):
        assert run_diagnose(last=True) == 0
        out = capsys.readouterr().out
        assert "vram_pressure" in out

    def test_json_output_is_the_raw_document(self, seeded_store, capsys):
        assert run_diagnose(last=True, as_json=True) == 0
        doc = json.loads(capsys.readouterr().out)
        assert doc["run"]["status"] == "error"
        assert doc["findings"][0]["code"] == "vram_pressure"
        assert doc["findings"][0]["severity"] == "critical"

    def test_strict_returns_one_when_critical_present(self, seeded_store):
        assert run_diagnose(last=True, strict=True) == 1

    def test_strict_returns_zero_on_clean_only_store(
        self, sample_env, sample_run, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("DIAGNOSIS_DIR", str(tmp_path / "clean_only"))
        _seed_clean(sample_env, sample_run)
        assert run_diagnose(last=True, strict=True) == 0

    def test_empty_store_returns_two(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DIAGNOSIS_DIR", str(tmp_path / "nothing_here"))
        assert run_diagnose(last=True) == 2

    def test_keyless_path_no_api_key_anywhere(self, seeded_store, capsys, monkeypatch):
        """D1: the entire diagnose path works with ANTHROPIC_API_KEY deleted."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert run_diagnose(last=True) == 0
        capsys.readouterr()  # discard the rendered report
        assert run_diagnose(last=True, as_json=True) == 0
        doc = json.loads(capsys.readouterr().out)
        assert doc["findings"][0]["code"] == "vram_pressure"
        latest = json.loads(query("latest"))
        assert latest["run"]["promptId"] == "p-oom-1"
        assert run_diagnose(last=True, strict=True) == 1


class TestMcpSurface:
    """The ONE MCP read surface: handle('diagnose', {...}) — Cherny cut #5."""

    def test_query_latest_returns_newest_doc(self, seeded_store):
        from agent.tools import handle

        doc = json.loads(handle("diagnose", {"query": "latest"}))
        assert doc["run"]["promptId"] == "p-oom-1"
        assert doc["run"]["status"] == "error"

    def test_query_env_returns_hash_env_and_open_findings(self, seeded_store, sample_env):
        from agent.tools import handle

        result = json.loads(handle("diagnose", {"query": "env"}))
        assert result["envHash"] == env_hash(sample_env)
        assert result["env"] == sample_env
        codes = {f["code"] for f in result["openFindings"]}
        assert "vram_pressure" in codes

    def test_query_by_prompt_id_finds_that_doc(self, seeded_store):
        from agent.tools import handle

        doc = json.loads(handle("diagnose", {"query": "p-clean-1"}))
        assert doc["run"]["promptId"] == "p-clean-1"
        assert doc["run"]["status"] == "completed"

    def test_query_nonexistent_id_returns_error_json_never_raises(self, seeded_store):
        from agent.tools import handle

        result = json.loads(handle("diagnose", {"query": "nonexistent-id"}))
        assert "error" in result


class TestCliVerb:
    """One heavy agent.cli import (house pattern — see tests/test_conn_ctx.py)."""

    def test_diagnose_verb_registered_and_json_parseable(self, sample_env, sample_run):
        from typer.testing import CliRunner

        from agent.cli import app

        _seed_error(sample_env, sample_run)
        result = CliRunner().invoke(app, ["diagnose", "--last", "--json"])
        assert result.exit_code == 0
        doc = json.loads(result.stdout.strip().splitlines()[-1])
        assert doc["run"]["status"] == "error"
        assert doc["findings"][0]["code"] == "vram_pressure"
