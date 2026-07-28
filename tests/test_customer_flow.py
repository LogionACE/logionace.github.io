"""
The customer flow, in a real browser, with no network.

Chrome loads the actual files from this worktree; the only API the pages know
about is answered by route handlers here. That combination is what makes these
tests worth having: the form is the shipped form, the scripts are the shipped
scripts, and the responses are ones a real API could return.

The path under test is the one a customer walks: submit a scope request, land on
a confirmation page holding a status link in the fragment, open the status page,
see a payment button appear only once the server has issued a payment URL, return
from the payment provider to a success page that refuses to claim the payment is
confirmed until the server says so.

Every test also asserts, implicitly, that nothing left the machine:
`harness.external_attempts` is filled by the conftest guard and checked at the end
of the flow tests.
"""
from __future__ import annotations

import json
import re

import pytest

from conftest import SAMPLE_ORDER_ID, SAMPLE_TOKEN

pytestmark = pytest.mark.browser


# -- fixtures for the shapes the API returns --------------------------------

def order_response(**overrides) -> dict:
    """The customer-safe projection, as `GET /v1/ace/orders/{id}` returns it."""
    payload = {
        "order_id": SAMPLE_ORDER_ID,
        "status": "submitted",
        "created_at": "2026-07-20T09:15:00+00:00",
        "updated_at": "2026-07-21T11:02:00+00:00",
        "requested_package": "public",
        "quoted_package": "",
        "amount_cents": 0,
        "currency": "",
        "visibility": "public",
        "sandbox_required": True,
        "access_method": "",
        "sandbox_policy_summary": "",
        "delivery_assumptions": "",
        "payment_url": "",
        "paid_at": "",
        "refunded_at": "",
        "cancelled_at": "",
        "delivered_at": "",
        "history": [{"status": "submitted", "at": "2026-07-20T09:15:00+00:00"}],
    }
    payload.update(overrides)
    return payload


