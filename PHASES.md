# Daily Briefing Builder — Implementation Phases

Companion to [SPEC.md](SPEC.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

Each phase ends with something you can see or use. Sub-phases (e.g., 1.5) are intermediate milestones within a larger phase.

---

## Phase 0 — Source Research & Curation

**Goal:** Identify and validate the actual sources for both briefings before writing any code.

### Phase 0.1 — AI Engineering Briefing Sources

- [x] Research RSS feeds for AI/ML news (Hacker News filtered, ArXiv CS.AI, etc.)
- [x] Find Anthropic's official blog feed URL and verify it works
- [x] Find 3–5 high-signal individual blogs (Simon Willison, Lilian Weng, etc.)
- [x] Find developer tools feeds (LangChain blog, LlamaIndex blog, etc.)
- [x] Test each feed: does it parse? How many items per day? How noisy?
- [x] Document each source: name, URL, type, expected volume, signal quality
- [x] Draft Matt's `briefing.yaml` with the validated source list

Sources ported from the working openclaw-setup system into `sources/ai-engineering.yaml`. Includes RSS (TechCrunch, WSJ via Google News), HN (12 Algolia queries), Reddit (6 subreddits + 8 search queries + 15 keyword filters), Twitter/X (9 accounts), Bluesky (3 accounts).

### Phase 0.2 — Long COVID Briefing Sources

- [x] Research PubMed API for long COVID queries (test `esearch` endpoint)
- [x] Find NIH and CDC RSS feeds related to long COVID
- [x] Find patient-facing sources (Body Politic, ME/CFS resources, etc.)
- [x] Find clinical trial feeds (ClinicalTrials.gov RSS or API)
- [x] Test each feed for signal quality and update frequency
- [x] Document each source
- [x] Draft Trial of One cohort `briefing.yaml` with the validated source list

Sources ported from healthcoach-v1. Cohort YAML at `users/_cohorts/trial-of-one-long-covid/briefing.yaml` with 6 validated RSS feeds (STAT News, ScienceDaily x3, The Sick Times, Nature Medicine).

### Phase 0.3 — Weather Block Research

- [x] ~~Sign up for OpenWeatherMap free tier API key~~ Using wttr.in instead (free, no API key)
- [x] Test the 7-day forecast endpoint
- [x] Verify response format and rate limits
- [x] Document the API contract (request params, response shape)

Using wttr.in `?format=j1` — returns 3-day forecast with hourly data. Free, no auth needed, reliable with retry logic.

### Phase 0.4 — Project Scaffolding

- [x] Initialize Git repo
- [x] Create directory structure per ARCHITECTURE.md
- [x] Create `requirements.txt` with pinned versions
- [x] Define `schemas/briefing.schema.json`
- [x] Commit Matt's `briefing.yaml`
- [x] Commit Trial of One cohort `briefing.yaml`
- [x] Verify both YAMLs pass schema validation

**Milestone:** Two validated YAML briefing specs in a structured repo, with every source tested by hand. ✅

---

## Phase 1 — Generate the HTML

**Goal:** Run a script that reads a `briefing.yaml`, fetches real content, and produces a readable HTML file.

### Phase 1.1 — RSS Fetcher

- [x] Build `src/fetchers/rss.py` using `feedparser`
- [x] Handle both RSS and Atom formats
- [x] Extract title, URL, published date, and summary from each entry
- [x] Normalize output to the common item format
- [x] Handle fetch errors gracefully (timeout, malformed feed, 404)
- [x] Test against each source in Matt's `briefing.yaml`
- [ ] Test against each source in the long COVID `briefing.yaml`

Also built:
- [x] `src/fetchers/hn.py` — Hacker News via Algolia API (ported from openclaw-setup)
- [x] `src/fetchers/reddit.py` — Reddit via public JSON API (ported from openclaw-setup)

### Phase 1.2 — Normalizer & Ranker

- [x] Build `src/normalize.py` — convert raw fetcher output to common item format
- [x] Build `src/rank.py` — keyword-based relevance scoring
- [x] Implement topic matching (title + summary vs. keywords)
- [x] Implement priority weighting (high/medium/low)
- [x] Implement recency boost
- [x] Implement `min_relevance` threshold filtering
- [x] Implement `exclude_keywords` filtering
- [x] Implement `max_age_hours` filtering
- [x] Implement `max_items` cap
- [x] Implement source-diversity ranking (per-source-type caps to ensure RSS/HN/Reddit all get representation)
- [x] Test: feed in 325 items, verify the top 30 are sensible and source-diverse

### Phase 1.3 — Weather Block Fetcher

- [x] Build `src/blocks/weather.py`
- [x] ~~Call OpenWeatherMap 7-day forecast API~~ Using wttr.in (free, no key)
- [x] Parse response into block output format (day, high, low, condition)
- [x] Implement `highlight` logic (flag days matching condition, e.g., "sunny")
- [x] Generate `summary_line` (e.g., "Sunny Wednesday and Thursday — good days to be outside.")
- [x] Handle API errors gracefully (bad key, rate limit, timeout)
- [x] Test with a real location (Seattle, WA)

### Phase 1.4 — HTML Renderer

- [x] Build `src/render.py`
- [x] Create `templates/briefing.html.j2` — full design from DESIGN.md reference
- [x] ~~Create `templates/blocks/weather.html.j2`~~ Weather block inline in main template
- [x] Render blocks at the top, news items below
- [x] Each news item shows: title (linked), source name, publication time, summary
- [x] Include briefing date and user name in the header
- [x] Generate `<date>.json` alongside the HTML
- [x] Test: generate Matt's briefing HTML and open it in a browser

Output: 43KB HTML with Inter font, emerald accent color scheme, 5 sections (TechCrunch, WSJ Tech, WSJ AI, HN, Reddit), weather card, TOC, sticky section headers.

### Phase 1.5 — Summary Generator

- [x] Create `templates/summary.txt.j2`
- [x] Include block summary lines first
- [x] Include top N news headlines (from `format.summary_items`)
- [x] Include link to full briefing (placeholder URL for now)
- [x] Generate `<date>.summary.txt` alongside HTML and JSON
- [x] Test: verify summary reads well as a standalone chat message

### Phase 1.6 — Build Script

- [x] Build `src/build.py` — main entry point
- [x] Build `src/config.py` — load YAML, validate against schema, resolve `sources_from` catalogs
- [x] Wire together: load config → fetch sources → fetch blocks → rank → render → write output
- [x] Run for a single user by specifying user ID (`--user matt`)
- [x] Run for all users in `users/` directory
- [x] Write output to `out/<user_id>/<date>.*`
- [x] Add basic logging (which user, how many items fetched, how many after filtering)
- [x] Test: `python src/build.py` produces complete output for Matt

**Milestone:** Run `python src/build.py` and get a real, readable HTML briefing with weather and ranked AI news. ✅

Tested: 326 items fetched from 3 RSS feeds + HN Algolia + Reddit JSON API. Filtered to 97 relevant items, ranked and capped to 30 (10 per source type). Weather block from wttr.in. Full HTML, JSON, and summary output generated in ~25 seconds.

---

## Phase 2 — Post to GitHub Pages

**Goal:** The briefing is published to a URL you can open on any device.

### Phase 2.1 — Manual Deploy

- [x] Create the GitHub repo (public or private with Pages enabled)
- [x] Push the project
- [x] Run `python src/build.py` locally
- [x] Push `out/` to `gh-pages` branch manually
- [x] Verify the briefing loads at the GitHub Pages URL
- [ ] Test on mobile

Live at: https://mrlerner.github.io/daily-briefing/matt/2026-02-23.html

### Phase 2.2 — Index Page

- [x] Generate `out/<user_id>/index.html` that redirects to the latest briefing
- [x] Generate `out/index.html` listing all users (for admin/review purposes)
- [x] Preserve previous days' briefings (don't overwrite, accumulate)

