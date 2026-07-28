/*
 * Public configuration for the LogionACE site.
 *
 * Everything here ships to the browser, so everything here is public by
 * definition: an API base, a set of paths, the published price list, and the
 * commit that the approved artifact snapshot is pinned to. No key, no token and
 * no per-customer value ever belongs in this file.
 *
 * The API base lives here once. Pages must not build their own, so that
 * pointing the site at a different deployment is one edit and cannot be done
 * half-way.
 */
window.ACE_CONFIG = Object.freeze({
  /* The LogionOS API that serves the ACE order endpoints. */
  API_BASE: 'https://logionos-api.onrender.com',

  ORDERS_PATH: '/v1/ace/orders',

  /*
   * Free hosting tiers idle. The first request after an idle period can take
   * many seconds to answer, which is a slow site rather than a broken one, so
   * the UI says so instead of reporting a failure.
   */
  REQUEST_TIMEOUT_MS: 45000,
  WAKE_UP_NOTICE_AFTER_MS: 4000,

  /*
   * The approved artifact snapshot. `benchmark`, the homepage counts and the
   * report downloads read nothing else: no draft file, no internal number and
   * no order data reaches a public page.
   */
  APPROVED_MANIFEST_PATH: 'approved-artifacts.json',

  /*
   * Provenance. The files published on GitHub main at this commit are the
   * historical approved snapshot; the commit is the approver of record, in
   * place of a human sign-off that never happened. A manifest naming any other
   * commit is not this snapshot and is refused.
   */
  APPROVED_PROVENANCE_COMMIT: 'b8a00c8ce38c27152837380f50c2c817aa639dd6',

  /*
   * The published price list. Amounts are the server's to decide -- these are
   * for display, and the quote a customer is asked to pay is whatever the
   * approved quote says.
   */
  PACKAGES: Object.freeze([
    Object.freeze({
      id: 'public',
      label: 'Public evaluation',
      price: '$25,000',
      summary: 'Results published, citable, and listed on the leaderboard.'
    }),
    Object.freeze({
      id: 'private',
      label: 'Private evaluation',
      price: '$40,000+',
      summary: 'Results delivered exclusively to you. Typical scope $40,000-$50,000.'
    }),
    Object.freeze({
      id: 'custom',
      label: 'Custom environment',
      price: '$60,000+',
      summary: 'For systems needing a test environment beyond the standard harness.'
    }),
    Object.freeze({
      id: 'founder',
      label: 'AI Founder Program',
      price: '$0',
      summary: 'Evaluation credits for selected Founder Program members. Subject to acceptance.'
    })
  ]),

  /*
   * Where a status token is allowed to live. The URL fragment is never sent to
   * the server or written to a server log, and session storage is dropped when
   * the tab closes -- which is why the token goes to both and to nothing else.
   * Never localStorage, never the query string, never an analytics call.
   */
  STATUS_SESSION_KEY: 'ace_status_link',

  /* Customer-facing pages, kept in one place so a rename cannot half-happen. */
  PAGES: Object.freeze({
    submitted: 'request-submitted.html',
    status: 'order-status.html',
    paymentSuccess: 'payment-success.html',
    paymentCancelled: 'payment-cancelled.html',
    access: 'access.html',
    evaluation: 'evaluation.html',
    terms: 'terms.html',
    privacy: 'privacy.html',
    trust: 'trust.html'
  }),

  SUPPORT_EMAIL: 'info@logionace.com'
});
