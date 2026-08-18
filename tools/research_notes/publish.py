"""Build and verify public ACE Research Note static artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from html import escape
from pathlib import Path
from typing import Any

from tools.research_notes.html import (
    CONTROL_LABELS,
    ROOT,
    render_note_html,
)
from tools.research_notes.model import load_note, note_slug
from tools.research_notes.pdf import build_pdf


START = "<!-- ACE_RESEARCH_NOTES_START -->"
END = "<!-- ACE_RESEARCH_NOTES_END -->"


class PublicationBuildError(RuntimeError):
    """Raised when generated Research Note artifacts are missing or stale."""


def _abstract(note: dict[str, Any]) -> str:
    return note["parts"]["problem"]["body"][0]["text"].split(" [", 1)[0]


def catalog_entry(note: dict[str, Any], source_bytes: bytes) -> dict[str, Any]:
    slug = note_slug(note)
    return {
        "id": note["id"],
        "title": note["title"],
        "type": "research-note",
        "date": note["date"],
        "abstract": _abstract(note),
        "authors": [note["author"]],
        "topics": note["topics"],
        "version": note["version"],
        "status": "published",
        "primary_control": note["primary_control"],
        "secondary_controls": note.get("secondary_controls", []),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "links": {
            "page": f"research-notes/{slug}.html",
            "pdf": f"research-notes/{note['id']}.pdf",
        },
    }


def render_hub_entries(notes: list[dict[str, Any]]) -> str:
    if not notes:
        return """    <article class="research-note research-publication">
      <span class="research-status">Series established</span>
      <h3>ACE Research Notes</h3>
      <p>Short technical analyses of verified failure patterns, enterprise impact, and remediation hypotheses. Each note records its evidence boundary and limitations.</p>
      <span class="research-note-state">No public notes released yet</span>
    </article>"""

    entries = []
    ordered = sorted(notes, key=lambda item: (item["date"], item["id"]), reverse=True)
    for note in ordered:
        slug = note_slug(note)
        scope = CONTROL_LABELS.get(note["primary_control"], note["primary_control"])
        entries.append(
            f"""    <article class="research-note research-publication">
      <span class="research-status">Published · {escape(note["date"])}</span>
      <p class="research-note-state">{escape(note["id"])} · {escape(scope)}</p>
      <h3><a href="research-notes/{slug}.html">{escape(note["title"])}</a></h3>
      <p>{escape(_abstract(note))}</p>
      <div class="research-actions">
        <a class="btn primary" href="research-notes/{slug}.html">Read note</a>
        <a class="btn outline" href="research-notes/{note["id"]}.pdf">Download PDF</a>
      </div>
    </article>"""
        )
    return "\n".join(entries)


def render_sitemap_entries(notes: list[dict[str, Any]]) -> str:
    ordered = sorted(notes, key=lambda item: (item["date"], item["id"]), reverse=True)
    return "\n".join(
        "  <url>"
        f"<loc>https://logionace.com/research-notes/{note_slug(note)}.html</loc>"
        f"<lastmod>{note['date']}</lastmod><priority>0.7</priority>"
        "</url>"
        for note in ordered
    )


def replace_generated_block(text: str, body: str) -> str:
    pattern = re.compile(rf"{re.escape(START)}.*?{re.escape(END)}", re.S)
    replacement = f"{START}\n{body.rstrip()}\n{END}"
    updated, count = pattern.subn(replacement, text)
    if count != 1:
        raise PublicationBuildError("expected one ACE Research Notes generated block")
    return updated


def _load_sources(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    source_dir = root / "research-notes" / "source"
    loaded = []
    if not source_dir.exists():
        return loaded
    for path in sorted(source_dir.glob("ace-rn-*.json")):
        note = load_note(path)
        expected_name = f"{note['id'].lower()}.json"
        if path.name != expected_name:
            raise PublicationBuildError(
                f"{path.name} must be named {expected_name}"
            )
        if note["status"] == "published":
            loaded.append((path, note))
    ids = [note["id"] for _, note in loaded]
    slugs = [note_slug(note) for _, note in loaded]
    if len(ids) != len(set(ids)) or len(slugs) != len(set(slugs)):
        raise PublicationBuildError("Research Note ids and slugs must be unique")
    return loaded


def _catalog_with_notes(
    catalog: dict[str, Any],
    loaded: list[tuple[Path, dict[str, Any]]],
) -> dict[str, Any]:
    retained = [
        item
        for item in catalog["publications"]
        if item.get("type") != "research-note"
    ]
    entries = [catalog_entry(note, path.read_bytes()) for path, note in loaded]
    publications = retained + sorted(
        entries,
        key=lambda item: (item["date"], item["id"]),
        reverse=True,
    )
    updated = dict(catalog)
    updated["publications"] = publications
    dates = [item["date"] for item in publications]
    if dates:
        updated["updated_at"] = max(dates)
    return updated


def build(root: Path = ROOT) -> list[Path]:
    loaded = _load_sources(root)
    notes = [note for _, note in loaded]
    output_dir = root / "research-notes"
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for _, note in loaded:
        html_path = output_dir / f"{note_slug(note)}.html"
        html_path.write_text(
            render_note_html(note, preview=False, asset_prefix="../"),
            "utf-8",
        )
        pdf_path = output_dir / f"{note['id']}.pdf"
        build_pdf(html_path, pdf_path)
        written.extend((html_path, pdf_path))

    catalog_path = root / "research-catalog.json"
    catalog = json.loads(catalog_path.read_text("utf-8"))
    updated_catalog = _catalog_with_notes(catalog, loaded)
    catalog_path.write_text(
        json.dumps(updated_catalog, ensure_ascii=False, indent=2) + "\n",
        "utf-8",
    )

    research_path = root / "research.html"
    research_path.write_text(
        replace_generated_block(
            research_path.read_text("utf-8"),
            render_hub_entries(notes),
        ),
        "utf-8",
    )
    sitemap_path = root / "sitemap.xml"
    sitemap_path.write_text(
        replace_generated_block(
            sitemap_path.read_text("utf-8"),
            render_sitemap_entries(notes),
        ),
        "utf-8",
    )
    written.extend((catalog_path, research_path, sitemap_path))
    return written


def check(root: Path = ROOT) -> None:
    loaded = _load_sources(root)
    notes = [note for _, note in loaded]

    for _, note in loaded:
        html_path = root / "research-notes" / f"{note_slug(note)}.html"
        expected = render_note_html(note, preview=False, asset_prefix="../")
        if not html_path.is_file() or html_path.read_text("utf-8") != expected:
            raise PublicationBuildError(f"stale generated page: {html_path.name}")
        pdf_path = root / "research-notes" / f"{note['id']}.pdf"
        if not pdf_path.is_file() or not pdf_path.read_bytes().startswith(b"%PDF-"):
            raise PublicationBuildError(f"missing generated PDF: {pdf_path.name}")

    catalog_path = root / "research-catalog.json"
    actual_catalog = json.loads(catalog_path.read_text("utf-8"))
    expected_catalog = _catalog_with_notes(actual_catalog, loaded)
    if actual_catalog != expected_catalog:
        raise PublicationBuildError("research-catalog.json is stale")

    research = (root / "research.html").read_text("utf-8")
    if research != replace_generated_block(research, render_hub_entries(notes)):
        raise PublicationBuildError("research.html note entries are stale")
    sitemap = (root / "sitemap.xml").read_text("utf-8")
    if sitemap != replace_generated_block(sitemap, render_sitemap_entries(notes)):
        raise PublicationBuildError("sitemap.xml note entries are stale")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or verify ACE Research Notes.")
    parser.add_argument("command", choices=("build", "check"))
    args = parser.parse_args()
    if args.command == "build":
        for path in build():
            print(f"wrote {path}")
    else:
        check()
        print("Research Note publications are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