Both index pages are generated by `build.py` automatically.

### Phase 2.3 — GitHub Actions Nightly Build

- [x] Create `.github/workflows/build.yml`
- [x] Schedule at 5:00 UTC (midnight ET) via cron
- [x] Add `workflow_dispatch` for manual triggers
- [x] Install dependencies and run `python src/build.py`
- [x] Deploy `out/` to GitHub Pages using `peaceiris/actions-gh-pages`
- [ ] Store API keys (OpenWeatherMap, etc.) as GitHub Actions secrets
- [ ] Test: trigger manually, verify new briefing appears on Pages

Workflow file created. No secrets needed for v1 (wttr.in weather is free/no-auth, all other sources are public APIs).

### Phase 2.4 — Build Reliability

- [x] Add error handling: if one source fails, skip it and continue
- [x] Add error handling: if one user's build fails, continue to next user
- [x] Add build summary log (`out/build-log.json` — timestamp, users built, errors)
- [ ] Add a build badge to the repo README
- [ ] Test: intentionally break one source URL, verify the build still completes

All error handling is built into `build.py`. Each fetcher catches its own exceptions and logs warnings. Per-user try/except ensures one user's failure doesn't block others. `build-log.json` written after every build.

**Milestone:** Every morning, a fresh briefing is automatically published to a URL. No manual steps.

