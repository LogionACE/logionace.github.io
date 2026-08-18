import subprocess
from pathlib import Path

from tools.research_notes.pdf import build_pdf


def test_pdf_builder_uses_local_file_and_disables_browser_headers(tmp_path, monkeypatch):
    html_path = tmp_path / "note.html"
    pdf_path = tmp_path / "note.pdf"
    chrome_path = tmp_path / "chrome"
    html_path.write_text("<html><body>note</body></html>", "utf-8")
    chrome_path.write_text("", "utf-8")
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        pdf_path.write_bytes(b"%PDF-1.7\npreview")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = build_pdf(html_path, pdf_path, chrome_bin=str(chrome_path))

    assert result == pdf_path
    command = calls[0][0]
    assert "--headless=new" in command
    assert "--no-pdf-header-footer" in command
    assert any(arg.startswith("--print-to-pdf=") for arg in command)
    assert command[-1] == html_path.resolve().as_uri()
