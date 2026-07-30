"""The clauses of the cross-repository contract that this site owns.

`contracts/ace-cross-repo-contract.v1.json` is one file, byte for byte
identical here, in the ACE automation repository and in the orders API. It
records what the three sides have agreed about a customer's journey: the
fields the form collects, the enumerations it may submit, the prices it shows,
the states it renders, the API base it talks to and the redirect pages Stripe
sends people back to.

The site is not built, and it has no schema. Its half of the agreement is
whatever the shipped bytes say, so the only honest way to check it is to read
the shipped bytes -- which is what this file does. A value changed on one side
alone fails here rather than in a customer's browser.

The digest is pinned in this file. A contract whose bytes have drifted is not
read at all: three copies that can diverge quietly are not an agreement.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from conftest import SITE_ROOT, read

CONTRACT_PATH = SITE_ROOT / "contracts" / "ace-cross-repo-contract.v1.json"
CONTRACT_SHA256 = "a50225a29993fdb5fe26c5991af92932a53e30eef3ecd37ace39a2b2e2e05874"


@pytest.fixture(scope="module")
def contract() -> dict:
    raw = CONTRACT_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == CONTRACT_SHA256, (
        "the cross-repository contract in this worktree is not the pinned one "
        f"(pinned {CONTRACT_SHA256[:12]}..., found {digest[:12]}...); it must "
        "change in one commit per repository or not at all"
    )
    payload = json.loads(raw.decode("utf-8"))
    canonical = (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    assert canonical == raw, "the contract is not in canonical form"
    return payload


def config_value(name: str) -> str:
    match = re.search(rf"{name}:\s*'([^']*)'", read("ace-config.js"))
    assert match, f"ace-config.js does not define {name}"
    return match.group(1)


# -- transport ---------------------------------------------------------------


def test_the_site_talks_to_the_contracted_api_base(contract):
    assert config_value("API_BASE") == contract["transport"]["api_base"]


def test_the_orders_path_is_the_contracted_one(contract):
    assert config_value("ORDERS_PATH") == contract["transport"]["orders_path"]


def test_no_page_builds_its_own_api_base(contract):
    """One base, in one file. A second one only some pages use is the bug."""
    base = contract["transport"]["api_base"]
    for path in sorted(SITE_ROOT.glob("*.js")) + sorted(SITE_ROOT.glob("*.html")):
        if path.name == "ace-config.js":
            continue
        assert base not in path.read_text(encoding="utf-8"), (
            f"{path.name} hard-codes the API base instead of reading ACE_CONFIG"
        )


def test_the_pages_stripe_returns_to_are_the_contracted_ones(contract):
    transport = contract["transport"]
    config = read("ace-config.js")
    for key, expected in (
        ("paymentSuccess", transport["checkout_success_path"]),
        ("paymentCancelled", transport["checkout_cancel_path"]),
    ):
        match = re.search(rf"{key}:\s*'([^']+)'", config)
        assert match, f"ace-config.js does not name the {key} page"
        assert match.group(1) == expected
        assert (SITE_ROOT / expected).is_file(), f"{expected} is not published"


def test_the_status_token_travels_in_the_contracted_header(contract):
    header = contract["transport"]["status_token_header"]
    assert header in read("ace-session.js") + read("ace-status.js")


# -- what the form may submit -------------------------------------------------


def test_the_intake_form_collects_exactly_the_contracted_fields(contract):
    """Extra fields are refused by the API; missing ones fail the submission."""
    order_js = read("ace-order.js")
    for field in contract["intake"]["fields"]:
        assert field in order_js, f"the intake form never sends {field}"


@pytest.mark.parametrize(
    "field",
    ["system_type", "mcp_transport", "industry", "visibility", "requested_package"],
)
def test_every_option_the_form_offers_is_one_the_api_accepts(field, contract):
    allowed = set(contract["intake"]["enums"][field])
    page = read("evaluation.html")
    offered = {
        match.group(1)
        for match in re.finditer(
            rf'<select[^>]*name="{field}".*?</select>', page, re.S
        )
        for match in re.finditer(r'value="([^"]+)"', match.group(0))
    }
    assert offered, f"evaluation.html offers no options for {field}"
    stray = sorted(offered - allowed)
    assert not stray, f"the form offers {field} values the API rejects: {stray}"


def test_the_form_never_asks_for_something_the_api_will_not_store(contract):
    allowed = set(contract["intake"]["fields"])
    page = read("evaluation.html")
    named = {
        match.group(1)
        for match in re.finditer(r'<(?:input|select|textarea)[^>]*name="([^"]+)"', page)
    }
    stray = sorted(named - allowed)
    assert not stray, f"the intake form collects fields the API does not accept: {stray}"


# -- prices -------------------------------------------------------------------


def test_the_displayed_prices_are_the_contracted_ones(contract):
    config = read("ace-config.js")
    for option, price in contract["packages"]["website_display_prices"].items():
        match = re.search(rf"id:\s*'{option}'.*?price:\s*'([^']+)'", config, re.S)
        assert match, f"ace-config.js does not list the {option} package"
        assert match.group(1) == price


def test_every_option_the_site_sells_maps_to_a_package_the_api_quotes(contract):
    mapping = contract["packages"]["website_option_to_package"]
    quotable = set(contract["packages"]["quotable"])
    config = read("ace-config.js")
    offered = set(re.findall(r"id:\s*'([a-z_]+)'", config))
    assert offered == set(mapping), (
        f"the site offers {sorted(offered)}; the contract maps {sorted(mapping)}"
    )
    for option, package in mapping.items():
        assert package in quotable, f"{option} maps to a package the API will not quote"


def test_no_page_states_a_price_the_price_list_does_not(contract):
    """A number in prose is a promise nobody regenerates."""
    known = set(contract["packages"]["website_display_prices"].values())
    known.update({"$40,000", "$50,000", "$60,000"})  # range text around the floors
    for path in sorted(SITE_ROOT.glob("*.html")):
        for amount in re.findall(r"\$\d[\d,]{3,}", path.read_text(encoding="utf-8")):
            assert amount in known, f"{path.name} states an unlisted price {amount}"


# -- what a customer is shown about their order -------------------------------


def test_the_status_page_renders_only_contracted_fields(contract):
    projection = set(contract["customer_status_projection"]["fields"])
    referenced = set(re.findall(r"order\.([a-z_]+)", read("ace-status.js")))
    stray = sorted(referenced - projection)
    assert not stray, f"the status page reads fields the API does not return: {stray}"


def code_of(path: Path) -> str:
    """The file with its comments removed.

    The site's comments discuss the fields the site deliberately does not
    read, which is the point of them. Searching the prose for those names
    would turn an explanation into a failure.
    """
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"(?m)^\s*//.*$", " ", text)
    return re.sub(r"<!--.*?-->", " ", text, flags=re.S)


#: Where a customer's own order is rendered. `endpoint_descriptor` is an
#: intake field the form legitimately submits, so the check is that the status
#: surface never reads one of these back -- not that the strings are absent
#: from the site.
STATUS_SURFACE = ("ace-status.js", "ace-session.js", "order-status.html")


def test_the_status_surface_never_reads_a_field_the_api_refuses_to_expose(contract):
    for hidden in contract["customer_status_projection"]["never_exposed"]:
        reference = re.compile(rf"""(?:\.{hidden}\b|['"]{hidden}['"])""")
        for name in STATUS_SURFACE:
            assert not reference.search(code_of(SITE_ROOT / name)), (
                f"{name} reads {hidden}, which no customer response carries"
            )


def test_the_payment_link_is_only_offered_in_the_contracted_state(contract):
    state = contract["customer_status_projection"]["payment_url_only_while"]
    status_js = read("ace-status.js")
    assert "payment_url" in status_js
    assert state in status_js, (
        "the status page shows a payment link without checking the order is "
        f"still {state}"
    )


def test_every_order_state_the_site_renders_is_one_the_api_can_produce(contract):
    states = set(contract["order_states"]["flow"]) | set(
        contract["order_states"]["off_flow"]
    )
    status_js = read("ace-status.js")
    rendered = set(re.findall(r"'([a-z_]+)':\s*\{", status_js))
    unknown = sorted(rendered - states - {"default"})
    assert not unknown, f"the status page renders states the API never sets: {unknown}"


# -- the approved public snapshot ---------------------------------------------


def test_the_approved_manifest_is_the_contracted_file(contract):
    artifacts = contract["approved_artifacts"]
    assert config_value("APPROVED_MANIFEST_PATH") == artifacts["manifest_path"]
    manifest = SITE_ROOT / artifacts["manifest_path"]
    assert (
        hashlib.sha256(manifest.read_bytes()).hexdigest() == artifacts["manifest_sha256"]
    ), (
        "the approved snapshot changed without the contract changing; "
        "republishing is a reviewed commit in all three repositories"
    )


def test_the_pin_names_the_contracted_provenance_commit(contract):
    artifacts = contract["approved_artifacts"]
    assert artifacts["provenance_commit"] in read(artifacts["pin_file"])


def test_every_entry_in_the_snapshot_has_the_contracted_shape(contract):
    artifacts = contract["approved_artifacts"]
    manifest = json.loads(
        (SITE_ROOT / artifacts["manifest_path"]).read_text(encoding="utf-8")
    )
    entries = manifest["artifacts"] if isinstance(manifest, dict) else manifest
    assert entries, "the approved snapshot is empty"
    for entry in entries:
        assert set(entry) >= set(artifacts["artifact_entry_fields"])
        assert entry["role"] in artifacts["roles"]
        assert re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
