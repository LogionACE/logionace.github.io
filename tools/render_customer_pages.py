"""
Generate the customer-flow pages from one source of chrome.

This site has no build step and no templating: every page carries its own copy
of the navigation and the footer. Five new pages sharing a status panel is five
chances for those copies to drift, so the chrome and the panel are written once
here and the pages are rendered from it.

The rendered HTML is the artifact -- it is committed and served as-is. Re-run
this after editing the chrome or the panel:

    python3 -m tools.render_customer_pages

Nav and footer are lifted from `evaluation.html` rather than restated, so the
generated pages cannot disagree with the hand-written ones about what the site's
navigation is.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_PAGE = ROOT / "evaluation.html"

STYLESHEET = 'style.css?v=20260616-scrollfix2'


def _extract(pattern: str, text: str, what: str) -> str:
    match = re.search(pattern, text, re.S)
    if not match:
        raise SystemExit(f"could not find the {what} in {SOURCE_PAGE.name}")
    return match.group(0)


def chrome() -> tuple[str, str]:
    source = SOURCE_PAGE.read_text("utf-8")
    nav = _extract(r'<nav class="site-nav">.*?</nav>', source, "navigation")
    footer = _extract(r'<footer class="site-footer">.*?</footer>', source, "footer")
    return nav, footer


STATUS_PANEL = """      <div id="ace-status-root" class="status-root">
        <p id="ace-status-live" class="form-live" role="status" aria-live="polite"></p>

        <div id="ace-status-error" class="form-error-summary" role="alert" hidden>
          <p id="ace-status-error-text"></p>
          <p class="field-help">Need this link resent? Email
            <a href="mailto:info@logionace.com">info@logionace.com</a> with your
            organisation name and we will find the request.</p>
        </div>

        <div id="ace-status-panel" class="status-panel" hidden>
          <p class="eyebrow">Evaluation request</p>
          <p class="status-order-id"><code id="ace-status-order-id"></code></p>
          <h2 id="ace-status-label"></h2>
          <p id="ace-status-detail" class="status-detail"></p>

          <dl class="status-facts">
            <div><dt>Requested</dt><dd id="ace-status-created"></dd></div>
            <div><dt>Last update</dt><dd id="ace-status-updated"></dd></div>
            <div><dt>Evaluation</dt><dd id="ace-status-package"></dd></div>
            <div id="ace-status-amount-row" hidden>
              <dt>Approved amount</dt><dd id="ace-status-amount"></dd>
            </div>
            <div><dt>Results</dt><dd id="ace-status-visibility"></dd></div>
            <div><dt>Environment</dt><dd id="ace-status-sandbox"></dd></div>
          </dl>

          <div id="ace-scope-block" class="status-scope" hidden>
            <h3>Approved scope</h3>
            <div id="ace-scope-access-row" hidden>
              <h4>How we will access the system</h4>
              <p id="ace-scope-access"></p>
            </div>
            <div id="ace-scope-sandbox-policy-row" hidden>
              <h4>Sandbox and data policy</h4>
              <p id="ace-scope-sandbox-policy"></p>
            </div>
            <div id="ace-scope-delivery-row" hidden>
              <h4>Delivery assumptions</h4>
              <p id="ace-scope-delivery"></p>
            </div>
          </div>

          <div id="ace-pay-block" class="status-pay" hidden>
            <h3>Approved quote ready for payment</h3>
            <p>The amount below is the approved quote for the scope above:
              <strong id="ace-pay-amount"></strong>. Payment is handled by Stripe;
              we never see or store your card details.</p>
            <a id="ace-pay-button" class="btn primary" rel="noopener" hidden>Pay securely with Stripe</a>
            <p class="field-help">Paying does not start the evaluation. Confirmation
              reaches us through a signed notification from Stripe, which can take a
              moment to arrive; this page will show payment as confirmed once it does.
              We then arrange secure access to the system being evaluated.</p>
          </div>

          <div id="ace-stamps-block" class="status-stamps" hidden>
            <p id="ace-stamp-paid" hidden></p>
            <p id="ace-stamp-delivered" hidden></p>
            <p id="ace-stamp-cancelled" hidden></p>
            <p id="ace-stamp-refunded" hidden></p>
          </div>

          <div id="ace-status-history-block" hidden>
            <h3>History</h3>
            <ol id="ace-status-history" class="status-history"></ol>
          </div>

          <div class="status-actions">
            <button id="ace-status-refresh" type="button" class="btn outline">Check for updates</button>
            <button id="ace-status-copy" type="button" class="btn ghost">Copy status link</button>
          </div>
          <p id="ace-status-autorefresh-note" class="field-help" hidden>
            Automatic checks have stopped so this page is not left polling. Use
            &ldquo;Check for updates&rdquo; whenever you want the latest state.
          </p>
          <label class="status-link-fallback" hidden>
            <span>Your status link</span>
            <input id="ace-status-link-fallback" type="text" readonly hidden>
          </label>
        </div>
      </div>
