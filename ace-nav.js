/*
 * Site chrome: the mobile nav, the scroll-reveal animation, and the pricing
 * "see all features" toggles.
 *
 * This was inline `<script>` and `onclick=` attributes on every page. It lives
 * in a file now so the pages that carry a status token or verify an artifact can
 * be served under a Content-Security-Policy without `unsafe-inline` -- a policy
 * with `unsafe-inline` in it does not stop the injection it is there to stop.
 */
(function () {
  'use strict';

  function revealOnScroll() {
    var targets = document.querySelectorAll('.fade-up');
    if (!targets.length) return;
    if (typeof IntersectionObserver !== 'function') {
      /* No observer: show everything rather than leaving the page blank. */
      for (var i = 0; i < targets.length; i += 1) targets[i].classList.add('visible');
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) entry.target.classList.add('visible');
      });
    }, { threshold: 0.15 });
    for (var j = 0; j < targets.length; j += 1) observer.observe(targets[j]);
  }

  function mobileNav() {
    var button = document.querySelector('.nav-hamburger');
    var links = document.querySelector('.nav-links');
    if (!button || !links) return;

    button.addEventListener('click', function () {
      var open = links.classList.toggle('nav-open');
      button.classList.toggle('active', open);
      button.setAttribute('aria-expanded', open ? 'true' : 'false');
      document.body.style.overflow = open ? 'hidden' : '';
    });

    var triggers = document.querySelectorAll('.nav-drop > .nav-trigger');
    for (var i = 0; i < triggers.length; i += 1) {
      triggers[i].addEventListener('click', function (event) {
        if (window.innerWidth <= 768) {
          event.preventDefault();
          this.parentElement.classList.toggle('drop-open');
        }
      });
      /* The dropdown triggers are not links, so they need to answer the
       * keyboard themselves. */
      triggers[i].setAttribute('tabindex', '0');
      triggers[i].addEventListener('keydown', function (event) {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          this.parentElement.classList.toggle('drop-open');
        }
      });
    }

    var anchors = links.querySelectorAll('a');
    for (var j = 0; j < anchors.length; j += 1) {
      anchors[j].addEventListener('click', function () {
        links.classList.remove('nav-open');
        button.classList.remove('active');
        button.setAttribute('aria-expanded', 'false');
        document.body.style.overflow = '';
      });
    }
  }

  function pricingToggles() {
    var toggles = document.querySelectorAll('[data-toggle-list]');
    for (var i = 0; i < toggles.length; i += 1) {
      toggles[i].addEventListener('click', function () {
        var list = document.getElementById(this.getAttribute('data-toggle-list'));
        if (!list) return;
        var expanded = list.classList.toggle('expanded');
        this.textContent = expanded ? 'Show less' : 'See all features';
        this.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      });
    }
  }

  function init() {
    revealOnScroll();
    mobileNav();
    pricingToggles();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