def error_response(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


VALID_INTAKE = {
    "contact_name": "Dana Ruiz",
    "contact_email": "dana.ruiz@example.com",
    "company_name": "Example Financial",
    "company_domain": "example.com",
    "system_type": "model_endpoint",
    "system_name": "Advisor Assistant",
    "endpoint_descriptor": "Staging REST endpoint behind our VPN, OpenAI-compatible.",
    "mcp_transport": "none",
    "industry": "financial_services",
    "visibility": "private",
    "requested_package": "private",
    "notes": "Launch review in September.",
}


def fill_form(harness, **overrides) -> None:
    values = dict(VALID_INTAKE)
    values.update(overrides)
    page = harness.page
    page.fill("#ace-contact-name", values["contact_name"])
    page.fill("#ace-contact-email", values["contact_email"])
    page.fill("#ace-company-name", values["company_name"])
    page.fill("#ace-company-domain", values["company_domain"])
    page.select_option("#ace-system-type", values["system_type"])
    page.fill("#ace-system-name", values["system_name"])
    page.fill("#ace-endpoint", values["endpoint_descriptor"])
    page.select_option("#ace-transport", values["mcp_transport"])
    page.select_option("#ace-industry", values["industry"])
    page.select_option("#ace-visibility", values["visibility"])
    page.select_option("#ace-package", values["requested_package"])
    page.fill("#ace-notes", values["notes"])
    if values.get("sandbox_required"):
        page.check("#ace-sandbox")
    if values.get("data_authorization", True):
        page.check("#ace-authorization")


def accepted(order_id: str = SAMPLE_ORDER_ID, token: str = SAMPLE_TOKEN) -> dict:
    return {"order_id": order_id, "status": "submitted", "status_token": token}


# -- submitting -------------------------------------------------------------

def test_a_valid_request_is_submitted_and_produces_a_status_link(site):
    site.api(site.orders_url(), status=201, payload=accepted())
    site.open("evaluation.html")
    fill_form(site)
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_url("**/request-submitted.html#*")

    posted = site.calls_to("/v1/ace/orders")
    assert len(posted) == 1
    request = posted[0]
    assert request["method"] == "POST"
    body = json.loads(request["body"])
    assert body["contact_email"] == "dana.ruiz@example.com"
    assert body["requested_package"] == "private"
    assert body["data_authorization"] is True
    assert body["sandbox_required"] is False
    assert set(body) == {
        "contact_name", "contact_email", "company_name", "company_domain",
        "system_type", "system_name", "endpoint_descriptor", "mcp_transport",
        "sandbox_required", "industry", "visibility", "requested_package",
        "data_authorization", "notes",
    }
    assert request["headers"]["idempotency-key"].startswith("web-")

    fragment = site.page.evaluate("() => window.location.hash")
    assert f"order={SAMPLE_ORDER_ID}" in fragment
    assert f"token={SAMPLE_TOKEN}" in fragment
    assert site.text("#ace-submitted-order-id") == SAMPLE_ORDER_ID

    # The token is in the fragment and in session storage. Nowhere else.
    assert site.page.evaluate("() => window.location.search") == ""
    assert site.local_storage() == {}
    stored = json.loads(site.session_storage()["ace_status_link"])
    assert stored == {"order_id": SAMPLE_ORDER_ID, "token": SAMPLE_TOKEN}
    assert site.external_attempts == []


def test_nothing_the_visitor_typed_is_left_in_the_browser(site):
    site.api(site.orders_url(), status=201, payload=accepted())
    site.open("evaluation.html")
    fill_form(site)
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_url("**/request-submitted.html#*")

    everything = json.dumps(
        {"local": site.local_storage(), "session": site.session_storage()}
    )
    for private in ("dana.ruiz@example.com", "Dana Ruiz", "Example Financial",
                    "Advisor Assistant", "behind our VPN"):
        assert private not in everything, f"{private} survived the submission"


def test_a_retry_after_a_failure_reuses_one_idempotency_key(site):
    attempts: list[str] = []

    def handler(route) -> None:
        attempts.append(route.request.headers["idempotency-key"])
        if len(attempts) == 1:
            route.fulfill(
                status=503,
                content_type="application/json",
                body=json.dumps(error_response("service_unavailable", "Try again shortly.")),
            )
            return
        route.fulfill(
            status=201, content_type="application/json", body=json.dumps(accepted())
        )

    site.api_handler(site.orders_url(), handler)
    site.open("evaluation.html")
    fill_form(site)
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_selector("#ace-form-error:not([hidden])")
    assert "not accepting requests" in site.text("#ace-form-error")

    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_url("**/request-submitted.html#*")
    assert len(attempts) == 2
    assert attempts[0] == attempts[1], "a retry must not create a second order"


def test_editing_the_request_earns_a_new_idempotency_key(site):
    keys: list[str] = []

    def handler(route) -> None:
        keys.append(route.request.headers["idempotency-key"])
        route.fulfill(
            status=500,
            content_type="application/json",
            body=json.dumps(error_response("internal_error", "Something broke.")),
        )

    site.api_handler(site.orders_url(), handler)
    site.open("evaluation.html")
    fill_form(site)
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_selector("#ace-form-error:not([hidden])")

    site.page.fill("#ace-notes", "Launch review moved to October.")
    site.page.click("#ace-order-form button[type=submit]")
    site.wait_until(lambda: len(keys) == 2, "the edited request to be submitted")
    assert len(keys) == 2
    assert keys[0] != keys[1], "a corrected request must not replay the old one"


# -- validation, before any request ----------------------------------------

def test_an_empty_form_is_refused_without_calling_the_api(site):
    site.api(site.orders_url(), status=201, payload=accepted())
    site.open("evaluation.html")
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_selector("#ace-form-error:not([hidden])")

    assert site.calls_to("/v1/ace/orders") == []
    assert "correct" in site.text("#ace-form-error").lower()
    # Focus is moved to the summary, not left on the button.
    assert site.page.evaluate("() => document.activeElement.id") == "ace-form-error"
    assert site.page.get_attribute("#ace-contact-name", "aria-invalid") == "true"
    assert site.visible("[data-field-error='contact_name']")


def test_an_endpoint_that_looks_like_a_credential_is_refused_locally(site):
    site.api(site.orders_url(), status=201, payload=accepted())
    site.open("evaluation.html")
    fill_form(
        site,
        endpoint_descriptor="https://api.example.com with key sk_live_9f8a7b6c5d4e3f2a1b0c",
    )
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_selector("[data-field-error='endpoint_descriptor']:not([hidden])")

    assert site.calls_to("/v1/ace/orders") == [], "a key must not be transmitted"
    message = site.text("[data-field-error='endpoint_descriptor']")
    assert "key or token" in message
    assert "sk_live" not in message


def test_a_bad_email_is_named_before_a_round_trip(site):
    site.api(site.orders_url(), status=201, payload=accepted())
    site.open("evaluation.html")
    fill_form(site, contact_email="dana.ruiz@example")
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_selector("[data-field-error='contact_email']:not([hidden])")
    assert site.calls_to("/v1/ace/orders") == []


def test_the_authorisation_box_is_required(site):
    site.api(site.orders_url(), status=201, payload=accepted())
    site.open("evaluation.html")
    fill_form(site, data_authorization=False)
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_selector("[data-field-error='data_authorization']:not([hidden])")
    assert site.calls_to("/v1/ace/orders") == []


# -- what the API can say back ---------------------------------------------

def test_a_field_the_server_rejects_is_shown_against_that_field(site):
    site.api(
        site.orders_url(),
        status=422,
        payload=error_response(
            "validation_error",
            "That domain does not look like a company domain.",
            [{"field": "company_domain"}],
        ),
    )
    site.open("evaluation.html")
    fill_form(site)
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_selector("[data-field-error='company_domain']:not([hidden])")
    assert "company domain" in site.text("[data-field-error='company_domain']")
    assert site.page.evaluate("() => document.activeElement.id") == "ace-form-error"


def test_a_rate_limit_asks_the_visitor_to_wait(site):
    site.api(
        site.orders_url(),
        status=429,
        payload=error_response("rate_limited", "Too many requests."),
    )
    site.open("evaluation.html")
    fill_form(site)
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_selector("#ace-form-error:not([hidden])")
    summary = site.text("#ace-form-error")
    assert "wait a minute" in summary
    assert "429" not in summary


def test_an_unreachable_service_says_a_retry_is_safe(site):
    def handler(route) -> None:
        route.abort("connectionfailed")

    site.api_handler(site.orders_url(), handler)
    site.open("evaluation.html")
    fill_form(site)
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_selector("#ace-form-error:not([hidden])")
    summary = site.text("#ace-form-error")
    assert "could not reach" in summary
    assert "will not create two requests" in summary


def test_an_error_never_prints_an_internal_detail(site):
    site.api(
        site.orders_url(),
        status=500,
        payload={
            "error": {
                "code": "internal_error",
                "message": "Something went wrong.",
                "trace": "File /srv/logionos/engine/ace_orders.py, line 812",
            }
        },
    )
    site.open("evaluation.html")
    fill_form(site)
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_selector("#ace-form-error:not([hidden])")
    body = site.page.text_content("body")
    assert "ace_orders.py" not in body
    assert "/srv/" not in body


# -- the status page --------------------------------------------------------

def test_the_status_page_needs_the_link_and_says_so(site):
    site.open("order-status.html")
    site.page.wait_for_selector("#ace-status-error:not([hidden])")
    assert site.calls_to("/v1/ace/orders") == []
    assert "# symbol" in site.text("#ace-status-error-text")


def test_a_submitted_order_shows_no_payment_button(site):
    site.api(site.orders_url(f"/{SAMPLE_ORDER_ID}"), payload=order_response())
    site.open("order-status.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-panel:not([hidden])")

    assert site.text("#ace-status-label") == "Request received"
    assert "Nothing is payable yet" in site.text("#ace-status-detail")
    assert not site.visible("#ace-pay-button")
    call = site.calls_to("/v1/ace/orders")[0]
    assert call["headers"]["x-ace-status-token"] == SAMPLE_TOKEN
    assert SAMPLE_TOKEN not in call["url"]


def test_an_approved_quote_without_a_payment_url_shows_no_button(site):
    site.api(
        site.orders_url(f"/{SAMPLE_ORDER_ID}"),
        payload=order_response(
            status="approved",
            quoted_package="private",
            amount_cents=4000000,
            currency="USD",
            access_method="Scoped API key for the staging tenant.",
            sandbox_policy_summary="Sandbox tenant, no production data.",
            delivery_assumptions="Report within three weeks of access.",
        ),
    )
    site.open("order-status.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-panel:not([hidden])")

    assert site.text("#ace-status-label") == "Quote approved"
    assert site.text("#ace-status-amount") == "$40,000"
    assert not site.visible("#ace-pay-button")
    assert "Scoped API key" in site.text("#ace-scope-access")


def test_a_payment_button_appears_only_when_the_server_issues_a_url(site):
    site.api(
        site.orders_url(f"/{SAMPLE_ORDER_ID}"),
        payload=order_response(
            status="payment_pending",
            quoted_package="private",
            amount_cents=4000000,
            currency="USD",
            payment_url="https://checkout.example.test/c/pay/cs_test_123",
        ),
    )
    site.open("order-status.html", site.status_fragment())
    site.page.wait_for_selector("#ace-pay-button:not([hidden])")

    button = site.page.query_selector("#ace-pay-button")
    assert button.get_attribute("href") == "https://checkout.example.test/c/pay/cs_test_123"
    assert site.text("#ace-pay-amount") == "$40,000"
    assert "does not start the evaluation" in site.page.text_content("#ace-pay-block")


@pytest.mark.parametrize(
    "hostile_url",
    [
        "javascript:alert(1)",
        "http://checkout.example.test/pay",
        "/pay",
        "data:text/html,<h1>pay</h1>",
    ],
)
def test_a_payment_url_that_is_not_absolute_https_is_refused(site, hostile_url):
    site.api(
        site.orders_url(f"/{SAMPLE_ORDER_ID}"),
        payload=order_response(
            status="payment_pending",
            quoted_package="private",
            amount_cents=4000000,
            currency="USD",
            payment_url=hostile_url,
        ),
    )
    site.open("order-status.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-panel:not([hidden])")
    assert not site.visible("#ace-pay-button")
    assert site.page.query_selector("#ace-pay-button").get_attribute("href") is None


def test_leaving_for_the_payment_provider_keeps_the_link_in_the_tab(site):
    site.api(
        site.orders_url(f"/{SAMPLE_ORDER_ID}"),
        payload=order_response(
            status="payment_pending",
            quoted_package="private",
            amount_cents=4000000,
            currency="USD",
            payment_url="https://checkout.example.test/c/pay/cs_test_123",
        ),
    )
    site.open("order-status.html", site.status_fragment())
    site.page.wait_for_selector("#ace-pay-button:not([hidden])")

    # The click is real. Its navigation is cancelled by a listener added after
    # the page's own, so the page's handler has already run and this tab is still
    # inspectable -- which is the state a visitor returns from Stripe into.
    site.page.evaluate(
        "() => document.getElementById('ace-pay-button')"
        ".addEventListener('click', event => event.preventDefault())"
    )
    site.page.click("#ace-pay-button")
    site.page.wait_for_timeout(200)
    stored = json.loads(site.session_storage()["ace_status_link"])
    assert stored["token"] == SAMPLE_TOKEN
    assert site.page.url.endswith(site.status_fragment()), "still on the status page"


def test_the_status_page_never_shows_an_internal_run_detail(site):
    """A response carrying operator fields must not put them on the page.

    The API does not send these -- the projection excludes them and the backend
    suite proves it -- so this asserts the second half of the boundary: even if
    one appeared, this page renders named fields only.
    """
    site.api(
        site.orders_url(f"/{SAMPLE_ORDER_ID}"),
        payload=order_response(
            status="running",
            ace_manifest_hash="c" * 64,
            estimated_cost_usd=812.44,
            invalid_rate_ppm=13500,
            draft_state="draft_building",
            human_review_state="review_requested",
            operator="ops@logionos.internal",
            judge_calls=2048,
            current_case=141,
            total_cases=272,
        ),
    )
    site.open("order-status.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-panel:not([hidden])")

    body = site.page.text_content("body")
    for internal in ("c" * 64, "812.44", "13500", "draft_building",
                     "review_requested", "ops@logionos.internal", "2048", "272"):
        assert internal not in body, f"{internal} reached the customer's page"
    assert site.text("#ace-status-label") == "Evaluation under way"


def test_a_wrong_or_stale_link_is_not_told_which_it_is(site):
    site.api(
        site.orders_url(f"/{SAMPLE_ORDER_ID}"),
        status=404,
        payload=error_response("order_not_found", "No such order."),
    )
    site.open("order-status.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-error:not([hidden])")
    message = site.text("#ace-status-error-text")
    assert "cannot find an evaluation request for this link" in message
    for leak in ("token", "digest", "404"):
        assert leak not in message.lower()


def test_a_rate_limited_status_check_asks_for_a_pause(site):
    site.api(
        site.orders_url(f"/{SAMPLE_ORDER_ID}"),
        status=429,
        payload=error_response("rate_limited", "Slow down."),
    )
    site.open("order-status.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-error:not([hidden])")
    assert "wait a minute" in site.text("#ace-status-error-text")


def test_an_explicit_refresh_is_the_only_thing_that_re_checks_quickly(site):
    site.api(site.orders_url(f"/{SAMPLE_ORDER_ID}"), payload=order_response())
    site.open("order-status.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-panel:not([hidden])")
    assert len(site.calls_to("/v1/ace/orders")) == 1

    site.page.wait_for_timeout(1200)
    assert len(site.calls_to("/v1/ace/orders")) == 1, "a settled order must not poll"

    site.page.click("#ace-status-refresh")
    site.page.wait_for_function(
        "() => document.getElementById('ace-status-refresh').textContent === "
        "'Check for updates'"
    )
    assert len(site.calls_to("/v1/ace/orders")) == 2


def test_the_history_is_rendered_as_text_not_markup(site):
    site.api(
        site.orders_url(f"/{SAMPLE_ORDER_ID}"),
        payload=order_response(
            status="paid",
            paid_at="2026-07-22T08:00:00+00:00",
            history=[
                {"status": "submitted", "at": "2026-07-20T09:15:00+00:00"},
                {"status": "<img src=x onerror=alert(1)>", "at": "2026-07-21T09:00:00+00:00"},
                {"status": "paid", "at": "2026-07-22T08:00:00+00:00"},
            ],
        ),
    )
    site.open("order-status.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-history-block:not([hidden])")
    assert site.page.query_selector("#ace-status-history img") is None
    assert "<img" in site.page.text_content("#ace-status-history")
    assert site.page.eval_on_selector(
        "#ace-status-history", "el => el.querySelectorAll('li').length"
    ) == 3


# -- returning from payment ------------------------------------------------

def test_the_success_page_does_not_claim_payment_is_confirmed(site):
    site.api(
        site.orders_url(f"/{SAMPLE_ORDER_ID}"),
        payload=order_response(
            status="payment_pending",
            quoted_package="private",
            amount_cents=4000000,
            currency="USD",
        ),
    )
    site.open("payment-success.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-panel:not([hidden])")

    copy = site.page.text_content("main")
    assert "signed" in copy
    assert "Payment does not start the evaluation" in copy
    assert site.text("#ace-status-label") == "Awaiting payment"
    assert "confirmed" not in site.text("#ace-status-label").lower()


def test_the_success_page_reflects_confirmation_once_the_webhook_lands(site):
    calls: list[int] = []

    def handler(route) -> None:
        calls.append(1)
        status = "payment_pending" if len(calls) == 1 else "paid"
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(
                order_response(
                    status=status,
                    quoted_package="private",
                    amount_cents=4000000,
                    currency="USD",
                    paid_at="" if status == "payment_pending" else "2026-07-22T08:00:00+00:00",
                )
            ),
        )

    site.api_handler(site.orders_url(f"/{SAMPLE_ORDER_ID}"), handler)
    site.open("payment-success.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-panel:not([hidden])")
    assert site.text("#ace-status-label") == "Awaiting payment"

    site.page.click("#ace-status-refresh")
    site.page.wait_for_function(
        "() => document.getElementById('ace-status-label').textContent === "
        "'Payment confirmed'"
    )
    assert "Payment confirmed:" in site.text("#ace-stamp-paid")


