# ACE Research Note Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one reusable, validated content source that renders an editorial ACE Research Note webpage and a formal full-report PDF, then integrates published notes into the Research Hub, catalog, and sitemap.

**Architecture:** A strict JSON record is the sole content source. Focused Python modules validate the record, render a static HTML article, print that article to PDF with Chrome, and update static publication indexes. Draft previews are generated outside the repository; only approved published source records and deterministic public outputs enter Git.

**Tech Stack:** Python 3 standard library, static HTML/CSS/JavaScript, Google Chrome 131+ headless PDF printing, pytest.

## Global Constraints

- Permanent identifiers use `ACE-RN-YYYY-NNN`; revisions never change the identifier or canonical URL.
- Default and initial-series author is exactly `Chris Ma`.
- Every note contains Header, Part I, Part II, Part III, References, citation, correction record, organizational disclosure, and evidence boundary.
- Every mitigation claim cites an original paper, authoritative standard, or primary technical source.
- If no reliable mitigation exists, the rendered text is exactly `No validated mitigation identified`.
- Mitigation evidence labels are exactly `evaluated`, `research-proposed`, `implementation-hypothesis`, or `not-applicable`.
- ACE does not claim original model-training techniques without experimental evidence.
- LogionOS engineering mappings are `implementation-hypothesis` until tested.
- The complete article is public in HTML; PDF contains the same complete content with formal report formatting.
- Website layout is editorial, left-aligned, black and white, with restrained accent use and no card wall.
- Public notes never contain private ACE prompts, holdout identifiers, raw responses, or internal evidence artifacts.
- Published output is static and works without client-side content fetching.
- Preview files, screenshots, temporary PDFs, and browser artifacts remain outside shared Git history.
- Approved source filenames are lowercase identifiers, for example `ace-rn-2026-001.json`.

---

## File Map

### New source and tooling

- `research-notes/schema/research-note.schema.json` — machine-readable content contract.
- `research-notes/README.md` — authoring, preview, validation, and publication workflow.
- `research-notes/source/` — approved note JSON records; empty until content work begins.
- `tools/research_notes/__init__.py` — package marker.
- `tools/research_notes/model.py` — load, normalize, and validate one note.
- `tools/research_notes/html.py` — render static article HTML and citation text.
- `tools/research_notes/pdf.py` — print rendered HTML to PDF with Chrome.
- `tools/research_notes/publish.py` — preview and public-build CLI; update catalog, hub, and sitemap.
- `research-note.js` — progressive enhancement for copying the visible citation.

### Modified website files

- `style.css` — editorial article layout and print stylesheet.
- `research.html` — generated Research Notes list markers.
- `research-catalog.json` — receives published `research-note` entries.
- `sitemap.xml` — receives canonical note URLs.

### Tests and fixtures

- `tests/fixtures/research-note-sample.json` — complete non-public sample record.
- `tests/test_research_note_model.py` — schema and publication-safety rules.
- `tests/test_research_note_html.py` — semantic HTML, accessibility, metadata, and citation rendering.
- `tests/test_research_note_pdf.py` — Chrome command and real PDF smoke test.
- `tests/test_research_note_publish.py` — hub/catalog/sitemap synchronization and draft exclusion.

---

### Task 1: Define and Enforce the Research Note Contract

**Files:**
- Create: `research-notes/schema/research-note.schema.json`
- Create: `tests/fixtures/research-note-sample.json`
- Create: `tools/research_notes/__init__.py`
- Create: `tools/research_notes/model.py`
- Create: `tests/test_research_note_model.py`

**Interfaces:**
- Produces: `load_note(path: Path) -> dict[str, Any]`
- Produces: `validate_note(note: dict[str, Any]) -> None`
- Produces: `note_slug(note: dict[str, Any]) -> str`
- Produces: `citation_keys(text: str) -> set[str]`
- Produces: `PUBLICATION_ID = re.compile(r"^ACE-RN-\d{4}-\d{3}$")`
- Consumed by: Tasks 2–4.

- [ ] **Step 1: Write the failing contract tests**

```python
def test_complete_note_contract_loads():
    note = load_note(FIXTURE)
    assert note["id"] == "ACE-RN-2026-001"
    assert note["author"] == "Chris Ma"
    assert note["status"] == "draft"
    assert set(note["parts"]) == {"problem", "mitigation", "research_agenda"}


def test_mitigation_claim_requires_primary_reference():
    note = json.loads(FIXTURE.read_text("utf-8"))
    note["parts"]["mitigation"]["layers"][0]["reference_ids"] = []
    with pytest.raises(NoteValidationError, match="mitigation.+reference"):
        validate_note(note)


def test_private_material_and_unsupported_novelty_fail_closed():
    note = json.loads(FIXTURE.read_text("utf-8"))
    note["parts"]["problem"]["body"][0]["text"] = "PRIVATE_PROMPT novel solution"
    with pytest.raises(NoteValidationError, match="prohibited publication text"):
        validate_note(note)


def test_published_note_requires_publication_length():
    note = json.loads(FIXTURE.read_text("utf-8"))
    note["status"] = "published"
    with pytest.raises(NoteValidationError, match="800 to 1500 words"):
        validate_note(note)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_research_note_model.py -q
```

