from pathlib import Path

from tools.research_notes import preview


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "research-note-sample.json"


def test_preview_copies_assets_and_builds_html_and_pdf(tmp_path, monkeypatch):
    def fake_pdf(html_path, pdf_path):
        assert html_path.is_file()
        pdf_path.write_bytes(b"%PDF-1.7\npreview")
        return pdf_path

    monkeypatch.setattr(preview, "build_pdf", fake_pdf)
    html_path, pdf_path = preview.build_preview(FIXTURE, tmp_path)

    assert html_path == tmp_path / "authority-must-shrink-not-grow.html"
    assert pdf_path == tmp_path / "ACE-RN-2026-001.pdf"
    assert '<link rel="stylesheet" href="style.css">' in html_path.read_text("utf-8")
    for asset in ("style.css", "research-note.js", "ace-nav.js", "logo.svg", "favicon.svg"):
        assert (tmp_path / asset).is_file()
