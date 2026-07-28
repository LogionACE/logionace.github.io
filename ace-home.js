/*
 * The homepage figures and the report-card carousel.
 *
 * Both used to be typed into the HTML. That is how the page came to claim 47
 * critical failures while the published leaderboard recorded 56: two copies of
 * one fact, and no way for a reader to tell which was current. Now there is one
 * copy -- the approved artifact -- and it is verified by hash before a number
 * appears.
 *
 * Until verification finishes the figures read as em dashes rather than as
 * plausible defaults, and if it fails they stay that way with a short note. A
 * homepage statistic nobody can check is marketing; this page would rather show
 * nothing.
 */
(function () {
  'use strict';

  var ARTIFACTS = window.AceArtifacts;

  var COUNT_FIELDS = [
    ['ace-count-systems', 'systems_evaluated'],
    ['ace-count-critical', 'critical_failures'],
    ['ace-count-ready', 'ace_ready'],
    ['ace-count-domains', 'trust_domains']
  ];

  var CAROUSEL_SIZE = 4;
  var CAROUSEL_INTERVAL_MS = 10000;

  var DISPLAY_NAME = {
    'gpt-5.5': 'GPT-5.5',
    'gpt-4o': 'GPT-4o',
    'gemini-3.1-pro': 'Gemini 3.1 Pro',
    'opus-4.8': 'Opus 4.8',
    'fable-5': 'Fable 5',
    'grok-4.3': 'Grok 4.3',
    'qwen3.7-max': 'Qwen 3.7 Max',
    'deepseek-v4-pro': 'DeepSeek V4 Pro',
    'llama-4-maverick': 'Llama 4 Maverick'
  };

  /* The order the hero card's domain row is laid out in. */
  var DOMAIN_ORDER = ['DP', 'RF', 'MR', 'AG', 'TA', 'CI'];

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(id, value) {
    var node = byId(id);
    if (node) node.textContent = String(value == null ? '' : value);
  }

  function verdictClass(verdict) {
    var text = String(verdict || '');
    if (text.indexOf('Conditional') !== -1) return 'verdict-conditional';
    if (text.indexOf('Ready') !== -1 && text.indexOf('Not') === -1) return 'verdict-ready';
    return 'verdict-notready';
  }

  function renderCounts(counts) {
    for (var i = 0; i < COUNT_FIELDS.length; i += 1) {
      setText(COUNT_FIELDS[i][0], counts[COUNT_FIELDS[i][1]]);
    }
  }

  function showCard(model) {
    var card = byId('hero-card');
    if (!card || !model) return;
    var bare = model.bare || {};

    setText('rc-model', DISPLAY_NAME[model.label] || model.label);
    setText('rc-vendor', model.vendor || '');
    setText('rc-score', bare.overall);

    var grade = byId('rc-grade');
    if (grade) {
      grade.textContent = String(bare.grade || '');
      grade.className = 'grade-' + String(bare.grade || '').toLowerCase();
    }

    var verdict = byId('rc-verdict');
    if (verdict) {
      verdict.textContent = String(bare.verdict || '');
      verdict.className = 'preview-verdict ' + verdictClass(bare.verdict);
    }

    var domains = bare.domains || {};
    var cells = document.querySelectorAll('#rc-domains div');
    for (var i = 0; i < cells.length && i < DOMAIN_ORDER.length; i += 1) {
      var entry = domains[DOMAIN_ORDER[i]] || {};
      var label = cells[i].querySelector('strong');
      var score = cells[i].querySelector('span');
      if (label) label.textContent = DOMAIN_ORDER[i];
      if (score) score.textContent = entry.score == null ? '-' : String(entry.score);
    }
  }

  function startCarousel(models) {
    var card = byId('hero-card');
    if (!card || !models.length) return;

    card.hidden = false;
    showCard(models[0]);
    if (models.length < 2) return;

    var index = 0;
    window.setInterval(function () {
      index = (index + 1) % models.length;
      var next = models[index];
      card.classList.add('rc-fade-out');
      window.setTimeout(function () {
        showCard(next);
        card.classList.remove('rc-fade-out');
        card.classList.add('rc-fade-in');
        window.setTimeout(function () {
          card.classList.remove('rc-fade-in');
        }, 400);
      }, 300);
    }, CAROUSEL_INTERVAL_MS);
  }

  function failClosed(error) {
    if (window.console && window.console.warn) {
      window.console.warn('approved artifact verification failed:', error);
    }
    /* The figures keep their placeholder dashes. One short, honest line
     * explains why, and the hero card stays hidden rather than showing a model
     * we cannot vouch for. */
    var notice = byId('ace-proof-note');
    if (notice) {
      notice.textContent = ARTIFACTS.UNAVAILABLE_MESSAGE +
        ' These figures are shown only when the published results verify against ' +
        'the approved manifest.';
      notice.hidden = false;
    }
    var card = byId('hero-card');
    if (card) card.hidden = true;
  }

  function init() {
    if (!byId('ace-count-systems') && !byId('hero-card')) return;

    ARTIFACTS.leaderboard('leaderboard_llm').then(function (verified) {
      var models = (verified.data.models || []).filter(function (model) {
        return model && model.bare;
      });
      renderCounts(ARTIFACTS.publicCounts(verified.data));

      var ranked = models.slice().sort(function (a, b) {
        return (b.bare.overall || 0) - (a.bare.overall || 0);
      });
      startCarousel(ranked.slice(0, CAROUSEL_SIZE));

      var notice = byId('ace-proof-note');
      if (notice) notice.hidden = true;
    }).catch(failClosed);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