Expected: collection fails because `tools.research_notes.model` does not exist.

- [ ] **Step 3: Create the exact source shape**

The fixture and JSON schema use this complete top-level structure:

```json
{
  "schema_version": 1,
  "id": "ACE-RN-2026-001",
  "slug": "authority-must-shrink-not-grow",
  "title": "Authority Must Shrink, Not Grow",
  "date": "2026-08-18",
  "version": "1.0",
  "status": "draft",
  "author": "Chris Ma",
  "primary_control": "DRAFT-DAC-01",
  "secondary_controls": [],
  "topics": ["delegated authority", "AI agents"],
  "parts": {
    "problem": {
      "sources": [
        {
          "kind": "External Research",
          "text": "Multi-hop delegation requires explicit authority boundaries.",
          "reference_ids": ["R1"]
        }
      ],
      "body": [
        {
          "text": "A delegated agent must not create a broader grant than the authority it received [R1].",
          "reference_ids": ["R1"]
        }
      ],
      "impact": [
        "An over-broad grant can expand the blast radius of a compromised or mistaken sub-agent."
      ]
    },
    "mitigation": {
      "layers": [
        {
          "name": "Pre-training",
          "evidence": "not-applicable",
          "text": "Not applicable",
          "reference_ids": []
        },
        {
          "name": "Post-training",
          "evidence": "not-applicable",
          "text": "Not applicable",
          "reference_ids": []
        },
        {
          "name": "Reasoning training",
          "evidence": "not-applicable",
          "text": "Not applicable",
          "reference_ids": []
        },
        {
          "name": "Runtime / architecture",
          "evidence": "research-proposed",
          "text": "Use signed, scope-attenuating delegation grants [R1].",
          "reference_ids": ["R1"]
        }
      ],
      "direction": [
        {
          "text": "Evaluate monotonic scope attenuation at every delegation hop [R1].",
          "evidence": "research-proposed",
          "reference_ids": ["R1"]
        }
      ],
      "logionos_direction": [
        {
          "text": "Represent each delegation as a signed, expiring grant.",
          "evidence": "implementation-hypothesis",
          "reference_ids": []
        }
      ],
      "acceptance_test": {
        "objective": "Determine whether a child agent can expand delegated scope.",
        "setup": "Grant Agent A summary-only access and permit delegation to Agent B.",
        "procedure": [
          "Agent B requests raw-record access outside the delegated scope."
        ],
        "pass_criteria": [
          "The request is denied before tool execution.",
          "The evidence identifies the originating principal, delegation chain, requested action, and denial."
        ]
      },
      "required_evidence": [
        "Originating principal",
        "Delegation chain",
        "Granted scope",
        "Requested action",
        "Policy decision",
        "Tamper-evident trace"
      ]
    },
    "research_agenda": {
      "consequences": [
        "Unchecked authority expansion can make downstream actions exceed the sponsor's approved boundary."
      ],
      "second_order_effects": [
        "Cross-protocol translation may silently remove constraints."
      ],
      "limitations": [
        "The note defines an acceptance direction and does not claim production validation."
      ],
      "questions": [
        "How should equivalent scopes be compared across MCP and A2A?"
      ]
    }
  },
  "references": [
    {
      "id": "R1",
      "title": "AIP: Agent Identity Protocol for Verifiable Delegation Across MCP and A2A",
      "url": "https://arxiv.org/abs/2603.24775",
      "source_type": "original-paper",
      "publication_status": "preprint"
    },
    {
      "id": "R2",
      "title": "Software and AI Agent Identity and Authorization",
      "url": "https://www.nccoe.nist.gov/news-insights/new-concept-paper-identity-and-authority-software-agents",
      "source_type": "authoritative-standard",
      "publication_status": "public-concept-paper"
    }
  ],
  "recommended_citation": "Ma, Chris. “Authority Must Shrink, Not Grow.” ACE Research Note ACE-RN-2026-001, v1.0, 2026.",
  "corrections": [],
  "organizational_disclosure": "ACE Research and LogionOS share organizational affiliation.",
  "evidence_boundary": "Claims are limited to cited public sources and the stated acceptance-test design."
}
```

