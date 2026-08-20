"""Build a local-only ACE Frontier Research HTML and PDF preview."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Callable, Optional, Tuple

from tools.frontier_research.html import render_report_html
from tools.frontier_research.model import load_report
from tools.research_notes.pdf import build_pdf


ROOT = Path(__file__).resolve().parents[2]
ASSETS = (
    "style.css",
    "frontier-research.css",
    "research-note.js",
    "ace-nav.js",
    "logo.svg",
    "favicon.svg",
)


def build_preview(
    source: Path,
    output_dir: Path,
    *,
    pdf_builder: Optional[Callable[[Path, Path], Path]] = None,
) -> Tuple[Path, Path]:
    report = load_report(source)
    ledger = json.loads(
        (ROOT / "frontier-research" / "ledger.json").read_text("utf-8")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    for asset in ASSETS:
        shutil.copy2(ROOT / asset, output_dir / asset)

    figure_output = output_dir / "frontier-research" / "assets"
    figure_output.mkdir(parents=True, exist_ok=True)
    for figure in report["figures"]:
        source_path = ROOT / "frontier-research" / "assets" / Path(
            figure["path"]
        ).name
        shutil.copy2(source_path, figure_output / source_path.name)

    html_path = output_dir / f"{report['id'].lower()}.html"
    html_path.write_text(
        render_report_html(
            report,
            ledger,
            preview=True,
            asset_prefix="",
        ),
        "utf-8",
    )
    pdf_path = output_dir / f"{report['id']}.pdf"
    builder = pdf_builder or build_pdf
    builder(html_path, pdf_path)
    return html_path, pdf_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a local HTML and PDF ACE Frontier Research preview."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/ace-afr-001-preview"),
    )
    args = parser.parse_args()
    html_path, pdf_path = build_preview(args.source, args.output)
    print(f"wrote {html_path}")
    print(f"wrote {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
