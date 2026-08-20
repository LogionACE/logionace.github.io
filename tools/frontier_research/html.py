"""Render ACE Frontier Research as a static editorial webpage."""

from __future__ import annotations

import html
import json
import re
from datetime import date
from typing import Any, Dict, Iterable, List

from tools.frontier_research.model import validate_ledger, validate_report
from tools.render_customer_pages import chrome


CLASSIFICATION_LABELS = {
    "observed-evidence": "Observed Evidence",
    "emerging-problem": "Emerging Problem",
    "ace-hypothesis": "ACE Hypothesis",
    "open-questions": "Open Questions",
    "analysis": "Analysis",
}


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _date(value: str) -> str:
    parsed = date.fromisoformat(value)
    return f"{parsed.day} {parsed.strftime('%B %Y')}"


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
            f'<a class="afr-cite" href="#ref-{match.group(1)}">'
            f"[{match.group(1)}]</a>"
        ),
        escaped,
    )


def _figure(report: Dict[str, Any], figure_id: str, asset_prefix: str) -> str:
    figure = next(item for item in report["figures"] if item["id"] == figure_id)
    return f"""        <figure class="afr-figure">
          <img src="{asset_prefix}frontier-research/{_e(figure["path"])}" alt="{_e(figure["alt"])}">
          <figcaption><strong>{_e(figure["title"])}</strong>{_e(figure.get("caption", ""))}</figcaption>
        </figure>"""


def _blocks(
    report: Dict[str, Any],
    blocks: Iterable[Dict[str, Any]],
    asset_prefix: str,
) -> str:
    rendered: List[str] = []
    for block in blocks:
        if block.get("type") == "paragraph":
            rendered.append(f"        <p>{_citations(block['text'])}</p>")
        elif block.get("type") == "figure":
            rendered.append(_figure(report, block["figure_id"], asset_prefix))
    return "\n".join(rendered)


def _sections(report: Dict[str, Any], asset_prefix: str) -> str:
    rendered = []
    for section in report["sections"]:
        label = CLASSIFICATION_LABELS[section["classification"]]
        rendered.append(
            f"""      <section class="afr-section" id="section-{_e(section["id"])}">
        <p class="afr-classification afr-classification-{_e(section["classification"])}">{_e(label)}</p>
        <h2>{_e(section["title"])}</h2>
{_blocks(report, section["blocks"], asset_prefix)}
      </section>"""
        )
    return "\n".join(rendered)


def _toc(report: Dict[str, Any]) -> str:
    return "\n".join(
        f'        <a href="#section-{_e(section["id"])}">{_e(section["title"])}</a>'
        for section in report["sections"]
    )


def _references(report: Dict[str, Any]) -> str:
    rows = []
    for reference in report["references"]:
        details = " · ".join(
            item
            for item in (
                reference.get("authors"),
                reference.get("publisher"),
                reference.get("date"),
            )
            if item
        )
        rows.append(
            f"""        <li id="ref-{_e(reference["id"])}">
          <span class="afr-ref-id">[{_e(reference["id"])}]</span>
          <div>
            <a href="{_e(reference["url"])}" rel="noopener">{_e(reference["title"])}</a>
            <p class="afr-ref-details">{_e(details)}</p>
            <a class="afr-ref-url" href="{_e(reference["url"])}" rel="noopener">{_e(reference["url"])}</a>
            <p class="afr-ref-status">{_e(reference["publication_status"])} · {_e(reference["source_type"])}</p>
          </div>
        </li>"""
        )
    return "\n".join(rows)


def _prediction_ledger(
    report: Dict[str, Any], ledger: Dict[str, Any]
) -> str:
    rows = []
    selected = {
        prediction["id"]: prediction
        for prediction in ledger["predictions"]
        if prediction["report_id"] == report["id"]
    }
    for prediction_id in report["prediction_ids"]:
        prediction = selected[prediction_id]
        falsifiers = "".join(
            f"<li>{_e(item)}</li>"
            for item in prediction["falsification_signals"]
        )
        rows.append(
            f"""        <article class="afr-prediction" id="prediction-{_e(prediction_id)}">
          <div class="afr-prediction-meta">
            <span>{_e(prediction_id)}</span>
            <span>{_e(prediction["confidence"])} confidence</span>
            <span>6 / 12 / 24 month review</span>
          </div>
          <p>{_e(prediction["statement"])}</p>
          <details>
            <summary>Falsification signals</summary>
            <ul>{falsifiers}</ul>
          </details>
        </article>"""
        )
    return "\n".join(rows)


def _print_cover(report: Dict[str, Any], asset_prefix: str) -> str:
    return f"""  <section class="afr-print-cover" aria-hidden="true">
    <div class="afr-print-arcs"></div>
    <div class="afr-print-top">
      <div class="afr-print-brand">
        <img src="{asset_prefix}logo.svg" alt="">
        <p>Logion<span>ACE</span></p>
      </div>
      <p class="afr-print-series">Autonomous Trust Systems</p>
    </div>
    <div class="afr-print-middle">
      <p class="afr-print-type">ACE Frontier Research</p>
      <p class="afr-print-heading">{_e(report["title"])}</p>
      <p class="afr-print-subtitle">{_e(report["subtitle"])}</p>
      <p class="afr-print-version">{_e(report["id"])} · Version {_e(report["version"])}</p>
      <p class="afr-print-preview">Draft for review</p>
    </div>
    <dl class="afr-print-meta">
      <div><dt>Author</dt><dd>{_e(", ".join(report["authors"]))}</dd></div>
      <div aria-label="Evidence cutoff {_e(_date(report["evidence_cutoff"]))}"><dt>Evidence cutoff</dt><dd>{_e(_date(report["evidence_cutoff"]))}</dd></div>
      <div><dt>Research status</dt><dd>{_e(report["research_status"])}</dd></div>
      <div><dt>Confidence</dt><dd>{_e(report["confidence"])}</dd></div>
    </dl>
    <p class="afr-print-footer">LogionACE — powered by LogionOS &nbsp;|&nbsp; © 2026 LogionOS &nbsp;|&nbsp; ACE Frontier Research</p>
  </section>"""


