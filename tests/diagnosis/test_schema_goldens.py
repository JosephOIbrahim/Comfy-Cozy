"""Schema goldens — the interchange treaty proven against pinned fixtures.

The four valid goldens validate against schema/diagnosis.schema.json and
round-trip byte-stable through the pydantic model in canonical form. The
INVALID_* fixtures are rejected by BOTH enforcement layers, and the
watched-fail proves the rejection teeth live in the invariant clause.
"""

import copy
import json

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from agent.diagnosis.diagnosis import Diagnosis, canonical_json

from conftest import GOLDEN_DIR, SCHEMA_PATH

VALID_GOLDENS = ["clean_run", "env_warn_clean_run", "vram_trigger", "error_run"]


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _golden(name: str) -> dict:
    """Load a golden fixture, stripping the top-level $comment annotation if present."""
    doc = json.loads((GOLDEN_DIR / f"{name}.json").read_text(encoding="utf-8"))
    doc.pop("$comment", None)
    return doc


class TestSchemaItself:
    def test_schema_is_a_valid_draft202012_schema(self):
        Draft202012Validator.check_schema(_schema())


class TestValidGoldens:
    @pytest.mark.parametrize("name", VALID_GOLDENS)
    def test_validates_against_schema(self, name):
        Draft202012Validator(_schema()).validate(_golden(name))

    @pytest.mark.parametrize("name", VALID_GOLDENS)
    def test_pydantic_round_trip_is_byte_stable(self, name):
        doc = _golden(name)
        round_tripped = Diagnosis.model_validate(doc).to_doc()
        assert canonical_json(round_tripped) == canonical_json(doc)


class TestWatchedFail:
    def test_silent_trigger_rejected_by_the_invariant_and_nowhere_else(self):
        """Watched fail: fixture passes under the weakened schema (allOf[0]
        blanked) and is rejected under the real one — both runs encoded here
        permanently."""
        doc = _golden("INVALID_silent_trigger")
        schema = _schema()
        # (a) the real schema rejects it — a fired trigger with no findings.
        assert not Draft202012Validator(schema).is_valid(doc)
        # (b) the runtime enforcer rejects it too.
        with pytest.raises(ValidationError):
            Diagnosis.model_validate(doc)
        # (c) blank THE INVARIANT (allOf[0]) and the fixture is ACCEPTED:
        # the rejection teeth live in that clause and nowhere else.
        weakened = copy.deepcopy(schema)
        del weakened["allOf"][0]
        assert Draft202012Validator(weakened).is_valid(doc)


class TestUnexplainedError:
    def test_error_without_execution_error_trigger_rejected_by_both_layers(self):
        """allOf[1]: an execution error is never allowed to be silent."""
        doc = _golden("INVALID_unexplained_error")
        assert not Draft202012Validator(_schema()).is_valid(doc)
        with pytest.raises(ValidationError):
            Diagnosis.model_validate(doc)