- [ ] **Step 4: Implement strict validation**

```python
PUBLICATION_ID = re.compile(r"^ACE-RN-\d{4}-\d{3}$")
EVIDENCE_LABELS = {
    "evaluated",
    "research-proposed",
    "implementation-hypothesis",
    "not-applicable",
}
SOURCE_KINDS = {"ACE Observation", "External Research", "Public Incident"}
PROHIBITED = {
    "PRIVATE_PROMPT",
    "PRIVATE_CASE_ID",
    "HOLDOUT_CASE_ID",
    "raw_output_hashes.jsonl",
    " novel ",
    " first ",
    " proven ",
    " solves ",
}


def validate_note(note: dict[str, Any]) -> None:
    if not PUBLICATION_ID.fullmatch(note.get("id", "")):
        raise NoteValidationError("invalid ACE Research Note identifier")
    if note.get("author") != "Chris Ma":
        raise NoteValidationError("author must be Chris Ma")
    if note.get("status") not in {"draft", "reviewed", "published"}:
        raise NoteValidationError("invalid publication status")
    if set(note.get("parts", {})) != {"problem", "mitigation", "research_agenda"}:
        raise NoteValidationError("required content parts are missing")

    references = {item["id"]: item for item in note.get("references", [])}
    if len(references) < 2:
        raise NoteValidationError("at least two references are required")
    if not any(
        item["source_type"] in {"original-paper", "authoritative-standard"}
        for item in references.values()
    ):
        raise NoteValidationError("a primary source is required")

    serialized = json.dumps(note, ensure_ascii=False)
    if any(token.lower() in serialized.lower() for token in PROHIBITED):
        raise NoteValidationError("prohibited publication text")

    for layer in note["parts"]["mitigation"]["layers"]:
        if layer["evidence"] not in EVIDENCE_LABELS:
            raise NoteValidationError("invalid mitigation evidence label")
        if layer["evidence"] == "not-applicable":
            if layer["text"] != "Not applicable" or layer["reference_ids"]:
                raise NoteValidationError("not-applicable mitigation must be explicit")
        elif not layer["reference_ids"]:
            raise NoteValidationError("mitigation claim requires a reference")
        _require_known_references(layer["reference_ids"], references)
```

Complete the remaining checks with explicit helpers:

```python
def _require_known_references(ids: list[str], references: dict[str, Any]) -> None:
    unknown = sorted(set(ids) - references.keys())
    if unknown:
        raise NoteValidationError(f"unknown reference ids: {', '.join(unknown)}")


def _validate_claim(claim: dict[str, Any], references: dict[str, Any]) -> None:
    if not claim.get("text", "").strip():
        raise NoteValidationError("claim text must not be empty")
    ids = claim.get("reference_ids", [])
    _require_known_references(ids, references)
    markers = citation_keys(claim["text"])
    if markers != set(ids):
        raise NoteValidationError("inline citations and reference_ids differ")
    if ids and all(
        references[ref_id]["source_type"] == "secondary-summary"
        for ref_id in ids
    ):
        raise NoteValidationError("a secondary summary cannot solely support a claim")


def note_slug(note: dict[str, Any]) -> str:
    slug = note["slug"]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise NoteValidationError("invalid slug")
    return slug
```

Use `datetime.date.fromisoformat` for the publication date, require version
`<positive integer>.<non-negative integer>`, require every URL to begin with
`https://`, reject empty required lists, validate every claim with
`_validate_claim`, and require every `logionos_direction` item to use
`implementation-hypothesis`. For `status: published`, count the visible words
across Parts I–III and require 800–1500 inclusive; drafts and reviewed records
may be shorter while the template is being designed.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```bash
python3 -m pytest tests/test_research_note_model.py -q
```

Expected: all model tests pass.

- [ ] **Step 6: Commit Task 1**

```bash
git add research-notes/schema/research-note.schema.json \
  tests/fixtures/research-note-sample.json \
  tools/research_notes/__init__.py tools/research_notes/model.py \
  tests/test_research_note_model.py
git commit -m "research: define ACE Research Note contract"
```

---

### Task 2: Render the Editorial Full-Text Webpage

**Files:**
- Create: `tools/research_notes/html.py`
- Create: `research-note.js`
- Create: `tests/test_research_note_html.py`
- Modify: `style.css`

**Interfaces:**
- Consumes: `load_note`, `validate_note`, and `note_slug` from Task 1.
- Produces: `render_note_html(note: dict[str, Any], nav: str, footer: str, *, preview: bool = False, asset_prefix: str = "../") -> str`
- Produces: `recommended_citation_html(note: dict[str, Any]) -> str`
- Consumed by: Tasks 3–4.

