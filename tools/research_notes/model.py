"""Validate the structured source used by ACE Research Note previews."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any


PUBLICATION_ID = re.compile(r"^ACE-RN-\d{4}-\d{3}$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
VERSION = re.compile(r"^[1-9]\d*\.\d+$")
CITATION = re.compile(r"\[(R\d+)\]")
EVIDENCE_LABELS = {
    "evaluated",
    "research-proposed",
    "implementation-hypothesis",
    "not-applicable",
}
SOURCE_KINDS = {"ACE Observation", "External Research", "Public Incident"}
PRIMARY_SOURCE_TYPES = {"original-paper", "authoritative-standard"}
PROHIBITED_TOKENS = {
    "private_prompt",
    "private_case_id",
    "holdout_case_id",
    "raw_output_hashes.jsonl",
}


class NoteValidationError(ValueError):
    """Raised when a Research Note source is unsafe or incomplete."""


def citation_keys(text: str) -> set[str]:
    return set(CITATION.findall(text))


def _require_nonempty(value: Any, name: str) -> None:
    if value is None or value == "" or value == []:
        raise NoteValidationError(f"{name} must not be empty")


def _require_known_references(
    reference_ids: list[str],
    references: dict[str, dict[str, Any]],
) -> None:
    unknown = sorted(set(reference_ids) - references.keys())
    if unknown:
        raise NoteValidationError(f"unknown reference ids: {', '.join(unknown)}")


def _validate_claim(
    claim: dict[str, Any],
    references: dict[str, dict[str, Any]],
) -> None:
    text = claim.get("text", "")
    _require_nonempty(text.strip(), "claim text")
    reference_ids = claim.get("reference_ids", [])
    _require_known_references(reference_ids, references)
    if citation_keys(text) != set(reference_ids):
        raise NoteValidationError("inline citations and reference_ids differ")


def note_slug(note: dict[str, Any]) -> str:
    slug = str(note.get("slug", ""))
    if not SLUG.fullmatch(slug):
        raise NoteValidationError("invalid Research Note slug")
    return slug


def visible_word_count(note: dict[str, Any]) -> int:
    visible: list[str] = []

    def collect(value: Any, key: str = "") -> None:
        if key == "reference_ids":
            return
        if isinstance(value, str):
            visible.append(value)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for child_key, child_value in value.items():
                collect(child_value, child_key)

    collect(note.get("parts", {}))
    return len(re.findall(r"\b[\w’'-]+\b", " ".join(visible)))


def load_note(path: Path) -> dict[str, Any]:
    note = json.loads(path.read_text("utf-8"))
    validate_note(note)
    return note


def validate_note(note: dict[str, Any]) -> None:
    if note.get("schema_version") != 1:
        raise NoteValidationError("unsupported schema version")
    if not PUBLICATION_ID.fullmatch(str(note.get("id", ""))):
        raise NoteValidationError("invalid ACE Research Note identifier")
    note_slug(note)
    if note.get("author") != "Chris Ma":
        raise NoteValidationError("author must be Chris Ma")
    if note.get("status") not in {"draft", "reviewed", "published"}:
        raise NoteValidationError("invalid publication status")
    if not VERSION.fullmatch(str(note.get("version", ""))):
        raise NoteValidationError("invalid publication version")
    try:
        date.fromisoformat(str(note.get("date", "")))
    except ValueError as exc:
        raise NoteValidationError("invalid publication date") from exc

    if set(note.get("parts", {})) != {"problem", "mitigation", "research_agenda"}:
        raise NoteValidationError("required content parts are missing")
    for key in (
        "title",
        "primary_control",
        "topics",
        "recommended_citation",
        "organizational_disclosure",
        "evidence_boundary",
    ):
        _require_nonempty(note.get(key), key)

    reference_items = note.get("references", [])
    if len(reference_items) < 2:
        raise NoteValidationError("at least two references are required")
    references: dict[str, dict[str, Any]] = {}
    for item in reference_items:
        reference_id = item.get("id")
        if not re.fullmatch(r"R\d+", str(reference_id or "")):
            raise NoteValidationError("invalid reference identifier")
        if reference_id in references:
            raise NoteValidationError(f"duplicate reference identifier: {reference_id}")
        if not str(item.get("url", "")).startswith("https://"):
            raise NoteValidationError(f"{reference_id} must use an https URL")
        for key in ("title", "source_type", "publication_status"):
            _require_nonempty(item.get(key), f"{reference_id} {key}")
        references[reference_id] = item
    if not any(
        item["source_type"] in PRIMARY_SOURCE_TYPES
        for item in references.values()
    ):
        raise NoteValidationError("an original paper or authoritative standard is required")

    serialized = json.dumps(note, ensure_ascii=False).lower()
    if any(token in serialized for token in PROHIBITED_TOKENS):
        raise NoteValidationError("prohibited publication text")

    problem = note["parts"]["problem"]
    for source in problem.get("sources", []):
        if source.get("kind") not in SOURCE_KINDS:
            raise NoteValidationError("invalid finding source kind")
        _validate_claim(source, references)
        if source["kind"] != "ACE Observation" and not source["reference_ids"]:
            raise NoteValidationError("external finding source requires a reference")
    for claim in problem.get("body", []):
        _validate_claim(claim, references)
    _require_nonempty(problem.get("impact"), "impact")

    mitigation = note["parts"]["mitigation"]
    for layer in mitigation.get("layers", []):
        evidence = layer.get("evidence")
        if evidence not in EVIDENCE_LABELS:
            raise NoteValidationError("invalid mitigation evidence label")
        _validate_claim(layer, references)
        if evidence == "not-applicable":
            if layer["text"] != "Not applicable" or layer["reference_ids"]:
                raise NoteValidationError("not-applicable mitigation must be explicit")
        elif evidence in {"evaluated", "research-proposed"} and not layer["reference_ids"]:
            raise NoteValidationError("mitigation claim requires a reference")

    for direction in mitigation.get("direction", []):
        if direction.get("evidence") not in EVIDENCE_LABELS:
            raise NoteValidationError("invalid mitigation evidence label")
        _validate_claim(direction, references)
        if (
            direction["evidence"] in {"evaluated", "research-proposed"}
            and not direction["reference_ids"]
        ):
            raise NoteValidationError("mitigation claim requires a reference")

    for direction in mitigation.get("logionos_direction", []):
        if direction.get("evidence") != "implementation-hypothesis":
            raise NoteValidationError(
                "LogionOS direction must remain implementation-hypothesis"
            )
        _validate_claim(direction, references)

    acceptance = mitigation.get("acceptance_test", {})
    for key in ("objective", "setup", "procedure", "pass_criteria"):
        _require_nonempty(acceptance.get(key), f"acceptance test {key}")
    _require_nonempty(mitigation.get("required_evidence"), "required evidence")

    agenda = note["parts"]["research_agenda"]
    for key in ("consequences", "second_order_effects", "limitations", "questions"):
        _require_nonempty(agenda.get(key), key)

    if note["status"] == "published":
        word_count = visible_word_count(note)
        if not 800 <= word_count <= 1500:
            raise NoteValidationError(
                f"published note must contain 800 to 1500 visible words; got {word_count}"
            )
