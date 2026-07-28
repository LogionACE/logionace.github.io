/*
 * The confirmation page shown immediately after a request is accepted.
 *
 * Its whole job is to hand the visitor their status link and make sure they
 * understand what it is. The link is read from the fragment the form navigated
 * to, saved to session storage, and never sent anywhere: this page makes no API
 * request at all, so a visitor who lands here with a link is not waiting on a
 * service that might be asleep.
 */
(function () {
  'use strict';

  var CONFIG = window.ACE_CONFIG;
  var SESSION = window.AceSession;

  function setText(id, text) {
    var node = document.getElementById(id);
    if (node) node.textContent = String(text == null ? '' : text);
  }

  function statusLinkUrl(link) {
    return window.location.origin +
      window.location.pathname.replace(/[^/]*$/, CONFIG.PAGES.status) +
      SESSION.buildFragment(link);
  }

  function init() {
    var link = SESSION.current();
    var missing = document.getElementById('ace-submitted-missing');

    if (!link) {
      /* No usable link: say so plainly rather than showing a copy button that
       * would put a broken URL on the clipboard. */
      if (missing) missing.hidden = false;
      var actions = document.getElementById('ace-submitted-copy');
      if (actions) actions.hidden = true;
      return;
    }

    SESSION.save(link);
    setText('ace-submitted-order-id', link.order_id);

    var url = statusLinkUrl(link);
    var anchors = document.querySelectorAll('[data-ace-status-link]');
    for (var i = 0; i < anchors.length; i += 1) {
      anchors[i].setAttribute('href', SESSION.statusUrl(link));
    }

    var fallbackInput = document.getElementById('ace-submitted-link-fallback');

    function reveal(message) {
      setText('ace-submitted-live', message);
      if (fallbackInput) {
        fallbackInput.value = url;
        fallbackInput.hidden = false;
        if (fallbackInput.parentElement) fallbackInput.parentElement.hidden = false;
      }
    }

    var copy = document.getElementById('ace-submitted-copy');
    if (copy) {
      copy.addEventListener('click', function () {
        if (window.navigator.clipboard && window.navigator.clipboard.writeText) {
          window.navigator.clipboard.writeText(url).then(function () {
            setText('ace-submitted-live',
              'Status link copied. Keep it private: it is the key to this request.');
          }, function () {
            reveal('Copying was blocked by the browser. Select the link below and copy it.');
          });
          return;
        }
        reveal('This browser will not copy for us. Select the link below and copy it.');
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