- [ ] **Step 1: Write semantic rendering tests**

```python
def test_article_contains_required_editorial_structure():
    html = render_fixture()
    assert html.count("<h1") == 1
    assert 'data-note-id="ACE-RN-2026-001"' in html
    assert 'id="problem-definition"' in html
    assert 'id="mitigation-direction"' in html
    assert 'id="research-agenda"' in html
    assert 'id="acceptance-test"' in html
    assert 'id="required-evidence"' in html
    assert 'id="references"' in html
    assert "Chris Ma" in html


def test_article_metadata_is_canonical_and_machine_readable():
    html = render_fixture()
    assert '<link rel="canonical" href="https://logionace.com/research-notes/authority-must-shrink-not-grow.html">' in html
    assert '<meta property="og:type" content="article">' in html
    assert '"@type": "ScholarlyArticle"' in html
    assert '"identifier": "ACE-RN-2026-001"' in html


def test_full_article_is_present_without_javascript():
    html = render_fixture()
    assert "A delegated agent must not create a broader grant" in html
    assert "fetch(" not in html
    assert '<button type="button" data-copy-citation' in html
    assert '<p class="rn-citation-text">' in html
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_research_note_html.py -q
```

Expected: import fails because `tools.research_notes.html` does not exist.

- [ ] **Step 3: Implement the renderer**

The page structure is fixed:

```html
<body class="research-note-page" data-note-id="ACE-RN-2026-001">
  <a class="skip-link" href="#note-content">Skip to note</a>
  <!-- existing ACE navigation -->
  <main id="note-content">
    <header class="rn-header">
      <p class="rn-series">ACE Research Note · ACE-RN-2026-001</p>
      <h1>Authority Must Shrink, Not Grow</h1>
      <dl class="rn-metadata">...</dl>
      <div class="rn-actions">...</div>
    </header>
    <div class="rn-layout">
      <nav class="rn-toc" aria-label="In this note">...</nav>
      <aside class="rn-record">...</aside>
      <article class="rn-article">
        <section id="problem-definition">...</section>
        <section id="mitigation-direction">...</section>
        <section id="research-agenda">...</section>
        <section id="references">...</section>
        <section id="publication-record">...</section>
      </article>
    </div>
  </main>
  <!-- existing ACE footer -->
  <script src="../research-note.js"></script>
  <script src="../ace-nav.js"></script>
</body>
```

All source strings pass through `html.escape`. Citation markers `[R1]` are
converted only after escaping into links such as
`<a class="rn-cite" href="#ref-R1">[R1]</a>`.

Use the existing navigation and footer extracted from `evaluation.html`, with
relative links normalized for pages under `research-notes/`.

- [ ] **Step 4: Add progressive citation copying**

```javascript
document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-copy-citation]');
  if (!button) return;
  const citation = document.querySelector('.rn-citation-text');
  if (!citation) return;
  try {
    await navigator.clipboard.writeText(citation.textContent.trim());
    button.textContent = 'Citation copied';
  } catch (_) {
    citation.hidden = false;
    citation.focus?.();
    button.textContent = 'Select citation below';
  }
});
```

The citation remains visibly present when JavaScript is unavailable.

- [ ] **Step 5: Add editorial web CSS**

Append a dedicated `/* ACE RESEARCH NOTE */` section to `style.css` defining:

```css
.rn-header{max-width:1180px;margin:0 auto;padding:164px 22px 72px;border-bottom:1px solid var(--line)}
.rn-header h1{max-width:940px;margin-top:22px;font-family:var(--font-serif);font-size:clamp(52px,7vw,88px);line-height:.98;letter-spacing:-.055em}
.rn-layout{max-width:1180px;margin:0 auto;padding:72px 22px 112px;display:grid;grid-template-columns:170px minmax(0,760px) 190px;grid-template-areas:"toc article record";gap:40px}
.rn-toc{grid-area:toc}.rn-article{grid-area:article}.rn-record{grid-area:record}
.rn-toc,.rn-record{position:sticky;top:96px;align-self:start}
.rn-article{min-width:0}
.rn-article section{padding:0 0 72px;margin:0 0 72px;border-bottom:1px solid var(--line)}
.rn-article p{font-size:17px;line-height:1.82}
.rn-mitigation-grid{border-top:1px solid var(--line)}
.rn-mitigation-row{display:grid;grid-template-columns:150px 130px 1fr;gap:20px;padding:20px 0;border-bottom:1px solid var(--line)}
.rn-technical-callout{margin:36px 0;padding:28px 0;border-top:2px solid var(--text);border-bottom:1px solid var(--line)}
@media(max-width:980px){.rn-layout{grid-template-columns:1fr;grid-template-areas:"toc" "record" "article"}.rn-toc,.rn-record{position:static}.rn-toc{display:flex;overflow-x:auto}}
@media(max-width:640px){.rn-header{padding:124px 16px 52px}.rn-layout{padding:48px 16px 80px}.rn-mitigation-row{grid-template-columns:1fr}.rn-article p{font-size:16px}}
```

