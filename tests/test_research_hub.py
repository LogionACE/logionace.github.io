import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = sorted(ROOT.glob("*.html"))


class ResearchHubTests(unittest.TestCase):
    def test_whitepaper_url_is_now_research_hub(self):
        page = (ROOT / "whitepaper.html").read_text(encoding="utf-8")
        self.assertIn("<title>ACE Research - LogionACE</title>", page)
        self.assertEqual(page.count("<h1"), 1)
        for section_id in (
            "featured",
            "research-notes",
            "deep-papers",
            "research-areas",
            "methods-integrity",
        ):
            self.assertIn(f'id="{section_id}"', page)

    def test_research_hub_removes_download_gate_and_countdown(self):
        page = (ROOT / "whitepaper.html").read_text(encoding="utf-8").lower()
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

    def test_catalog_is_machine_readable_and_does_not_publish_unreleased_links(self):
        catalog = json.loads((ROOT / "research-catalog.json").read_text(encoding="utf-8"))
        self.assertEqual(catalog["schema_version"], 1)
        self.assertGreaterEqual(len(catalog["publications"]), 1)
        featured = catalog["publications"][0]
        for key in ("id", "title", "type", "date", "abstract", "authors", "topics", "version", "status", "links"):
            self.assertIn(key, featured)
        self.assertEqual(featured["status"], "in-preparation")
        self.assertNotIn("pdf", featured["links"])
        self.assertNotIn("arxiv", featured["links"])

    def test_all_site_entries_call_the_page_research(self):
        for path in HTML_FILES:
            page = path.read_text(encoding="utf-8")
            self.assertNotRegex(page, r'>\s*Whitepaper\s*<', msg=str(path))
        homepage = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Explore ACE Research", homepage)

    def test_privacy_policy_no_longer_claims_a_whitepaper_lead_form(self):
        privacy = (ROOT / "privacy.html").read_text(encoding="utf-8").lower()
        self.assertNotIn("whitepaper download form", privacy)
        self.assertNotIn("deliver requested whitepapers", privacy)

    def test_accessible_static_content_exists_without_javascript(self):
        page = (ROOT / "whitepaper.html").read_text(encoding="utf-8")
        self.assertIn('class="skip-link"', page)
        self.assertIn('href="#main-content"', page)
        self.assertIn('aria-current="page"', page)
        self.assertRegex(page, r'<article[^>]*class="[^"]*research-publication')
        self.assertNotIn("fetch(", page)


if __name__ == "__main__":
    unittest.main()
