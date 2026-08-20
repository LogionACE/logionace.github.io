"""Validation model for ACE Frontier Research source documents."""

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set


class FrontierResearchValidationError(ValueError):
    """Raised when an AFR source document violates the publication contract."""


REPORT_ID_RE = re.compile(r"^AFR-[0-9]{4}-[0-9]{3}$")
PREDICTION_ID_RE = re.compile(r"^AFR-[0-9]{4}-[0-9]{3}-P[0-9]{2}$")
CITATION_RE = re.compile(r"\[(R[0-9]+)\]")
WORD_RE = re.compile(r"\b[\w][\w'’\-]*\b", re.UNICODE)
REQUIRED_REPORT_FIELDS = {
    "schema_version",
    "id",
    "slug",
    "series",
    "title",
    "subtitle",
    "status",
    "publication_date",
    "evidence_cutoff",
    "research_status",
    "confidence",
    "authors",
    "version",
    "abstract",
    "sections",
    "figures",
    "prediction_ids",
    "references",
    "recommended_citation",
    "organizational_disclosure",
    "evidence_boundary",
    "corrections",
}
SECTION_CLASSIFICATIONS = {
    "observed-evidence",
    "emerging-problem",
    "ace-hypothesis",
    "open-questions",
    "analysis",
}
ALLOWED_STATUSES = {"draft", "review", "published", "archived"}
ALLOWED_RESEARCH_STATUSES = {"Emerging", "Developing", "Established", "Falsified"}
ALLOWED_CONFIDENCE = {"Low", "Moderate", "Moderate-High", "High"}
PROHIBITED_PATTERNS = (
    re.compile(r"\bcontrol plane\b", re.IGNORECASE),
    re.compile(r"\bACE invented\b", re.IGNORECASE),
    re.compile(r"\bACE discovered (?:AI |agent )?authori[sz]ation\b", re.IGNORECASE),
)


def _fail(message: str) -> None:
    raise FrontierResearchValidationError(message)


def _valid_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _reader_texts(report: Dict[str, Any]) -> Iterable[str]:
    for key in (
        "title",
        "subtitle",
        "recommended_citation",
        "organizational_disclosure",
        "evidence_boundary",
    ):
        value = report.get(key)
        if isinstance(value, str):
            yield value
    abstract = report.get("abstract", {})
    if isinstance(abstract, dict) and isinstance(abstract.get("text"), str):
        yield abstract["text"]
    for section in report.get("sections", []):
        if not isinstance(section, dict):
            continue
        if isinstance(section.get("title"), str):
            yield section["title"]
        for block in section.get("blocks", []):
            if isinstance(block, dict):
                for key in ("heading", "text", "caption"):
                    if isinstance(block.get(key), str):
                        yield block[key]
                for item in block.get("items", []):
                    if isinstance(item, str):
                        yield item
    for figure in report.get("figures", []):
        if isinstance(figure, dict):
            for key in ("title", "caption"):
                if isinstance(figure.get(key), str):
                    yield figure[key]