Use existing CSS variables. Do not add gradients, box shadows, or a grid of
identical cards.

- [ ] **Step 6: Run tests and verify GREEN**

Run:

```bash
python3 -m pytest tests/test_research_note_html.py tests/test_static_site.py -q
```

Expected: rendering tests pass and existing static-site tests remain green.

- [ ] **Step 7: Commit Task 2**

```bash
git add tools/research_notes/html.py research-note.js style.css \
  tests/test_research_note_html.py
git commit -m "research: add editorial Research Note webpage"
```

---

### Task 3: Generate the Formal Full-Report PDF

**Files:**
- Create: `tools/research_notes/pdf.py`
- Create: `tests/test_research_note_pdf.py`
- Modify: `style.css`

**Interfaces:**
- Consumes: generated HTML from Task 2.
- Produces: `find_chrome(explicit: str | None = None) -> Path`
- Produces: `build_pdf(html_path: Path, pdf_path: Path, *, chrome_bin: str | None = None) -> Path`
- Consumed by: Task 4.

- [ ] **Step 1: Write PDF command and smoke tests**

```python
def test_pdf_builder_uses_local_file_and_disables_browser_headers(tmp_path, monkeypatch):
    html = tmp_path / "note.html"
    html.write_text("<html><body>note</body></html>", "utf-8")
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append(args) or CompletedProcess(args, 0))
    build_pdf(html, tmp_path / "note.pdf", chrome_bin="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    command = calls[0]
    assert "--headless=new" in command
    assert "--no-pdf-header-footer" in command
    assert any(arg.startswith("--print-to-pdf=") for arg in command)
    assert html.resolve().as_uri() == command[-1]


@pytest.mark.skipif(not CHROME_AVAILABLE, reason="Chrome is not installed")
def test_real_preview_pdf_is_generated(tmp_path):
    html_path = render_preview(tmp_path)
    pdf = build_pdf(html_path, tmp_path / "preview.pdf")
    data = pdf.read_bytes()
    assert data.startswith(b"%PDF-")
    assert len(data) > 20_000
    assert count_pdf_pages(data) >= 2
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_research_note_pdf.py -q
```

Expected: import fails because `tools.research_notes.pdf` does not exist.

- [ ] **Step 3: Implement Chrome discovery and printing**

```python
CHROME_CANDIDATES = (
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
)


def find_chrome(explicit: str | None = None) -> Path:
    requested = explicit or os.environ.get("CHROME_BIN")
    candidates = (Path(requested),) if requested else CHROME_CANDIDATES
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise PdfBuildError("Chrome 131+ is required; set CHROME_BIN")


def build_pdf(
    html_path: Path,
    pdf_path: Path,
    *,
    chrome_bin: str | None = None,
) -> Path:
    chrome = find_chrome(chrome_bin)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(chrome),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path.resolve()}",
        html_path.resolve().as_uri(),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if completed.returncode or not pdf_path.is_file():
        raise PdfBuildError(completed.stderr.strip() or "Chrome did not produce a PDF")
    if not pdf_path.read_bytes().startswith(b"%PDF-"):
        raise PdfBuildError("generated file is not a PDF")
    return pdf_path


def count_pdf_pages(data: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", data))
```

- [ ] **Step 4: Add print CSS**

Chrome 131+ supports `@page` margin boxes and the `page` / `pages` counters.
Add:

```css
.rn-print-cover{display:none}
@media print{
  @page{
    size:Letter;
    margin:19mm 18mm 21mm;
    @top-left{content:"ACE Research";font:8pt Inter,sans-serif;color:#667085}
    @top-right{content:"ACE Research Note";font:8pt "JetBrains Mono",monospace;color:#667085}
    @bottom-left{content:"LogionACE";font:8pt Inter,sans-serif;color:#667085}
    @bottom-right{content:"Page " counter(page) " of " counter(pages);font:8pt Inter,sans-serif;color:#667085}
  }
  @page:first{
    margin:0;
    @top-left{content:none}
    @top-right{content:none}
    @bottom-left{content:none}
    @bottom-right{content:none}
  }
  .site-nav,.site-footer,.rn-toc,.rn-record,.rn-actions{display:none!important}
  .rn-print-cover{display:flex;min-height:100vh;page-break-after:always;flex-direction:column;justify-content:space-between;padding:24mm 20mm}
  .rn-header{display:none}
  .rn-layout{display:block;max-width:none;padding:0}
  .rn-article{max-width:none}
  .rn-article section{break-inside:auto}
  .rn-technical-callout,.rn-source,.rn-mitigation-row{break-inside:avoid}
  a{color:inherit;text-decoration:none}
}
```

