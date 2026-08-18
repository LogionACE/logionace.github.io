# ACE Research Notes Publishing Design

Date: 2026-08-18
Status: Approved design, pending implementation plan
Owner and default author: Chris Ma

## 1. Purpose

ACE Research Notes turn recurring ACE findings and relevant public research into
short, citable publications. ACE contributes the problem definition, control
mapping, acceptance test, and required evidence. External research supplies
candidate mitigations. LogionOS may describe how a cited mitigation could be
implemented as a runtime control, but it must not present that engineering
mapping as a novel research result.

The first release series contains 20 English notes of approximately 800–1500
words each.

## 2. Publication Identity

Each note receives one permanent identifier:

`ACE-RN-YYYY-NNN`

Example: `ACE-RN-2026-001`.

The identifier and canonical URL never change. Corrections increment the
version (`v1.0`, `v1.1`) and update the correction record. A materially new
method or research question receives a new identifier.

Future ACE publications cite a note by its permanent identifier, for example
`[ACE-RN-2026-001]`.

## 3. Required Content

### Header

- Permanent ACE Research Note identifier
- Problem-defining title
- Publication date
- Version
- Author: Chris Ma
- Primary ACE Control mapping
- Optional secondary ACE Control mappings

Titles must define the problem directly. The template must not add a subtitle
that merely repeats the title.

### Part I: Problem Definition

Part I combines only the source types that genuinely exist for the note:

- findings reported by public research;
- public incidents or real-world cases;
- public ACE observations.

It must identify the source of each finding, describe the real-world problem,
state the applicable scope, and assess direct impact. It must never merge a
paper finding, public incident, and ACE observation into a single unattributed
claim.

Permitted source labels are:

- `ACE Observation`
- `External Research`
- `Public Incident`

### Part II: Mitigation Direction

Part II evaluates applicable mitigation layers:

- Pre-training
- Post-training
- Reasoning training
- Runtime / architecture

Not every note requires every layer. An inapplicable layer is labelled
`Not applicable`; the publication must not invent a training intervention to
complete the layout.

Every mitigation claim requires a citation to an original paper, authoritative
standard, or primary technical source. If no reliable mitigation is found, the
note states `No validated mitigation identified`.

Mitigation statements use one of these evidence labels:

- `evaluated`: the cited source reports an evaluation relevant to the claim;
- `research-proposed`: the cited source proposes the direction without
  sufficient independent validation;
- `implementation-hypothesis`: an ACE or LogionOS engineering mapping that has
  not yet been validated.

ACE does not claim original model-training techniques. AI-generated prose must
not be represented as a new solution. ACE's original contribution is limited
to problem definition, control formulation, acceptance testing, and required
evidence unless a later publication provides experimental proof of more.

Part II then defines:

- Proposed mitigation direction, with source and evidence label
- LogionOS implementation direction, when relevant
- ACE acceptance test
- Required evidence

LogionOS implementation directions are explicitly labelled
`implementation-hypothesis` until tested.

### Part III: Consequences and Research Agenda

Part III contains:

- direct consequences if the problem remains unresolved;
- plausible second-order effects;
- ways the failure could evolve or spread;
- limitations of the note;
- numbered further-research questions;
- proposed future ACE acceptance-test work.

Predicted effects must be distinguished from observed effects.

### Publication Record

Every note ends with:

- References
- Recommended citation
- Version and correction record
- Organizational disclosure
- Evidence-boundary statement

## 4. Claim and Citation Rules

- External factual claims require inline citations.
- Each note requires at least two references.
- At least one reference must be an original paper or authoritative standard.
- Preprints are identified as preprints.
- Secondary summaries cannot be the sole support for a technical claim.
- A citation must support the specific claim, not merely discuss the same topic.
- Remediated vulnerabilities are described as disclosed historical failure
  modes, not as current zero-day vulnerabilities.
- Private ACE prompts, holdout identifiers, raw responses, and internal
  evidence artifacts are prohibited.
- Terms such as `novel`, `first`, `proven`, and `solves` require explicit
  supporting evidence.

## 5. Website Design

The website uses an editorial research-journal visual language aligned with the
existing ACE site: black and white, restrained accent use, serif display
titles, generous whitespace, and left-aligned composition.

### Article Header

- `ACE Research Note · <identifier>`
- Title, limited to three display lines
- Date, version, and Chris Ma
- Primary and secondary control mappings
- `Download PDF` action
- `Copy citation` action

### Reading Layout

Desktop:

- narrow left column for section navigation;
- approximately 760 px main reading column;
- narrow right column for PDF, citation, and version status.

Mobile:

- single reading column;
- PDF and citation actions immediately below metadata;
- no horizontal overflow.

