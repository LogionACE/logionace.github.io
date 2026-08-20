"""Build and verify public ACE Frontier Research static artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from html import escape
from pathlib import Path
from typing import Any, Optional

from tools.frontier_research.html import render_report_html
from tools.frontier_research.model import load_report, validate_ledger
from tools.research_notes.pdf import build_pdf


ROOT = Path(__file__).resolve().parents[2]
HUB_START = "<!-- ACE_FRONTIER_RESEARCH_START -->"
HUB_END = "<!-- ACE_FRONTIER_RESEARCH_END -->"
LIBRARY_START = "<!-- ACE_FRONTIER_RESEARCH_LIBRARY_START -->"
LIBRARY_END = "<!-- ACE_FRONTIER_RESEARCH_LIBRARY_END -->"


class FrontierPublicationBuildError(RuntimeError):
    """Raised when generated Frontier Research artifacts are missing or stale."""


def catalog_entry(report: dict[str, Any], source_bytes: bytes) -> dict[str, Any]:
    return {
        "id": report["id"],
        "title": f"{report['title']}: {report['subtitle']}",
        "type": "frontier-research",
        "date": report["publication_date"],
        "abstract": report["abstract"]["text"],
        "authors": report["authors"],
        "topics": [
            "AI authority",
            "agent identity",
            "delegated authorization",
            "evidence",
        ],
        "series": report["series"],
        "version": report["version"],
        "status": "published",
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "links": {
            "page": f"frontier-research/{report['slug']}.html",
            "pdf": f"frontier-research/{report['id']}.pdf",
        },
    }


def _published(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (report for report in reports if report.get("status") == "published"),
        key=lambda report: (report["publication_date"], report["id"]),
        reverse=True,
    )


def render_hub_entries(
    reports: list[dict[str, Any]],
    limit: Optional[int] = None,
) -> str:
    published = _published(reports)
    if limit is not None:
        published = published[:limit]
    return "\n".join(
        f"""    <article class="research-frontier-card research-publication">
      <div class="research-frontier-meta">
        <span class="research-status">Published · {escape(report["publication_date"])}</span>
        <span>{escape(report["id"])} · {escape(report["research_status"])} · {escape(report["confidence"])}</span>
      </div>
      <p class="eyebrow">ACE Frontier Research</p>
      <h3><a href="frontier-research/{escape(report["slug"])}.html">{escape(report["title"])}</a></h3>
      <p class="research-frontier-subtitle">{escape(report["subtitle"])}</p>
      <div class="research-actions">
        <a class="btn primary" href="frontier-research/{escape(report["slug"])}.html">Read report</a>
        <a class="btn outline" href="frontier-research/{escape(report["id"])}.pdf">Download PDF</a>
      </div>
    </article>"""
        for report in published
    )


def render_sitemap_entries(reports: list[dict[str, Any]]) -> str:
    return "\n".join(
        "  <url>"
        f"<loc>https://logionace.com/frontier-research/{escape(report['slug'])}.html</loc>"
        f"<lastmod>{escape(report['publication_date'])}</lastmod>"
        "<priority>0.8</priority>"
        "</url>"
        for report in _published(reports)
    )


def replace_generated_block(
    text: str,
    body: str,
    start: str = HUB_START,
    end: str = HUB_END,
) -> str:
    pattern = re.compile(rf"{re.escape(start)}.*?{re.escape(end)}", re.S)
    replacement = f"{start}\n{body.rstrip()}\n{end}"
    updated, count = pattern.subn(replacement, text)
    if count != 1:
        raise FrontierPublicationBuildError(
            f"expected one generated block between {start} and {end}"
        )
    return updated


def _load_sources(
    root: Path,
) -> tuple[list[tuple[Path, dict[str, Any]]], dict[str, Any]]:
    ledger = json.loads(
        (root / "frontier-research" / "ledger.json").read_text("utf-8")
    )
    loaded = []
    for path in sorted(
        (root / "frontier-research" / "source").glob("afr-*.json")
    ):
        report = load_report(path)
        validate_ledger(report, ledger)
        if report["status"] == "published":
            loaded.append((path, report))
    ids = [report["id"] for _, report in loaded]
    slugs = [report["slug"] for _, report in loaded]
    if len(ids) != len(set(ids)) or len(slugs) != len(set(slugs)):
        raise FrontierPublicationBuildError(
            "Frontier Research ids and slugs must be unique"
        )
    return loaded, ledger


def _catalog_with_reports(
    catalog: dict[str, Any],
    loaded: list[tuple[Path, dict[str, Any]]],
) -> dict[str, Any]:
    retained = [
        item
        for item in catalog["publications"]
        if item.get("type") != "frontier-research"
    ]
    entries = [
        catalog_entry(report, path.read_bytes()) for path, report in loaded
    ]
    publications = sorted(
        retained + entries,
        key=lambda item: (item["date"], item["id"]),
        reverse=True,
    )
    updated = dict(catalog)
    updated["publications"] = publications
    if publications:
        updated["updated_at"] = max(
            item["date"] for item in publications if item.get("date")
        )
    return updated


def build(root: Path = ROOT) -> list[Path]:
    loaded, ledger = _load_sources(root)
    reports = [report for _, report in loaded]
    output_dir = root / "frontier-research"
    written: list[Path] = []

    for _, report in loaded:
        html_path = output_dir / f"{report['slug']}.html"
        html_path.write_text(
            render_report_html(
                report,
                ledger,
                preview=False,
                asset_prefix="../",
            ),
            "utf-8",
        )
        pdf_path = output_dir / f"{report['id']}.pdf"
        build_pdf(html_path, pdf_path)
        written.extend((html_path, pdf_path))

    catalog_path = root / "research-catalog.json"
    catalog = json.loads(catalog_path.read_text("utf-8"))
    catalog_path.write_text(
        json.dumps(
            _catalog_with_reports(catalog, loaded),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        "utf-8",
    )

    research_path = root / "research.html"
    research_path.write_text(
        replace_generated_block(
            research_path.read_text("utf-8"),
            render_hub_entries(reports, limit=3),
        ),
        "utf-8",
    )
    library_path = root / "research-library.html"
    library_path.write_text(
        replace_generated_block(
            library_path.read_text("utf-8"),
            render_hub_entries(reports),
            LIBRARY_START,
            LIBRARY_END,
        ),
        "utf-8",
    )
    sitemap_path = root / "sitemap.xml"
    sitemap_path.write_text(
        replace_generated_block(
            sitemap_path.read_text("utf-8"),
            render_sitemap_entries(reports),
        ),
        "utf-8",
    )
    written.extend((catalog_path, research_path, library_path, sitemap_path))
    return written


def check(root: Path = ROOT) -> None:
    loaded, ledger = _load_sources(root)
    reports = [report for _, report in loaded]
    for _, report in loaded:
        html_path = root / "frontier-research" / f"{report['slug']}.html"
        expected = render_report_html(
            report,
            ledger,
            preview=False,
            asset_prefix="../",
        )
        if not html_path.is_file() or html_path.read_text("utf-8") != expected:
            raise FrontierPublicationBuildError(
                f"stale generated page: {html_path.name}"
            )
        pdf_path = root / "frontier-research" / f"{report['id']}.pdf"
        if not pdf_path.is_file() or not pdf_path.read_bytes().startswith(b"%PDF-"):
            raise FrontierPublicationBuildError(
                f"missing generated PDF: {pdf_path.name}"
            )

    catalog_path = root / "research-catalog.json"
    actual_catalog = json.loads(catalog_path.read_text("utf-8"))
    if actual_catalog != _catalog_with_reports(actual_catalog, loaded):
        raise FrontierPublicationBuildError("research-catalog.json is stale")

    research = (root / "research.html").read_text("utf-8")
    if research != replace_generated_block(
        research,
        render_hub_entries(reports, limit=3),
    ):
        raise FrontierPublicationBuildError("research.html AFR entries are stale")
    library = (root / "research-library.html").read_text("utf-8")
    if library != replace_generated_block(
        library,
        render_hub_entries(reports),
        LIBRARY_START,
        LIBRARY_END,
    ):
        raise FrontierPublicationBuildError(
            "research-library.html AFR entries are stale"
        )
    sitemap = (root / "sitemap.xml").read_text("utf-8")
    if sitemap != replace_generated_block(
        sitemap,
        render_sitemap_entries(reports),
    ):
        raise FrontierPublicationBuildError("sitemap.xml AFR entries are stale")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build or verify ACE Frontier Research."
    )
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args()
    if args.command == "build":
        for path in build():
            print(f"wrote {path}")
    else:
        check()
        print("Frontier Research publications are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