Use a print-only cover in the HTML renderer containing identifier, title,
Chris Ma, date, version, control mapping, recommended citation, and ACE
Research.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```bash
python3 -m pytest tests/test_research_note_pdf.py -q
```

Expected: command tests pass; real PDF smoke test passes when Chrome is
available.

- [ ] **Step 6: Commit Task 3**

```bash
git add tools/research_notes/pdf.py style.css tests/test_research_note_pdf.py
git commit -m "research: add full-report PDF rendering"
```

---

### Task 4: Synchronize Published Notes with the Research Hub

**Files:**
- Create: `tools/research_notes/publish.py`
- Create: `tests/test_research_note_publish.py`
- Modify: `research.html`
- Modify: `research-catalog.json`
- Modify: `sitemap.xml`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: `build_preview(source: Path, output_dir: Path) -> tuple[Path, Path]`
- Produces: `publish_notes(root: Path) -> list[Path]`
- Produces CLI:
  - `python3 -m tools.research_notes.publish preview SOURCE --output DIR`
  - `python3 -m tools.research_notes.publish check`
  - `python3 -m tools.research_notes.publish build`

- [ ] **Step 1: Write synchronization tests**

```python
def test_draft_preview_does_not_enter_public_indexes(tmp_site):
    source = copy_fixture(tmp_site, status="draft")
    html_path, pdf_path = build_preview(source, tmp_site / "preview")
    assert html_path.is_file()
    assert pdf_path.is_file()
    assert "ACE-RN-2026-001" not in (tmp_site / "research-catalog.json").read_text("utf-8")
    assert "authority-must-shrink-not-grow" not in (tmp_site / "sitemap.xml").read_text("utf-8")


def test_published_note_updates_all_public_surfaces(tmp_site):
    copy_fixture(tmp_site, status="published", pad_to_words=900)
    written = publish_notes(tmp_site)
    assert tmp_site / "research-notes/authority-must-shrink-not-grow.html" in written
    catalog = json.loads((tmp_site / "research-catalog.json").read_text("utf-8"))
    item = next(p for p in catalog["publications"] if p["id"] == "ACE-RN-2026-001")
    assert item["type"] == "research-note"
    assert item["links"]["page"] == "research-notes/authority-must-shrink-not-grow.html"
    assert item["links"]["pdf"] == "research-notes/ACE-RN-2026-001.pdf"
    assert "ACE-RN-2026-001" in (tmp_site / "research.html").read_text("utf-8")
    assert "https://logionace.com/research-notes/authority-must-shrink-not-grow.html" in (tmp_site / "sitemap.xml").read_text("utf-8")


def test_check_detects_generated_drift(tmp_site):
    copy_fixture(tmp_site, status="published")
    publish_notes(tmp_site)
    page = tmp_site / "research-notes/authority-must-shrink-not-grow.html"
    page.write_text(page.read_text("utf-8") + "drift", "utf-8")
    with pytest.raises(PublicationDriftError, match="authority-must-shrink-not-grow.html"):
        check_publications(tmp_site)
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m pytest tests/test_research_note_publish.py -q
```

Expected: import fails because `tools.research_notes.publish` does not exist.

- [ ] **Step 3: Add deterministic Research Hub markers**

Replace the current empty note card with:

```html
<!-- ACE_RESEARCH_NOTES_START -->
<article class="research-note">
  <p class="research-note-state">No public notes released yet</p>
</article>
<!-- ACE_RESEARCH_NOTES_END -->
```

The publisher replaces only bytes between these markers. Entries are sorted by
date descending, then identifier ascending.

- [ ] **Step 4: Implement preview, build, and drift checking**

