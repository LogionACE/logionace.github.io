import json
from pathlib import Path

from tools.research_notes.html import render_note_html
from tools.research_notes.model import load_note


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "research-note-sample.json"


def render_fixture() -> str:
    note = load_note(FIXTURE)
    return render_note_html(note, preview=True, asset_prefix="")


def test_article_contains_required_editorial_structure():
    page = render_fixture()
    assert page.count("<h1") == 1
    assert 'data-note-id="ACE-RN-2026-001"' in page
    assert 'id="problem-definition"' in page
    assert 'id="mitigation-direction"' in page
    assert 'id="research-agenda"' in page
    assert 'id="acceptance-test"' in page
    assert 'id="required-evidence"' in page
    assert 'id="references"' in page
    assert "Chris Ma" in page


def test_preview_is_noindex_and_exposes_scholarly_metadata():
    page = render_fixture()
    assert '<meta name="robots" content="noindex, nofollow">' in page
    assert '<meta property="og:type" content="article">' in page
    assert '<link rel="canonical" href="https://logionace.com/research-notes/authority-must-shrink-not-grow.html">' in page
    marker = '<script type="application/ld+json">'
    payload = page.split(marker, 1)[1].split("</script>", 1)[0]
    metadata = json.loads(payload)
    assert metadata["@type"] == "ScholarlyArticle"
    assert metadata["identifier"] == "ACE-RN-2026-001"
    assert metadata["author"]["name"] == "Chris Ma"


def test_pdf_cover_uses_the_evaluation_report_brand_structure():
    page = render_fixture()
    assert 'class="rn-print-arcs"' in page
    assert '<img src="logo.svg" alt="">' in page
    assert 'class="rn-print-brand-name">Logion<span>ACE</span>' in page
    assert 'class="rn-print-type">ACE Research Note</p>' in page
    assert 'class="rn-print-meta"' in page
    assert 'class="rn-print-footer"' in page


def test_full_article_and_citation_are_present_without_javascript():
    page = render_fixture()
    assert "A valid delegation chain should attenuate authority" in page
    assert '<a class="rn-cite" href="#ref-R1">[R1]</a>' in page
    assert '<button type="button" data-copy-citation' in page
    assert '<p class="rn-citation-text"' in page
    assert "fetch(" not in page


def test_mobile_action_panel_precedes_article_in_source_order():
    page = render_fixture()
    record = page.index('<aside class="rn-record"')
    article = page.index('<article class="rn-article"')
    assert record < article


def test_control_codes_are_explained_in_plain_language():
    page = render_fixture()
    assert "<dt>Research scope</dt>" in page
    assert "Delegated authority containment" in page
    assert "Tool &amp; data authorization" in page
    assert "Decision evidence completeness" in page
    assert '<span class="rn-control-id">DRAFT-DAC-01</span>' in page


def test_editorial_styles_cover_desktop_mobile_and_print():
    stylesheet = (ROOT / "style.css").read_text("utf-8")
    assert "/* === ACE RESEARCH NOTE === */" in stylesheet
    assert 'grid-template-areas:"toc article record"' in stylesheet
    assert 'grid-template-areas:"toc" "record" "article"' in stylesheet
    assert ".rn-metadata dd{" in stylesheet
    assert "font-size:15px" in stylesheet
    assert ".rn-actions .btn{" in stylesheet
    assert "padding:9px 15px" in stylesheet
    assert "@media print" in stylesheet
    assert "counter(page)" in stylesheet
    assert ".rn-print-cover" in stylesheet


def test_copy_citation_is_progressive_enhancement():
    script = (ROOT / "research-note.js").read_text("utf-8")
    assert "navigator.clipboard.writeText" in script
    assert "Citation copied" in script
    assert "Select citation below" in script


def test_research_pages_inherit_the_same_background_as_the_homepage():
    stylesheet = (ROOT / "style.css").read_text("utf-8")
    assert ".research-page{\n  background:" not in stylesheet
    assert ".research-note-page{\n  background:" not in stylesheet
