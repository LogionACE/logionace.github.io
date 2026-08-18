"""Print an ACE Research Note HTML page to PDF with local Chrome."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


CHROME_CANDIDATES = (
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
)


class PdfBuildError(RuntimeError):
    """Raised when Chrome cannot create a Research Note PDF."""


def find_chrome(explicit: str | None = None) -> Path:
    requested = explicit or os.environ.get("CHROME_BIN")
    candidates = (Path(requested),) if requested else CHROME_CANDIDATES
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise PdfBuildError("Chrome is required; set CHROME_BIN to its executable")


def build_pdf(
    html_path: Path,
    pdf_path: Path,
    *,
    chrome_bin: str | None = None,
) -> Path:
    chrome = find_chrome(chrome_bin)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path.resolve()}",
        html_path.resolve().as_uri(),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise PdfBuildError(completed.stderr.strip() or "Chrome failed to print PDF")
    if not pdf_path.is_file():
        raise PdfBuildError("Chrome did not produce a PDF")
    if not pdf_path.read_bytes().startswith(b"%PDF-"):
        raise PdfBuildError("generated file is not a PDF")
    return pdf_path