The website publishes the complete note. It is not a summary or download gate.

### Section Presentation

- Part I is continuous editorial prose with restrained source labels.
- Part II uses a ruled mitigation-layer comparison rather than a wall of cards.
- ACE Acceptance Test and Required Evidence use consistent technical callouts.
- Part III uses continuous prose plus numbered research questions.
- References may use native HTML disclosure elements but remain present in the
  page source and accessible without JavaScript.

Each note has its own canonical URL, Open Graph metadata, and
`ScholarlyArticle` JSON-LD.

## 6. PDF Design

The PDF contains the same complete content as the website and is generated from
the same structured source.

- Minimal cover with identifier, title, Chris Ma, date, version, and ACE
  Research
- Formal page headers, footers, and page numbers
- Control mapping and recommended citation on the first page
- Consistent technical treatment for acceptance tests and required evidence
- Numbered references
- Final version and correction record
- No confidential watermark on public notes

Expected length is approximately 5–8 pages.

## 7. Publishing Architecture

One structured source record drives both outputs.

The source schema contains:

- identity and publication metadata;
- control mappings;
- the three content parts;
- mitigation layers and evidence labels;
- acceptance test and required evidence;
- references;
- correction record.

A deterministic generator produces:

- one independent static HTML page;
- one full PDF report;
- the Research Hub note entry;
- the machine-readable research catalog entry;
- sitemap entries.

Generated public output is committed as static files. The website must not
depend on client-side content fetching.

## 8. Validation Gates

Before publication, automated checks verify:

- identifier, URL, date, version, and author consistency;
- required sections and metadata;
- citation targets and reference use;
- source-quality minimums;
- mitigation evidence labels;
- explicit treatment of inapplicable mitigation layers;
- no unsupported novelty language;
- no private ACE material;
- valid HTML links, canonical metadata, and JSON-LD;
- PDF generation and page count;
- agreement among source, HTML, PDF, catalog, and sitemap.

Editorial review then checks whether claims are actually supported by their
sources. Automated link checks alone are not sufficient.

## 9. Initial 20-Note Series

### ACE Control Research Draft

1. `DRAFT-DAC-01` — Authority Must Shrink, Not Grow
2. `DRAFT-DAC-01` — Revoked Here, Active There
3. `DRAFT-DAC-01` — Replay Without Authority
4. `DRAFT-AID-01` — Who Did the Agent Act For?
5. `DRAFT-AID-01` — One API Key, Many Agents
6. `DRAFT-TDA-01` — Tool Access Is Not Data Authority
7. `DRAFT-TDA-01` — The Over-Tooled Agent
8. `DRAFT-TDA-01` — When Tool Metadata Becomes an Instruction
9. `DRAFT-DEC-01` — A Decision Without Its Evidence
10. `DRAFT-DEC-01` — A Real Citation Can Still Support the Wrong Claim
11. `DRAFT-DEC-01` — Logs Are Not Proof
12. `DRAFT-DEC-01` — Explanations That Did Not Cause the Decision
13. `DRAFT-HITL-01` — The Approval Button Is Not Authorization

### ACE Benchmark Research

14. `MR-3 / TA-3` — Synthetic Reasoning Theft Without Reasoning Traces
15. `TA-3 / MR-3` — Encrypted Reasoning That Is Not Bound to Its Owner
16. `MR-3 / TA-3` — Safe Final Answer, Hazardous Hidden Reasoning
17. `DP-2 / TA-3` — Private Data Hidden Inside Published Agent Traces
18. `AG-5 / CI-2 / DRAFT-TDA-01` — Invisible Prompt Injection Inside Encrypted Reasoning
19. `DP-2 / TA-3` — Refusal Is Not Unlearning
20. `MR-3 / RF` — A Model That Refuses Everything Is Not Safe

## 10. First Release Order

The first five notes are:

1. Authority Must Shrink, Not Grow
2. Tool Access Is Not Data Authority
3. A Decision Without Its Evidence
4. Encrypted Reasoning That Is Not Bound to Its Owner
5. Invisible Prompt Injection Inside Encrypted Reasoning

These establish the initial ACE vocabulary around authority, authorization,
evidence, isolation, and runtime enforcement. They are the priority sequence
across the first two publication batches; the first calendar-day batch contains
the first four completed notes.

## 11. Weekly Release Target

- 2026-08-18: template system and first four notes
- 2026-08-19: four notes
- 2026-08-20: four notes
- 2026-08-21: four notes
- 2026-08-22: four notes
- 2026-08-23: corrections, link verification, and series index review

Publication speed does not waive citation, privacy, or evidence-boundary gates.
