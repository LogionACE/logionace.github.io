"""
What the published files may and may not contain.

These are the cheap checks that catch the expensive mistakes: a price that drifts
from the price list, a lead-capture form posting a customer's email to a third
party, a token in a query string, a second hard-coded API base that only some
pages use, a secret pasted into a commit. None of them need a browser, so they
run everywhere and run first.

The rule behind most of them: the site is a static tree of files, so anything
true of the site has to be true of the bytes. If a property cannot be asserted
about the bytes, it is not really a property of the site.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from conftest import (
    API_PLACEHOLDER,
    SITE_ROOT,
    html_pages,
    read,
    site_scripts,
)

CUSTOMER_FLOW_PAGES = (
    "request-submitted.html",
    "order-status.html",
    "payment-success.html",
    "payment-cancelled.html",
)

PUBLIC_PAGES = (
    "index.html",
    "benchmark.html",
    "evaluation.html",
    "methodology.html",
    "whitepaper.html",
    "company.html",
    "trust.html",
    "access.html",
    "privacy.html",
    "terms.html",
)

TEXT_SUFFIXES = {".html", ".js", ".json", ".css", ".xml", ".txt", ".svg", ".py", ".md"}


def text_files() -> list[Path]:
    """Every file a reader could fetch, plus the tooling, minus the binaries."""
    out: list[Path] = []
    for path in sorted(SITE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        parts = set(path.parts)
        if ".git" in parts or "__pycache__" in parts or ".pytest_cache" in parts:
            continue
        if "tests" in parts:
            # The suite itself carries the patterns it looks for.
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            out.append(path)
    return out


def relative(path: Path) -> str:
    return str(path.relative_to(SITE_ROOT))


# -- prices -----------------------------------------------------------------

EXPECTED_PRICES = {
    "public": "$25,000",
    "private": "$40,000+",
    "custom": "$60,000+",
    "founder": "$0",
}


def test_the_price_list_is_exactly_the_published_one():
    config = read("ace-config.js")
    for package, price in EXPECTED_PRICES.items():
        block = re.search(
            r"id:\s*'" + package + r"'.*?price:\s*'([^']+)'", config, re.S
        )
        assert block, f"ace-config.js does not list the {package} package"
        assert block.group(1) == price


def test_the_request_form_and_pricing_table_quote_the_same_prices():
    evaluation = read("evaluation.html")
    for price in EXPECTED_PRICES.values():
        assert price in evaluation, f"{price} is missing from evaluation.html"

    # A price the price list does not contain must not appear anywhere on the
    # page: that is how "$25,000" and "$30,000" end up on one site.
    quoted = set(re.findall(r"\$\d[\d,]*\+?", evaluation))
    allowed = set(EXPECTED_PRICES.values()) | {"$40,000", "$50,000"}
    assert quoted <= allowed, f"unexpected amounts on evaluation.html: {quoted - allowed}"


def test_the_form_never_presents_itself_as_immediate_payment():
    evaluation = read("evaluation.html")
    assert "Submit request" in evaluation
    for forbidden in ("Pay now", "Buy now", "Checkout", "Add to cart"):
        assert forbidden.lower() not in evaluation.lower()


# -- lead capture and PII ---------------------------------------------------

def test_no_page_posts_to_a_third_party_form_service():
    for path in text_files():
        body = path.read_text("utf-8", errors="replace").lower()
        for service in ("formspree", "hubspot", "mailchimp", "typeform", "getform"):
            assert service not in body, f"{relative(path)} still references {service}"


def test_nothing_writes_customer_details_to_local_storage():
    """Session storage is allowed and localStorage is not.

    A shared laptop outlives a tab. The status token and the idempotency key live
    in session storage, and the intake -- name, work email, company, endpoint --
    lives in neither.
    """
    calls = re.compile(r"localStorage\s*(?:\.|\[)")
    for path in list(html_pages()) + list(site_scripts()):
        body = path.read_text("utf-8")
        # Comments explaining the rule are allowed to name it; calls are not.
        code = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
        code = re.sub(r"^\s*//.*$", "", code, flags=re.M)
        found = calls.findall(code)
        assert not found, f"{relative(path)} calls localStorage"


def test_no_page_keeps_a_lead_list_in_the_browser():
    for path in text_files():
        body = path.read_text("utf-8", errors="replace")
        for leak in ("wp_leads", "LogionACE Lead", "leads.push"):
            assert leak not in body, f"{relative(path)} keeps a lead list"


def test_the_intake_is_never_persisted_by_the_form_script():
    order = read("ace-order.js")
    # The only thing the form is allowed to persist is the idempotency material.
    stored = re.findall(r"sessionStorage\.setItem\(\s*([A-Za-z_$][\w$]*)", order)
    assert stored == ["IDEMPOTENCY_SESSION_KEY"], stored


# -- secrets ----------------------------------------------------------------

SECRET_PATTERNS = (
    r"-----BEGIN[A-Z ]*PRIVATE KEY-----",
    r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{8,}",
    r"\bpk_(?:live|test)_[A-Za-z0-9]{8,}",
    r"\bwhsec_[A-Za-z0-9]{8,}",
    r"\bsk-(?:[A-Za-z0-9]+-)?[A-Za-z0-9]{20,}",
    r"\blg_[A-Za-z0-9_\-]{20,}",
    r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    r"\bAIza[0-9A-Za-z_\-]{30,}",
    r"\bghp_[A-Za-z0-9]{20,}",
    r"\bx-admin-key\s*[:=]\s*['\"][^'\"]+",
)


@pytest.mark.parametrize("pattern", SECRET_PATTERNS)
def test_the_published_tree_contains_no_credential(pattern):
    compiled = re.compile(pattern, re.I)
    for path in text_files():
        body = path.read_text("utf-8", errors="replace")
        if path.name == "ace-order.js":
            # It carries the patterns itself, as a detector.
            continue
        match = compiled.search(body)
        assert not match, f"{relative(path)} looks like it contains a credential"


def test_no_admin_surface_is_referenced_by_the_public_site():
    for path in list(html_pages()) + list(site_scripts()):
        body = path.read_text("utf-8")
        for internal in ("/v1/ace/admin", "X-Admin-Key", "ace_run_admin", "run_projection"):
            assert internal not in body, f"{relative(path)} references {internal}"


def test_the_site_never_talks_to_stripe_directly():
    for path in list(html_pages()) + list(site_scripts()):
        body = path.read_text("utf-8")
        assert "js.stripe.com" not in body, relative(path)
        assert "api.stripe.com" not in body, relative(path)
        assert "checkout.stripe.com" not in body, relative(path)
    # The payment URL is whatever the server sent, subject to being https.
    status = read("ace-status.js")
    assert "order.payment_url" in status
    assert "parsed.protocol !== 'https:'" in status


# -- the API base -----------------------------------------------------------

def test_the_api_base_is_declared_exactly_once():
    hits = [
        relative(path)
        for path in text_files()
        if API_PLACEHOLDER in path.read_text("utf-8", errors="replace")
    ]
    assert hits == ["ace-config.js"], hits


def test_every_api_call_builds_its_url_from_the_config():
    for path in site_scripts():
        body = path.read_text("utf-8")
        for call in re.findall(r"fetch\(\s*([^,)]+)", body):
            call = call.strip()
            assert (
                call.startswith("CONFIG.API_BASE")
                or call.startswith("CONFIG.APPROVED_MANIFEST_PATH")
                or call.startswith("entry.path")
            ), f"{relative(path)} fetches {call}"


def test_the_api_base_is_https():
    assert API_PLACEHOLDER.startswith("https://")


# -- the status token -------------------------------------------------------

def test_the_status_token_only_ever_travels_in_a_fragment_or_a_header():
    session = read("ace-session.js")
    status = read("ace-status.js")
    order = read("ace-order.js")

    assert "window.location.hash" in session
    assert "sessionStorage" in session
    for source in (session, status, order):
        assert "location.search" not in source
        assert "URLSearchParams" not in source
    # The lookup authenticates with a header, never a query parameter.
    assert "'X-ACE-Status-Token': link.token" in status
    assert "?token=" not in status and "?token=" not in session


def test_the_fragment_parser_refuses_a_malformed_link():
    session = read("ace-session.js")
    assert re.search(r"ORDER_ID_RE\s*=\s*/\^aceord_\[0-9a-f\]\{16,64\}\$/", session)
    assert re.search(r"TOKEN_RE\s*=\s*/\^\[A-Za-z0-9_-\]\{20,200\}\$/", session)
    # Both halves or nothing.
    assert "if (!ORDER_ID_RE.test(order) || !TOKEN_RE.test(token)) return null;" in session


def test_no_analytics_or_third_party_script_can_see_the_token():
    for path in list(html_pages()) + list(site_scripts()):
        body = path.read_text("utf-8")
        for tracker in ("googletagmanager", "google-analytics", "gtag(", "plausible.io",
                        "segment.com", "hotjar", "clarity.ms", "posthog"):
            assert tracker not in body, f"{relative(path)} loads {tracker}"
        for src in re.findall(r'<script[^>]*src="([^"]+)"', body):
            assert "//" not in src, f"{relative(path)} loads an external script: {src}"


def test_polling_is_bounded():
    status = read("ace-status.js")
    assert "AUTO_REFRESH_LIMIT" in status
    assert "setInterval" not in status, "the status page must not poll forever"
    limit = re.search(r"AUTO_REFRESH_LIMIT\s*=\s*(\d+)", status)
    assert limit and 1 <= int(limit.group(1)) <= 5


# -- the intake -------------------------------------------------------------

REQUIRED_INTAKE_FIELDS = (
    "contact_name",
    "contact_email",
    "company_name",
    "company_domain",
    "system_type",
    "system_name",
    "endpoint_descriptor",
    "mcp_transport",
    "sandbox_required",
    "industry",
    "visibility",
    "requested_package",
    "data_authorization",
    "notes",
)


def test_the_form_asks_for_every_field_the_api_accepts():
    evaluation = read("evaluation.html")
    names = set(re.findall(r'name="([a-z_]+)"', evaluation))
    missing = set(REQUIRED_INTAKE_FIELDS) - names
    assert not missing, f"evaluation.html is missing {sorted(missing)}"


def test_every_field_has_a_label_and_an_error_slot():
    evaluation = read("evaluation.html")
    ids = set(re.findall(r'<(?:input|select|textarea)[^>]*id="([^"]+)"', evaluation))
    labelled = set(re.findall(r'<label[^>]*for="([^"]+)"', evaluation))
    unlabelled = {i for i in ids if i.startswith("ace-")} - labelled
    assert not unlabelled, f"unlabelled fields: {sorted(unlabelled)}"

    slots = set(re.findall(r'data-field-error="([a-z_]+)"', evaluation))
    for field in REQUIRED_INTAKE_FIELDS:
        assert field in slots, f"no error slot for {field}"


def test_the_endpoint_field_tells_the_visitor_not_to_paste_a_credential():
    evaluation = read("evaluation.html")
    help_text = re.search(
        r'id="help-endpoint">(.*?)</p>', evaluation, re.S
    )
    assert help_text
    assert "do not paste" in help_text.group(1).lower()
    assert "credential" in help_text.group(1).lower()


def html_select_values(html: str, select_id: str) -> list[str]:
    block = re.search(
        r'<select[^>]*id="' + select_id + r'".*?</select>', html, re.S
    )
    assert block, f"no select #{select_id}"
    values = re.findall(r'value="([^"]*)"', block.group(0))
    return [value for value in values if value]


def js_array(source: str, name: str) -> list[str]:
    block = re.search(r"var\s+" + name + r"\s*=\s*\[(.*?)\]", source, re.S)
    assert block, f"ace-order.js has no {name}"
    return re.findall(r"'([^']+)'", block.group(1))


@pytest.mark.parametrize(
    "select_id,js_name",
    [
        ("ace-transport", "MCP_TRANSPORTS"),
        ("ace-industry", "INDUSTRIES"),
        ("ace-visibility", "VISIBILITIES"),
        ("ace-package", "PACKAGES"),
    ],
)
def test_the_dropdowns_offer_exactly_what_the_validator_accepts(select_id, js_name):
    offered = html_select_values(read("evaluation.html"), select_id)
    accepted = js_array(read("ace-order.js"), js_name)
    assert sorted(offered) == sorted(accepted)


def test_the_client_validator_mirrors_the_api_vocabulary():
    """Compare against the backend if the sibling worktree is checked out.

    The two repositories deploy separately, so this cannot be a hard dependency;
    when the backend is present, though, a divergence should be caught here
    rather than by a customer whose industry the API refuses.
    """
    backend = Path("/Users/chris/Desktop/LogionOS/LogionOS-API-ace-orders/engine/ace_orders.py")
    if not backend.is_file():
        pytest.skip("backend worktree is not checked out beside this one")

    source = backend.read_text("utf-8")

    def python_tuple(name: str) -> list[str]:
        block = re.search(
            name + r":\s*Final\[tuple\[str, \.\.\.\]\]\s*=\s*\((.*?)\)", source, re.S
        )
        assert block, f"{name} not found in the backend"
        return re.findall(r'"([^"]+)"', block.group(1))

    order = read("ace-order.js")
    for name in ("SYSTEM_TYPES", "MCP_TRANSPORTS", "INDUSTRIES", "VISIBILITIES"):
        assert sorted(js_array(order, name)) == sorted(python_tuple(name)), name

    limits = dict(
        re.findall(r'"([a-z_]+)":\s*(\d+),', re.search(
            r"FIELD_MAX_LENGTHS:\s*Final\[dict\[str, int\]\]\s*=\s*\{(.*?)\}",
            source,
            re.S,
        ).group(1))
    )
    js_limits = dict(
        re.findall(
            r"([a-z_]+):\s*(\d+)",
            re.search(r"var MAX_LENGTHS = \{(.*?)\};", order, re.S).group(1),
        )
    )
    assert js_limits == limits


def test_a_retry_reuses_one_idempotency_key():
    order = read("ace-order.js")
    assert "'Idempotency-Key': idempotencyKeyFor(intake)" in order
    # Same intake, same key: a retry replays rather than duplicating.
    assert "saved.fingerprint === fingerprint" in order
    # Edited intake, new key: a corrected request is not answered with the old order.
    assert "var key = randomKey();" in order


# -- pages and links --------------------------------------------------------

def test_every_customer_flow_page_exists():
    for page in CUSTOMER_FLOW_PAGES + ("access.html",):
        assert (SITE_ROOT / page).is_file(), page


def test_local_links_resolve_to_a_file():
    broken: list[str] = []
    for path in html_pages():
        body = path.read_text("utf-8")
        for href in re.findall(r'href="([^"]+)"', body):
            if href.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            target = href.split("#")[0].split("?")[0]
            if not target or target == "/":
                continue
            candidates = [SITE_ROOT / target, SITE_ROOT / (target + ".html")]
            if not any(candidate.exists() for candidate in candidates):
                broken.append(f"{relative(path)} -> {href}")
    assert not broken, broken


def test_the_customer_flow_pages_are_not_indexable_and_not_in_the_sitemap():
    sitemap = read("sitemap.xml")
    for page in CUSTOMER_FLOW_PAGES:
        body = read(page)
        assert 'name="robots" content="noindex, nofollow"' in body, page
        assert page not in sitemap, f"{page} should not be advertised"


def test_the_public_pages_are_in_the_sitemap():
    sitemap = read("sitemap.xml")
    for page in PUBLIC_PAGES:
        expected = "https://logionace.com/" if page == "index.html" else f"https://logionace.com/{page}"
        assert expected in sitemap, page


def test_the_status_pages_link_to_the_security_instructions():
    for page in ("request-submitted.html", "order-status.html", "evaluation.html"):
        assert 'href="access.html"' in read(page), page


def test_the_generated_pages_match_their_generator():
    """The rendered HTML is committed, so it can drift from what produced it.

    A hand edit to one of the five customer-flow pages fails here, which is the
    point: the fix is to edit `tools/render_customer_pages.py` and re-run it.
    """
    from tools import render_customer_pages as renderer

    nav, footer = renderer.chrome()
    for name, expected in renderer.build_pages(nav, footer).items():
        assert read(name) == expected, (
            f"{name} differs from tools/render_customer_pages.py; re-run "
            f"`python3 -m tools.render_customer_pages`"
        )


def test_no_page_carries_an_inline_script_or_handler():
    """CSP-compatible by construction: behaviour lives in files, not attributes."""
    for path in html_pages():
        body = path.read_text("utf-8")
        assert "<script>" not in body, f"{relative(path)} has an inline script"
        assert not re.search(r"\son[a-z]+=", body), f"{relative(path)} has an inline handler"


# -- approved artifacts, as bytes ------------------------------------------

def test_the_public_pages_read_numbers_only_through_the_verifier():
    for page in ("index.html", "benchmark.html"):
        body = read(page)
        assert 'src="ace-artifacts.js"' in body, page
    for script in ("ace-home.js", "ace-benchmark.js"):
        body = read(script)
        assert "ARTIFACTS.leaderboard(" in body, script
        # No direct read of the raw JSON: that is the unverified path.
        assert "fetch(" not in body, script
        assert "ace-leaderboard.json" not in body, script
        assert "agent-leaderboard.json" not in body, script


def test_the_homepage_states_no_count_of_its_own():
    body = read("index.html")
    counts = re.findall(
        r'id="(ace-count-[a-z]+)"[^>]*>([^<]*)<', body
    )
    assert len(counts) == 4, counts
    for name, rendered in counts:
        assert rendered.strip() in ("&mdash;", "-", ""), f"{name} is hard-coded"


def test_verification_failure_is_the_only_fallback():
    for script in ("ace-home.js", "ace-benchmark.js"):
        body = read(script)
        assert "failClosed" in body
        assert "UNAVAILABLE_MESSAGE" in body
    artifacts = read("ace-artifacts.js")
    assert "Published reports unavailable." in artifacts
    assert "manifest.state !== APPROVED_STATE" in artifacts
    assert "provenance.commit !== PIN.PROVENANCE_COMMIT" in artifacts


# -- the approved publication anchor ---------------------------------------

def pin_values() -> dict:
    """The two constants the site is anchored to, read from the pin file."""
    body = read("ace-approved-pin.js")
    digest = re.search(r"MANIFEST_SHA256:\s*'([0-9a-f]{64})'", body)
    commit = re.search(r"PROVENANCE_COMMIT:\s*'([0-9a-f]{40})'", body)
    assert digest and commit, "the pin file must declare both constants"
    return {"digest": digest.group(1), "commit": commit.group(1)}


def test_the_pin_lives_alone_in_its_own_file():
    """Updating the anchor should be a one-line diff nobody can miss."""
    body = read("ace-approved-pin.js")
    assert "window.ACE_APPROVED_PIN" in body
    # Nothing else: no API base, no page list, no logic.
    assert "fetch(" not in body
    assert "function" not in body
    declared = set(re.findall(r"^\s*([A-Z0-9_]+):", body, re.M))
    assert declared == {"MANIFEST_SHA256", "PROVENANCE_COMMIT"}, declared


def test_the_pin_matches_the_manifest_on_disk():
    from tools import ace_artifacts as artifacts

    pin = pin_values()
    manifest = json.loads(read("approved-artifacts.json"))
    assert manifest["state"] == "approved"
    assert manifest["provenance"]["commit"] == pin["commit"]
    assert artifacts.manifest_digest(manifest) == pin["digest"]
    # The served bytes are the canonical bytes, because the digest is over them.
    assert (SITE_ROOT / "approved-artifacts.json").read_bytes() == (
        artifacts.canonical_bytes(manifest)
    )


def test_the_provenance_commit_is_declared_once():
    """The pin file is the only place either constant is written down."""
    for path in text_files():
        if path.name in ("ace-approved-pin.js", "ace_artifacts.py"):
            continue
        body = path.read_text("utf-8", errors="replace")
        assert "APPROVED_PROVENANCE_COMMIT" not in body, relative(path)


def test_the_browser_verifies_the_digest_before_it_parses_anything():
    """Order matters: an unpinned manifest is never handed to a parser's rules.

    Structural validation of an arbitrary document tells you the document is
    well-formed, not that it is the approved one. The digest check is what makes
    the rest of the checks meaningful, so it happens first.
    """
    body = read("ace-artifacts.js")
    loader = body[body.index("function loadManifest()"):body.index("function toHex(")]

    # Raw bytes, hashed and compared, then parsed, then the contents judged.
    assert loader.index("arrayBuffer()") < loader.index("PIN.MANIFEST_SHA256")
    assert loader.index("PIN.MANIFEST_SHA256") < loader.index("JSON.parse")
    assert loader.index("JSON.parse") < loader.index("validateManifest(")

    # And the bytes that were hashed have to be the canonical ones, so the pinned
    # digest names one document rather than one formatting of it.
    assert loader.index("canonicalBytesText") < loader.index("validateManifest(")
    assert "canonicalJson" in body


def test_the_anchor_documents_what_it_does_not_defend_against():
    """A pin in the same repository is not a defence against owning the repo."""
    pin = read("ace-approved-pin.js").lower()
    assert "accidental" in pin or "unapproved" in pin
    assert "compromise" in pin or "compromised" in pin


# -- terms and security copy -----------------------------------------------

TERMS_CLAUSES = (
    "prepaid",
    "approved scope",
    "refund",
    "cannot access the system",
    "authorised",
    "credential",
    "signed engagement agreement",
    "legal review",
    "Joanna",
)


@pytest.mark.parametrize("clause", TERMS_CLAUSES)
def test_the_terms_cover_the_payment_flow(clause):
    assert clause.lower() in read("terms.html").lower(), clause


def test_the_terms_claim_no_certification():
    body = read("terms.html").lower()
    for overclaim in ("certified compliant", "guarantees compliance",
                      "legally certified", "guaranteed compliance"):
        assert overclaim not in body


SECURITY_TOPICS = (
    "never ask you to paste",
    "revocable",
    "sandbox",
    "90 days",
    "does not start an evaluation",
    "info@logionace.com",
)


@pytest.mark.parametrize("topic", SECURITY_TOPICS)
def test_the_security_page_explains_the_engagement(topic):
    assert topic.lower() in read("access.html").lower(), topic


def test_the_payment_pages_do_not_claim_fulfilment_from_a_redirect():
    success = read("payment-success.html").lower()
    assert "signed" in success and "webhook" in success or "signed notification" in success
    assert "does not start the evaluation" in success or "payment does not start" in success
    for claim in ("your evaluation has started", "evaluation is now running"):
        assert claim not in success