"""

SECURITY_REMINDER = """      <div class="callout">
        <h3>Never send us a credential by email or web form</h3>
        <p>API keys, tokens, passwords and private keys are exchanged through a secure
          handoff after the scope is approved and paid for. If anything asks you to
          paste a key into this website, it is not us. See
          <a href="access.html">access and security</a>.</p>
      </div>
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - LogionACE</title>
  <meta name="description" content="{description}">
  <meta name="robots" content="{robots}">
  <link rel="icon" href="favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{stylesheet}">
</head>
<body>
{nav}
<main>
  <section class="page-hero narrow">
    <p class="eyebrow">{eyebrow}</p>
    <h1>{heading}</h1>
    <p>{intro}</p>
  </section>
  <section class="section compact">
    <div class="narrow-body">
{body}    </div>
  </section>
</main>
{footer}
{scripts}
</body>
</html>
"""


def scripts(*names: str) -> str:
    return "\n".join(f'<script src="{name}"></script>' for name in names)


def build_pages(nav: str, footer: str) -> dict[str, str]:
    """The five customer-flow pages. Order matters only for readability."""
    common = ("ace-config.js", "ace-session.js")
    status_scripts = scripts(*common, "ace-status.js", "ace-nav.js")

    pages: dict[str, dict] = {}

    pages["request-submitted.html"] = dict(
        title="Request received",
        description=(
            "Your LogionACE evaluation request has been received. Keep your status "
            "link to follow it."
        ),
        robots="noindex, nofollow",
        eyebrow="Request received",
        heading="Thank you &mdash; we have your request.",
        intro=(
            "Nothing is payable yet. We review the scope and reply with a fixed quote; "
            "payment happens only after you approve it."
        ),
        body="""      <div class="callout accent">
        <h3>Your request reference</h3>
        <p class="status-order-id"><code id="ace-submitted-order-id">&mdash;</code></p>
        <p>Save the link below. It is the only way to check this request, so treat it
          like a password: anyone holding it can see this order's status.</p>
        <div class="status-actions">
          <a class="btn primary" id="ace-submitted-status-link" data-ace-status-link href="order-status.html">Open status page</a>
          <button class="btn outline" type="button" id="ace-submitted-copy">Copy status link</button>
        </div>
        <p id="ace-submitted-live" class="form-live" role="status" aria-live="polite"></p>
        <label class="status-link-fallback" hidden>
          <span>Your status link</span>
          <input id="ace-submitted-link-fallback" type="text" readonly hidden>
        </label>
        <p id="ace-submitted-missing" class="form-error-summary" role="alert" hidden>
          This page did not receive a status link. If you have just submitted a request,
          check your email, or contact
          <a href="mailto:info@logionace.com">info@logionace.com</a> and we will resend it.
        </p>
      </div>

      <h2>What happens next</h2>
      <ol class="steps-list">
        <li><strong>We read it.</strong> Usually within two business days.</li>
        <li><strong>We scope it and quote it.</strong> You get the access we would need,
          the sandbox and data policy, delivery assumptions, and a fixed price.</li>
        <li><strong>You approve, then pay.</strong> A payment link appears on your status
          page once the quote is approved. Until then there is nothing to pay.</li>
        <li><strong>We arrange access.</strong> Credentials are exchanged securely after
          payment is confirmed. The evaluation does not start automatically.</li>
      </ol>

"""
        + SECURITY_REMINDER,
        scripts=scripts(*common, "ace-submitted.js", "ace-nav.js"),
    )

    pages["order-status.html"] = dict(
        title="Evaluation request status",
        description=(
            "Check the status of a LogionACE evaluation request using the status link "
            "issued when it was submitted."
        ),
        robots="noindex, nofollow",
        eyebrow="Request status",
        heading="Your evaluation request.",
        intro=(
            "This page reads the request your status link identifies. Keep the link "
            "private &mdash; it is what authenticates you here."
        ),
        body=STATUS_PANEL + "\n" + SECURITY_REMINDER,
        scripts=status_scripts,
    )

    pages["payment-success.html"] = dict(
        title="Payment submitted",
        description="Your LogionACE payment has been submitted to Stripe.",
        robots="noindex, nofollow",
        eyebrow="Payment submitted",
        heading="Thank you &mdash; your payment has been submitted.",
        intro=(
            "Returning to this page means Stripe accepted your payment attempt. It is "
            "not itself proof of payment, so we tell you what we actually know below."
        ),
        body="""      <div class="callout">
        <h3>Confirmation may take a moment</h3>
        <p>We treat a payment as confirmed only when Stripe sends us a signed
          notification of it &mdash; not when a browser returns to this page. That
          notification usually arrives within seconds, occasionally later.</p>
        <p>Your request below shows <strong>Payment confirmed</strong> once it has
          arrived. If it still says <strong>Awaiting payment</strong>, use
          &ldquo;Check for updates&rdquo;. Nothing is lost either way, and you will not
          be charged twice.</p>
        <p>Payment does not start the evaluation. Once payment is confirmed we arrange
          secure access to the system being evaluated, and the evaluation is scheduled
          from there.</p>
      </div>

