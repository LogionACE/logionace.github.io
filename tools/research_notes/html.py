"""Render one validated ACE Research Note as a static editorial webpage."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Iterable

from tools.render_customer_pages import chrome
from tools.research_notes.model import note_slug, validate_note


ROOT = Path(__file__).resolve().parents[2]
CONTROL_LABELS = {
    "DRAFT-DAC-01": "Delegated authority containment",
    "DRAFT-TDA-01": "Tool & data authorization",
    "DRAFT-DEC-01": "Decision evidence completeness",
    "DRAFT-AID-01": "AI identity attribution",
    "DRAFT-HITL-01": "Human approval integrity",
    "MR-3": "Misuse resistance",
    "TA-3": "Uncertainty disclosure",
    "DP-2": "Data handling safeguards",
    "AG-5": "Cost and loop containment",
    "CI-2": "Content integrity",
    "RF": "Regulatory fitness",
}


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _assetize(fragment: str, prefix: str) -> str:
    if not prefix:
        return fragment

    def replace(match: re.Match[str]) -> str:
        attribute, target = match.groups()
        if target.startswith(("http://", "https://", "mailto:", "tel:", "#", "/")):
            return match.group(0)
        return f'{attribute}="{prefix}{target}"'

    return re.sub(r'(href|src)="([^"]+)"', replace, fragment)


def _citations(text: str) -> str:
    escaped = _e(text)
    return re.sub(
        r"\[(R\d+)\]",
        lambda match: (
            f'<a class="rn-cite" href="#ref-{match.group(1)}">'
            f"[{match.group(1)}]</a>"
        ),
        escaped,
    )


def _paragraphs(claims: Iterable[dict[str, Any]]) -> str:
    return "\n".join(f"          <p>{_citations(item['text'])}</p>" for item in claims)


def _list(items: Iterable[str], *, ordered: bool = False, class_name: str = "") -> str:
    tag = "ol" if ordered else "ul"
    class_attr = f' class="{class_name}"' if class_name else ""
    body = "\n".join(f"            <li>{_e(item)}</li>" for item in items)
    return f"          <{tag}{class_attr}>\n{body}\n          </{tag}>"


def _metadata(note: dict[str, Any]) -> str:
    controls = [note["primary_control"], *note.get("secondary_controls", [])]
    control_names = " · ".join(CONTROL_LABELS.get(item, item) for item in controls)
    control_ids = " · ".join(
        f'<span class="rn-control-id">{_e(item)}</span>' for item in controls
    )
    return f"""      <dl class="rn-metadata">
        <div><dt>Published</dt><dd>{_e(note["date"])}</dd></div>
        <div><dt>Version</dt><dd>{_e(note["version"])}</dd></div>
        <div><dt>Author</dt><dd>{_e(note["author"])}</dd></div>
        <div class="rn-metadata-scope">
          <dt>Research scope</dt>
          <dd>{_e(control_names)}<small>{control_ids}</small></dd>
        </div>
      </dl>"""


def _source_rows(note: dict[str, Any]) -> str:
    rows = []
    for source in note["parts"]["problem"]["sources"]:
        rows.append(
            f"""          <div class="rn-source">
            <span>{_e(source["kind"])}</span>
            <p>{_citations(source["text"])}</p>
          </div>"""
        )
    return "\n".join(rows)


def _mitigation_rows(note: dict[str, Any]) -> str:
    rows = []
    for layer in note["parts"]["mitigation"]["layers"]:
        label = layer["evidence"].replace("-", " ")
        rows.append(
            f"""          <div class="rn-mitigation-row">
            <h3>{_e(layer["name"])}</h3>
            <span class="rn-evidence rn-evidence-{_e(layer["evidence"])}">{_e(label)}</span>
            <p>{_citations(layer["text"])}</p>
          </div>"""
        )
    return "\n".join(rows)


def _directions(items: list[dict[str, Any]]) -> str:
    rows = []
    for index, item in enumerate(items, start=1):
        label = item["evidence"].replace("-", " ")
        rows.append(
            f"""          <li>
            <span class="rn-direction-number">{index:02d}</span>
            <div>
              <span class="rn-evidence rn-evidence-{_e(item["evidence"])}">{_e(label)}</span>
              <p>{_citations(item["text"])}</p>
            </div>
          </li>"""
        )
    return "\n".join(rows)


def _references(note: dict[str, Any]) -> str:
    rows = []
    for item in note["references"]:
        rows.append(
            f"""          <li id="ref-{_e(item["id"])}">
            <span class="rn-ref-id">[{_e(item["id"])}]</span>
            <div>
              <a href="{_e(item["url"])}" rel="noopener">{_e(item["title"])}</a>
              <p>{_e(item["publication_status"])} · {_e(item["source_type"])}</p>
            </div>
          </li>"""
        )
    return "\n".join(rows)


def _print_cover(note: dict[str, Any], asset_prefix: str) -> str:
    controls = [note["primary_control"], *note.get("secondary_controls", [])]
    control_names = " · ".join(CONTROL_LABELS.get(item, item) for item in controls)
    return f"""  <section class="rn-print-cover" aria-hidden="true">
    <div class="rn-print-arcs"></div>
    <div class="rn-print-top">
      <div class="rn-print-brand">
        <img src="{asset_prefix}logo.svg" alt="">
        <p class="rn-print-brand-name">Logion<span>ACE</span></p>
      </div>
      <p class="rn-print-series">ACE Research</p>
    </div>
    <div class="rn-print-middle">
      <p class="rn-print-type">ACE Research Note</p>
      <p class="rn-print-heading">{_e(note["title"])}</p>
      <p class="rn-print-version">{_e(note["id"])} · Version {_e(note["version"])}</p>
      <p class="rn-print-preview">Template Preview</p>
    </div>
    <dl class="rn-print-meta">
      <div><dt>Author</dt><dd>{_e(note["author"])}</dd></div>
      <div><dt>Published</dt><dd>{_e(note["date"])}</dd></div>
      <div><dt>Version</dt><dd>{_e(note["version"])}</dd></div>
      <div class="rn-print-meta-scope"><dt>Research scope</dt><dd>{_e(control_names)}</dd></div>
    </dl>
    <p class="rn-print-footer">LogionACE — powered by LogionOS &nbsp;|&nbsp; © 2026 LogionOS &nbsp;|&nbsp; Published as part of the ACE Research series.</p>
  </section>"""


def render_note_html(
    note: dict[str, Any],
    *,
    preview: bool = False,
    asset_prefix: str = "../",
) -> str:
    validate_note(note)
    slug = note_slug(note)
    canonical = f"https://logionace.com/research-notes/{slug}.html"
    nav, footer = chrome()
    nav = _assetize(nav, asset_prefix)
    footer = _assetize(footer, asset_prefix)
    problem = note["parts"]["problem"]
    mitigation = note["parts"]["mitigation"]
    agenda = note["parts"]["research_agenda"]
    description = problem["body"][0]["text"].split(" [", 1)[0]
    metadata = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "identifier": note["id"],
        "name": note["title"],
        "headline": note["title"],
        "datePublished": note["date"],
        "version": note["version"],
        "author": {"@type": "Person", "name": note["author"]},
        "publisher": {"@type": "Organization", "name": "ACE Research"},
        "url": canonical,
        "isPartOf": "ACE Research Notes",
        "description": description,
    }
    status = "Template preview" if preview else "Published"
    robots = "noindex, nofollow" if preview else "index, follow"
    corrections = (
        _list(note["corrections"])
        if note["corrections"]
        else '          <p class="rn-empty-record">No corrections recorded.</p>'
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(note["title"])} | ACE Research</title>
  <meta name="description" content="{_e(description)}">
  <meta name="robots" content="{robots}">
  <meta property="og:title" content="{_e(note["title"])} | ACE Research">
  <meta property="og:description" content="{_e(description)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical}">
  <link rel="canonical" href="{canonical}">
  <link rel="icon" href="{asset_prefix}favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{asset_prefix}style.css">
  <script type="application/ld+json">
{json.dumps(metadata, ensure_ascii=False, indent=2)}
  </script>
</head>
<body class="research-note-page" data-note-id="{_e(note["id"])}">
  <a class="skip-link" href="#note-content">Skip to note</a>
{nav}
{_print_cover(note, asset_prefix)}
  <main id="note-content">
    <header class="rn-header">
      <p class="rn-series">ACE Research Note · {_e(note["id"])}</p>
      <h1>{_e(note["title"])}</h1>
      <p class="rn-preview-state">{status}</p>
{_metadata(note)}
      <div class="rn-actions">
        <a class="btn primary" href="{_e(note["id"])}.pdf">Download PDF</a>
        <button type="button" data-copy-citation class="btn outline">Copy citation</button>
      </div>
    </header>

    <div class="rn-layout">
      <nav class="rn-toc" aria-label="In this note">
        <p>In this note</p>
        <a href="#problem-definition">I · Problem</a>
        <a href="#mitigation-direction">II · Mitigation</a>
        <a href="#research-agenda">III · Research</a>
        <a href="#references">References</a>
      </nav>

      <aside class="rn-record">
        <p class="rn-record-label">Publication record</p>
        <dl>
          <div><dt>Status</dt><dd>{status}</dd></div>
          <div><dt>Version</dt><dd>{_e(note["version"])}</dd></div>
          <div>
            <dt>Primary research area</dt>
            <dd>
              {_e(CONTROL_LABELS.get(note["primary_control"], note["primary_control"]))}
              <span class="rn-control-id">{_e(note["primary_control"])}</span>
            </dd>
          </div>
        </dl>
        <a href="{_e(note["id"])}.pdf">Download PDF <span>↘</span></a>
        <p class="rn-citation-text" tabindex="-1">{_e(note["recommended_citation"])}</p>
      </aside>

      <article class="rn-article">
        <section id="problem-definition">
          <p class="rn-part">Part I</p>
          <h2>Problem Definition</h2>
          <div class="rn-source-list">
{_source_rows(note)}
          </div>
{_paragraphs(problem["body"])}
          <h3 class="rn-subheading">Real-world impact</h3>
{_list(problem["impact"])}
        </section>

        <section id="mitigation-direction">
          <p class="rn-part">Part II</p>
          <h2>Mitigation Direction</h2>
          <div class="rn-mitigation-grid">
{_mitigation_rows(note)}
          </div>

          <h3 class="rn-subheading">Research-backed direction</h3>
          <ol class="rn-directions">
{_directions(mitigation["direction"])}
          </ol>

          <h3 class="rn-subheading">LogionOS engineering mapping</h3>
          <p class="rn-boundary-note">Implementation hypotheses only. No production validation is claimed.</p>
          <ol class="rn-directions">
{_directions(mitigation["logionos_direction"])}
          </ol>

          <div class="rn-technical-callout" id="acceptance-test">
            <p class="rn-callout-label">ACE Acceptance Test</p>
            <h3>{_e(mitigation["acceptance_test"]["objective"])}</h3>
            <h4>Setup</h4>
            <p>{_e(mitigation["acceptance_test"]["setup"])}</p>
            <h4>Procedure</h4>
{_list(mitigation["acceptance_test"]["procedure"], ordered=True)}
            <h4>Pass criteria</h4>
{_list(mitigation["acceptance_test"]["pass_criteria"])}
          </div>

          <div class="rn-technical-callout" id="required-evidence">
            <p class="rn-callout-label">Required Evidence</p>
            <h3>What the tested configuration must produce</h3>
{_list(mitigation["required_evidence"], class_name="rn-evidence-list")}
          </div>
        </section>

        <section id="research-agenda">
          <p class="rn-part">Part III</p>
          <h2>Consequences and Research Agenda</h2>
          <h3 class="rn-subheading">Consequences</h3>
{_list(agenda["consequences"])}
          <h3 class="rn-subheading">Second-order effects</h3>
{_list(agenda["second_order_effects"])}
          <h3 class="rn-subheading">Limitations</h3>
{_list(agenda["limitations"])}
          <h3 class="rn-subheading">Open research questions</h3>
{_list(agenda["questions"], ordered=True, class_name="rn-questions")}
        </section>

        <section id="references">
          <p class="rn-part">Sources</p>
          <h2>References</h2>
          <ol class="rn-references">
{_references(note)}
          </ol>
        </section>

        <section id="publication-record">
          <p class="rn-part">Record</p>
          <h2>Publication Record</h2>
          <h3 class="rn-subheading">Recommended citation</h3>
          <p class="rn-citation-text" tabindex="-1">{_e(note["recommended_citation"])}</p>
          <h3 class="rn-subheading">Corrections</h3>
{corrections}
          <h3 class="rn-subheading">Organizational disclosure</h3>
          <p>{_e(note["organizational_disclosure"])}</p>
          <h3 class="rn-subheading">Evidence boundary</h3>
          <p>{_e(note["evidence_boundary"])}</p>
        </section>
      </article>
    </div>
  </main>
{footer}
  <script src="{asset_prefix}research-note.js"></script>
  <script src="{asset_prefix}ace-nav.js"></script>
</body>
</html>
"""
