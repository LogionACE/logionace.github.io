/*
 * Status-link handling for the LogionACE customer flow.
 *
 * An order's status token is a bearer credential for one order. Where it is
 * allowed to live is the whole design of this file:
 *
 *   * The URL fragment. Never sent to a server, never in an access log, never
 *     in a `Referer` header. This is the customer's copy of the link.
 *   * Session storage, for the length of one tab. Needed because paying means
 *     leaving for Stripe and coming back to a page with a fresh URL.
 *
 * And where it is not allowed to live: the query string (logged by every proxy
 * in the path), localStorage (survives the browser closing on a shared
 * machine), any analytics call, and any DOM attribute a copy-paste of the page
 * would carry.
 *
 * Nothing here stores intake fields. The customer's name, email, company and
 * endpoint descriptor go to the API and are then forgotten by the browser: a
 * form the visitor filled in once should not be sitting in a shared laptop's
 * storage afterwards.
 */
(function () {
  'use strict';

  var CONFIG = window.ACE_CONFIG;
  var ORDER_ID_RE = /^aceord_[0-9a-f]{16,64}$/;
  /* `secrets.token_urlsafe` output: base64url, no padding. */
  var TOKEN_RE = /^[A-Za-z0-9_-]{20,200}$/;

  function parseFragment(rawFragment) {
    var fragment = String(rawFragment || '');
    if (fragment.charAt(0) === '#') fragment = fragment.slice(1);
    if (!fragment) return null;

    var order = '';
    var token = '';
    var parts = fragment.split('&');
    for (var i = 0; i < parts.length; i += 1) {
      var pair = parts[i].split('=');
      var name = decodeURIComponent(pair[0] || '');
      var value = decodeURIComponent(pair.slice(1).join('=') || '');
      if (name === 'order') order = value;
      if (name === 'token') token = value;
    }
    /* Both halves, both well-formed, or nothing. A partial link is a link that
     * will fail one request later with a confusing message. */
    if (!ORDER_ID_RE.test(order) || !TOKEN_RE.test(token)) return null;
    return { order_id: order, token: token };
  }

  function buildFragment(link) {
    return '#order=' + encodeURIComponent(link.order_id) +
      '&token=' + encodeURIComponent(link.token);
  }

  function statusUrl(link) {
    return CONFIG.PAGES.status + buildFragment(link);
  }

  function save(link) {
    if (!link) return;
    try {
      window.sessionStorage.setItem(
        CONFIG.STATUS_SESSION_KEY,
        JSON.stringify({ order_id: link.order_id, token: link.token })
      );
    } catch (error) {
      /* Private browsing, or storage disabled. The fragment in the address bar
       * is still the customer's copy, so this is a degraded experience rather
       * than a broken one and must not throw. */
    }
  }

  function load() {
    try {
      var raw = window.sessionStorage.getItem(CONFIG.STATUS_SESSION_KEY);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== 'object') return null;
      if (!ORDER_ID_RE.test(String(parsed.order_id || ''))) return null;
      if (!TOKEN_RE.test(String(parsed.token || ''))) return null;
      return { order_id: String(parsed.order_id), token: String(parsed.token) };
    } catch (error) {
      return null;
    }
  }

  function clear() {
    try {
      window.sessionStorage.removeItem(CONFIG.STATUS_SESSION_KEY);
    } catch (error) { /* nothing to clear */ }
  }

  /* The fragment first, session storage second. A link someone just opened
   * beats one this tab happened to remember. */
  function current() {
    var fromFragment = parseFragment(window.location.hash);
    if (fromFragment) {
      save(fromFragment);
      return fromFragment;
    }
    return load();
  }

  window.AceSession = {
    parseFragment: parseFragment,
    buildFragment: buildFragment,
    statusUrl: statusUrl,
    save: save,
    load: load,
    clear: clear,
    current: current
  };
})();
