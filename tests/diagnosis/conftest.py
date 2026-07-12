"""Shared fixtures for the diagnosis suite.

Every test gets an isolated document store: diagnosis_dir() reads DIAGNOSIS_DIR
at call time, so pointing it at tmp_path guarantees no test reads another's
documents (and none touch the real STATE_DIR).
"""

from pathlib import Path

import pytest

SAMPLE_ENV = {
    "os": "Windows-11",
    "python": "3.12.10",
    "torch": "2.7.1+cu128",
    "torchCuda": "cu128",
    "driver": "576.88",
    "comfyuiVersion": "0.3.44",
}

SAMPLE_RUN = {
    "promptId": "p-test-1",
    "workflowHash": "a" * 32,
    "status": "completed",
    "durationS": 41.2,
    "vramPeakGb": None,
    "stages": [{"stage": "9:KSampler", "ms": 36900.0}, {"stage": "8:VAEDecode", "ms": 2100.0}],
}

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
SCHEMA_PATH = Path(__file__).parents[2] / "schema" / "diagnosis.schema.json"
VECTORS_PATH = Path(__file__).parents[2] / "schema" / "handshake" / "env_hash_vectors.json"


@pytest.fixture(autouse=True)
def isolated_diagnosis_dir(tmp_path, monkeypatch):
    """Point the document store at a per-test temp dir (autouse)."""
    d = tmp_path / "diagnosis"
    monkeypatch.setenv("DIAGNOSIS_DIR", str(d))
    return d


@pytest.fixture
def sample_env():
    return dict(SAMPLE_ENV)


@pytest.fixture
def sample_run():
    return {k: (list(v) if isinstance(v, list) else v) for k, v in SAMPLE_RUN.items()}
