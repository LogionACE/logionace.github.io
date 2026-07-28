/*
 * The customer's view of one evaluation order.
 *
 * Authenticated by the status token in the page fragment, which means this page
 * shows exactly what `GET /v1/ace/orders/{id}` returns and nothing else. That
 * response is a deliberately narrow projection: status, package, the approved
 * amount, the scope summaries, and a payment URL when there is one. It carries
 * no manifest hash, no token or judge counts, no cost estimate, no draft or
 * reviewer state and no operator identity -- so there is nothing here to filter,
 * and this file adds nothing of its own.
 *
 * Two behaviours worth stating outright:
 *
 *   * A payment button exists only when the server has put a payment URL in the
 *     response. The page cannot construct one, cannot guess one, and refuses a
 *     URL that is not an absolute https address.
 *   * Returning from Stripe proves nothing. The success page says so: payment is
 *     confirmed by a signed webhook, which may land a moment later, and until
 *     the status says `paid` this page will not claim it does.
 *
 * Refreshing is explicit, or bounded. A page that polls forever is a page left
 * open in a tab hammering an API for a week.
 */
(function () {
  'use strict';

  var CONFIG = window.ACE_CONFIG;
  var SESSION = window.AceSession;

  /* Bounded, not endless: a few automatic re-checks while something is
   * genuinely in flight, then the visitor is asked to refresh. */
  var AUTO_REFRESH_LIMIT = 3;
  var AUTO_REFRESH_INTERVAL_MS = 15000;
  var AUTO_REFRESH_STATUSES = ['payment_pending', 'paid'];

  var STATUS_COPY = {
    submitted: {
      label: 'Request received',
      detail: 'We have your request and are reviewing the scope. ' +
        'Nothing is payable yet.'
    },
    scoped: {
      label: 'Scope drafted',
      detail: 'We have drafted the scope and the quote. You will be able to ' +
        'review it here once it has been approved internally.'
    },
    approved: {
      label: 'Quote approved',
      detail: 'The scope and quote below are approved. A payment link appears ' +
        'here once it has been issued.'
    },
    payment_pending: {
      label: 'Awaiting payment',
      detail: 'A payment link has been issued for the approved quote. ' +
        'Payment is confirmed by our payment provider, not by returning to this site.'
    },
    paid: {
      label: 'Payment confirmed',
      detail: 'Payment is confirmed. We will arrange secure access to the system ' +
        'being evaluated; the evaluation does not start automatically.'
    },
    credentials_ready: {
      label: 'Access arranged',
      detail: 'Access to the system under evaluation has been arranged and the ' +
        'evaluation is scheduled.'
    },
    running: {
      label: 'Evaluation under way',
      detail: 'The evaluation is running. We will be in touch when the draft ' +
        'report is ready for review.'
    },
    draft_ready: {
      label: 'Draft under review',
      detail: 'A draft report exists and is being reviewed by our team before ' +
        'it is delivered.'
    },
    delivered: {
      label: 'Delivered',
      detail: 'The evaluation report has been delivered. Contact us if you need ' +
        'another copy or a debrief.'
    },
    cancelled: {
      label: 'Cancelled',
      detail: 'This request has been cancelled. Any payment link previously ' +
        'issued is no longer valid.'
    },
    refunded: {
      label: 'Refunded',
      detail: 'A refund has been recorded against this order.'
    }
  };

  var nodes = {};
  var link = null;
  var autoRefreshesUsed = 0;
  var autoRefreshTimer = null;
  var wakeUpTimer = null;
  var inFlight = false;

  /* -- DOM ---------------------------------------------------------------- */

  /* Text, never markup. Everything rendered below arrived over the network. */
  function setText(id, text) {
    var node = document.getElementById(id);
    if (node) node.textContent = String(text == null ? '' : text);
    return node;
  }

  function show(id, visible) {
    var node = document.getElementById(id);
    if (node) node.hidden = !visible;
    return node;
  }

  function announce(message) {
    setText('ace-status-live', message);
  }

  function fail(message) {
    show('ace-status-panel', false);
    show('ace-status-error', true);
    setText('ace-status-error-text', message);
  }

  /* -- values ------------------------------------------------------------- */

  function money(cents, currency) {
    var amount = Number(cents);
    if (!isFinite(amount) || amount < 0) return '';
    var whole = Math.floor(amount / 100);
    var pennies = amount % 100;
    var grouped = String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    var code = String(currency || '').toUpperCase();
    return (code === 'USD' ? '$' : '') + grouped +
      (pennies ? '.' + (pennies < 10 ? '0' : '') + pennies : '') +
      (code && code !== 'USD' ? ' ' + code : '');
  }

  function date(value) {
    var raw = String(value || '');
    if (!raw) return '';
    var parsed = new Date(raw);
    if (isNaN(parsed.getTime())) return raw;
    return parsed.toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
  }

  /*
   * A payment URL is only usable if the server sent an absolute https address.
   * Anything else -- a relative path, a `javascript:` scheme, a plain http link
   * -- is refused rather than rendered, so no response can turn this button
   * into a redirect of someone else's choosing.
   */
  function usablePaymentUrl(raw) {
    var candidate = String(raw || '');
    if (!candidate) return '';
    try {
      var parsed = new URL(candidate);
      if (parsed.protocol !== 'https:') return '';
      return parsed.href;
    } catch (error) {
      return '';
    }
  }

  /* -- rendering ---------------------------------------------------------- */

  function renderHistory(history) {
    var list = document.getElementById('ace-status-history');
    if (!list) return;
    list.textContent = '';
    var entries = Array.isArray(history) ? history : [];
    for (var i = 0; i < entries.length; i += 1) {
      var entry = entries[i] || {};
      var copy = STATUS_COPY[String(entry.status || '')];
      var item = document.createElement('li');
      var name = document.createElement('strong');
      name.textContent = copy ? copy.label : String(entry.status || '');
      var when = document.createElement('span');
      when.textContent = date(entry.at);
      item.appendChild(name);
      item.appendChild(when);
      list.appendChild(item);
    }
    show('ace-status-history-block', entries.length > 0);
  }

  function renderScope(order) {
    var rows = [
      ['ace-scope-access', order.access_method],
      ['ace-scope-sandbox-policy', order.sandbox_policy_summary],
      ['ace-scope-delivery', order.delivery_assumptions]
    ];
    var anyPresent = false;
    for (var i = 0; i < rows.length; i += 1) {
      var text = String(rows[i][1] || '');
      setText(rows[i][0], text);
      var row = document.getElementById(rows[i][0] + '-row');
      if (row) row.hidden = !text;
      if (text) anyPresent = true;
    }
    show('ace-scope-block', anyPresent);
  }

  function renderPayment(order) {
    var url = usablePaymentUrl(order.payment_url);
    var button = document.getElementById('ace-pay-button');
    if (!button) return;

    if (!url) {
      button.hidden = true;
      button.removeAttribute('href');
      show('ace-pay-block', false);
      return;
    }

    button.href = url;
    button.hidden = false;
    show('ace-pay-block', true);
    setText('ace-pay-amount', money(order.amount_cents, order.currency));
  }

  function renderMilestones(order) {
    var stamps = [
      ['ace-stamp-paid', 'Payment confirmed', order.paid_at],
      ['ace-stamp-delivered', 'Report delivered', order.delivered_at],
      ['ace-stamp-cancelled', 'Cancelled', order.cancelled_at],
      ['ace-stamp-refunded', 'Refunded', order.refunded_at]
    ];
    var any = false;
    for (var i = 0; i < stamps.length; i += 1) {
      var when = date(stamps[i][2]);
      var row = document.getElementById(stamps[i][0]);
      if (row) {
        row.textContent = when ? stamps[i][1] + ': ' + when : '';
        row.hidden = !when;
      }
      if (when) any = true;
    }
    show('ace-stamps-block', any);
  }

  function render(order) {
    var status = String(order.status || '');
    var copy = STATUS_COPY[status] || {
      label: status || 'Status unavailable',
      detail: 'This order is in a stage we do not have a description for. ' +
        'Email ' + CONFIG.SUPPORT_EMAIL + ' if you need detail.'
    };

    show('ace-status-error', false);
    show('ace-status-panel', true);

    setText('ace-status-order-id', String(order.order_id || ''));
    setText('ace-status-label', copy.label);
    setText('ace-status-detail', copy.detail);
    setText('ace-status-updated', date(order.updated_at));
    setText('ace-status-created', date(order.created_at));

    var quoted = String(order.quoted_package || '');
    var requested = String(order.requested_package || '');
    setText('ace-status-package', quoted || requested);
    var amount = money(order.amount_cents, order.currency);
    setText('ace-status-amount', amount);
    var amountRow = document.getElementById('ace-status-amount-row');
    if (amountRow) amountRow.hidden = !amount;

    setText('ace-status-visibility', String(order.visibility || ''));
    setText('ace-status-sandbox',
      order.sandbox_required ? 'Sandbox required' : 'No sandbox required');

    renderScope(order);
    renderPayment(order);
    renderMilestones(order);
    renderHistory(order.history);

    announce(copy.label + '. ' + copy.detail);
    scheduleAutoRefresh(status);
  }

  /* -- fetching ----------------------------------------------------------- */

  function startWakeUpNotice() {
    stopWakeUpNotice();
    wakeUpTimer = window.setTimeout(function () {
      announce('Still checking. The evaluation service may be waking up, which ' +
        'can take up to a minute.');
    }, CONFIG.WAKE_UP_NOTICE_AFTER_MS);
  }

  function stopWakeUpNotice() {
    if (wakeUpTimer !== null) {
      window.clearTimeout(wakeUpTimer);
      wakeUpTimer = null;
    }
  }

  function refreshButtonBusy(isBusy) {
    var button = document.getElementById('ace-status-refresh');
    if (!button) return;
    button.disabled = isBusy;
    button.setAttribute('aria-busy', isBusy ? 'true' : 'false');
    button.textContent = isBusy ? 'Checking...' : 'Check for updates';
  }

  function reportApiError(status, payload) {
    var error = (payload && payload.error) || {};
    if (status === 404) {
      /* The API answers "no such order" and "wrong token" identically, on
       * purpose, and so does this page. */
      fail('We cannot find an evaluation request for this link. Check that you ' +
        'opened the full status link, including the part after the # symbol. ' +
        'If it was issued a long time ago, email ' + CONFIG.SUPPORT_EMAIL + '.');
      return;
    }
    if (status === 429) {
      fail('This link has been checked too many times in the last minute. ' +
        'Please wait a minute and try again.');
      return;
    }
    if (status === 503) {
      fail('The evaluation service is temporarily unavailable. Your request is ' +
        'unaffected; please check again shortly.');
      return;
    }
    fail(String(error.message || 'We could not load this evaluation request right now.'));
  }

  function load() {
    if (inFlight || !link) return;
    inFlight = true;
    refreshButtonBusy(true);
    announce('Checking the status of your request.');
    startWakeUpNotice();

    var controller = typeof AbortController === 'function' ? new AbortController() : null;
    var timeout = window.setTimeout(function () {
      if (controller) controller.abort();
    }, CONFIG.REQUEST_TIMEOUT_MS);

    var options = {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        /* The token goes in a header, never in the query string, so it does not
         * land in an access log or a referrer. */
        'X-ACE-Status-Token': link.token
      }
    };
    if (controller) options.signal = controller.signal;

    fetch(CONFIG.API_BASE + CONFIG.ORDERS_PATH + '/' + encodeURIComponent(link.order_id), options)
      .then(function (response) {
        window.clearTimeout(timeout);
        return response.json().catch(function () { return null; }).then(function (payload) {
          return { ok: response.ok, status: response.status, payload: payload };
        });
      })
      .then(function (result) {
        stopWakeUpNotice();
        inFlight = false;
        refreshButtonBusy(false);
        if (result.ok && result.payload) {
          render(result.payload);
          return;
        }
        reportApiError(result.status, result.payload);
      })
      .catch(function (error) {
        window.clearTimeout(timeout);
        stopWakeUpNotice();
        inFlight = false;
        refreshButtonBusy(false);
        if (error && error.name === 'AbortError') {
          fail('The service did not answer in time. Your request is unaffected; ' +
            'use "Check for updates" to try again.');
          return;
        }
        if (!window.navigator.onLine) {
          fail('This browser is offline. Reconnect and use "Check for updates".');
          return;
        }
        fail('We could not reach the evaluation service. Check your connection ' +
          'and use "Check for updates" to try again.');
      });
  }

  function scheduleAutoRefresh(status) {
    if (autoRefreshTimer !== null) {
      window.clearTimeout(autoRefreshTimer);
      autoRefreshTimer = null;
    }
    if (AUTO_REFRESH_STATUSES.indexOf(status) === -1) return;
    if (autoRefreshesUsed >= AUTO_REFRESH_LIMIT) {
      show('ace-status-autorefresh-note', true);
      return;
    }
    autoRefreshesUsed += 1;
    autoRefreshTimer = window.setTimeout(load, AUTO_REFRESH_INTERVAL_MS);
  }

  /* -- the status link --------------------------------------------------- */

  function copyStatusLink() {
    var url = window.location.origin + window.location.pathname.replace(
      /[^/]*$/, CONFIG.PAGES.status
    ) + SESSION.buildFragment(link);

    function done(ok) {
      announce(ok
        ? 'Status link copied to the clipboard. Keep it private: it is the key to this request.'
        : 'Copying failed. Select the link below and copy it manually.');
      var fallback = document.getElementById('ace-status-link-fallback');
      if (fallback) {
        fallback.value = url;
        fallback.hidden = false;
      }
    }

    if (window.navigator.clipboard && window.navigator.clipboard.writeText) {
      window.navigator.clipboard.writeText(url).then(function () { done(true); },
        function () { done(false); });
      return;
    }
    done(false);
  }

  function init() {
    if (!document.getElementById('ace-status-root')) return;

    link = SESSION.current();
    if (!link) {
      fail('This page needs the status link we issued when your request was ' +
        'received -- including the part after the # symbol. Open that link ' +
        'again, or email ' + CONFIG.SUPPORT_EMAIL + ' and we will resend it.');
      return;
    }
    /* Saved before anything else: the visitor may be about to leave for the
     * payment provider, and the fragment does not survive that round trip. */
    SESSION.save(link);
    setText('ace-status-order-id', link.order_id);

    var refresh = document.getElementById('ace-status-refresh');
    if (refresh) {
      refresh.addEventListener('click', function () {
        /* An explicit check re-earns the bounded automatic ones. */
        autoRefreshesUsed = 0;
        show('ace-status-autorefresh-note', false);
        load();
      });
    }

    var copy = document.getElementById('ace-status-copy');
    if (copy) copy.addEventListener('click', copyStatusLink);

    var pay = document.getElementById('ace-pay-button');
    if (pay) {
      pay.addEventListener('click', function () {
        /* Leaving for the payment provider. The fragment will not come back, so
         * the session copy is what brings the visitor to their status page. */
        SESSION.save(link);
      });
    }

    var statusLinks = document.querySelectorAll('[data-ace-status-link]');
    for (var i = 0; i < statusLinks.length; i += 1) {
      statusLinks[i].setAttribute('href', SESSION.statusUrl(link));
    }

    load();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  /* Exposed for the offline test suite. */
  window.AceStatusPage = {
    usablePaymentUrl: usablePaymentUrl,
    money: money,
    STATUS_COPY: STATUS_COPY,
    AUTO_REFRESH_LIMIT: AUTO_REFRESH_LIMIT
  };
})();
