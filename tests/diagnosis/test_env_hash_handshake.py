"""env_hash handshake — cross-repo parity vectors (DIAG.C4).

Every vector in schema/handshake/env_hash_vectors.json must pass verbatim;
the same file is mirrored into any consuming repo, so drift here is a treaty break.
"""

import json
import re
from pathlib import Path

from agent.diagnosis.diagnosis import env_hash

# File-relative, not conftest-imported: the packaging gate runs this suite
# from a non-repo cwd where 'conftest' is not importable as a module.
VECTORS_PATH = Path(__file__).parents[2] / "schema" / "handshake" / "env_hash_vectors.json"


def _vectors() -> list[dict]:
    return json.loads(VECTORS_PATH.read_text(encoding="utf-8"))["vectors"]


def _vector(name: str) -> dict:
    return next(v for v in _vectors() if v["name"] == name)


class TestHandshakeVectors:
    def test_every_vector_passes(self):
        vectors = _vectors()
        assert vectors, "handshake file has no vectors"
        for v in vectors:
            assert env_hash(v["env"]) == v["expected"], f"vector {v['name']!r} drifted"

    def test_reordered_keys_hash_identically_to_nominal(self):
        nominal = _vector("nominal")
        reordered = _vector("reordered-keys")
        assert env_hash(reordered["env"]) == env_hash(nominal["env"]) == nominal["expected"]


class TestHashProperties:
    def test_changing_any_single_field_changes_the_hash(self):
        nominal = _vector("nominal")["env"]
        assert len(nominal) == 6  # the canonical six-field block
        base = env_hash(nominal)
        for field in nominal:
            mutated = dict(nominal)
            mutated[field] = nominal[field] + "-mutated"
            assert env_hash(mutated) != base, f"changing {field!r} did not change the hash"

    def test_hash_shape_is_32_chars_lowercase_hex(self):
        for v in _vectors():
            digest = env_hash(v["env"])
            assert re.fullmatch(r"[0-9a-f]{32}", digest), digest
