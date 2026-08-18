import json
from pathlib import Path

import pytest

from tools.research_notes.model import (
    NoteValidationError,
    load_note,
    validate_note,
    visible_word_count,
)


FIXTURE = Path(__file__).parent / "fixtures" / "research-note-sample.json"


def test_complete_note_contract_loads():
    note = load_note(FIXTURE)
    assert note["id"] == "ACE-RN-2026-001"
    assert note["author"] == "Chris Ma"
    assert note["status"] == "draft"
    assert set(note["parts"]) == {"problem", "mitigation", "research_agenda"}


def test_mitigation_claim_requires_research_reference():
    note = json.loads(FIXTURE.read_text("utf-8"))
    runtime = note["parts"]["mitigation"]["layers"][-1]
    runtime["reference_ids"] = []
    runtime["text"] = "Represent delegation as an explicit authorization object."

    with pytest.raises(NoteValidationError, match="mitigation claim requires a reference"):
        validate_note(note)


def test_logionos_direction_remains_an_implementation_hypothesis():
    note = json.loads(FIXTURE.read_text("utf-8"))
    note["parts"]["mitigation"]["logionos_direction"][0]["evidence"] = "evaluated"

    with pytest.raises(NoteValidationError, match="implementation-hypothesis"):
        validate_note(note)


def test_private_material_fails_closed():
    note = json.loads(FIXTURE.read_text("utf-8"))
    note["parts"]["problem"]["body"][0]["text"] = "PRIVATE_PROMPT"

    with pytest.raises(NoteValidationError, match="prohibited publication text"):
        validate_note(note)


def test_published_note_enforces_800_to_1500_visible_words():
    note = json.loads(FIXTURE.read_text("utf-8"))
    assert 800 <= visible_word_count(note) <= 1500
    note["status"] = "published"
    validate_note(note)

    note["parts"]["problem"]["body"] *= 8
    with pytest.raises(NoteValidationError, match="800 to 1500"):
        validate_note(note)