"""
        + STATUS_PANEL,
        scripts=status_scripts,
    )

    pages["payment-cancelled.html"] = dict(
        title="Payment cancelled",
        description="A LogionACE payment attempt was cancelled. The request is unchanged.",
        robots="noindex, nofollow",
        eyebrow="Payment cancelled",
        heading="Payment cancelled &mdash; nothing has changed.",
        intro=(
            "You left the payment page without completing it. No charge was made and "
            "your evaluation request is exactly as it was."
        ),
        body="""      <div class="callout">
        <h3>Where this leaves you</h3>
        <p>The approved quote and the payment link are still valid. You can return to
          your status page and pay whenever you are ready.</p>
        <p>If the quote or the scope is not right, reply to the email we sent with the
          quote, or contact <a href="mailto:info@logionace.com">info@logionace.com</a>.
          We would rather re-scope than have you pay for the wrong thing.</p>
      </div>

"""
        + STATUS_PANEL,
        scripts=status_scripts,
    )

    pages["access.html"] = dict(
        title="Evaluation access and security",
        description=(
            "How LogionACE handles credentials, sandbox access, retention and support "
            "for an evaluation engagement."
        ),
        robots="index, follow",
        eyebrow="Access and security",
        heading="How we get access, and how we handle it.",
        intro=(
            "What we ask for, what we never ask for, and what happens to it afterwards."
        ),
        body="""      <h2>Never through this website</h2>
      <p>The request form takes a <em>description</em> of how your system can be
        reached &mdash; &ldquo;staging endpoint behind our VPN&rdquo;, &ldquo;MCP server
        over SSE in a sandbox tenant&rdquo;. It does not take credentials, and our
        service rejects a submission that appears to contain one.</p>
      <p>We will never ask you to paste an API key, token, password or private key into
        a web form or an email. If something claiming to be LogionACE does, it is not
        us. Forward it to
        <a href="mailto:info@logionace.com">info@logionace.com</a>.</p>

      <h2>Secure handoff, after payment is confirmed</h2>
      <p>Access is arranged only once payment for the approved scope is confirmed. At
        that point we agree a handoff with your team &mdash; typically one of:</p>
      <ul>
        <li>a scoped, revocable key issued for the evaluation and nothing else;</li>
        <li>an account in a sandbox tenant you control;</li>
        <li>network access to a staging deployment for a defined window.</li>
      </ul>
      <p>Whatever the mechanism, it is time-boxed and revocable by you. We ask for the
        least access that lets the evaluation run, and we tell you when we are done so
        you can revoke it.</p>

      <h2>Paying does not start an evaluation</h2>
      <p>There is no self-service evaluation, and no automatic run. A confirmed payment
        means an engagement is funded; a human on our side then arranges access and
        schedules the work. You will know when it starts because you will have been part
        of arranging it.</p>

      <h2>Your responsibilities</h2>
      <ul>
        <li><strong>Authority.</strong> Whoever submits the request must be entitled to
          have the system evaluated and to grant the access involved.</li>
        <li><strong>Environment.</strong> If the system must not be tested in
          production, say so on the request and provide a sandbox. We will not decide
          that for you.</li>
        <li><strong>No production personal data.</strong> Evaluation environments should
          not contain real customer data. Our batteries do not need it, and it should
          not be exposed to a third party that does not need it.</li>
        <li><strong>Credential hygiene.</strong> Issue evaluation-specific credentials,
          and revoke them when the engagement ends.</li>
      </ul>

      <h2>What we keep, and for how long</h2>
      <ul>
        <li>Evaluation logs and raw outputs: retained for 90 days, then purged.</li>
        <li>The report and its evidence package: retained so we can reissue it to you.</li>
        <li>Your request details: kept to scope the work, quote it, and answer you.</li>
        <li>Payment records: held by Stripe; we store a reference, never card data.</li>
      </ul>
      <p>We do not use your evaluation data to train models, and we do not share it with
        third parties. Published results happen only under a public evaluation, through
        an approval workflow, after you have seen them. See our
        <a href="privacy.html">Privacy Policy</a> and
        <a href="trust.html">Trust &amp; Security</a> pages for the full detail.</p>

      <h2>Your status link</h2>
      <p>When a request is submitted we issue a status link containing a token. It is the
        credential for that one request: anyone with the link can see that request's
        status. It lives in the part of the URL after the <code>#</code>, which browsers
        do not send to servers, and we keep it in your tab's session storage so a trip to
        the payment provider does not lose it. Treat it like a password, and ask us to
        reissue it if it has been shared more widely than you intended.</p>

      <h2>Questions</h2>
      <p>Security questionnaires, a data processing addendum, NDAs, or anything else
        procurement needs: <a href="mailto:info@logionace.com">info@logionace.com</a>.</p>
""",
        scripts=scripts("ace-config.js", "ace-nav.js"),
    )

    rendered: dict[str, str] = {}
    for name, page in pages.items():
        rendered[name] = PAGE_TEMPLATE.format(
            stylesheet=STYLESHEET, nav=nav, footer=footer, **page
        )
    return rendered


def main() -> int:
    nav, footer = chrome()
    for name, html in build_pages(nav, footer).items():
        (ROOT / name).write_text(html, "utf-8")
        print(f"wrote {name} ({len(html)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
