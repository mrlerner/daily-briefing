# Daily Briefing Builder — Architecture & Build Plan

Companion to [SPEC.md](SPEC.md). This document covers the technical architecture in enough detail to start building.

---

## 1. Repository Structure

```
daily-briefing/
├── SPEC.md
├── ARCHITECTURE.md
├── requirements.txt
│
├── schemas/
│   └── briefing.schema.json          # JSON Schema for briefing.yaml validation
│
├── sources/                             # Curated source catalogs (per domain)
│   ├── ai-engineering.yaml              # AI/ML news, Twitter, Reddit, HN
│   └── long-covid.yaml                  # Medical research, patient resources
│
├── templates/
│   ├── briefing.html.j2              # Jinja2 template for the full HTML briefing
│   ├── summary.txt.j2               # Template for the short summary message
│   └── blocks/
│       ├── weather.html.j2           # Weather forecast block
│       ├── stocks.html.j2            # Stock quotes block
│       └── sports.html.j2            # Sports scores/updates block
│
├── users/
│   ├── matt/
│   │   └── briefing.yaml            # Matt's AI engineering briefing
│   └── _cohorts/
│       └── trial-of-one-long-covid/
│           └── briefing.yaml         # Default briefing for Trial of One users
│
├── src/
│   ├── build.py                      # Main entry point — nightly build
│   ├── config.py                     # Load and validate briefing.yaml
│   ├── fetchers/                     # News source fetchers (return item lists)
│   │   ├── __init__.py
│   │   ├── rss.py                    # RSS/Atom feed fetcher
│   │   ├── api.py                    # Generic REST API fetcher
│   │   └── web.py                    # Web page fetcher (fallback)
│   ├── blocks/                       # Structured data block fetchers
│   │   ├── __init__.py
│   │   ├── weather.py                # Weather forecast (e.g., OpenWeatherMap)
│   │   ├── stocks.py                 # Stock quotes (e.g., Yahoo Finance API)
│   │   └── sports.py                 # Sports scores and updates
│   ├── normalize.py                  # Convert fetched items to common format
│   ├── rank.py                       # Filter and rank news items
│   ├── render.py                     # Generate HTML, JSON, and summary
│   └── publish.py                    # Git commit + push to trigger Pages deploy
│
├── out/                              # Build output (deployed to GitHub Pages)
│   └── <user_id>/
│       ├── <date>.html
│       ├── <date>.json
│       ├── <date>.summary.txt
│       └── index.html                # Redirects to latest briefing
│
└── .github/
    └── workflows/
        ├── build.yml                 # Scheduled nightly build
        └── pages.yml                 # Deploy out/ to GitHub Pages
```

---

## 2. Briefing Spec Format

Each user's `briefing.yaml` is the single source of truth for their briefing. Everything the build system needs is in this file.

### Example: Matt's AI Engineering Briefing

```yaml
version: 1

user:
  id: matt
  name: Matt

topics:
  - name: AI engineering
    keywords: ["AI", "LLM", "machine learning", "transformer"]
    priority: high
  - name: Anthropic
    keywords: ["Anthropic", "Claude"]
    priority: high
  - name: Developer tools
    keywords: ["LangChain", "LlamaIndex", "vector database"]
    priority: medium

sources_from: ai-engineering       # load curated catalog from sources/ai-engineering.yaml

blocks:
  - type: weather
    label: Weather
    location: "New York, NY"
    days: 7
    highlight: sunny

filters:
  exclude_keywords: ["crypto", "NFT", "blockchain"]
  max_age_hours: 36
  min_relevance: 0.3

format:
  max_items: 15
  summary_items: 4
  style: concise

delivery:
  time: "07:00"
  timezone: America/New_York
```

### Example: Trial of One Long COVID Cohort Default