*Partially complete — build pipeline works locally, GitHub Actions workflow created, awaiting repo setup and first deploy.*

---

## Phase 3 — Multi-User Support

**Goal:** The system builds briefings for multiple users, including cohort-based defaults.

### Phase 3.1 — User Directory Structure

- [x] Ensure `build.py` iterates over all `users/<user_id>/` directories
- [x] Skip `users/_cohorts/` during the build (templates only, not buildable users)
- [x] Each user's output is isolated in `out/<user_id>/`
- [ ] Test: add a second test user, verify both briefings build

`discover_users()` in `config.py` iterates `users/` and skips `_` prefixed directories.

### Phase 3.2 — Cohort Template System

- [x] Create `users/_cohorts/trial-of-one-long-covid/briefing.yaml`
- [ ] Build a script or `build.py` flag to onboard a new user from a cohort template
- [ ] Onboarding copies the cohort YAML into `users/<user_id>/briefing.yaml`
- [ ] The new user's YAML is independent — edits don't affect the cohort template
- [ ] Test: onboard a new Trial of One user, verify their briefing builds correctly

### Phase 3.3 — Long COVID Briefing End-to-End

- [x] Finalize the long COVID cohort `briefing.yaml` with real, validated sources
- [ ] Add PubMed API fetcher if needed (or confirm RSS covers it)
- [ ] Build a sample long COVID briefing and review for quality
- [ ] Adjust keywords, filters, and source list based on output quality
- [ ] Verify the summary reads well for a patient audience (accessible language)

**Milestone:** Multiple users receive different briefings from the same build. A new Trial of One user can be onboarded in one step.

---

## Phase 4 — Deliver Briefing Through OpenClaw

**Goal:** Users receive their briefing summary as a message from OpenClaw at their chosen time.

### Phase 4.1 — Delivery Mechanism

- [ ] Determine how OpenClaw sends scheduled messages (cron job, webhook, polling)
- [ ] Build the delivery script or skill that reads `<date>.summary.txt`
- [ ] Construct the message: summary text + GitHub Pages link
- [ ] Send via OpenClaw's messaging channel

### Phase 4.2 — Scheduled Delivery

- [ ] Read each user's `delivery.time` and `delivery.timezone` from their YAML
- [ ] Schedule message delivery at the correct local time
- [ ] Handle timezone edge cases (DST transitions, UTC offsets)
- [ ] Test: configure a delivery time a few minutes in the future, verify message arrives