def render_report_html(
    report: Dict[str, Any],
    ledger: Dict[str, Any],
    *,
    preview: bool = False,
    asset_prefix: str = "../",
) -> str:
    validate_report(report)
    validate_ledger(report, ledger)
    nav, footer = chrome()
    nav = _assetize(nav, asset_prefix)
    footer = _assetize(footer, asset_prefix)
    canonical = (
        f"https://logionace.com/frontier-research/{report['id'].lower()}.html"
    )
    description = report["abstract"]["text"].split(" [", 1)[0]
    status = (
        "Draft for review — not published"
        if preview
        else report["status"].title()
    )
    robots = "noindex, nofollow" if preview else "index, follow"
    metadata = {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        "identifier": report["id"],
        "name": f"{report['title']}: {report['subtitle']}",
        "headline": report["title"],
        "version": report["version"],
        "author": [
            {"@type": "Person", "name": author}
            for author in report["authors"]
        ],
        "publisher": {"@type": "Organization", "name": "ACE Research"},
        "isPartOf": "ACE Frontier Research",
        "description": description,
        "url": canonical,
    }
    if report["publication_date"]:
        metadata["datePublished"] = report["publication_date"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(report["title"])} | ACE Frontier Research</title>
  <meta name="description" content="{_e(description)}">
  <meta name="robots" content="{robots}">
  <meta property="og:title" content="{_e(report["title"])} | ACE Frontier Research">
  <meta property="og:description" content="{_e(description)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical}">
  <link rel="canonical" href="{canonical}">
  <link rel="icon" href="{asset_prefix}favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{asset_prefix}style.css">
  <link rel="stylesheet" href="{asset_prefix}frontier-research.css?v={_e(report["version"])}">
  <script type="application/ld+json">
{json.dumps(metadata, ensure_ascii=False, indent=2)}
  </script>
</head>
<body class="frontier-research-page" data-report-id="{_e(report["id"])}">
  <a class="skip-link" href="#afr-content">Skip to research</a>
{nav}
{_print_cover(report, asset_prefix)}
  <main id="afr-content">
    <header class="afr-header">
      <p class="afr-series">ACE Frontier Research · {_e(report["id"])}</p>
      <h1>{_e(report["title"])}</h1>
      <p class="afr-subtitle">{_e(report["subtitle"])}</p>
      <p class="afr-preview-state">{_e(status)}</p>
      <dl class="afr-metadata">
        <div><dt>Evidence cutoff</dt><dd>{_e(_date(report["evidence_cutoff"]))}</dd></div>
        <div><dt>Research status</dt><dd>{_e(report["research_status"])}</dd></div>
        <div><dt>Confidence</dt><dd>{_e(report["confidence"])}</dd></div>
        <div><dt>Author</dt><dd>{_e(", ".join(report["authors"]))}</dd></div>
        <div><dt>Version</dt><dd>{_e(report["version"])}</dd></div>
      </dl>
      <div class="afr-actions">
        <a class="btn primary" href="{_e(report["id"])}.pdf">Download PDF</a>
        <button type="button" data-copy-citation class="btn outline">Copy citation</button>
      </div>
    </header>

    <div class="afr-layout">
      <nav class="afr-toc" aria-label="In this report">
        <p>In this report</p>
{_toc(report)}
        <a href="#prediction-ledger">Ledger</a>
        <a href="#references">References</a>
      </nav>

      <article class="afr-article">
        <section class="afr-abstract" id="abstract">
          <p class="afr-classification">Research Abstract</p>
          <h2>Abstract</h2>
          <p>{_citations(report["abstract"]["text"])}</p>
        </section>
{_sections(report, asset_prefix)}

        <section class="afr-ledger" id="prediction-ledger">
          <p class="afr-classification">Prediction Record</p>
          <h2>AFR Prediction Ledger</h2>
          <p>Each statement is permanent, falsifiable, and scheduled for review at six, twelve, and twenty-four months. Publication dates remain unset while this report is a draft.</p>
{_prediction_ledger(report, ledger)}
        </section>

        <section class="afr-references-section" id="references">
          <p class="afr-classification">Evidence Base</p>
          <h2>References</h2>
          <ol class="afr-references">
{_references(report)}
          </ol>
        </section>

        <section class="afr-publication-record" id="publication-record">
          <p class="afr-classification">Record</p>
          <h2>Publication Record</h2>
          <h3>Recommended citation</h3>
          <p class="rn-citation-text" tabindex="-1">{_e(report["recommended_citation"])}</p>
          <h3>Organizational disclosure</h3>
          <p>{_e(report["organizational_disclosure"])}</p>
          <h3>Evidence boundary</h3>
          <p>{_e(report["evidence_boundary"])}</p>
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