def test_the_cancelled_page_explains_that_nothing_was_charged(site):
    site.api(
        site.orders_url(f"/{SAMPLE_ORDER_ID}"),
        payload=order_response(
            status="payment_pending",
            quoted_package="private",
            amount_cents=4000000,
            currency="USD",
            payment_url="https://checkout.example.test/c/pay/cs_test_123",
        ),
    )
    site.open("payment-cancelled.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-panel:not([hidden])")
    copy = site.page.text_content("main").lower()
    assert "no charge was made" in copy
    assert site.visible("#ace-pay-button"), "the approved quote is still payable"


def test_the_session_copy_of_the_link_survives_a_fragmentless_return(site):
    """Coming back from Stripe means arriving without a fragment."""
    site.api(site.orders_url(f"/{SAMPLE_ORDER_ID}"), payload=order_response())
    site.open("order-status.html", site.status_fragment())
    site.page.wait_for_selector("#ace-status-panel:not([hidden])")

    site.open("payment-success.html")  # no fragment, same tab
    site.page.wait_for_selector("#ace-status-panel:not([hidden])")
    assert site.text("#ace-status-order-id") == SAMPLE_ORDER_ID


# -- the confirmation page --------------------------------------------------

def test_the_confirmation_page_makes_no_api_call(site):
    site.open("request-submitted.html", site.status_fragment())
    site.page.wait_for_selector("#ace-submitted-order-id")
    assert site.calls_to("/v1/ace/orders") == []
    assert site.text("#ace-submitted-order-id") == SAMPLE_ORDER_ID
    href = site.page.get_attribute("#ace-submitted-status-link", "href")
    assert href.startswith("order-status.html#order=")
    assert SAMPLE_TOKEN in href


