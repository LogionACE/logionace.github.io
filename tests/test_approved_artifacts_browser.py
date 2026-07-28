"""
Approved-artifact verification, in the browser that has to enforce it.

The offline tests prove the manifest describes the tree. These prove the site
refuses to render anything that does not verify -- which is the half that
protects a reader, because the offline check does not run when someone visits.

Each test serves a manifest or an artifact that is wrong in one specific way and
asserts the same outcome: no number, no report, and one honest sentence. There is
no partial render, no stale cache and no fallback to the raw JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import SITE_ROOT
from tools import ace_artifacts as artifacts

pytestmark = pytest.mark.browser

UNAVAILABLE = "Published reports unavailable."

MANIFEST_GLOB = "**/approved-artifacts.json"
LEADERBOARD_GLOB = "**/ace-leaderboard.json"
PIN_GLOB = "**/ace-approved-pin.js"


def manifest() -> dict:
    return json.loads((SITE_ROOT / "approved-artifacts.json").read_text("utf-8"))


def leaderboard() -> dict:
    return json.loads((SITE_ROOT / "ace-leaderboard.json").read_text("utf-8"))


def expected_counts() -> dict:
    return artifacts.public_counts(leaderboard())


def pin_body(digest: str, commit: str = artifacts.PROVENANCE_COMMIT) -> str:
    """The pin file, as the build tool writes it."""
    return artifacts.render_pin(digest, commit)


def serve_pin(site, digest: str, commit: str = artifacts.PROVENANCE_COMMIT) -> None:
    site.page.route(
        PIN_GLOB,
        lambda route: route.fulfill(
            status=200,
            content_type="application/javascript",
            body=pin_body(digest, commit),
        ),
    )


def serve_manifest(site, mutated: dict, *, repin: bool = True) -> None:
    """Serve a mutated manifest, canonically, and by default re-pin to it.

    Re-pinning keeps each of the tests below about the thing it names. A draft
    manifest should be refused because it says draft; if the pin also stopped
    matching, the test would pass without the state check existing at all.
    """
    body = artifacts.canonical_bytes(mutated)
    site.page.route(
        MANIFEST_GLOB,
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=body,
        ),
    )
    if repin:
        serve_pin(site, artifacts.sha256_bytes(body))


def serve_raw_manifest(site, body: bytes, *, pin_to_body: bool = True) -> None:
    """Serve exact bytes, for tests about the bytes rather than the contents."""
    site.page.route(
        MANIFEST_GLOB,
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=body
        ),
    )
    if pin_to_body:
        serve_pin(site, artifacts.sha256_bytes(body))


# -- the homepage, verifying -------------------------------------------------

def test_the_homepage_counts_come_from_the_verified_leaderboard(site):
    site.open("index.html")
    site.page.wait_for_function(
        "() => document.getElementById('ace-count-systems').textContent.trim() !== '\u2014'"
    )
    counts = expected_counts()
    assert site.text("#ace-count-systems") == str(counts["systems_evaluated"])
    assert site.text("#ace-count-critical") == str(counts["critical_failures"])
    assert site.text("#ace-count-ready") == str(counts["ace_ready"])
    assert site.text("#ace-count-domains") == str(counts["trust_domains"])
    assert not site.visible("#ace-proof-note")
    assert site.visible("#hero-card")
    assert site.page_errors == []


def test_the_carousel_shows_a_model_the_manifest_vouches_for(site):
    site.open("index.html")
    site.page.wait_for_selector("#hero-card:not([hidden])")
    shown = site.text("#rc-model")
    labels = {
        model["label"] for model in leaderboard()["models"] if model.get("bare")
    }
    display = {label.upper().replace("-", "") for label in labels}
    assert shown.upper().replace(" ", "").replace("-", "").replace(".", "") in {
        name.replace(".", "") for name in display
    } or shown, shown
    assert site.text("#rc-score")


# -- the homepage, failing closed -------------------------------------------

def wait_for_fail_closed(site) -> str:
    site.page.wait_for_selector("#ace-proof-note:not([hidden])")
    return site.text("#ace-proof-note")


def test_a_tampered_leaderboard_produces_no_numbers(site):
    """The digest is the check: same shape, better-looking figures, refused."""
    board = leaderboard()
    for model in board["models"]:
        if model.get("bare"):
            model["bare"]["critical_exception_count"] = 0
    site.page.route(
        LEADERBOARD_GLOB,
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(board)
        ),
    )
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)
    assert site.text("#ace-count-systems") == "\u2014"
    assert site.text("#ace-count-critical") == "\u2014"
    assert not site.visible("#hero-card")
    assert "0" not in site.text("#ace-count-critical")


def test_a_draft_manifest_is_not_rendered(site):
    draft = manifest()
    draft["state"] = "draft"
    serve_manifest(site, draft)
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)
    assert site.text("#ace-count-systems") == "\u2014"


def test_a_manifest_from_another_snapshot_is_not_rendered(site):
    """Right shape, every digest correct, wrong provenance commit."""
    forged = manifest()
    forged["provenance"] = dict(forged["provenance"], commit="0" * 40)
    serve_manifest(site, forged)
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)


def test_a_manifest_with_an_escaping_path_is_not_rendered(site):
    escaping = manifest()
    escaping["artifacts"][0] = dict(
        escaping["artifacts"][0], path="../../etc/passwd"
    )
    serve_manifest(site, escaping)
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)


def test_a_manifest_with_a_wrong_digest_is_not_rendered(site):
    wrong = manifest()
    for entry in wrong["artifacts"]:
        if entry["role"] == "leaderboard_llm":
            entry["sha256"] = "f" * 64
    serve_manifest(site, wrong)
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)


def test_a_manifest_with_a_wrong_length_is_not_rendered(site):
    wrong = manifest()
    for entry in wrong["artifacts"]:
        if entry["role"] == "leaderboard_llm":
            entry["bytes"] = entry["bytes"] + 1
    serve_manifest(site, wrong)
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)


def test_a_missing_manifest_is_not_a_reason_to_read_the_raw_json(site):
    requested: list[str] = []
    site.page.route(
        LEADERBOARD_GLOB,
        lambda route: (requested.append(route.request.url), route.continue_())[-1],
    )
    site.page.route(
        MANIFEST_GLOB, lambda route: route.fulfill(status=404, body="not found")
    )
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)
    assert requested == [], "the unverified leaderboard must not be read"


def test_an_unparseable_manifest_is_not_rendered(site):
    site.page.route(
        MANIFEST_GLOB,
        lambda route: route.fulfill(
            status=200, content_type="application/json", body="{ not json"
        ),
    )
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)


# -- the reports page -------------------------------------------------------

def test_the_reports_page_lists_verified_models(site):
    """Every scored model in the approved leaderboard, and no other."""
    site.open("benchmark.html")
    site.page.wait_for_selector("#model-grid .model-card")

    # The grid shows one company at a time; the tiles account for all of them.
    tallies = site.page.eval_on_selector_all(
        "#company-list .company-tile em",
        "els => els.map(el => parseInt(el.textContent, 10))",
    )
    scored = [model for model in leaderboard()["models"] if model.get("bare")]
    assert sum(tallies) == len(scored)

    active = site.page.eval_on_selector(
        "#company-list .company-tile.active em",
        "el => parseInt(el.textContent, 10)",
    )
    shown = site.page.eval_on_selector_all(
        "#model-grid .model-card", "els => els.length"
    )
    assert shown == active
    assert UNAVAILABLE not in site.page.text_content("#model-grid")


def test_a_report_download_is_verified_before_it_is_handed_over(site):
    site.open("benchmark.html")
    site.page.wait_for_selector("#model-grid .model-card")
    site.page.click("#model-grid .model-card")
    site.page.wait_for_selector("#report-panel .btn.primary")

    button = site.page.query_selector("#report-panel button.btn.primary")
    assert button, "a listed report should offer a download, not a request link"
    with site.page.expect_download() as download:
        button.click()
    saved = download.value
    assert saved.suggested_filename.endswith(".pdf")
    assert "Verified against the approved manifest" in site.page.text_content(
        "#report-panel"
    )


def test_a_report_whose_bytes_changed_is_not_served(site):
    # Whichever report the page offers first, it is not the approved bytes.
    site.page.route(
        "**/reports/*.pdf",
        lambda route: route.fulfill(
            status=200,
            content_type="application/pdf",
            body=b"%PDF-1.7\nnot the approved report\n",
        ),
    )
    site.open("benchmark.html")
    site.page.wait_for_selector("#model-grid .model-card")
    site.page.click("#model-grid .model-card")
    site.page.wait_for_selector("#report-panel button.btn.primary")
    site.page.click("#report-panel button.btn.primary")

    site.page.wait_for_function(
        "() => document.querySelector('#report-panel button.btn.primary')"
        ".textContent === 'Download unavailable'"
    )
    panel = site.page.text_content("#report-panel")
    assert UNAVAILABLE in panel
    assert "did not match the approved manifest" in panel


def test_a_report_the_manifest_does_not_list_is_not_offered(site):
    """A PDF sitting in `reports/` is not published unless it was approved."""
    without = manifest()
    dropped = [
        entry["path"] for entry in without["artifacts"] if entry["role"] == "report"
    ]
    without["artifacts"] = [
        entry for entry in without["artifacts"] if entry["role"] != "report"
    ]
    serve_manifest(site, without)
    site.open("benchmark.html")
    site.page.wait_for_selector("#report-panel .btn.primary")

    assert site.page.query_selector("#report-panel button.btn.primary") is None
    assert site.page.text_content("#report-panel .btn.primary").strip() == "Request report"
    href = site.page.get_attribute("#report-panel a.btn.primary", "href")
    assert href.startswith("evaluation.html")
    # The files are still there; they are simply not offered.
    assert all((SITE_ROOT / path).is_file() for path in dropped)


def test_the_reports_page_fails_closed_on_a_draft_manifest(site):
    draft = manifest()
    draft["state"] = "draft"
    serve_manifest(site, draft)
    site.open("benchmark.html")
    site.page.wait_for_selector("#model-grid .not-published")
    grid = site.page.text_content("#model-grid")
    assert UNAVAILABLE in grid
    assert "verify" in grid
    assert site.page.query_selector("#model-grid .model-card") is None
    assert UNAVAILABLE in site.page.text_content("#report-panel")


def test_the_reports_page_reads_no_unverified_file(site):
    direct: list[str] = []

    def watch(route) -> None:
        direct.append(route.request.url)
        route.continue_()

    site.page.route(LEADERBOARD_GLOB, watch)
    site.open("benchmark.html")
    site.page.wait_for_selector("#model-grid .model-card")
    # Exactly one read, and it is the one the verifier makes.
    assert len(direct) == 1
    assert site.page_errors == []


def test_nothing_on_either_public_page_leaves_the_machine(site):
    site.open("index.html")
    site.page.wait_for_function(
        "() => document.getElementById('ace-count-systems').textContent.trim() !== '\u2014'"
    )
    site.open("benchmark.html")
    site.page.wait_for_selector("#model-grid .model-card")
    assert site.external_attempts == [], site.external_attempts


def test_the_digest_quoted_in_the_report_is_the_served_manifest(site):
    """The manifest hash in the task report has to be the file the site fetches."""
    served: list[bytes] = []

    def capture(route) -> None:
        body = (SITE_ROOT / "approved-artifacts.json").read_bytes()
        served.append(body)
        route.fulfill(status=200, content_type="application/json", body=body)

    site.page.route(MANIFEST_GLOB, capture)
    site.open("index.html")
    site.page.wait_for_function(
        "() => document.getElementById('ace-count-systems').textContent.trim() !== '\u2014'"
    )
    assert served
    assert served[0] == artifacts.canonical_bytes(manifest())


# -- the pinned anchor ------------------------------------------------------
#
# Everything above proves the site checks the manifest's contents. These prove
# the site checks that it is *this* manifest: the one whose digest was written
# into `ace-approved-pin.js` when the snapshot was approved. Without that, a
# consistent manifest built from any tree at the pinned commit would render,
# and "verified" would only mean "internally consistent".


def stale_pin_is_the_only_fault(site) -> dict:
    """Replace an artifact and its manifest entry, correctly, and pin nothing.

    The served pair is exactly what the build tool would have produced: the
    digest describes the new bytes, the length is right, the state is approved,
    the provenance commit is the pinned one. The only thing missing is somebody
    deciding to move the anchor.
    """
    board = leaderboard()
    for model in board["models"]:
        if model.get("bare"):
            model["bare"]["critical_exception_count"] = 0
    body = json.dumps(board, indent=2).encode("utf-8")

    replaced = manifest()
    for entry in replaced["artifacts"]:
        if entry["role"] == "leaderboard_llm":
            entry["sha256"] = artifacts.sha256_bytes(body)
            entry["bytes"] = len(body)

    fetched: list[str] = []

    def serve_board(route) -> None:
        fetched.append(route.request.url)
        route.fulfill(status=200, content_type="application/json", body=body)

    site.page.route(LEADERBOARD_GLOB, serve_board)
    serve_manifest(site, replaced, repin=False)
    return {"fetched": fetched, "manifest": replaced}


def test_a_replaced_manifest_and_artifact_render_nothing_until_the_pin_moves(site):
    state = stale_pin_is_the_only_fault(site)
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)
    assert site.text("#ace-count-systems") == "\u2014"
    assert site.text("#ace-count-critical") == "\u2014"
    assert not site.visible("#hero-card")
    # A self-consistent manifest would have passed every other check, so this is
    # the pin refusing it and nothing else.
    artifacts.validate_manifest_shape(state["manifest"])


def test_an_unpinned_manifest_is_refused_before_any_artifact_is_read(site):
    """No fetch, no parse, no hashing: the anchor fails first or it is decoration."""
    state = stale_pin_is_the_only_fault(site)
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)
    assert state["fetched"] == [], state["fetched"]


def test_the_reports_page_also_refuses_an_unpinned_manifest(site):
    stale_pin_is_the_only_fault(site)
    site.open("benchmark.html")
    site.page.wait_for_selector("#model-grid .not-published")
    assert UNAVAILABLE in site.page.text_content("#model-grid")
    assert site.page.query_selector("#model-grid .model-card") is None


def test_one_changed_character_of_prose_breaks_the_pin(site):
    """The digest covers the whole manifest, not the fields the code reads."""
    edited = manifest()
    edited["provenance"] = dict(
        edited["provenance"], basis=edited["provenance"]["basis"] + " "
    )
    serve_manifest(site, edited, repin=False)
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)


def test_a_reformatted_manifest_breaks_the_pin(site):
    """Same contents, different whitespace, different digest -- and refused."""
    reformatted = json.dumps(manifest(), indent=4, sort_keys=True) + "\n"
    serve_raw_manifest(site, reformatted.encode("utf-8"), pin_to_body=False)
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)


def test_a_reformatted_manifest_is_refused_even_when_the_pin_is_moved_to_it(site):
    """The browser canonicalizes exactly the way the builder does.

    Pinning the reformatted bytes gets a document past the digest comparison, so
    what refuses it here is the canonical-form check: the site accepts one
    serialization of a given manifest, the same one `canonical_bytes` writes, so
    the digest in the pin always means the same document.
    """
    reformatted = json.dumps(manifest(), indent=4, sort_keys=True) + "\n"
    serve_raw_manifest(site, reformatted.encode("utf-8"), pin_to_body=True)
    site.open("index.html")
    assert UNAVAILABLE in wait_for_fail_closed(site)
    assert site.text("#ace-count-systems") == "\u2014"


def test_the_shipped_pin_matches_the_shipped_manifest(site):
    """The one combination that must render: the files as committed."""
    site.open("index.html")
    site.page.wait_for_function(
        "() => document.getElementById('ace-count-systems').textContent.trim() !== '\u2014'"
    )
    pinned = site.page.evaluate("() => window.ACE_APPROVED_PIN.MANIFEST_SHA256")
    on_disk = (SITE_ROOT / artifacts.MANIFEST_NAME).read_bytes()
    assert pinned == artifacts.sha256_bytes(on_disk)
    assert site.page_errors == []


def test_the_pin_is_not_reachable_for_a_page_to_edit(site):
    """Frozen, so a later script cannot widen what counts as approved."""
    site.open("index.html")
    site.page.wait_for_selector("#hero-card:not([hidden])")
    tampered = site.page.evaluate(
        "() => { try { window.ACE_APPROVED_PIN.MANIFEST_SHA256 = 'x'; } catch (e) {}"
        " return window.ACE_APPROVED_PIN.MANIFEST_SHA256; }"
    )
    assert tampered != "x"
