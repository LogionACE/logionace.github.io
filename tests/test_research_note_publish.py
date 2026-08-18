import json
from pathlib import Path

from tools.research_notes.publish import (
    catalog_entry,
    render_hub_entries,
    render_sitemap_entries,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "research-note-sample.json"


def published_note():
    note = json.loads(FIXTURE.read_text("utf-8"))
    note["status"] = "published"
    return note


def test_catalog_entry_keeps_human_and_machine_readable_control_mapping():
    note = published_note()
    entry = catalog_entry(note, b"source")
    assert entry["id"] == "ACE-RN-2026-001"
    assert entry["type"] == "research-note"
    assert entry["primary_control"] == "DRAFT-DAC-01"
    assert entry["secondary_controls"] == ["DRAFT-TDA-01", "DRAFT-DEC-01"]
    assert entry["links"]["page"] == "research-notes/authority-must-shrink-not-grow.html"
    assert entry["links"]["pdf"] == "research-notes/ACE-RN-2026-001.pdf"
    assert len(entry["source_sha256"]) == 64


def test_hub_and_sitemap_entries_link_to_the_independent_note():
    note = published_note()
    hub = render_hub_entries([note])
    sitemap = render_sitemap_entries([note])
    assert "Authority Must Shrink, Not Grow" in hub
    assert 'href="research-notes/authority-must-shrink-not-grow.html"' in hub
    assert "Delegated authority containment" in hub
    assert "https://logionace.com/research-notes/authority-must-shrink-not-grow.html" in sitemap
    assert "<lastmod>2026-08-18</lastmod>" in sitemap


def test_hub_entry_escapes_publication_text():
    note = published_note()
    note["title"] = "<script>alert(1)</script>"
    hub = render_hub_entries([note])
    assert "<script>" not in hub
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in hub


def test_public_index_files_have_deterministic_note_markers():
    research = (ROOT / "research.html").read_text("utf-8")
    sitemap = (ROOT / "sitemap.xml").read_text("utf-8")
    for text in (research, sitemap):
        assert "ACE_RESEARCH_NOTES_START" in text
        assert "ACE_RESEARCH_NOTES_END" in text


def test_authoring_workflow_and_schema_are_present():
    readme = (ROOT / "research-notes" / "README.md").read_text("utf-8")
    schema = json.loads(
        (ROOT / "research-notes" / "schema" / "research-note.schema.json").read_text(
            "utf-8"
        )
    )
    assert "python3 -m tools.research_notes.preview" in readme
    assert "python3 -m tools.research_notes.publish check" in readme
    assert "No validated mitigation identified" in readme
    assert "1–2 new Research Notes per day" in readme
    assert "one note on X each day" in readme
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["id"]["pattern"] == "^ACE-RN-[0-9]{4}-[0-9]{3}$"