### Phase 4.3 — Delivery Confirmation & Error Handling

- [ ] Log each delivery (user, timestamp, success/failure)
- [ ] Handle missing briefing gracefully (build failed? send a "no briefing today" note)
- [ ] Handle missing summary file (fall back to just sending the link)
- [ ] Test: delete a summary file, verify OpenClaw handles it gracefully

**Milestone:** Each morning, OpenClaw sends a short message with the top headlines and a link to the full briefing, at the right time for each user.

---

## Phase 5 — Conversational Modification Through OpenClaw

**Goal:** Users can change their briefing by talking to OpenClaw.

### Phase 5.1 — `briefing_admin` Skill (Simple Edits)

- [ ] Build the OpenClaw skill that can read a user's `briefing.yaml`
- [ ] Implement: add a topic (new entry in `topics`)
- [ ] Implement: remove a topic
- [ ] Implement: add a source (new entry in `sources`)
- [ ] Implement: remove a source
- [ ] Implement: add a block (new entry in `blocks`)
- [ ] Implement: remove a block
- [ ] Implement: change `format.max_items` (make it shorter/longer)
- [ ] Implement: add/remove `filters.exclude_keywords`
- [ ] Implement: change `delivery.time`
- [ ] All edits validate against schema before committing
- [ ] Test: "Make it shorter" → verify `max_items` decreases in the YAML

### Phase 5.2 — Preview Before Commit

- [ ] After producing a YAML edit, run a preview build
- [ ] Show the user a before/after summary (what changed in the YAML)
- [ ] Show a preview of what tomorrow's briefing would look like
- [ ] User confirms → commit the change
- [ ] User rejects → discard the change
- [ ] Test: request a change, review preview, confirm, verify YAML is updated

### Phase 5.3 — `briefing_builder` Skill (Onboarding)

- [ ] Build the onboarding conversation flow
- [ ] Parse natural language into candidate topics, keywords, and block types
- [ ] Run source discovery: search for feeds matching the user's interests
- [ ] Present candidate sources to the user for approval
- [ ] Assemble and validate the new `briefing.yaml`
- [ ] Run a preview build and show the user a sample briefing
- [ ] On approval, commit the YAML and trigger the first real build
- [ ] Test: walk through onboarding for a brand new interest ("Kansas City Chiefs updates")

### Phase 5.4 — Source Discovery

- [ ] Build the source discovery logic (search for RSS feeds given a topic)
- [ ] Rank candidate sources by quality signals (official domain, feed freshness, item count)
- [ ] Apply the source discovery rules from SPEC.md (prefer primary, prefer structured, avoid junk)
- [ ] Present top 3–5 candidates to the user
- [ ] Store selected sources in YAML
- [ ] Test: discover sources for "electric vehicle news", verify quality

**Milestone:** A user can say "Add weather for San Francisco" or "I want less hype" and OpenClaw updates their briefing with a preview.

---

## Phase 6 — World-Class Typography & Styling

**Goal:** The HTML briefing looks beautiful — something you'd want to read every morning.

### Phase 6.1 — Typography Foundation

- [x] Choose a typeface pairing — Inter (Google Fonts) with system fallback
- [ ] ~~Use system font stack or self-hosted web fonts (no Google Fonts dependency)~~ Currently using Google Fonts; can migrate to self-hosted later
- [x] Set a readable baseline: 15px body, 1.6 line height, 720px max-width
- [x] Establish a type scale (headings, subheadings, body, captions, metadata)
- [x] Style links: subtle emerald green, underline on hover

### Phase 6.2 — Layout & Structure

- [x] Single-column reading layout, centered, with generous margins
- [x] Clear visual hierarchy: date header → TOC → blocks → news sections → footer
- [x] Section dividers (2px solid borders between sections)
- [x] Each news item: title (linked), source, time, summary — visually distinct layers
- [x] Weather block: card-based layout, highlighted days stand out
- [x] Responsive: reads well on mobile (padding-based, no fixed widths)

