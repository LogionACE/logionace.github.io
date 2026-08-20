import json
from copy import deepcopy
from pathlib import Path

import pytest

from tools.frontier_research.model import (
    FrontierResearchValidationError,
    load_report,
    validate_ledger,
    validate_report,
    visible_word_count,
)


ROOT = Path(__file__).resolve().parents[1]


def valid_report() -> dict:
    references = [
        {
            "id": f"R{index}",
            "title": f"Primary source {index}",
            "url": f"https://example.com/source-{index}",
            "source_type": (
                "official-initiative" if index == 1 else "original-paper"
            ),
            "publication_status": "published",
            "checked_at": "2026-08-19",
        }
        for index in range(1, 21)
    ]
    paragraph = " ".join(["authority"] * 420)
    return {
        "schema_version": 1,
        "id": "AFR-2026-001",
        "slug": "beyond-identity-emerging-authority-layer",
        "series": "Autonomous Trust Systems",
        "title": "Beyond Identity",
        "subtitle": "The Emerging Authority Layer for Autonomous AI Systems",
        "status": "draft",
        "publication_date": None,
        "evidence_cutoff": "2026-08-19",
        "research_status": "Emerging",
        "confidence": "Moderate-High",
        "authors": ["Chris Ma"],
        "version": "0.9",
        "abstract": {
            "text": "Agent identity is becoming infrastructure, but authority remains unresolved [R1].",
            "reference_ids": ["R1"],
        },
        "sections": [
            {
                "id": f"section-{index}",
                "title": f"Section {index}",
                "classification": (
                    "observed-evidence" if index < 3 else "ace-hypothesis"
                ),
                "blocks": [
                    {
                        "type": "paragraph",
                        "text": (
                            f"{paragraph} [R{index}]"
                            if index <= 11
                            else paragraph
                        ),
                        "reference_ids": [f"R{index}"] if index <= 11 else [],
                    }
                ],
            }
            for index in range(1, 12)
        ],
        "figures": [
            {
                "id": "authority-layer",
                "title": "The proposed AI Authority Layer",
                "path": "assets/authority-layer.svg",
                "alt": "Authority flows from a principal through an agent identity and a proposed authority layer to an action and evidence.",
            },
            {
                "id": "authority-attenuation",
                "title": "Authority attenuation across delegation",
                "path": "assets/authority-attenuation.svg",
                "alt": "A human delegates to Agent A, which delegates narrower authority to Agent B and Agent C.",
            },
        ],
        "prediction_ids": [
            "AFR-2026-001-P01",
            "AFR-2026-001-P02",
        ],
        "references": references,
        "recommended_citation": "Ma, Chris. Beyond Identity. AFR-2026-001, draft.",
        "organizational_disclosure": "ACE and LogionOS share organizational affiliation.",
        "evidence_boundary": "This draft synthesizes public evidence and states a falsifiable hypothesis.",
        "corrections": [],
    }


def valid_ledger() -> dict:
    return {
        "schema_version": 1,
        "series": "ACE Frontier Research Prediction Ledger",
        "predictions": [
            {
                "id": prediction_id,
                "report_id": "AFR-2026-001",
                "statement": "Enterprise authorization systems will add task-bound agent authority evidence.",
                "confidence": "Moderate-High",
                "review_horizons_months": [6, 12, 24],
                "supporting_signals": ["NIST agenda", "OAuth Internet-Drafts"],
                "falsification_signals": [
                    "Enterprise deployments converge on static identity and scope without task-bound authority."
                ],
                "publication_date": None,
                "reviews": [],
            }
            for prediction_id in (
                "AFR-2026-001-P01",
                "AFR-2026-001-P02",
            )
        ],
    }


def test_valid_draft_report_and_ledger_are_accepted():
    report = valid_report()
    validate_report(report)
    validate_ledger(report, valid_ledger())
    assert 4000 <= visible_word_count(report) <= 6000


def test_report_requires_permanent_id_and_exact_evidence_cutoff():
    report = valid_report()
    report["id"] = "AFR-001"
    with pytest.raises(FrontierResearchValidationError, match="identifier"):
        validate_report(report)

    report = valid_report()
    report["evidence_cutoff"] = "August 19, 2026"
    with pytest.raises(FrontierResearchValidationError, match="evidence cutoff"):
        validate_report(report)


def test_draft_has_no_publication_date_but_published_report_requires_one():
    report = valid_report()
    report["publication_date"] = "2026-08-20"
    with pytest.raises(FrontierResearchValidationError, match="draft publication"):
        validate_report(report)

    report = valid_report()
    report["status"] = "published"
    with pytest.raises(FrontierResearchValidationError, match="publication date"):
        validate_report(report)


def test_report_enforces_word_and_reference_bounds():
    report = valid_report()
    report["sections"] = report["sections"][:2]
    with pytest.raises(FrontierResearchValidationError, match="4,000 to 6,000"):
        validate_report(report)

    report = valid_report()
    report["references"] = report["references"][:19]
    with pytest.raises(FrontierResearchValidationError, match="20 to 30"):
        validate_report(report)


def test_external_claims_require_matching_inline_citations():
    report = valid_report()
    report["sections"][0]["blocks"][0]["reference_ids"] = []
    with pytest.raises(FrontierResearchValidationError, match="inline citations"):
        validate_report(report)

    report = valid_report()
    report["sections"][0]["blocks"][0]["text"] += " [R30]"
    report["sections"][0]["blocks"][0]["reference_ids"].append("R30")
    with pytest.raises(FrontierResearchValidationError, match="unknown reference"):
        validate_report(report)


@pytest.mark.parametrize(
    "phrase",
    [
        "AI Authority control plane",
        "ACE invented AI Authority",
        "ACE discovered agent authorization",
    ],
)
def test_report_rejects_prohibited_positioning(phrase):
    report = valid_report()
    report["sections"][0]["blocks"][0]["text"] = phrase
    report["sections"][0]["blocks"][0]["reference_ids"] = []
    with pytest.raises(FrontierResearchValidationError, match="prohibited"):
        validate_report(report)


def test_ledger_covers_report_predictions_and_review_horizons():
    report = valid_report()
    ledger = valid_ledger()
    ledger["predictions"].pop()
    with pytest.raises(FrontierResearchValidationError, match="prediction ids"):
        validate_ledger(report, ledger)

    ledger = valid_ledger()
    ledger["predictions"][0]["review_horizons_months"] = [12, 24]
    with pytest.raises(FrontierResearchValidationError, match="6, 12, and 24"):
        validate_ledger(report, ledger)


def test_repository_schema_declares_frontier_metadata_contract():
    schema = json.loads(
        (
            ROOT
            / "frontier-research"
            / "schema"
            / "frontier-research.schema.json"
        ).read_text("utf-8")
    )
    required = set(schema["required"])
    assert {
        "id",
        "evidence_cutoff",
        "research_status",
        "confidence",
        "prediction_ids",
        "references",
    } <= required
    assert schema["properties"]["id"]["pattern"] == (
        "^AFR-[0-9]{4}-[0-9]{3}$"
    )


def test_load_report_validates_source_file(tmp_path):
    source = tmp_path / "afr.json"
    source.write_text(json.dumps(valid_report()), "utf-8")
    assert load_report(source)["id"] == "AFR-2026-001"

    invalid = deepcopy(valid_report())
    invalid["authors"] = []
    source.write_text(json.dumps(invalid), "utf-8")
    with pytest.raises(FrontierResearchValidationError):
        load_report(source)
