import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = sorted(ROOT.glob("*.html"))


class ResearchHubTests(unittest.TestCase):
    def test_research_hub_contains_whitepaper(self):
        page = (ROOT / "research.html").read_text(encoding="utf-8")
        self.assertIn("<title>ACE Research - LogionACE</title>", page)
        self.assertEqual(page.count("<h1"), 1)
        for section_id in (
            "featured",
            "whitepaper",
            "research-notes",
            "deep-papers",
            "research-areas",
            "methods-integrity",
        ):
            self.assertIn(f'id="{section_id}"', page)
        self.assertIn("ACE Benchmark v1.1 Technical Whitepaper", page)
        self.assertIn('href="ACE_Whitepaper_v1.1.pdf"', page)
        self.assertIn("Archived research", page)
        self.assertIn("June 2026", page)

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

    def test_catalog_is_machine_readable_and_does_not_publish_unreleased_links(self):
        catalog = json.loads((ROOT / "research-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"], 1)
        self.assertGreaterEqual(len(catalog["publications"]), 2)
        featured = next(item for item in catalog["publications"] if item["id"] == "ace-272-benchmark-paper")
        for key in ("id", "title", "type", "date", "abstract", "authors", "topics", "version", "status", "links"):
            self.assertIn(key, featured)
        self.assertEqual(featured["status"], "in-preparation")
        self.assertNotIn("pdf", featured["links"])
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


if __name__ == "__main__":
    unittest.main()
