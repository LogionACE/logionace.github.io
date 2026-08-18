"""Generate a local-only ACE Research Note webpage and PDF preview."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from tools.research_notes.html import ROOT, render_note_html
from tools.research_notes.model import load_note, note_slug
from tools.research_notes.pdf import build_pdf


ASSETS = (
    "style.css",
    "research-note.js",
    "ace-nav.js",
    "logo.svg",
    "favicon.svg",
)


def build_preview(source: Path, output_dir: Path) -> tuple[Path, Path]:
    note = load_note(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    for asset in ASSETS:
        shutil.copy2(ROOT / asset, output_dir / asset)

    html_path = output_dir / f"{note_slug(note)}.html"
    html_path.write_text(
        render_note_html(note, preview=True, asset_prefix=""),
        "utf-8",
    )
    pdf_path = output_dir / f"{note['id']}.pdf"
    build_pdf(html_path, pdf_path)
    return html_path, pdf_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a local HTML and PDF ACE Research Note preview."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    html_path, pdf_path = build_preview(args.source, args.output)
    print(f"wrote {html_path}")
    print(f"wrote {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