### Phase 6.3 — Color & Polish

- [x] Light mode: white background with slate text, emerald accents
- [ ] Dark mode support via `prefers-color-scheme` media query
- [x] Subtle color accents for source labels (emerald), rank badges (emerald tint)
- [x] No decorative clutter — every visual element serves a purpose
- [ ] Print stylesheet: clean printout with no navigation or decorative elements

### Phase 6.4 — Micro-Details

- [ ] Proper typographic quotes and dashes (not straight quotes)
- [x] Smart date formatting ("February 22, 2026" not "2026-02-22")
- [x] Relative timestamps for news items ("3h ago", "12h ago")
- [ ] Favicon and Open Graph meta tags (for nice link previews when sharing)
- [ ] Accessible: semantic HTML, sufficient contrast ratios, screen-reader friendly
- [x] Fast: page is ~43KB with no external JS dependencies

### Phase 6.5 — Template Refinement

- [ ] Review 5+ real daily builds and iterate on layout
- [ ] Adjust spacing, sizing, and hierarchy based on actual content
- [ ] Test with short briefings (3 items) and long ones (15 items)
- [ ] Test with and without blocks
- [ ] Get feedback from at least one other person
- [ ] Finalize and lock the template

**Milestone:** The briefing is something you'd be proud to show anyone. Clean, fast, readable, beautiful.

---

## Future Phases (Not Scheduled)

These are known directions but not yet planned in detail.

### Twitter / X Integration

- [x] Research Twitter API v2 access and costs — using Nitter RSS instead (no API needed)
- [x] Build a Twitter list or search-based fetcher — in `sources/ai-engineering.yaml` (Nitter + Bluesky accounts)
- [ ] Handle rate limits and authentication
- [ ] Build `src/fetchers/twitter.py` — Nitter RSS + Bluesky fetcher
- [ ] Normalize tweets into the common item format

### Subscription / Paywalled Sources

- [ ] Research feasibility (newsletter ingestion, RSS-from-email services)
- [ ] Build an email-to-feed bridge or integrate with a service like Kill the Newsletter
- [ ] Handle authentication for paywalled APIs

### Stocks & Sports Blocks

- [ ] Build `src/blocks/stocks.py` (Alpha Vantage or Yahoo Finance)
- [ ] Build `src/blocks/sports.py` (ESPN API or similar)
- [ ] Create templates for each block type
- [ ] Add to schema validation

### Advanced Relevance Scoring

- [ ] Replace keyword matching with embeddings-based scoring
- [ ] Use a lightweight model (e.g., sentence-transformers) for semantic similarity
- [ ] Incorporate user feedback signals (clicked vs. skipped items)

### Access Control

- [ ] Add authentication for health-related briefings
- [ ] Token-based or password-protected GitHub Pages (or move to a different host)
- [ ] Per-user access control for sensitive cohort briefings

### Build Monitoring & Alerts

- [ ] Alert on build failure (Slack, email, or OpenClaw message)
- [ ] Monitor source health (detect feeds that haven't updated in N days)
- [ ] Track build metrics over time (items fetched, filtered, published)

---

## Phase Summary

| Phase | What You Get | Status |
|-------|-------------|--------|
| **0** | Validated sources, structured repo, two YAML specs | ✅ Complete |
| **1** | A real HTML briefing generated from code | ✅ Complete |
| **2** | Briefing auto-published to a URL every morning | 🔶 Partial (needs repo + deploy) |
| **3** | Multiple users, cohort onboarding, long COVID briefing live | 🔶 Partial (structure done) |
| **4** | OpenClaw sends you the briefing summary each morning | Not started |
| **5** | Change your briefing by talking to OpenClaw | Not started |
| **6** | A briefing that looks as good as it reads | 🔶 Partial (baseline styling done) |
