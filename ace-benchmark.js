/*
 * The public reports browser.
 *
 * Everything this page shows comes from `AceArtifacts`, which will not return a
 * byte until it has re-hashed the file against the approved manifest. There is
 * no other data source here: no direct fetch of the leaderboard, no fallback to
 * a cached copy, no inline numbers. If verification fails the page says
 * "Published reports unavailable." and shows nothing, because a report card we
 * cannot prove is worse than an empty page -- the reader cannot tell which one
 * they are looking at.
 *
 * Report downloads go through the same gate. There used to be a lead-capture
 * form in front of them that wrote a name, email and company to localStorage;
 * that is gone. Published means published, and the visitor's details are not
 * the price of reading an evaluation we call public.
 */
(function () {
  'use strict';

  var ARTIFACTS = window.AceArtifacts;

  var CATEGORY_ROLES = {
    llm: 'leaderboard_llm',
    agent: 'leaderboard_agent'
  };

  var AGENT_LABEL = {
    'agent-reference-compliant': 'Reference: well-governed agent',
    'agent-reference-reckless': 'Reference: ungoverned agent'
  };

  var VENDOR_WORDMARK = {
    OpenAI: 'OpenAI', Google: 'Google', Anthropic: 'Anthropic', xAI: 'xAI',
    Alibaba: 'Qwen', DeepSeek: 'DeepSeek', Meta: 'Meta', LogionOS: 'LogionOS'
  };

  /* Model label -> published report filename. A name here is only a *claim*
   * that a report exists; the manifest decides whether it does, and the button
   * is not rendered unless the manifest lists the file. */
  var REPORT_FILE = {
    'gpt-5.6-sol': 'ACE_Evaluation_Report_GPT-5.6-Sol.pdf',
    'kimi-k3': 'ACE_Evaluation_Report_Kimi-K3.pdf',
    'gpt-5.5': 'ACE_Evaluation_Report_GPT-5.5.pdf',
    'gemini-3.1-pro': 'ACE_Evaluation_Report_Gemini-3.1-Pro.pdf',
    'opus-4.8': 'ACE_Evaluation_Report_Opus-4.8.pdf',
    'fable-5': 'ACE_Evaluation_Report_Fable-5.pdf',
    'gpt-4o': 'ACE_Evaluation_Report_GPT-4o.pdf',
    'grok-4.3': 'ACE_Evaluation_Report_Grok-4.3.pdf',
    'qwen3.7-max': 'ACE_Evaluation_Report_Qwen3.7-Max.pdf',
    'deepseek-v4-pro': 'ACE_Evaluation_Report_DeepSeek-V4-Pro.pdf',
    'llama-4-maverick': 'ACE_Evaluation_Report_Llama-4-Maverick.pdf'
  };

  var DISPLAY_NAME = {
    'gpt-5.6-sol': 'GPT-5.6 Sol',
    'kimi-k3': 'Kimi K3',
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

  var DOMAIN_DETAIL = {
    DP: { name: 'Data Protection', desc: 'Measures whether the system leaks or mishandles personal data, identifiers, sensitive records, or transfer obligations.', controls: ['DP-1 PII leakage', 'DP-2 minimization and lawful handling', 'DP-3 cross-border transfer guidance'] },
    RF: { name: 'Regulatory Fitness', desc: 'Measures whether responses stay current and jurisdiction-specific under real regulatory obligations.', controls: ['RF-1 obligation accuracy', 'RF-2 regulatory currency', 'RF-3 cross-jurisdiction consistency'] },
    MR: { name: 'Misuse Resistance', desc: 'Measures resistance to prohibited use, manipulation, fraud assistance, and unsafe handling of vulnerable users.', controls: ['MR-1 prohibited use refusal', 'MR-2 fraud and manipulation resistance', 'MR-3 dual-use decomposition', 'MR-4 vulnerable-user safety'] },
    AG: { name: 'Agentic Governance', desc: 'Measures whether tool-using agents stay inside permission, escalation, exfiltration, and cost boundaries.', controls: ['AG-1 destructive action control', 'AG-2 permission and exfiltration control', 'AG-3 data egress resistance', 'AG-4 escalation behavior', 'AG-5 resource and sub-agent limits'] },
    TA: { name: 'Transparency and Auditability', desc: 'Measures disclosure, uncertainty handling, citation fidelity, and resistance to audit-record falsification.', controls: ['TA-1 AI identity and source disclosure', 'TA-2 audit and citation integrity', 'TA-3 uncertainty disclosure'] },
    CI: { name: 'Content Integrity', desc: 'Measures copyright, provenance, likeness, and impersonation risks in generated content.', controls: ['CI-1 provenance handling', 'CI-2 copyright and licensing', 'CI-3 likeness and impersonation'] }
  };

  var state = {
    category: 'llm',
    models: [],
    manifest: null,
    vendor: null,
    selected: null,
    query: ''
  };

  /* -- DOM building -------------------------------------------------------
   *
   * Built with `createElement` and `textContent` rather than HTML strings.
   * These values come out of a JSON file, and the previous version escaped them
   * by hand with a four-character replace: correct as written, but one missed
   * call away from injection. Nodes cannot be escaped wrongly.
   */

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = String(text);
    return node;
  }

  function replaceChildren(node, children) {
    if (!node) return;
    node.textContent = '';
    if (!children) return;
    var list = Array.isArray(children) ? children : [children];
    for (var i = 0; i < list.length; i += 1) {
      if (list[i]) node.appendChild(list[i]);
    }
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function gradeClass(grade) {
    return 'grade-' + String(grade || '').toLowerCase();
  }

  function verdictClass(verdict) {
    var text = String(verdict || '');
    if (text.indexOf('Conditional') !== -1) return 'verdict-conditional';
    if (text.indexOf('Ready') !== -1 && text.indexOf('Not') === -1) return 'verdict-ready';
    return 'verdict-notready';
  }

  function displayLabel(model) {
    if (state.category === 'agent') return AGENT_LABEL[model.label] || model.label;
    return DISPLAY_NAME[model.label] || model.label;
  }

  function companyOf(model) {
    if (state.category === 'agent') return 'LogionOS';
    var vendor = model.vendor || 'Unknown';
    return vendor.indexOf('OpenAI') === 0 ? 'OpenAI' : vendor;
  }

  function wordmark(vendor) {
    return VENDOR_WORDMARK[vendor] || vendor;
  }

  function matchesQuery(model) {
    var query = state.query.trim().toLowerCase();
    if (!query) return true;
    return [displayLabel(model), companyOf(model), model.label]
      .join(' ').toLowerCase().indexOf(query) !== -1;
  }

  function unique(values) {
    var seen = Object.create(null);
    var out = [];
    for (var i = 0; i < values.length; i += 1) {
      if (!seen[values[i]]) {
        seen[values[i]] = true;
        out.push(values[i]);
      }
    }
    return out;
  }

  /* -- failure ------------------------------------------------------------ */

  function failClosed(error) {
    /* One message for every verification failure. Which check failed is a
     * detail for whoever is debugging, not for a visitor deciding whether to
     * trust a number. */
    if (window.console && window.console.warn) {
      window.console.warn('approved artifact verification failed:', error);
    }
    var notice = el('div', 'not-published');
    notice.appendChild(el('strong', null, ARTIFACTS.UNAVAILABLE_MESSAGE));
    notice.appendChild(el('p', null,
      'We publish evaluation results only when we can verify that the files ' +
      'being served are the approved ones. That check did not pass just now, so ' +
      'nothing is shown here. Please reload; if this persists, contact ' +
      'info@logionace.com.'));
    replaceChildren(byId('model-grid'), notice);
    replaceChildren(byId('company-list'), null);
    replaceChildren(byId('report-panel'),
      el('div', 'empty-report', ARTIFACTS.UNAVAILABLE_MESSAGE));
    var title = byId('model-panel-title');
    if (title) title.textContent = 'Reports';
  }

  /* -- rendering ---------------------------------------------------------- */

  function renderAgentPlaceholder() {
    replaceChildren(byId('company-list'), null);
    byId('model-panel-title').textContent = 'Agent reports';

    var block = el('div', 'not-published');
    block.appendChild(el('strong', null, 'Coming Q3 2026'));
    block.appendChild(el('p', null,
      'Agent evaluations are conducted under the ACE Agentic Governance track ' +
      '(AG-1 through AG-5), including tool-call safety, permission boundaries, ' +
      'and autonomous action controls.'));
    var request = el('p', null, 'Public agent reports will be listed here as ' +
      'evaluations are completed. ');
    var link = el('a', null, 'Request an agent evaluation');
    link.href = 'evaluation.html#contact';
    request.appendChild(link);
    block.appendChild(request);
    var disclosure = el('p', 'not-published-note',
      'Reference agents developed by LogionOS, Inc. are evaluated under our ');
    var policy = el('a', null, 'affiliated system disclosure policy');
    policy.href = 'trust.html';
    disclosure.appendChild(policy);
    disclosure.appendChild(document.createTextNode('.'));
    block.appendChild(disclosure);

    replaceChildren(byId('model-grid'), block);
    replaceChildren(byId('report-panel'),
      el('div', 'empty-report', 'Select an agent evaluation to view its report card.'));
  }

  function companyTile(vendor, count) {
    var button = el('button', 'company-tile' + (vendor === state.vendor ? ' active' : ''));
    button.type = 'button';
    button.appendChild(el('span', 'vendor-logo wordmark', wordmark(vendor)));
    var text = el('span');
    text.appendChild(el('strong', null, vendor));
    text.appendChild(el('em', null, count + ' tested'));
    button.appendChild(text);
    button.addEventListener('click', function () {
      state.vendor = vendor;
      state.selected = null;
      render();
    });
    return button;
  }

  function modelCard(model) {
    var active = state.selected && state.selected.label === model.label;
    var button = el('button', 'model-card' + (active ? ' active' : ''));
    button.type = 'button';
    button.setAttribute('data-model-label', model.label);
    button.appendChild(el('span', 'model-logo wordmark', wordmark(companyOf(model))));
    button.appendChild(el('strong', null, displayLabel(model)));
    button.appendChild(el('span', null, companyOf(model)));
    var meta = el('div', 'model-meta');
    meta.appendChild(el('em', null, model.bare.overall));
    meta.appendChild(el('i', gradeClass(model.bare.grade), model.bare.grade));
    button.appendChild(meta);
    button.addEventListener('click', function () {
      state.selected = model;
      render();
    });
    return button;
  }

  function domainPill(key, entry) {
    var detail = DOMAIN_DETAIL[key] ||
      { name: key, desc: 'Domain details pending.', controls: [] };
    var pill = el('span', 'domain-pop');
    pill.setAttribute('tabindex', '0');
    pill.setAttribute('aria-label', detail.name);
    pill.appendChild(el('strong', null, key));
    pill.appendChild(el('span', 'domain-score', entry.score));
    pill.appendChild(el('em', null, '?'));

    var tooltip = el('span', 'domain-tooltip');
    tooltip.setAttribute('role', 'tooltip');
    tooltip.appendChild(el('b', null, detail.name));
    tooltip.appendChild(el('small', null, detail.desc));
    var controls = el('i');
    for (var i = 0; i < detail.controls.length; i += 1) {
      if (i) controls.appendChild(document.createElement('br'));
      controls.appendChild(document.createTextNode(detail.controls[i]));
    }
    tooltip.appendChild(controls);
    pill.appendChild(tooltip);
    return pill;
  }

  function downloadButton(model) {
    var filename = REPORT_FILE[model.label];
    var path = filename ? 'reports/' + filename : '';

    /* Not "does the file exist on the server" but "is this file in the approved
     * manifest". An unlisted PDF is not offered, however present it is. */
    if (!path || !ARTIFACTS.hasReport(state.manifest, path)) {
      var request = el('a', 'btn primary', 'Request report');
      request.href = 'evaluation.html#contact';
      return request;
    }

    var button = el('button', 'btn primary', 'Download report');
    button.type = 'button';
    var note = el('p', 'field-help');
    note.hidden = true;

    button.addEventListener('click', function () {
      button.disabled = true;
      button.textContent = 'Verifying...';
      note.hidden = false;
      note.textContent = 'Checking this file against the approved manifest.';

      ARTIFACTS.downloadReport(path, filename).then(function () {
        button.disabled = false;
        button.textContent = 'Download report';
        note.textContent = 'Verified against the approved manifest and downloaded.';
      }).catch(function (error) {
        if (window.console && window.console.warn) {
          window.console.warn('report verification failed:', error);
        }
        button.disabled = true;
        button.textContent = 'Download unavailable';
        note.textContent = ARTIFACTS.UNAVAILABLE_MESSAGE +
          ' This file did not match the approved manifest, so we have not served it.';
      });
    });

    var wrapper = document.createDocumentFragment();
    wrapper.appendChild(button);
    wrapper.appendChild(note);
    return wrapper;
  }

  function renderReport() {
    var panel = byId('report-panel');
    if (!state.selected) {
      replaceChildren(panel,
        el('div', 'empty-report', 'Select a model to view its report card.'));
      return;
    }

    var model = state.selected;
    var bare = model.bare;
    var card = el('div', 'report-card-detail');
    card.appendChild(el('p', 'eyebrow', 'Report Card'));

    var top = el('div', 'report-top');
    top.appendChild(el('span', 'vendor-logo wordmark large', wordmark(companyOf(model))));
    var heading = el('div');
    heading.appendChild(el('p', 'eyebrow', companyOf(model)));
    heading.appendChild(el('h2', null, displayLabel(model)));
    top.appendChild(heading);
    card.appendChild(top);

    var scores = el('div', 'score-block');
    var overall = el('div');
    overall.appendChild(el('span', null, 'Overall'));
    overall.appendChild(el('strong', null, bare.overall));
    var grade = el('div');
    grade.appendChild(el('span', null, 'Grade'));
    grade.appendChild(el('strong', gradeClass(bare.grade), bare.grade));
    scores.appendChild(overall);
    scores.appendChild(grade);
    card.appendChild(scores);

    card.appendChild(el('div', 'verdict-line ' + verdictClass(bare.verdict), bare.verdict));

    var facts = el('div', 'report-facts');
    var evaluated = model.evaluated_at
      ? new Date(model.evaluated_at).toISOString().slice(0, 10)
      : '2026-06';
    [['Evaluated', evaluated],
     ['Critical exceptions', bare.critical_exception_count],
     ['Helpfulness', bare.helpfulness_retention == null
        ? '-' : bare.helpfulness_retention + '%']
    ].forEach(function (pair) {
      var fact = el('span', null, pair[0] + ': ');
      fact.appendChild(el('strong', null, pair[1]));
      facts.appendChild(fact);
    });
    card.appendChild(facts);

    if (bare.domains) {
      var mini = el('div', 'domain-mini');
      Object.keys(bare.domains).forEach(function (key) {
        mini.appendChild(domainPill(key, bare.domains[key] || {}));
      });
      card.appendChild(mini);
    }

    card.appendChild(el('div', 'risk-note',
      'Evaluation focuses on business risk before enterprise AI deployment: data ' +
      'leakage, regulatory failure, unsafe agent actions, transparency gaps, and ' +
      'content integrity issues.'));

    var actions = el('div', 'report-actions');
    actions.appendChild(downloadButton(model));
    var whitepaper = el('a', 'btn outline', 'Read whitepaper');
    whitepaper.href = 'whitepaper.html';
    actions.appendChild(whitepaper);
    card.appendChild(actions);

    card.appendChild(el('p', 'report-note',
      'Report cards are public. Full evaluation reports include scores, evidence ' +
      'packages, control-level analysis, and remediation guidance. Every file ' +
      'offered here is verified against the approved publication manifest before ' +
      'it is served.'));

    replaceChildren(panel, card);
  }

  function render() {
    if (state.category === 'agent') {
      renderAgentPlaceholder();
      return;
    }

    var visible = state.models.filter(matchesQuery);
    var vendors = unique(visible.map(companyOf));

    if (vendors.indexOf(state.vendor) === -1) {
      state.vendor = vendors[0] || null;
      state.selected = null;
    }

    if (!vendors.length) {
      replaceChildren(byId('company-list'),
        el('div', 'not-published', 'No reports match this search.'));
      byId('model-panel-title').textContent = 'Models';
      replaceChildren(byId('model-grid'), null);
      replaceChildren(byId('report-panel'),
        el('div', 'empty-report', 'Try another company initial or model name.'));
      return;
    }

    var tiles = vendors.map(function (vendor) {
      return companyTile(vendor, visible.filter(function (model) {
        return companyOf(model) === vendor;
      }).length);
    });
    replaceChildren(byId('company-list'), tiles);

    var rows = visible.filter(function (model) {
      return companyOf(model) === state.vendor;
    });
    if (!state.selected || !rows.some(function (model) {
      return model.label === state.selected.label;
    })) {
      state.selected = rows[0] || null;
    }

    byId('model-panel-title').textContent = 'Models by ' + state.vendor;
    replaceChildren(byId('model-grid'), rows.map(modelCard));
    renderReport();
  }

  function loadCategory(category) {
    state.category = category;
    state.query = '';
    var search = byId('report-search');
    if (search) search.value = '';

    var tabs = document.querySelectorAll('.category-tab');
    for (var i = 0; i < tabs.length; i += 1) {
      var isActive = tabs[i].getAttribute('data-category') === category;
      tabs[i].classList.toggle('active', isActive);
      tabs[i].setAttribute('aria-selected', isActive ? 'true' : 'false');
    }

    replaceChildren(byId('model-grid'),
      el('div', 'not-published', 'Verifying published reports...'));

    return ARTIFACTS.leaderboard(CATEGORY_ROLES[category]).then(function (verified) {
      state.manifest = verified.manifest;
      state.models = (verified.data.models || [])
        .filter(function (model) { return model && model.bare; })
        .sort(function (a, b) {
          return (b.bare.overall || 0) - (a.bare.overall || 0);
        });
      state.vendor = unique(state.models.map(companyOf))[0] || null;
      state.selected = null;
      render();
    }).catch(function (error) {
      state.models = [];
      state.manifest = null;
      failClosed(error);
    });
  }

  function init() {
    if (!byId('model-grid')) return;

    var tabs = document.querySelectorAll('.category-tab');
    for (var i = 0; i < tabs.length; i += 1) {
      tabs[i].addEventListener('click', function () {
        loadCategory(this.getAttribute('data-category'));
      });
    }

    var search = byId('report-search');
    if (search) {
      search.addEventListener('input', function (event) {
        state.query = event.target.value;
        render();
      });
    }

    loadCategory('llm');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
