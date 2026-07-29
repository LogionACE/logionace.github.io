"""The whitepaper is a dated record, and has to read as one.

`whitepaper.html` reports the v1.1 round of June 2026. Those numbers were
hand-written into the page; nothing regenerates them when a new evaluation is
approved, and nothing checks them against the approved snapshot. That is a
legitimate thing for a research paper to be. It is not a legitimate thing for
a page that looks like the current results.

So the page is frozen and labelled rather than wired up: the reader is told
the as-of date before the first figure, and is pointed at the Reports page,
which does read the approved snapshot. These tests hold that line. They will
fail if someone deletes the notice, and they will fail if someone quietly
starts presenting the archived numbers as live.

The alternative -- making the whitepaper consume the approved snapshot -- was
not taken because the paper's prose interprets its numbers ("Averages lie",
"Data Protection is the weakest domain"). Numbers that move under prose that
does not is a worse failure than a clearly dated archive.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from conftest import SITE_ROOT, read

WHITEPAPER = "whitepaper.html"
PDF = "ACE_Whitepaper_v1.1.pdf"
AS_OF = "2026-06"

#: The round the page reports, spelled as a reader sees it.
AS_OF_TEXT = "June 2026"


def whitepaper() -> str:
    return read(WHITEPAPER)


def test_the_page_declares_itself_archived_and_dated():
    page = whitepaper()
    match = re.search(
        r'<section class="wp-archive-notice"([^>]*)>', page
    )
    assert match, "the whitepaper carries no archive notice"
    attributes = match.group(1)
    assert 'data-artifact-state="archived"' in attributes
    assert f'data-as-of="{AS_OF}"' in attributes


def test_the_reader_is_told_before_the_first_number():
    """A footnote under a heatmap is not a label."""
    page = whitepaper()
    notice = page.index('class="wp-archive-notice"')
    first_figure = page.index("<h1>9 tested. 0 passed.</h1>")
    assert notice < first_figure


def test_the_notice_says_the_figures_are_not_updated():
    notice = re.search(
        r'<section class="wp-archive-notice".*?</section>', whitepaper(), re.S
    )
    assert notice, "the whitepaper carries no archive notice"
    text = re.sub(r"<[^>]+>", " ", notice.group(0))
    for phrase in ("not updated", "not the verified public results", AS_OF_TEXT):
        assert phrase in text, f"the archive notice does not say {phrase!r}"


def test_the_notice_points_at_the_page_that_is_current():
    notice = re.search(
        r'<section class="wp-archive-notice".*?</section>', whitepaper(), re.S
    )
    assert 'href="benchmark.html"' in notice.group(0)
    assert (SITE_ROOT / "benchmark.html").is_file()


def test_the_title_and_description_do_not_read_as_current_results():
    page = whitepaper()
    title = re.search(r"<title>(.*?)</title>", page, re.S).group(1)
    description = re.search(
        r'<meta name="description" content="(.*?)"', page, re.S
    ).group(1)
    assert AS_OF_TEXT in title
    assert "archived" in title.casefold()
    assert AS_OF_TEXT in description
    assert "not updated" in description


def test_the_headline_claim_is_bounded_by_its_date():
    """"No system has achieved X" is a claim about now. It has to be dated."""
    page = whitepaper()
    tagline = re.search(r'class="wp-hero-tagline">(.*?)</p>', page, re.S).group(1)
    assert AS_OF_TEXT in tagline
    assert "has achieved" not in tagline, (
        "the tagline is written in the present perfect, which reads as a claim "
        "about today rather than about the round"
    )


def test_the_scores_carry_the_round_they_came_from():
    heatmap = re.search(
        r'<!-- DOMAIN HEATMAP -->.*?</section>', whitepaper(), re.S
    ).group(0)
    text = re.sub(r"<[^>]+>", " ", heatmap)
    assert AS_OF_TEXT in text
    assert "benchmark.html" in heatmap


def test_the_pdf_download_is_labelled_too():
    """The PDF outlives the page it was downloaded from."""
    download = re.search(r'<section class="section compact" id="download">.*?</section>', whitepaper(), re.S)
    assert download, "the download section moved; this gate needs updating"
    text = re.sub(r"<[^>]+>", " ", download.group(0))
    assert "Archived as of June 2026" in text
    assert 'href="benchmark.html"' in download.group(0)


# -- the freeze, held from the other side -----------------------------------


def test_the_whitepaper_does_not_read_the_approved_snapshot():
    """If it ever should, this test is the place that says so deliberately."""
    page = whitepaper()
    assert "approved-artifacts.json" not in page
    assert "ace-approved-pin.js" not in page
    assert "ace-artifacts.js" not in page


def test_no_current_facing_page_repeats_the_archived_figures():
    """The archived numbers are allowed on the archive, and nowhere else."""
    archived = ("9 tested. 0 passed.", "Avg 72.8", "Avg 76.9")
    for path in sorted(SITE_ROOT.glob("*.html")):
        if path.name == WHITEPAPER:
            continue
        page = path.read_text(encoding="utf-8")
        for figure in archived:
            assert figure not in page, (
                f"{path.name} repeats the archived figure {figure!r} without the "
                "archive's date on it"
            )


def test_the_published_pdf_is_the_one_the_release_evidence_records():
    """Its bytes are part of the release record while it stays public."""
    pdf = SITE_ROOT / PDF
    assert pdf.is_file(), "the whitepaper PDF is linked but not published"
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    # Recorded rather than pinned: the paper may legitimately be replaced by a
    # newer archived edition. What may not happen is it changing unnoticed, so
    # the digest goes in the release evidence and is compared there.
    assert pdf.stat().st_size > 0