```yaml
version: 1

cohort:
  id: trial-of-one-long-covid
  name: Trial of One — Long COVID

topics:
  - name: Long COVID treatment
    keywords: ["long COVID", "post-COVID", "PASC"]
    priority: high
  - name: Pacing and energy management
    keywords: ["pacing", "energy envelope", "PEM", "post-exertional malaise"]
    priority: high
  - name: Clinical trials
    keywords: ["clinical trial", "long COVID trial"]
    priority: medium

sources:
  - name: NIH Long COVID Research
    type: rss
    url: https://www.nih.gov/rss/long-covid.xml
  - name: PubMed Long COVID
    type: api
    url: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
    params:
      db: pubmed
      term: "long COVID treatment"
      retmax: 20
      sort: date

filters:
  exclude_keywords: ["ivermectin", "hydroxychloroquine"]
  max_age_hours: 48
  min_relevance: 0.4

format:
  max_items: 10
  summary_items: 3
  style: accessible

delivery:
  time: "08:00"
  timezone: America/New_York
```

When a new Trial of One user is onboarded, their `briefing.yaml` is initialized from the cohort default and can be customized from there.

---

## 3. Curated Source Catalogs

Some domains — like AI engineering and long COVID — benefit from hand-curated, pre-validated source lists rather than on-the-fly discovery. These are checked into the repo as YAML files under `sources/`.

### Why Curated Catalogs Exist

Source discovery (Phase 5) works well for general-interest topics where finding an RSS feed or subreddit is straightforward. But for domains we care about deeply, we want:

- **Validated sources** — feeds tested by hand, confirmed to parse correctly and produce signal
- **Platform-specific collection** — not just RSS, but also Reddit subreddits with tuned search queries, Hacker News via Algolia, Twitter/X accounts via Nitter, Bluesky handles
- **Keyword filters** — per-platform relevance filters already dialed in (e.g., which AI keywords to match against Reddit post titles)
- **Stability** — the source list doesn't change unless someone deliberately updates it

Curated catalogs are the starting point for these briefings. Users can still add, remove, or adjust sources through OpenClaw — but they start with something good instead of discovering from scratch.

### Catalog Format

Each catalog file lives in `sources/` and defines sources grouped by platform:

```yaml
catalog: ai-engineering
name: AI Engineering
description: AI/ML news, developer tools, and engineering leadership

rss:
  - name: TechCrunch AI
    url: https://techcrunch.com/category/artificial-intelligence/feed/
  # ...

hn:
  queries:
    - "AI engineering team"
    - "Claude Code"
    # ...

reddit:
  subreddits: ["ExperiencedDevs", "programming", "MachineLearning"]
  queries:
    - "AI coding assistant"
    # ...
  keywords: ["ai", "llm", "gpt", "claude"]

twitter:
  accounts: ["AnthropicAI", "OpenAI", "karpathy"]

bluesky:
  accounts: ["simonwillison.net", "karpathy.ai"]
```

See `sources/ai-engineering.yaml` for the complete, validated list.

### How Briefings Reference Catalogs

A `briefing.yaml` can pull in a curated catalog instead of (or in addition to) listing sources inline:

```yaml
sources_from: ai-engineering    # load sources/ai-engineering.yaml

sources:                        # additional inline sources (merged with catalog)
  - name: My Team's Blog
    type: rss
    url: https://example.com/blog/feed.xml
```

When `sources_from` is set, the build pipeline loads the catalog and merges it with any inline `sources`. Inline sources are additive — they don't replace the catalog.

### Catalog vs. Inline Sources

| | Curated catalog | Inline sources |
|---|---|---|
| **Defined in** | `sources/<catalog>.yaml` | `users/<id>/briefing.yaml` |
| **Shared across** | Multiple users referencing the same catalog | Single user |
| **Updated by** | Manual curation (checked into Git) | OpenClaw or manual edit |
| **Best for** | Domains with known, tested sources | One-off additions, personal feeds |

A briefing can use only a catalog, only inline sources, or both. The only requirement is that it has at least one source of content (sources or blocks).

---

## 4. Common Item Format

Every fetcher normalizes its output into this structure before ranking:

```json
{
  "id": "sha256-hash-of-url",
  "title": "Anthropic Publishes New Tool-Use Benchmarks",
  "url": "https://anthropic.com/blog/tool-use-benchmarks",
  "source": "Anthropic Blog",
  "published": "2026-02-22T14:30:00Z",
  "summary": "Two-sentence summary of the item.",
  "topics_matched": ["Anthropic", "AI engineering"],
  "relevance_score": 0.87
}
```

This is the contract between news source fetchers and the ranking/rendering stages. All news fetchers must produce this; everything downstream consumes only this.

---

## 5. Content Blocks

Not everything in a briefing is a news item. Some content is structured data — weather forecasts, stock quotes, sports scores — that comes from dedicated APIs and renders as its own section rather than a ranked list of articles.

### How Blocks Differ from News Sources

| | News sources | Content blocks |
|---|---|---|
| **Data shape** | List of articles | Structured data (forecast, quotes, scores) |
| **Fetched by** | `src/fetchers/` | `src/blocks/` |
| **Ranked?** | Yes — filtered and scored by relevance | No — rendered as-is |
| **Template** | Shared item list in `briefing.html.j2` | Per-type partial in `templates/blocks/` |
| **Summary contribution** | Top N headlines | One-line callout (e.g., "Sunny Wed and Thu") |

### Block Config in `briefing.yaml`

```yaml
blocks:
  - type: weather
    label: Weather
    location: "New York, NY"
    days: 7
    highlight: sunny          # flag days matching this condition

  - type: stocks
    label: Portfolio
    tickers: ["TSLA", "VOO", "SPY"]
    show: [price, change_pct]

  - type: sports
    label: Chiefs
    league: nfl
    team: KC
    show: [schedule, injuries]
```

Each block type has a dedicated fetcher in `src/blocks/` that knows how to call the relevant API and return structured data. Each also has a Jinja2 partial in `templates/blocks/` that knows how to render it.

### Block Output Format

Block fetchers return a typed dict, not the common item format. Example for weather:

```json
{
  "type": "weather",
  "label": "Weather",
  "location": "New York, NY",
  "days": [
    { "date": "2026-02-23", "day": "Mon", "high": 42, "low": 31, "condition": "cloudy" },
    { "date": "2026-02-24", "day": "Tue", "high": 38, "low": 28, "condition": "snow" },
    { "date": "2026-02-25", "day": "Wed", "high": 51, "low": 39, "condition": "sunny" },
    { "date": "2026-02-26", "day": "Thu", "high": 55, "low": 42, "condition": "sunny" },
    { "date": "2026-02-27", "day": "Fri", "high": 45, "low": 34, "condition": "rain" }
  ],
  "highlights": ["Wed", "Thu"],
  "summary_line": "Sunny Wednesday and Thursday — good days to be outside."
}
```

Every block fetcher must return a `summary_line` — a single sentence that gets folded into the briefing summary message.

### Supported Block Types (Initial)

| Type | API | Config keys |
|------|-----|-------------|
| `weather` | OpenWeatherMap (free tier) | `location`, `days`, `highlight` |
| `stocks` | Yahoo Finance / Alpha Vantage | `tickers`, `show` |
| `sports` | ESPN API / public feeds | `league`, `team`, `show` |

New block types can be added by creating a fetcher in `src/blocks/` and a template in `templates/blocks/`. No changes to the core pipeline needed.

---

## 6. Build Pipeline

### Entry Point: `src/build.py`

```
for each user in users/:
    1.  Load briefing.yaml
    2.  Validate against schema
    3.  For each source → call appropriate news fetcher
    4.  Normalize all news items to common format
    5.  Score relevance against user's topics/keywords
    6.  Filter (age, relevance threshold, exclusions)
    7.  Rank and cap to max_items
    8.  For each block → call appropriate block fetcher
    9.  Render HTML: blocks first, then ranked news items
   10.  Render JSON (news items + block data)
   11.  Render summary (block summary lines + top N headlines)
   12.  Write to out/<user_id>/<date>.*
   13.  Update out/<user_id>/index.html → latest
```

