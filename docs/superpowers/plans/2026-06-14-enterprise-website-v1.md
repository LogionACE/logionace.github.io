# LogionACE Enterprise Website V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a first credible enterprise-facing LogionACE homepage that combines AI technology positioning with audit/compliance trust.

**Architecture:** Keep the current static GitHub Pages site. Rework `index.html` for buyer-focused information hierarchy and `style.css` for a restrained audit-tech visual system. Preserve JSON-driven leaderboards.

**Tech Stack:** Static HTML, CSS, vanilla JavaScript, GitHub Pages.

---

### Task 1: Reframe Homepage Content

**Files:**
- Modify: `index.html`

- [ ] Replace the current benchmark-led hero with enterprise assurance positioning.
- [ ] Add above-the-fold proof strip: 272 cases, 21 controls, 12 jurisdictions, 9 models.
- [ ] Add sections: What customers receive, public benchmark proof, agent evaluation, methodology, final CTA.
- [ ] Replace non-ASCII separators/dashes with ASCII-safe text to avoid replacement-glyph rendering.
- [ ] Preserve dynamic loading from `ace-leaderboard.json` and `agent-leaderboard.json`.

### Task 2: Rework Visual System

**Files:**
- Modify: `style.css`

- [ ] Replace inherited marketing-site CSS with focused Audit-Tech styling.
- [ ] Use dark enterprise base, muted surfaces, precise blue accent, restrained status colors.
- [ ] Style leaderboard and agent tables for readability.
- [ ] Make mobile layout readable and keep navigation simple.
- [ ] Avoid decorative cyberpunk patterns, neon-green hacker tropes, and heavy animation.

### Task 3: Verify

**Files:**
- Check: `index.html`, `style.css`, JSON assets

- [ ] Run a local static server.
- [ ] Fetch the homepage and assets.
- [ ] Confirm no replacement glyphs or non-ASCII punctuation remain in `index.html`.
- [ ] Confirm leaderboard JavaScript still uses the existing JSON files.
