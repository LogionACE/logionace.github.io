import json
from pathlib import Path

from tools.frontier_research.html import render_report_html
from tools.frontier_research.model import load_report
from tools.frontier_research.preview import build_preview


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontier-research" / "source" / "afr-2026-001.json"
LEDGER = ROOT / "frontier-research" / "ledger.json"


def report_and_ledger():
    return load_report(SOURCE), json.loads(LEDGER.read_text("utf-8"))


def test_html_is_full_length_noindex_frontier_research_article():
    report, ledger = report_and_ledger()
    page = render_report_html(
        report,
        ledger,
        preview=True,
        asset_prefix="",
    )

    assert '<meta name="robots" content="noindex, nofollow">' in page
    assert page.count("<h1>") == 1
    assert "ACE Frontier Research · AFR-2026-001" in page
    assert "The Emerging Authority Layer for Autonomous AI Systems" in page
    assert "Evidence cutoff" in page
    assert "Moderate-High" in page
    assert "Observed Evidence" in page
    assert "ACE Hypothesis" in page
    assert "Open Questions" in page
    assert 'href="frontier-research.css?v=1.0"' in page
    assert page.count('class="afr-section"') == 11
    assert 'href="#section-research-boundary"' in page
    assert (
        'href="#section-research-boundary">'
        "1. Research Boundary: A Synthesis, Not a Claim of Invention</a>"
    ) in page
    assert 'src="frontier-research/assets/authority-layer.svg"' in page
    assert 'src="frontier-research/assets/authority-attenuation.svg"' in page
    assert 'href="#ref-R1"' in page
    assert 'id="prediction-AFR-2026-001-P01"' in page
    assert "Draft for review — not published" in page


def test_print_cover_and_references_preserve_evidence_status():
    report, ledger = report_and_ledger()
    page = render_report_html(
        report,
        ledger,
        preview=True,
        asset_prefix="",
    )

    assert 'class="afr-print-cover"' in page
    assert "ACE Frontier Research" in page
    assert "Evidence cutoff 19 August 2026" in page
    assert "Expired individual Internet-Draft" in page
    assert "work in progress" in page
    assert "preprint with bounded proof-of-concept" in page
    assert "This report presents a research hypothesis" in page


def test_preview_builder_copies_assets_and_uses_injected_pdf_builder(tmp_path):
    calls = []

    def fake_pdf_builder(html_path: Path, pdf_path: Path) -> Path:
        calls.append((html_path, pdf_path))
        pdf_path.write_bytes(b"%PDF-1.7\npreview")
        return pdf_path

    html_path, pdf_path = build_preview(
        SOURCE,
        tmp_path,
        pdf_builder=fake_pdf_builder,
    )

    assert html_path.name == "afr-2026-001.html"
    assert pdf_path.name == "AFR-2026-001.pdf"
    assert calls == [(html_path, pdf_path)]
    assert (tmp_path / "style.css").is_file()
    assert (tmp_path / "frontier-research.css").is_file()
    assert (tmp_path / "logo.svg").is_file()
    assert (
        tmp_path / "frontier-research" / "assets" / "authority-layer.svg"
    ).is_file()
    assert (
        tmp_path
        / "frontier-research"
        / "assets"
        / "authority-attenuation.svg"
    ).is_file()
    assert "noindex, nofollow" in html_path.read_text("utf-8")


def test_authority_diagrams_are_accessible_and_use_approved_language():
    for name in ("authority-layer.svg", "authority-attenuation.svg"):
        source = (
            ROOT / "frontier-research" / "assets" / name
        ).read_text("utf-8")
        assert "<title>" in source
        assert "<desc>" in source
        assert "role=\"img\"" in source
        assert "control plane" not in source.lower()
        assert "Trust Layer" in source or "Authority" in source

    authority_layer = (
        ROOT
        / "frontier-research"
        / "assets"
        / "authority-layer.svg"
    ).read_text("utf-8")
    assert "Effective Authority = f(Identity, Principal, Delegation" in authority_layer
    assert "NOT A MATHEMATICAL MODEL" in authority_layer


def test_references_expose_clickable_official_urls():
    report, ledger = report_and_ledger()
    page = render_report_html(
        report,
        ledger,
        preview=True,
        asset_prefix="",
    )
    assert page.count('class="afr-ref-url"') == len(report["references"])
    for reference in report["references"]:
        assert f'href="{reference["url"]}"' in page
        assert f'>{reference["url"]}</a>' in page


def test_frontier_styles_define_screen_mobile_and_print_contract():
    stylesheet = (ROOT / "frontier-research.css").read_text("utf-8")
    assert "/* === ACE FRONTIER RESEARCH === */" in stylesheet
    assert ".frontier-research-page{" not in stylesheet
    assert ".afr-layout" in stylesheet
    assert "@media(max-width:980px)" in stylesheet
    assert "@media(max-width:640px)" in stylesheet
    assert "@media print" in stylesheet
    assert "@page:first" in stylesheet
    assert ".afr-print-cover" in stylesheet
