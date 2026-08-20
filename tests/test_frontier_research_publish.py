import copy
import json
from pathlib import Path

from tools.frontier_research import publish


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontier-research" / "source" / "afr-2026-001.json"


def published_report():
    report = json.loads(SOURCE.read_text("utf-8"))
    report["status"] = "published"
    report["publication_date"] = "2026-08-20"
    report["version"] = "1.0"
    return report


def test_catalog_entry_preserves_frontier_research_identity_and_links():
    entry = publish.catalog_entry(published_report(), b"afr-source")
    assert entry["id"] == "AFR-2026-001"
    assert entry["type"] == "frontier-research"
    assert entry["date"] == "2026-08-20"
    assert entry["status"] == "published"
    assert entry["links"]["page"] == (
        "frontier-research/beyond-identity-emerging-authority-layer.html"
    )
    assert entry["links"]["pdf"] == "frontier-research/AFR-2026-001.pdf"
    assert len(entry["source_sha256"]) == 64


def test_frontier_index_excludes_drafts_and_limits_latest_three_reports():
    reports = []
    for number in range(1, 6):
        report = copy.deepcopy(published_report())
        report["id"] = f"AFR-2026-{number:03d}"
        report["slug"] = f"report-{number:03d}"
        report["title"] = f"Frontier Report {number:03d}"
        report["publication_date"] = f"2026-08-{number + 10:02d}"
        reports.append(report)
    draft = copy.deepcopy(reports[-1])
    draft["id"] = "AFR-2026-999"
    draft["status"] = "draft"
    draft["publication_date"] = None

    block = publish.render_hub_entries(reports + [draft], limit=3)

    assert "AFR-2026-005" in block
    assert "AFR-2026-003" in block
    assert "AFR-2026-002" not in block
    assert "AFR-2026-999" not in block
    assert block.count('class="research-frontier-card research-publication"') == 3


def test_frontier_sitemap_entry_uses_public_slug_and_publication_date():
    sitemap = publish.render_sitemap_entries([published_report()])
    assert (
        "https://logionace.com/frontier-research/"
        "beyond-identity-emerging-authority-layer.html"
    ) in sitemap
    assert "<lastmod>2026-08-20</lastmod>" in sitemap


def test_public_index_files_have_independent_frontier_markers():
    research = (ROOT / "research.html").read_text("utf-8")
    library = (ROOT / "research-library.html").read_text("utf-8")
    sitemap = (ROOT / "sitemap.xml").read_text("utf-8")
    assert "ACE_FRONTIER_RESEARCH_START" in research
    assert "ACE_FRONTIER_RESEARCH_LIBRARY_START" in library
    assert "ACE_FRONTIER_RESEARCH_START" in sitemap