def _claim_blocks(report: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    abstract = report.get("abstract")
    if isinstance(abstract, dict):
        yield abstract
    for section in report.get("sections", []):
        if not isinstance(section, dict):
            continue
        for block in section.get("blocks", []):
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                yield block


def _validate_claim_citations(
    report: Dict[str, Any], reference_ids: Set[str]
) -> None:
    for block in _claim_blocks(report):
        text = block.get("text", "")
        declared = block.get("reference_ids", [])
        if not isinstance(declared, list) or not all(
            isinstance(item, str) for item in declared
        ):
            _fail("reference_ids must be a list of strings")
        markers = set(CITATION_RE.findall(text))
        declared_set = set(declared)
        if markers != declared_set:
            _fail("inline citations and reference_ids differ")
        unknown = declared_set - reference_ids
        if unknown:
            _fail(f"unknown reference ids: {', '.join(sorted(unknown))}")


def validate_report(report: Dict[str, Any]) -> None:
    if not isinstance(report, dict):
        _fail("report must be an object")
    missing = REQUIRED_REPORT_FIELDS - set(report)
    if missing:
        _fail(f"missing required fields: {', '.join(sorted(missing))}")
    if report.get("schema_version") != 1:
        _fail("unsupported schema version")
    if not REPORT_ID_RE.fullmatch(str(report.get("id", ""))):
        _fail("invalid canonical AFR identifier")
    if not _valid_iso_date(report.get("evidence_cutoff")):
        _fail("invalid evidence cutoff; expected YYYY-MM-DD")

    status = report.get("status")
    publication_date = report.get("publication_date")
    if status not in ALLOWED_STATUSES:
        _fail("invalid publication status")
    if status in {"draft", "review"} and publication_date is not None:
        _fail("draft publication date must be null")
    if status in {"published", "archived"} and not _valid_iso_date(
        publication_date
    ):
        _fail("published report requires a valid publication date")

    if report.get("research_status") not in ALLOWED_RESEARCH_STATUSES:
        _fail("invalid research status")
    if report.get("confidence") not in ALLOWED_CONFIDENCE:
        _fail("invalid confidence")
    authors = report.get("authors")
    if not isinstance(authors, list) or not authors or not all(
        isinstance(author, str) and author.strip() for author in authors
    ):
        _fail("at least one author is required")

    sections = report.get("sections")
    if not isinstance(sections, list) or not sections:
        _fail("at least one section is required")
    section_ids: Set[str] = set()
    for section in sections:
        if not isinstance(section, dict):
            _fail("section must be an object")
        section_id = section.get("id")
        if not isinstance(section_id, str) or not section_id:
            _fail("section id is required")
        if section_id in section_ids:
            _fail(f"duplicate section id: {section_id}")
        section_ids.add(section_id)
        if section.get("classification") not in SECTION_CLASSIFICATIONS:
            _fail(f"invalid classification for section {section_id}")
        if not isinstance(section.get("blocks"), list) or not section["blocks"]:
            _fail(f"section {section_id} requires content blocks")

    references = report.get("references")
    if not isinstance(references, list) or not 20 <= len(references) <= 30:
        _fail("AFR report must contain 20 to 30 references")
    reference_ids: List[str] = []
    for reference in references:
        if not isinstance(reference, dict):
            _fail("reference must be an object")
        reference_id = reference.get("id")
        if not isinstance(reference_id, str) or not re.fullmatch(
            r"R[0-9]+", reference_id
        ):
            _fail("invalid reference identifier")
        if not all(
            isinstance(reference.get(key), str) and reference[key].strip()
            for key in (
                "title",
                "url",
                "source_type",
                "publication_status",
                "checked_at",
            )
        ):
            _fail(f"incomplete reference {reference_id}")
        if not _valid_iso_date(reference["checked_at"]):
            _fail(f"invalid checked_at date for {reference_id}")
        reference_ids.append(reference_id)
    if len(reference_ids) != len(set(reference_ids)):
        _fail("duplicate reference identifier")
    _validate_claim_citations(report, set(reference_ids))

    prediction_ids = report.get("prediction_ids")
    if not isinstance(prediction_ids, list) or not prediction_ids:
        _fail("at least one prediction id is required")
    if len(prediction_ids) != len(set(prediction_ids)) or not all(
        isinstance(item, str) and PREDICTION_ID_RE.fullmatch(item)
        for item in prediction_ids
    ):
        _fail("invalid or duplicate prediction identifiers")
    report_prefix = f"{report['id']}-P"
    if not all(item.startswith(report_prefix) for item in prediction_ids):
        _fail("prediction ids must belong to the report")

    word_count = visible_word_count(report)
    if not 4000 <= word_count <= 6000:
        _fail(
            f"AFR report must contain 4,000 to 6,000 visible words; found {word_count}"
        )

    all_text = "\n".join(_reader_texts(report))
    for pattern in PROHIBITED_PATTERNS:
        if pattern.search(all_text):
            _fail(f"prohibited positioning: {pattern.pattern}")


def validate_ledger(report: Dict[str, Any], ledger: Dict[str, Any]) -> None:
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1:
        _fail("invalid prediction ledger")
    predictions = ledger.get("predictions")
    if not isinstance(predictions, list):
        _fail("prediction ledger requires predictions")
    ledger_ids: Set[str] = set()
    for prediction in predictions:
        if not isinstance(prediction, dict):
            _fail("prediction must be an object")
        prediction_id = prediction.get("id")
        if not isinstance(prediction_id, str) or not PREDICTION_ID_RE.fullmatch(
            prediction_id
        ):
            _fail("invalid prediction identifier")
        if prediction.get("report_id") != report.get("id"):
            continue
        ledger_ids.add(prediction_id)
        if prediction.get("confidence") not in ALLOWED_CONFIDENCE:
            _fail(f"invalid confidence for {prediction_id}")
        if prediction.get("review_horizons_months") != [6, 12, 24]:
            _fail(f"{prediction_id} must define 6, 12, and 24 month reviews")
        for key in ("statement",):
            if not isinstance(prediction.get(key), str) or not prediction[
                key
            ].strip():
                _fail(f"{prediction_id} requires a falsifiable statement")
        for key in ("supporting_signals", "falsification_signals", "reviews"):
            if not isinstance(prediction.get(key), list):
                _fail(f"{prediction_id} requires {key}")
        if not prediction["falsification_signals"]:
            _fail(f"{prediction_id} requires falsification signals")
        if report.get("status") in {"draft", "review"}:
            if prediction.get("publication_date") is not None:
                _fail("draft prediction publication date must be null")
        elif prediction.get("publication_date") != report.get(
            "publication_date"
        ):
            _fail("prediction publication date must match report")
    if ledger_ids != set(report.get("prediction_ids", [])):
        _fail("prediction ids in ledger do not match the report")


def visible_word_count(report: Dict[str, Any]) -> int:
    return sum(len(WORD_RE.findall(text)) for text in _reader_texts(report))


def load_report(path: Path) -> Dict[str, Any]:
    try:
        report = json.loads(Path(path).read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FrontierResearchValidationError(
            f"unable to load AFR source: {exc}"
        ) from exc
    validate_report(report)
    return report