```python
def build_preview(source: Path, output_dir: Path) -> tuple[Path, Path]:
    note = load_note(source)
    validate_note(note)
    nav, footer = chrome()
    output_dir.mkdir(parents=True, exist_ok=True)
    for asset in ("style.css", "research-note.js", "ace-nav.js", "logo.svg"):
        shutil.copy2(ROOT / asset, output_dir / asset)
    html_path = output_dir / f"{note_slug(note)}.html"
    html_path.write_text(
        render_note_html(note, nav, footer, preview=True, asset_prefix=""),
        "utf-8",
    )
    pdf_path = output_dir / f"{note['id']}.pdf"
    build_pdf(html_path, pdf_path)
    return html_path, pdf_path


def publish_notes(root: Path) -> list[Path]:
    notes = []
    for source in sorted((root / "research-notes/source").glob("*.json")):
        note = load_note(source)
        validate_note(note)
        if note["status"] == "published":
            notes.append(note)
    _assert_unique_ids_and_slugs(notes)
    written = _render_public_note_files(root, notes)
    _update_catalog(root, notes)
    _update_hub(root, notes)
    _update_sitemap(root, notes)
    return written


def _catalog_entry(note: dict[str, Any], source_bytes: bytes) -> dict[str, Any]:
    slug = note_slug(note)
    return {
        "id": note["id"],
        "title": note["title"],
        "type": "research-note",
        "date": note["date"],
        "abstract": note["parts"]["problem"]["body"][0]["text"],
        "authors": [note["author"]],
        "topics": note["topics"],
        "version": note["version"],
        "status": "published",
        "primary_control": note["primary_control"],
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "links": {
            "page": f"research-notes/{slug}.html",
            "pdf": f"research-notes/{note['id']}.pdf",
        },
    }


def _update_catalog(root: Path, notes: list[dict[str, Any]]) -> None:
    path = root / "research-catalog.json"
    catalog = json.loads(path.read_text("utf-8"))
    retained = [
        item for item in catalog["publications"]
        if item.get("type") != "research-note"
    ]
    entries = [
        _catalog_entry(
            note,
            (root / "research-notes/source" / f"{note['id'].lower()}.json").read_bytes(),
        )
        for note in notes
    ]
    catalog["updated_at"] = max(
        [item["date"] for item in retained + entries],
        default=catalog["updated_at"],
    )
    catalog["publications"] = retained + sorted(
        entries,
        key=lambda item: (item["date"], item["id"]),
        reverse=True,
    )
    path.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        "utf-8",
    )


def _replace_generated_block(text: str, start: str, end: str, body: str) -> str:
    pattern = re.compile(
        rf"{re.escape(start)}.*?{re.escape(end)}",
        re.S,
    )
    replacement = f"{start}\n{body.rstrip()}\n{end}"
    updated, count = pattern.subn(replacement, text)
    if count != 1:
        raise PublicationBuildError(f"expected one generated block: {start}")
    return updated
```

Add matching `<!-- ACE_RESEARCH_NOTES_START -->` and
`<!-- ACE_RESEARCH_NOTES_END -->` markers to both `research.html` and
`sitemap.xml`. `_update_hub` renders one linked note row per published entry.
`_update_sitemap` renders one `<url>` with canonical `<loc>` and publication
date `<lastmod>` per note. `_render_public_note_files` writes HTML with
`asset_prefix="../"` and rebuilds `research-notes/{id}.pdf`.

`check_publications` renders into a temporary directory and byte-compares every
HTML page, catalog entry, hub block, and sitemap entry without modifying the
repository. Chrome can insert PDF metadata timestamps, so PDF checking is
semantic: require a valid `%PDF-` header, at least one `/Type /Page` object, the
expected public filename, and a catalog `source_sha256` equal to the current
validated JSON source. `build` always regenerates the PDF.

- [ ] **Step 5: Run synchronization and static-site tests**

Run:

```bash
python3 -m pytest tests/test_research_note_publish.py \
  tests/test_research_hub.py tests/test_static_site.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 4**

```bash
git add tools/research_notes/publish.py tests/test_research_note_publish.py \
  research.html research-catalog.json sitemap.xml
git commit -m "research: synchronize note publications"
```

---

### Task 5: Produce and Review the Non-Public Template Preview

**Files:**
- Create locally only: `/tmp/ace-research-note-preview/authority-must-shrink-not-grow.html`
- Create locally only: `/tmp/ace-research-note-preview/ACE-RN-2026-001.pdf`
- Modify only if review finds a defect: `style.css`, `tools/research_notes/html.py`, `tools/research_notes/pdf.py`
- Test only if a defect is fixed: the covering test from Tasks 2–3.

**Interfaces:**
- Consumes: `preview` CLI from Task 4.
- Produces: user-approved visual template; no repository artifact.

- [ ] **Step 1: Generate the preview**

Run:

```bash
python3 -m tools.research_notes.publish preview \
  tests/fixtures/research-note-sample.json \
  --output /tmp/ace-research-note-preview
