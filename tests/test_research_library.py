import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ResearchLibraryTests(unittest.TestCase):
    def test_library_is_a_complete_static_publication_index(self):
        page = (ROOT / "research-library.html").read_text(encoding="utf-8")
        self.assertEqual(page.count("<h1"), 1)
        self.assertIn("Research Library", page)
        self.assertIn("Frontier Research", page)
        self.assertIn("Evidence Notes", page)
        self.assertIn("Papers &amp; Archive", page)
        self.assertNotIn("fetch(", page)
        self.assertNotIn('type="module"', page)

    def test_library_lists_published_afr_and_all_twenty_notes(self):
        page = (ROOT / "research-library.html").read_text(encoding="utf-8")
        frontier = re.search(
            r"<!-- ACE_FRONTIER_RESEARCH_LIBRARY_START -->(.*?)"
            r"<!-- ACE_FRONTIER_RESEARCH_LIBRARY_END -->",
            page,
            re.S,
        )
        notes = re.search(
            r"<!-- ACE_RESEARCH_NOTES_LIBRARY_START -->(.*?)"
            r"<!-- ACE_RESEARCH_NOTES_LIBRARY_END -->",
            page,
            re.S,
        )
        self.assertIsNotNone(frontier)
        self.assertIsNotNone(notes)
        self.assertIn("AFR-2026-001", frontier.group(1))
        self.assertEqual(
            notes.group(1).count('class="research-note research-publication"'),
            20,
        )
        for note_number in range(1, 21):
            self.assertIn(f"ACE-RN-2026-{note_number:03d}", notes.group(1))

    def test_library_keeps_benchmarks_and_archived_whitepaper_accessible(self):
        page = (ROOT / "research-library.html").read_text(encoding="utf-8")
        self.assertIn("ACE-272", page)
        self.assertIn("Long-Context Benchmark", page)
        self.assertIn("ACE Governance &amp; Compliance Benchmark", page)
        self.assertIn("Archived whitepaper", page)
        self.assertIn('href="ACE_Whitepaper_v1.1.pdf"', page)

    def test_library_is_discoverable_from_sitemap_and_research_hub(self):
        sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
        hub = (ROOT / "research.html").read_text(encoding="utf-8")
        self.assertIn("https://logionace.com/research-library.html", sitemap)
        self.assertIn('href="research-library.html"', hub)


if __name__ == "__main__":
    unittest.main()