Blocks and news items are fetched independently and composed at render time. A briefing can have only blocks, only news, or both.

### Fetchers

Each source type has a fetcher module:

| Type | Module | Input | Notes |
|------|--------|-------|-------|
| `rss` | `fetchers/rss.py` | Feed URL | Uses `feedparser`. Handles RSS and Atom. |
| `api` | `fetchers/api.py` | URL + params | Generic HTTP GET, expects JSON. Needs per-API response mapping. |
| `web` | `fetchers/web.py` | Page URL + selectors | Fallback scraper. Uses CSS selectors. Last resort. |

All fetchers return a list of common-format items.

### Relevance Scoring

Simple keyword-based scoring for v1:

1. Check title and summary against topic keywords
2. Weight by topic priority (high = 1.0, medium = 0.6, low = 0.3)
3. Boost for recency (newer = higher)
4. Filter below `min_relevance` threshold

This is intentionally simple. Can be replaced with embeddings-based scoring later without changing the pipeline structure.

### Rendering

Uses Jinja2 templates:

- **HTML** (`briefing.html.j2`) — clean, readable single-page document. Mobile-friendly. No JavaScript required. Content blocks render at the top in their own sections (using per-type partials from `templates/blocks/`), followed by the ranked news items.
- **JSON** (`<date>.json`) — block data + ranked item list, for programmatic consumption.
- **Summary** (`summary.txt.j2`) — block summary lines + top N headlines as a short paragraph. This is what OpenClaw sends in the chat message.

Summary template output example:

```
Sunny Wednesday and Thursday — good days to be outside.

Today's briefing: OpenAI ships a new reasoning model, Anthropic publishes
tool-use benchmarks, and LangChain adds streaming support.

Full briefing: https://<org>.github.io/briefings/matt/2026-02-22.html
```

---

## 7. Scheduling & Deployment

### GitHub Actions: Nightly Build

```yaml
# .github/workflows/build.yml
name: Nightly Briefing Build
on:
  schedule:
    - cron: '0 5 * * *'    # 5:00 UTC daily (midnight ET)
  workflow_dispatch:         # manual trigger for testing

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python src/build.py
      - uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./out
```

The build runs early enough that all briefings are published before the earliest delivery time. OpenClaw handles per-user delivery timing separately.

### GitHub Pages

The `out/` directory is published as a static site. URL structure:

```
https://<org>.github.io/daily-briefing/<user_id>/<date>.html
https://<org>.github.io/daily-briefing/<user_id>/index.html  → latest
```

No server required. No authentication for now (briefings are not sensitive in v1). Access control can be layered on later if needed for health use cases.

---

## 8. OpenClaw Integration

### Division of Responsibility

**This repo** handles briefing generation: fetching content, ranking, rendering HTML/JSON/summary, and publishing to GitHub Pages. A laptop `launchd` cron job runs `python3 src/build.py` daily at 5 AM ET so briefings are pre-built.

**OpenClaw** handles everything user-facing: scheduled delivery (via its own cron system), messaging (via whatever channel each user is on — Telegram, WhatsApp, iMessage, etc.), and conversational interaction. OpenClaw already knows how to reach each user; we don't duplicate that.

**The filesystem is the contract.** OpenClaw writes YAML configs, the build reads them. The build writes output files, OpenClaw reads them.

### Skill: `daily-briefing`

Installed at `~/.openclaw/skills/daily-briefing/SKILL.md` (shared across all OpenClaw agents). This single skill teaches OpenClaw three capabilities:

**1. Find a briefing.** The skill tells the agent where pre-built output lives:
- Summary: `out/<user_id>/<briefing_name>/<YYYY-MM-DD>.summary.txt`
- Full HTML: `out/<user_id>/<briefing_name>/<YYYY-MM-DD>.html`
- GitHub Pages: `https://mrlerner.github.io/daily-briefing/<user_id>/<briefing_name>/<date>.html`