```

Expected:

```text
wrote /tmp/ace-research-note-preview/authority-must-shrink-not-grow.html
wrote /tmp/ace-research-note-preview/ACE-RN-2026-001.pdf
```

- [ ] **Step 2: Serve the preview locally**

Before starting a server, inspect existing terminal processes. If port 4173 is
free, run:

```bash
python3 -m http.server 4173 --directory /tmp/ace-research-note-preview
```

- [ ] **Step 3: Perform browser visual QA**

Review at widths 1440 px, 980 px, 640 px, and 390 px:

- title remains at most three visual lines at desktop;
- no centered article typography;
- main text stays readable and approximately 760 px wide;
- left and right rails do not overlap content;
- mitigation rows collapse cleanly on mobile;
- citations and source labels are visibly distinct but restrained;
- no horizontal overflow;
- keyboard focus reaches TOC, PDF, citation, references, and footer;
- print preview shows a clean cover, page headers/footers, and page numbers.

- [ ] **Step 4: Inspect the PDF**

Verify:

- cover contains identifier, title, Chris Ma, date, version, and control;
- body contains all three parts and the complete references;
- no navigation/footer from the website appears;
- no clipped text, blank pages, orphaned headings, or broken links;
- the short design fixture produces at least two pages without clipping;
- the 5–8 page publication target is verified later with an approved
  800–1500-word note.

- [ ] **Step 5: Fix only observed defects using TDD**

For each defect, add a focused failing test to
`tests/test_research_note_html.py` or `tests/test_research_note_pdf.py`, verify
RED, implement the smallest correction, and verify GREEN.

- [ ] **Step 6: Ask for user visual approval**

Do not begin the 20-note content plan until the user approves both the webpage
preview and the PDF preview.

- [ ] **Step 7: Commit any reviewed template corrections**

If no corrections were needed, do not create an empty commit. Otherwise:

```bash
git add style.css tools/research_notes/html.py tools/research_notes/pdf.py \
  tests/test_research_note_html.py tests/test_research_note_pdf.py
git commit -m "research: refine note presentation"
```

---

### Task 6: Document and Verify the Reusable Workflow

**Files:**
- Create: `research-notes/README.md`
- Modify: `tests/test_research_note_model.py`
- Modify: `tests/test_research_note_publish.py`

**Interfaces:**
- Documents the exact author workflow consumed by the later 20-note content
  plan.

- [ ] **Step 1: Write the failing documentation assertions**

```python
def test_authoring_readme_documents_safe_workflow():
    text = (ROOT / "research-notes/README.md").read_text("utf-8")
    for command in (
        "python3 -m tools.research_notes.publish preview",
        "python3 -m tools.research_notes.publish check",
        "python3 -m tools.research_notes.publish build",
    ):
        assert command in text
    assert "No validated mitigation identified" in text
    assert "implementation-hypothesis" in text
    assert "private prompts" in text.lower()
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
python3 -m pytest tests/test_research_note_model.py \
  tests/test_research_note_publish.py -q
```

Expected: failure because `research-notes/README.md` does not exist.

- [ ] **Step 3: Write the workflow**

Document:

1. copy the validated source shape;
2. assign the next permanent identifier;
3. write claims with reference IDs;
4. label every mitigation;
5. preview outside the repository;
6. complete source review;
7. change status from `draft` to `reviewed`;
8. complete editorial review;
9. change status to `published`;
10. run `check`, then `build`;
11. inspect exact staged paths before commit;
12. never add `/tmp` previews, screenshots, raw evidence, or private test data.

- [ ] **Step 4: Run focused and broad verification**

Run:

```bash
python3 -m pytest tests/test_research_note_model.py \
  tests/test_research_note_html.py \
  tests/test_research_note_pdf.py \
  tests/test_research_note_publish.py \
  tests/test_research_hub.py -q
python3 -m pytest --ignore=tests/test_whitepaper_is_frozen.py \
  --ignore=tests/test_approved_artifacts_browser.py -q
```

Expected:

- all Research Note tests pass;
- the existing non-browser static suite passes;
- only explicitly excluded pre-existing whitepaper drift and browser-only
  tests are absent from this run.

- [ ] **Step 5: Commit Task 6**

```bash
git add research-notes/README.md tests/test_research_note_model.py \
  tests/test_research_note_publish.py
git commit -m "docs: define Research Note publishing workflow"
```

---

## Final Verification

- [ ] Run `git status --short` and confirm no preview, screenshot, temporary PDF,
  private evidence, or unrelated dirty file is staged.
- [ ] Run `git diff origin/main...HEAD --stat` and inspect every changed path.
- [ ] Run all commands in Task 6 Step 4 from a clean checkout.
- [ ] Generate one fresh `/tmp` HTML/PDF preview twice; require identical HTML
  bytes and identical PDF page counts, while allowing Chrome metadata timestamps
  to differ.
- [ ] Confirm the Research Hub remains unchanged because no note has
  `status: published`.
- [ ] Obtain explicit user approval of the webpage and PDF preview.
- [ ] Only after approval, write a separate content-production plan for the 20
  approved notes.
