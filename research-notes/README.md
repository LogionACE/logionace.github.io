# ACE Research Notes

ACE Research Notes are short, citable publications generated from one validated
JSON source. The same source produces the full webpage, PDF, Research Hub entry,
research catalog entry, and sitemap entry.

## Authoring

1. Copy `tests/fixtures/research-note-sample.json`.
2. Name the source with the lowercase permanent identifier, for example
   `research-notes/source/ace-rn-2026-001.json`.
3. Keep the author as `Chris Ma`.
4. Map only controls materially addressed by the note. Do not add unrelated
   controls merely to cover the framework.
5. Add inline `[R1]` markers and matching `reference_ids` for factual claims.
6. Cite at least two sources, including an original paper or authoritative
   standard.
7. Label every mitigation as `evaluated`, `research-proposed`,
   `implementation-hypothesis`, or `not-applicable`.
8. Keep LogionOS engineering mappings at `implementation-hypothesis` until
   tested.
9. If the research does not support a reliable mitigation, write exactly:
   `No validated mitigation identified`.
10. Never include private prompts, holdout identifiers, raw responses, internal
    evidence artifacts, credentials, or customer data.

## Local preview

Generate previews outside the repository:

```bash
python3 -m tools.research_notes.preview \
  research-notes/source/ace-rn-2026-001.json \
  --output /tmp/ace-research-note-preview
```

Review the HTML at desktop and mobile widths. Inspect the complete PDF for
clipped text, blank pages, page headers, page numbers, references, correction
record, and evidence boundary.

## Publication states

- `draft`: content or sourcing is incomplete.
- `reviewed`: source and editorial review are complete, but the note is not
  public.
- `published`: the generator includes the note in public site artifacts.

Changing an existing note requires a new version and a correction record. Its
identifier and canonical slug remain stable.

## Build and check

Validate that committed public artifacts match their sources:

```bash
python3 -m tools.research_notes.publish check
```

After final approval, generate public artifacts:

```bash
python3 -m tools.research_notes.publish build
python3 -m tools.research_notes.publish check
```

Before committing, inspect exact paths. Do not stage `/tmp` previews,
screenshots, temporary PDFs, raw evidence, or unrelated dirty files.

## Ongoing publication cadence

After the initial 20-note series, publish 1–2 new Research Notes per day while
usable ACE findings remain. Define one bounded problem per note; do not combine
unrelated findings merely to meet the cadence.

Introduce one note on X each day. The post should state the problem in plain
language, name the practical consequence, link to the full note, and avoid
claims that exceed the cited evidence. Corrections to the note take priority
over the daily posting schedule.