The pre-built summary is already formatted for messaging (top headlines + link). OpenClaw sends it directly without rewriting.

**2. Modify a briefing.** The skill maps natural language to YAML edits:

| User says | YAML change |
|-----------|-------------|
| "Make it shorter" | Decrease `format.max_items` |
| "Less hype" | Add hype-related terms to `filters.exclude_keywords` |
| "More Chiefs injury updates" | Add topic with injury-related keywords |
| "Add clinical trials" | Add topic + discover relevant sources |
| "Remove ArXiv" | Remove source entry |
| "Add weather for New York" | Add weather block to `blocks` |
| "I don't need the sports section" | Remove block entry |

Workflow: read the YAML, make the edit, show a diff, write on confirmation.

**3. Generate on demand.** The skill tells the agent how to run the build:
```
cd /Users/Shared/daily-briefing && python3 src/build.py --user <user_id> --briefing <briefing_name>
```
After building (~25 seconds), the agent reads the summary and sends it to the user. This is used when a user modifies their briefing and wants to see the result immediately.

### Scheduled Delivery

OpenClaw configures its own cron job (via `openclaw cron add`) to deliver briefings at each user's preferred time. The cron job triggers an agent turn that uses the `daily-briefing` skill to find and send the pre-built summary. Delivery channel and timing are OpenClaw's concern, not this repo's.

### Laptop Build Cron

A `launchd` plist (`~/Library/LaunchAgents/com.dailybriefing.build.plist`) runs `scripts/build.sh` daily at 5 AM ET. The script:
1. Runs `python3 src/build.py` (generates all users' briefings)
2. Logs to `logs/build.log`

GitHub Pages deployment is handled separately (GitHub Actions or manual push).

---

## 9. Cohort System

For Trial of One and future group briefings:

```
users/_cohorts/<cohort_id>/briefing.yaml    # cohort default
users/<user_id>/briefing.yaml               # individual (inherits from cohort)
```

**Onboarding a cohort user:**
1. Copy cohort default to `users/<user_id>/briefing.yaml`
2. User can customize from there — their file diverges from the cohort template
3. Cohort template updates don't automatically propagate to existing users (avoids surprises)

**Pre-configured briefings:** An admin (or OpenClaw) can create a cohort default once, and every new user in that cohort gets a working briefing immediately with no setup conversation required.

---

## 10. Schema Validation

`schemas/briefing.schema.json` enforces:

- Required fields: `version`, `delivery`, and at least one of `sources` or `blocks`
- Valid source types: `rss`, `api`, `web`
- Valid block types: `weather`, `stocks`, `sports` (extensible)
- Per-block-type required fields (e.g., weather requires `location`)
- Valid time format for delivery
- Valid timezone
- No unknown top-level keys

Validation runs:
- Before every commit (OpenClaw edits)
- At the start of every build (nightly pipeline)
- As a CI check on pull requests

---

## 11. Build Phases

See [PHASES.md](PHASES.md) for the detailed, up-to-date phase tracker.

---

## 12. Dependencies

Initial Python dependencies:

| Package | Purpose |
|---------|---------|
| `feedparser` | Parse RSS and Atom feeds |
| `jinja2` | HTML and summary templating |
| `pyyaml` | Load briefing YAML files |
| `jsonschema` | Validate YAML against schema |
| `requests` | HTTP client for API and web fetchers |
| `beautifulsoup4` | Web fetcher HTML parsing (Phase 5) |

No database. No server. No deployment infrastructure beyond GitHub Pages and Actions.

---

## 13. What This Architecture Avoids

- **No backend server** — static site generation, deployed to Pages
- **No database** — YAML files in Git are the data store
- **No user auth** — OpenClaw handles identity; Pages are public for now
- **No complex orchestration** — one Python script, one cron schedule
- **No custom infrastructure** — GitHub provides hosting, CI, and version control

The entire system is a Git repo with YAML configs, a Python build script, and GitHub Actions. That's it.
