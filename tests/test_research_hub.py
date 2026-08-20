import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = sorted(ROOT.glob("*.html"))


class ResearchHubTests(unittest.TestCase):
    def test_current_research_is_visible_before_historical_papers(self):
        page = (ROOT / "research.html").read_text(encoding="utf-8")
        self.assertIn(
            '<h1 id="research-title">Defining what trustworthy AI must mean.</h1>',
            page,
        )
        for section_id in (
            "latest-update",
            "frontier-research",
            "evidence-notes",
            "papers-archive",
            "research-sponsorship",
        ):
            self.assertIn(f'id="{section_id}"', page)
        self.assertLess(
            page.index('id="latest-update"'),
            page.index('id="papers-archive"'),
        )
        self.assertLess(
            page.index('id="frontier-research"'),
            page.index('id="papers-archive"'),
        )
        self.assertIn("Evidence Notes", page)
        self.assertIn("And more", page)
        self.assertIn('href="research-library.html"', page)

    def test_landing_page_limits_frontier_research_and_evidence_notes(self):
        page = (ROOT / "research.html").read_text(encoding="utf-8")
        frontier = re.search(
            r"<!-- ACE_FRONTIER_RESEARCH_START -->(.*?)"
            r"<!-- ACE_FRONTIER_RESEARCH_END -->",
            page,
            re.S,
        )
        notes = re.search(
            r"<!-- ACE_RESEARCH_NOTES_START -->(.*?)"
            r"<!-- ACE_RESEARCH_NOTES_END -->",
            page,
            re.S,
        )
        self.assertIsNotNone(frontier)
        self.assertIsNotNone(notes)
        self.assertLessEqual(
            frontier.group(1).count('class="research-frontier-card'),
            3,
        )
        self.assertEqual(
            notes.group(1).count('class="research-note research-publication"'),
            10,
        )

    def test_institutional_sponsorship_preserves_research_independence(self):
        page = (ROOT / "research.html").read_text(encoding="utf-8")
        self.assertIn("Support ACE Research", page)
        self.assertIn("institutional research sponsorship", page)
        self.assertIn(
            "Sponsors do not control ACE methods, findings, ratings, or publication decisions.",
            page,
        )
        self.assertIn('href="evaluation.html#contact"', page)
        self.assertIn("Discuss research sponsorship", page)
        self.assertNotIn("sponsorship pricing", page.lower())

    def test_research_hub_keeps_papers_and_archived_whitepaper_accessible(self):
        page = (ROOT / "research.html").read_text(encoding="utf-8")
        page_lower = page.lower()
        self.assertIn("<title>ACE Research - LogionACE</title>", page)
        self.assertEqual(page.count("<h1"), 1)
        for section_id in (
            "latest-update",
            "frontier-research",
            "evidence-notes",
            "papers-archive",
            "whitepaper",
            "research-programs",
            "methods-integrity",
        ):
            self.assertIn(f'id="{section_id}"', page)
        self.assertIn("ACE Benchmark v1.1 Technical Whitepaper", page)
        self.assertIn('href="ACE_Whitepaper_v1.1.pdf"', page)
        self.assertIn("Papers &amp; Archive", page)
        self.assertIn("June 2026", page)
        self.assertNotIn("In preparation", page)
        self.assertIn("Download paper", page)
        self.assertIn("retrospective 272-case cohort", page)
        self.assertNotIn("is a current 350-case benchmark", page_lower)
        self.assertIn("not a current 350-case benchmark", page_lower)
        self.assertIn("preregistered dual-rater agreement is still in progress", page)
        self.assertNotIn("manual agreement has been validated", page_lower)
        self.assertIn("private prompts", page_lower)
        self.assertIn("holdout ids", page_lower)
        self.assertIn("raw responses", page_lower)
        archive_block = re.search(
            r'<section class="research-section" id="papers-archive".*?</section>',
            page,
            re.S,
        )
        self.assertIsNotNone(archive_block)
        archive_html = archive_block.group(0)
        self.assertIn('href="ACE-272-paper.pdf"', archive_html)
        self.assertIn('href="benchmark.html"', archive_html)

    def test_research_hub_removes_download_gate_and_countdown(self):
        page = (ROOT / "research.html").read_text(encoding="utf-8").lower()
        for forbidden in (
            "gate-modal",
            "gate-form",
            "open-modal-btn",
            "wp_leads",
            "formspree",
            "coming soon",
            "17 pages",
            "target=new date",
        ):
            self.assertNotIn(forbidden, page)

    def test_old_whitepaper_url_redirects_to_embedded_whitepaper(self):
        page = (ROOT / "whitepaper.html").read_text(encoding="utf-8")
        self.assertIn('url=research.html#whitepaper', page)
        self.assertIn('href="research.html#whitepaper"', page)
        self.assertNotIn("<main id=\"main-content\">", page)

    def test_catalog_is_machine_readable_and_tracks_published_deep_paper(self):
        catalog = json.loads((ROOT / "research-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"], 1)
        self.assertGreaterEqual(len(catalog["publications"]), 2)
        featured = next(item for item in catalog["publications"] if item["id"] == "ace-272-benchmark-paper")
        for key in ("id", "title", "type", "date", "abstract", "authors", "topics", "version", "status", "links"):
            self.assertIn(key, featured)
        self.assertEqual(featured["status"], "published")
        self.assertEqual(featured["date"], "2026-08-18")
        abstract_lower = featured["abstract"].lower()
        self.assertIn("historical", abstract_lower)
        self.assertIn("retrospective", abstract_lower)
        self.assertIn("272-case", abstract_lower)
        self.assertIn("not a current 350-case benchmark", abstract_lower)
        self.assertIn("preregistered dual-rater agreement pending", abstract_lower)
        self.assertEqual(featured["links"]["pdf"], "ACE-272-paper.pdf")
        self.assertNotIn("results", featured["links"])
        self.assertIn("methodology", featured["links"])
        self.assertNotIn("arxiv", featured["links"])
        whitepaper = next(item for item in catalog["publications"] if item["id"] == "ace-v1-1-whitepaper")
        self.assertEqual(whitepaper["status"], "archived")
        self.assertEqual(whitepaper["links"]["pdf"], "ACE_Whitepaper_v1.1.pdf")

    def test_all_site_entries_call_the_page_research(self):
        for path in HTML_FILES:
            page = path.read_text(encoding="utf-8")
            self.assertNotRegex(page, r'>\s*Whitepaper\s*<', msg=str(path))
            if path.name != "whitepaper.html":
                self.assertNotRegex(page, r'href="/?whitepaper(?:\.html)?"', msg=str(path))
        homepage = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Explore ACE Research", homepage)
        self.assertIn('href="research.html"', homepage)

    def test_privacy_policy_no_longer_claims_a_whitepaper_lead_form(self):
        privacy = (ROOT / "privacy.html").read_text(encoding="utf-8").lower()
        self.assertNotIn("whitepaper download form", privacy)
        self.assertNotIn("deliver requested whitepapers", privacy)

    def test_accessible_static_content_exists_without_javascript(self):
        page = (ROOT / "research.html").read_text(encoding="utf-8")
        self.assertIn('class="skip-link"', page)
        self.assertIn('href="#main-content"', page)
        self.assertIn('aria-current="page"', page)
        self.assertRegex(page, r'<article[^>]*class="[^"]*research-publication')
        self.assertNotIn("fetch(", page)

    def test_research_page_is_in_sitemap_and_static_page_set(self):
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        self.assertIn("https://logionace.com/research.html", sitemap)
        static_page_suite = (ROOT / "tests" / "test_static_site.py").read_text(encoding="utf-8")
        self.assertRegex(static_page_suite, r'PUBLIC_PAGES\s*=\s*\([^)]*"research\.html"')

    def test_research_head_has_featured_share_metadata_and_canonical(self):
        page = (ROOT / "research.html").read_text(encoding="utf-8")
        self.assertIn(
            '<meta property="og:title" content="ACE Research | Enterprise AI Trust">',
            page,
        )
        self.assertIn(
            '<meta property="og:description" content="Frontier reports, control evidence notes, benchmark papers, and methods for enterprise AI trust.">',
            page,
        )
        self.assertIn('<meta property="og:type" content="website">', page)
        self.assertIn('<meta property="og:url" content="https://logionace.com/research.html">', page)
        self.assertIn('<link rel="canonical" href="https://logionace.com/research.html">', page)

    def test_research_page_exposes_collection_jsonld(self):
        page = (ROOT / "research.html").read_text(encoding="utf-8")
        match = re.search(
            r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
            page,
            re.S,
        )
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertEqual(data["@context"], "https://schema.org")
        self.assertEqual(data["@type"], "CollectionPage")
        self.assertEqual(data["name"], "ACE Research")
        self.assertEqual(data["url"], "https://logionace.com/research.html")
        self.assertEqual(data["mainEntity"]["@type"], "ItemList")
        self.assertEqual(len(data["mainEntity"]["itemListElement"]), 3)
        self.assertIn(
            "frontier-research/beyond-identity-emerging-authority-layer.html",
            data["mainEntity"]["itemListElement"][0]["url"],
        )


if __name__ == "__main__":
    unittest.main()