def test_the_confirmation_page_without_a_link_says_what_to_do(site):
    site.open("request-submitted.html")
    site.page.wait_for_selector("#ace-submitted-missing:not([hidden])")
    assert not site.visible("#ace-submitted-copy")
    assert "resend" in site.text("#ace-submitted-missing")


@pytest.mark.parametrize(
    "fragment",
    [
        "order=aceord_4f1c9b2ad7e35081",                       # no token
        "token=" + SAMPLE_TOKEN,                                # no order
        "order=not-an-order&token=" + SAMPLE_TOKEN,             # wrong id shape
        "order=" + SAMPLE_ORDER_ID + "&token=short",            # wrong token shape
        "order=" + SAMPLE_ORDER_ID + "&token=" + SAMPLE_TOKEN + "%20<script>",
    ],
)
def test_a_malformed_fragment_is_treated_as_no_link_at_all(site, fragment):
    site.api(site.orders_url(f"/{SAMPLE_ORDER_ID}"), payload=order_response())
    site.open("order-status.html", fragment)
    site.page.wait_for_selector("#ace-status-error:not([hidden])")
    assert site.calls_to("/v1/ace/orders") == []
    assert site.session_storage() == {}


def test_the_whole_flow_touches_nothing_outside_the_machine(site):
    site.api(site.orders_url(), status=201, payload=accepted())
    site.api(
        site.orders_url(f"/{SAMPLE_ORDER_ID}"),
        payload=order_response(status="approved", quoted_package="private",
                               amount_cents=4000000, currency="USD"),
    )
    site.open("evaluation.html")
    fill_form(site)
    site.page.click("#ace-order-form button[type=submit]")
    site.page.wait_for_url("**/request-submitted.html#*")
    site.page.click("#ace-submitted-status-link")
    site.page.wait_for_selector("#ace-status-panel:not([hidden])")

    assert site.external_attempts == [], site.external_attempts
    assert site.page_errors == [], site.page_errors
