import json
import re
from pathlib import Path

from tools.frontier_research.html import render_report_html
from tools.frontier_research.model import (
    load_report,
    validate_ledger,
    visible_word_count,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontier-research" / "source" / "afr-2026-001.json"
LEDGER = ROOT / "frontier-research" / "ledger.json"


def load_source():
    report = load_report(SOURCE)
    ledger = json.loads(LEDGER.read_text("utf-8"))
    validate_ledger(report, ledger)
    return report, ledger


def test_afr_001_matches_locked_editorial_scope():
    report, ledger = load_source()
    assert report["id"] == "AFR-2026-001"
    assert report["authors"] == ["Chris Ma"]
    assert report["evidence_cutoff"] == "2026-08-19"
    assert report["status"] == "published"
    assert report["publication_date"] == "2026-08-20"
    assert report["version"] == "1.0"
    assert report["research_status"] == "Emerging"
    assert report["confidence"] == "Moderate-High"
    assert len(report["sections"]) == 11
    assert 4000 <= visible_word_count(report) <= 6000
    assert 20 <= len(report["references"]) <= 30
    assert len(ledger["predictions"]) == 4


def test_every_reference_is_used_and_every_inline_marker_resolves():
    report, _ = load_source()
    body = json.dumps(
        {
            "abstract": report["abstract"],
            "sections": report["sections"],
        }
    )
    used = set(re.findall(r"\[(R\d+)\]", body))
    declared = {reference["id"] for reference in report["references"]}
    assert used == declared


def test_source_distinguishes_drafts_preprints_and_product_documentation():
    report, _ = load_source()
    by_id = {reference["id"]: reference for reference in report["references"]}
    for reference_id in ("R9", "R11", "R12", "R13"):
        status = by_id[reference_id]["publication_status"].lower()
        assert "work in progress" in status
        assert "no formal ietf standing" in status
    assert "expired" in by_id["R10"]["publication_status"].lower()
    for reference_id in ("R22", "R23", "R24", "R25", "R26"):
        assert "preprint" in by_id[reference_id]["publication_status"].lower()
    for reference_id in ("R3", "R4", "R5", "R6", "R7"):
        assert by_id[reference_id]["source_type"] == "product-documentation"


def test_publication_avoids_prohibited_claims_and_exposes_metadata():
    report, ledger = load_source()
    source_text = SOURCE.read_text("utf-8").lower()
    assert "control plane" not in source_text
    assert "ace invented" not in source_text
    assert "ace discovered agent authorization" not in source_text

    page = render_report_html(report, ledger, preview=False, asset_prefix="")
    assert '"datePublished": "2026-08-20"' in page
    assert "Draft for review — not published" not in page
    assert all(
        prediction["publication_date"] == "2026-08-20"
        for prediction in ledger["predictions"]
    )


def test_conceptual_formula_is_explicitly_not_a_mathematical_model():
    report, _ = load_source()
    conceptual_section = next(
        section
        for section in report["sections"]
        if section["id"] == "conceptual-model"
    )
    text = " ".join(
        block.get("text", "") for block in conceptual_section["blocks"]
    )
    assert "not a mathematical model" in text.lower()
    assert (
        "Effective Authority = f(Identity, Principal, Delegation, Intent, "
        "Scope, Context, Time, Policy, Risk)"
    ) in text
