/*
 * The LogionACE evaluation request form.
 *
 * This form submits a *scope request*. It never charges anybody, never starts
 * an evaluation and never asks for a credential. What happens after it is: we
 * read it, we scope it, we send an approved quote, and only then is there
 * anything to pay. The copy on the page says so, and this file cannot do
 * otherwise -- there is no payment call in it.
 *
 * Client validation here mirrors the API's enums and length limits so the
 * visitor is told about a problem before a round trip, but the server remains
 * the authority: a field this file accepts can still be refused, and the
 * refusal is displayed as the server phrased it.
 *
 * Three details that are easy to get wrong and matter:
 *
 *   * The `Idempotency-Key` is generated once per distinct submission and
 *     reused on retry, so "submit, connection drops, submit again" produces one
 *     order rather than two identical ones a human then has to reconcile.
 *   * Nothing the visitor typed is written to localStorage. The intake contains
 *     a name, a work email and a system endpoint; leaving that in a shared
 *     browser is a leak we would have caused, not the visitor.
 *   * The status token that comes back is handed to `AceSession`, which puts it
 *     in the fragment and session storage and nowhere else.
 */
(function () {
  'use strict';

  var CONFIG = window.ACE_CONFIG;
  var SESSION = window.AceSession;

  /* Mirrors of the API's vocabulary. Duplicated deliberately: the alternative
   * is fetching a schema before the form can be used, which trades a wrong
   * dropdown for a form that does not work when the API is asleep. The static
   * test suite asserts these lists match the server's. */
  var SYSTEM_TYPES = ['model_endpoint', 'ai_agent', 'workflow', 'deployed_product', 'other'];
  var MCP_TRANSPORTS = ['none', 'stdio', 'http_streamable', 'sse', 'websocket', 'other'];
  var INDUSTRIES = ['financial_services', 'healthcare', 'legal', 'government',
    'education', 'technology', 'retail', 'manufacturing', 'media', 'telecom', 'other'];
  var VISIBILITIES = ['public', 'private'];
  var PACKAGES = ['public', 'private', 'custom', 'founder_program', 'undecided'];

  var MAX_LENGTHS = {
    contact_name: 120,
    contact_email: 254,
    company_name: 160,
    company_domain: 253,
    system_name: 160,
    endpoint_descriptor: 400,
    notes: 2000
  };

  var EMAIL_RE = /^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$/;

  /*
   * A deliberately small subset of the server's credential screen, matched
   * client-side so we can say "please don't paste a key" before the key has
   * been sent anywhere. The server screens properly; this is about not
   * transmitting the thing in the first place.
   */
  var CREDENTIAL_PATTERNS = [
    /-----BEGIN[A-Z ]*PRIVATE KEY-----/,
    /\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{8,}/,
    /\bpk_(?:live|test)_[A-Za-z0-9]{8,}/,
    /\bwhsec_[A-Za-z0-9]{8,}/,
    /\bsk-(?:[A-Za-z0-9]+-)?[A-Za-z0-9]{20,}/,
    /\blg_[A-Za-z0-9_\-]{20,}/,
    /\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/,
    /\bAIza[0-9A-Za-z_\-]{30,}/,
    /\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{5,}/,
    /\bbearer\s+[A-Za-z0-9_\-.=]{16,}/i,
    /\bauthorization\s*[:=]/i,
    /\bx-api-key\b/i,
    /:\/\/[^/\s:@]+:[^/\s@]{3,}@/,
    /[?&](?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|token|key|secret)=[^&\s]{6,}/i
  ];

  var IDEMPOTENCY_SESSION_KEY = 'ace_submission_key';

  var FIELDS = ['contact_name', 'contact_email', 'company_name', 'company_domain',
    'system_type', 'system_name', 'endpoint_descriptor', 'mcp_transport',
    'sandbox_required', 'industry', 'visibility', 'requested_package',
    'data_authorization', 'notes'];

  var form;
  var statusRegion;
  var errorSummary;
  var submitButton;
  var wakeUpTimer = null;
  var inFlight = false;

  /* -- small DOM helpers -------------------------------------------------- */

  /* Every one of these writes text, not markup. An API message, a field name
   * or anything else that did not originate in this file is untrusted, and
   * `textContent` means it cannot become an element. */
  function setText(node, text) {
    if (node) node.textContent = String(text == null ? '' : text);
  }

  function announce(message) {
    setText(statusRegion, message);
  }

  function clearErrors() {
    setText(errorSummary, '');
    errorSummary.hidden = true;
    var fields = form.querySelectorAll('[data-field-error]');
    for (var i = 0; i < fields.length; i += 1) {
      setText(fields[i], '');
      fields[i].hidden = true;
    }
    var inputs = form.querySelectorAll('[name]');
    for (var j = 0; j < inputs.length; j += 1) {
      inputs[j].removeAttribute('aria-invalid');
    }
  }

  function showFieldError(name, message) {
    var slot = form.querySelector('[data-field-error="' + name + '"]');
    var input = form.querySelector('[name="' + name + '"]');
    if (slot) {
      setText(slot, message);
      slot.hidden = false;
    }
    if (input) input.setAttribute('aria-invalid', 'true');
  }

  function showSummary(message) {
    setText(errorSummary, message);
    errorSummary.hidden = false;
    /* Focus moves to the summary so a keyboard or screen-reader user is taken
     * to the problem instead of being left at the submit button. */
    errorSummary.setAttribute('tabindex', '-1');
    errorSummary.focus();
  }

  /* -- reading and validating -------------------------------------------- */

  function value(name) {
    var input = form.querySelector('[name="' + name + '"]');
    if (!input) return '';
    if (input.type === 'checkbox') return input.checked;
    return String(input.value || '').trim();
  }

  function readIntake() {
    return {
      contact_name: value('contact_name'),
      contact_email: value('contact_email').toLowerCase(),
      company_name: value('company_name'),
      company_domain: value('company_domain').toLowerCase(),
      system_type: value('system_type'),
      system_name: value('system_name'),
      endpoint_descriptor: value('endpoint_descriptor'),
      mcp_transport: value('mcp_transport'),
      sandbox_required: value('sandbox_required') === true,
      industry: value('industry'),
      visibility: value('visibility'),
      requested_package: value('requested_package'),
      data_authorization: value('data_authorization') === true,
      notes: value('notes')
    };
  }

  var REQUIRED_TEXT = {
    contact_name: 'Please give us a name to reply to.',
    contact_email: 'A work email address is required.',
    company_name: 'Please tell us which organisation is requesting this.',
    endpoint_descriptor: 'Describe how the system can be reached, without credentials.'
  };

  var ENUMS = {
    system_type: { values: SYSTEM_TYPES, message: 'Choose the kind of system to evaluate.' },
    mcp_transport: { values: MCP_TRANSPORTS, message: 'Choose a transport, or "Not applicable".' },
    industry: { values: INDUSTRIES, message: 'Choose the industry this system operates in.' },
    visibility: { values: VISIBILITIES, message: 'Choose whether results may be published.' },
    requested_package: { values: PACKAGES, message: 'Choose the evaluation you are asking about.' }
  };

  function findCredential(text) {
    for (var i = 0; i < CREDENTIAL_PATTERNS.length; i += 1) {
      if (CREDENTIAL_PATTERNS[i].test(text)) return true;
    }
    return false;
  }

  /* Returns a list of `{field, message}`; empty means the form may be sent. */
  function validate(intake) {
    var problems = [];

    Object.keys(REQUIRED_TEXT).forEach(function (name) {
      if (!intake[name]) problems.push({ field: name, message: REQUIRED_TEXT[name] });
    });

    if (intake.contact_email && !EMAIL_RE.test(intake.contact_email)) {
      problems.push({
        field: 'contact_email',
        message: 'That does not look like an email address we can reply to.'
      });
    }

    Object.keys(MAX_LENGTHS).forEach(function (name) {
      var limit = MAX_LENGTHS[name];
      if (String(intake[name] || '').length > limit) {
        problems.push({
          field: name,
          message: 'Please keep this under ' + limit + ' characters.'
        });
      }
    });

    Object.keys(ENUMS).forEach(function (name) {
      if (ENUMS[name].values.indexOf(intake[name]) === -1) {
        problems.push({ field: name, message: ENUMS[name].message });
      }
    });

    if (!intake.data_authorization) {
      problems.push({
        field: 'data_authorization',
        message: 'We need your confirmation that you are authorised to have this system evaluated.'
      });
    }

    ['endpoint_descriptor', 'notes', 'system_name', 'company_domain'].forEach(function (name) {
      if (intake[name] && findCredential(String(intake[name]))) {
        problems.push({
          field: name,
          message: 'This looks like it contains a key or token. Describe how to reach ' +
            'the system instead -- credentials are exchanged securely after the ' +
            'scope is approved and paid for.'
        });
      }
    });

    return problems;
  }

  /* -- idempotency ------------------------------------------------------- */

  function randomKey() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return 'web-' + window.crypto.randomUUID();
    }
    if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
      var bytes = new Uint8Array(16);
      window.crypto.getRandomValues(bytes);
      var hex = '';
      for (var i = 0; i < bytes.length; i += 1) {
        hex += (bytes[i] < 16 ? '0' : '') + bytes[i].toString(16);
      }
      return 'web-' + hex;
    }
    return 'web-' + String(Date.now()) + '-' + String(Math.random()).slice(2, 12);
  }

  /*
   * One key per distinct submission, stable across retries.
   *
   * Keyed on the intake itself: retrying the same form reuses the key, so the
   * server replays the first order instead of creating a second. Editing a
   * field and submitting again is a different request and gets a new key --
   * otherwise a corrected submission would be answered with the uncorrected
   * order.
   */
  function idempotencyKeyFor(intake) {
    var fingerprint = JSON.stringify(intake);
    try {
      var raw = window.sessionStorage.getItem(IDEMPOTENCY_SESSION_KEY);
      if (raw) {
        var saved = JSON.parse(raw);
        if (saved && saved.fingerprint === fingerprint && saved.key) return saved.key;
      }
    } catch (error) { /* fall through and mint a new one */ }

    var key = randomKey();
    try {
      window.sessionStorage.setItem(
        IDEMPOTENCY_SESSION_KEY,
        /* The fingerprint is the intake, so this is session-only and cleared on
         * success -- the same reason the intake never goes to localStorage. */
        JSON.stringify({ key: key, fingerprint: fingerprint })
      );
    } catch (error) { /* a non-reused key still submits correctly */ }
    return key;
  }

  function clearIdempotencyKey() {
    try {
      window.sessionStorage.removeItem(IDEMPOTENCY_SESSION_KEY);
    } catch (error) { /* nothing to clear */ }
  }

  /* -- submitting -------------------------------------------------------- */

  function busy(isBusy, label) {
    inFlight = isBusy;
    submitButton.disabled = isBusy;
    setText(submitButton, label || (isBusy ? 'Sending request...' : 'Submit request'));
    submitButton.setAttribute('aria-busy', isBusy ? 'true' : 'false');
  }

  function startWakeUpNotice() {
    stopWakeUpNotice();
    wakeUpTimer = window.setTimeout(function () {
      announce('Still sending. The evaluation service may be waking up, which ' +
        'can take up to a minute on the first request.');
    }, CONFIG.WAKE_UP_NOTICE_AFTER_MS);
  }

  function stopWakeUpNotice() {
    if (wakeUpTimer !== null) {
      window.clearTimeout(wakeUpTimer);
      wakeUpTimer = null;
    }
  }

  function errorBodyOf(payload) {
    if (payload && typeof payload === 'object' && payload.error &&
        typeof payload.error === 'object') {
      return payload.error;
    }
    return {};
  }

  /*
   * Turn a refusal into something a customer can act on.
   *
   * The server's message is shown as-is: it is written for this purpose and
   * contains no internals. What we do not do is invent detail, guess at a
   * cause, or print a status code as if it were an explanation.
   */
  function reportApiError(status, payload) {
    var error = errorBodyOf(payload);
    var code = String(error.code || '');
    var message = String(error.message || '');

    if (status === 422 || status === 400) {
      var details = Array.isArray(error.details) ? error.details : [];
      var field = details.length && details[0] ? String(details[0].field || '') : '';
      if (field && FIELDS.indexOf(field) !== -1) {
        showFieldError(field, message || 'Please check this field.');
        showSummary('One field needs attention: ' + (message || 'please check it.'));
        return;
      }
      showSummary(message || 'Some details need attention before we can accept this request.');
      return;
    }

    if (status === 429) {
      showSummary('Too many requests from this network in a short time. ' +
        'Please wait a minute and submit again.');
      return;
    }

    if (status === 503) {
      showSummary('The evaluation service is not accepting requests right now. ' +
        'Please try again shortly, or email ' + CONFIG.SUPPORT_EMAIL + '.');
      return;
    }

    if (status >= 500) {
      showSummary('Something went wrong on our side and your request was not ' +
        'recorded. Please try again, or email ' + CONFIG.SUPPORT_EMAIL + '.');
      return;
    }

    /* Anything else: say what we know without dressing it up. Codes are stable
     * and safe to quote, so support can be told one. */
    showSummary((message || 'We could not submit this request.') +
      (code ? ' (' + code + ')' : ''));
  }

  function onSuccess(payload) {
    var orderId = String((payload && payload.order_id) || '');
    var token = String((payload && payload.status_token) || '');
    var link = SESSION.parseFragment('#order=' + encodeURIComponent(orderId) +
      '&token=' + encodeURIComponent(token));

    /* This submission is done: a later, different form on the same tab must get
     * its own idempotency key. */
    clearIdempotencyKey();

    if (!link) {
      /* Accepted, but without a usable status link -- possible on a replay
       * where the token is deliberately not reissued. Say what is true rather
       * than pretending we have a link. */
      announce('');
      showSummary('Your request was received' +
        (orderId ? ' as ' + orderId : '') +
        ', but this browser did not receive a status link. ' +
        'Email ' + CONFIG.SUPPORT_EMAIL + ' quoting that reference and we will resend it.');
      busy(false);
      return;
    }

    SESSION.save(link);
    /* The token travels in the fragment, so it is not in the navigation the
     * server sees, and `replace` keeps it out of the back button's history
     * entry for the form page. */
    window.location.replace(CONFIG.PAGES.submitted + SESSION.buildFragment(link));
  }

  function submit(intake) {
    var controller = typeof AbortController === 'function' ? new AbortController() : null;
    var timeout = window.setTimeout(function () {
      if (controller) controller.abort();
    }, CONFIG.REQUEST_TIMEOUT_MS);

    var options = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'Idempotency-Key': idempotencyKeyFor(intake)
      },
      body: JSON.stringify(intake)
    };
    if (controller) options.signal = controller.signal;

    return fetch(CONFIG.API_BASE + CONFIG.ORDERS_PATH, options)
      .then(function (response) {
        window.clearTimeout(timeout);
        return response.json().catch(function () { return null; }).then(function (payload) {
          return { status: response.status, ok: response.ok, payload: payload };
        });
      })
      .catch(function (error) {
        window.clearTimeout(timeout);
        throw error;
      });
  }

  function onSubmit(event) {
    event.preventDefault();
    if (inFlight) return;

    clearErrors();
    announce('');

    var intake = readIntake();
    var problems = validate(intake);
    if (problems.length) {
      problems.forEach(function (problem) {
        showFieldError(problem.field, problem.message);
      });
      /* Focus lands on the summary, not on the first bad field: it is the one
       * place that says how many problems there are, and it is the same landing
       * point a server-side refusal produces. Each field is marked
       * `aria-invalid` so tabbing from here reaches them in order. */
      showSummary(problems.length === 1
        ? problems[0].message
        : 'Please correct ' + problems.length + ' fields below.');
      return;
    }

    if (!window.navigator.onLine) {
      showSummary('This browser is offline. Your details are still in the form; ' +
        'reconnect and submit again.');
      return;
    }

    busy(true);
    announce('Sending your request.');
    startWakeUpNotice();

    submit(intake).then(function (result) {
      stopWakeUpNotice();
      if (result.ok) {
        onSuccess(result.payload);
        return;
      }
      busy(false);
      announce('');
      reportApiError(result.status, result.payload);
    }).catch(function (error) {
      stopWakeUpNotice();
      busy(false);
      announce('');
      if (error && error.name === 'AbortError') {
        showSummary('The request timed out before the service answered. ' +
          'Submitting again is safe -- it will not create a second request.');
        return;
      }
      showSummary('We could not reach the evaluation service. Check your ' +
        'connection and submit again; submitting twice will not create two requests.');
    });
  }

  function init() {
    form = document.getElementById('ace-order-form');
    if (!form) return;
    statusRegion = document.getElementById('ace-form-status');
    errorSummary = document.getElementById('ace-form-error');
    submitButton = form.querySelector('[type="submit"]');
    form.addEventListener('submit', onSubmit);

    /* A visitor who leaves and comes back should not find a stale error. */
    form.addEventListener('input', function (event) {
      var name = event.target && event.target.name;
      if (!name) return;
      var slot = form.querySelector('[data-field-error="' + name + '"]');
      if (slot && !slot.hidden) {
        setText(slot, '');
        slot.hidden = true;
        event.target.removeAttribute('aria-invalid');
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  /* Exposed for the offline test suite, which exercises the validation and the
   * idempotency rule directly rather than only through the DOM. */
  window.AceOrderForm = {
    validate: validate,
    readIntake: readIntake,
    idempotencyKeyFor: idempotencyKeyFor,
    SYSTEM_TYPES: SYSTEM_TYPES,
    MCP_TRANSPORTS: MCP_TRANSPORTS,
    INDUSTRIES: INDUSTRIES,
    VISIBILITIES: VISIBILITIES,
    PACKAGES: PACKAGES,
    MAX_LENGTHS: MAX_LENGTHS
  };
})();
