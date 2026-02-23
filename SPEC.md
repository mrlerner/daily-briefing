# Daily Briefing Builder — System Spec (v1)

## Purpose

An AI-powered system that creates personalized daily briefings from plain English requests, delivered through OpenClaw.

**Initial use cases:**

- **Matt's AI engineering briefing** — daily digest of AI engineering news, Anthropic updates, and related developments.
- **Trial of One long COVID briefings** — customizable briefings for patients covering treatment research, pacing strategies, and clinical trial updates. These may be individually configured or pre-configured for entire user cohorts.
- **Fully customizable briefings** — any user can say *"I want car news, stock quotes, and Kansas City Chiefs updates"* and immediately start receiving exactly that.

**Core requirements:**

1. Start from plain English
2. Find high-quality sources automatically
3. Create a personal daily briefing
4. Support pre-configured briefings for entire user groups
5. Improve continuously through conversation
6. Stay reliable and auditable under the hood

---

## 1. User Experience

### Step 1 — Offer

OpenClaw asks:

> "Do you want me to put together a daily briefing for you? What should it include?"

The user responds naturally:

- *"AI engineering news and Anthropic updates."*
- *"Long COVID treatment research and pacing advice."*
- *"TSLA, VOO, and S&P futures."*
- *"Car news and Kansas City Chiefs updates."*

For Trial of One users, the briefing may already be configured by default.

### Step 2 — Light Clarification

Only when needed:

- Which stocks?
- Which team?
- How long should it be?
- What time should I send it?

Defaults are sensible and minimal.

### Step 3 — Source Discovery

OpenClaw:

1. Searches for reputable sources
2. Prefers structured feeds and official APIs
3. Filters out spammy or rumor-driven outlets
4. Selects a small set of high-signal sources
5. Stores them in the user's briefing spec

This is automatic and transparent.

### Step 4 — Daily Delivery

Each night:

1. The system pulls content from selected sources
2. Filters and ranks it
3. Builds a short, readable briefing
4. Publishes the full briefing to GitHub Pages
5. Sends a short summary message via OpenClaw at the chosen time

The summary message includes the top headlines and a link to the full briefing. For example:

> *Today's briefing: OpenAI ships a new reasoning model, Anthropic publishes tool-use benchmarks, and LangChain adds streaming support.* [Read the full briefing →](https://example.github.io/briefings/matt/2026-02-22.html)

The user begins receiving it immediately.

### Step 5 — Continuous Improvement

User feedback is conversational:

- *"Make it shorter."*
- *"Less hype."*
- *"More Chiefs injury updates."*
- *"Focus on EV battery breakthroughs."*
- *"Add clinical trials."*

OpenClaw updates the briefing configuration and shows a preview before changes go live.

---

## 2. System Architecture

### High-Level Flow

```
User (chat)
   ↓
OpenClaw Agent
   ↓
Briefing Skills (custom)
   ↓
Policy Store (YAML files in Git)
   ↓
Nightly Build Pipeline (Python)
   ↓
Per-user HTML + JSON + summary
   ↓
GitHub Pages (full briefing)
   ↓
OpenClaw message (summary + link)
```

### A. Policy Store

Each user has a single editable file:

```
users/<user_id>/briefing.yaml
```

This file defines:

- Topics and interests
- Selected sources
- Filters and exclusions
- Formatting preferences
- Delivery time

For Trial of One, default briefing specs can be pre-created and applied across user cohorts.

**Access rules:**

- OpenClaw can edit these files.
- OpenClaw cannot edit application code.

**Safety constraints on edits:**

- All edits are small diffs
- All edits must pass schema validation
- All edits trigger a preview build before commit

### B. Briefing Skills (OpenClaw)

Two custom skills:

#### `briefing_builder`

Used during setup and major changes.

Responsibilities:

- Run onboarding interview
- Perform source discovery
- Create initial `briefing.yaml`
- Re-run discovery if requested

#### `briefing_admin`

Used for ongoing updates.

Capabilities:

- Add/remove topic
- Adjust length
- Modify filters
- Add/remove source
- Preview today's briefing
- Commit changes
- Trigger rebuild
- Send briefing

### C. Nightly Build System

A scheduled Python job runs daily.

For each user:

1. Load `briefing.yaml`
2. Pull content from listed sources
3. Normalize into a common item format
4. Filter and rank
5. Generate:
   - **HTML** — the full briefing, published to GitHub Pages
   - **JSON** — structured output for programmatic use
   - **Summary** — a short plain-text digest (top 3–5 headlines) for the OpenClaw message
6. Store in:

```
out/<user_id>/<date>.html
out/<user_id>/<date>.json
out/<user_id>/<date>.summary.txt
```

**Publishing:** The `out/` directory is deployed to GitHub Pages. Each briefing is accessible at a stable, per-user URL (e.g., `https://<org>.github.io/briefings/<user_id>/<date>.html`).

**Delivery:** OpenClaw sends the summary text plus the GitHub Pages link to the user at their configured delivery time.

---

## 3. Source Discovery Rules

OpenClaw may discover sources, but must follow these constraints:

| Rule | Rationale |
|------|-----------|
| Prefer official or primary sources | Higher signal, more reliable |
| Prefer structured feeds over scraping | More stable, less brittle |
| Avoid low-quality aggregators | Reduce noise |
| Keep the initial set small | Easier to audit and refine |
| Store everything in YAML | Transparency and version control |
| Require preview approval before committing new sources | User stays in control |

**Discovery is flexible. Execution is stable.**

---

## 4. Design Principles

1. **Plain-English control** — no technical knowledge required
2. **Agent handles setup and improvement** — users just talk
3. **Configuration is human-readable** — YAML files anyone can inspect
4. **Builds are predictable and repeatable** — same spec produces same structure
5. **One system supports any mix of interests** — sports, stocks, health, tech
6. **Supports both personal and cohort-level briefings** — individual or pre-configured
7. **Safe enough for health use cases** — auditable, validated, preview-gated
8. **No technical knowledge required** — from setup through daily use

---

## 5. Summary

The Daily Briefing Builder:

- Works for Matt's AI engineering updates
- Powers Trial of One long COVID briefings (individual or pre-configured)
- Scales to fully customizable daily briefings for any topic mix
- Starts from conversation
- Improves through feedback
- Runs reliably in the background

**OpenClaw is the experience layer.**
**The nightly build is the production layer.**

Everything is controlled through editable briefing specs — not code.

---

## 6. Related Projects

- **[Signex](https://github.com/zhiyuzi/Signex)** — A personal intelligence agent powered by Claude Code. Users describe what to watch, and it collects, analyzes, and learns using extensible sensors (Hacker News, GitHub Trending, Reddit, RSS, search APIs, etc.) and lenses (deep insight, flash brief, pro/con, timeline). Runs entirely inside Claude Code with SQLite storage and a feedback loop for continuous refinement. Similar in spirit to Daily Briefing Builder but oriented around signal monitoring and analysis rather than curated daily delivery.
