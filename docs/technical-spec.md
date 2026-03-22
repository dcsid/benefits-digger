# Benefits Digger Technical Spec

## Summary

Benefits Digger is a rules-based benefits screener for U.S. public benefits.
It asks adaptive questions, separates federal and state results, shows confidence as explicit factors, and keeps source updates traceable through snapshots and review tasks.

## Current MVP Shape

- FastAPI backend
- Browser UI served from the same app
- SQLite persistence
- Rule-driven screening sessions
- Federal ingestion from the official USA.gov benefit finder feed
- State ingestion from the official USA.gov state social-service directory
- Bounded crawl enrichment of direct official government pages
- Gemini-based relevance filtering over crawled official pages
- Gemini-grounded state program extraction from official state pages
- Review queue entries when source snapshots change

## Core Product Flow

1. User chooses `Federal`, `State`, or `Both`
2. If needed, user selects a state
3. User chooses one or more categories
4. User answers adaptive questions
5. App ranks federal and state results separately
6. Each result shows:
   - eligibility status
   - confidence score
   - matched reasons
   - missing facts
   - source links
   - application link

## Data Model

Main tables:

- `jurisdictions`
- `agencies`
- `programs`
- `program_versions`
- `questions`
- `eligibility_rules`
- `amount_rules`
- `sources`
- `source_snapshots`
- `change_events`
- `review_tasks`
- `screening_sessions`
- `session_answers`

## Ingestion Strategy

Federal:

- pull the official USA.gov benefit finder JSON
- normalize questions and benefit eligibility rules
- version the program records
- enrich program sources with bounded crawl results from direct official government pages
- create a review task when the upstream snapshot changes

State:

- pull the official USA.gov state social-service directory
- create one official state entry-point record per state
- use those official state pages as crawl seeds
- crawl bounded official government pages on the same state site
- use Gemini to filter crawled pages for benefits relevance
- use those crawled official pages as grounding for state program extraction
- version those records and track source changes

## How Benefits Searching Works

So under the hood it works like this:

### Seed discovery

- Federal benefits start from the official USA.gov benefits JSON feed.
- State discovery starts from the official USA.gov state social-services directory.

### Normalize into the local catalog

- The app turns those sources into local `programs`, `questions`, `rules`, `amounts`, and `sources`.
- Federal is the cleanest path because USA.gov already gives structured eligibility criteria.

### Bounded official-site crawling

- The app now also crawls direct official government pages linked from those sources.
- It does not crawl the whole web and it does not try to find literally every benefits site from scratch.
- It stays on official government domains, shallow depth, and capped page counts.

### Gemini relevance filtering

- After pages are crawled, Gemini is used to pick which crawled pages are actually relevant to benefits and program details.
- Gemini is acting like a filter and ranker over official pages, not the source of truth.

### State grounding and extraction

- For state programs, Gemini then uses those crawled official state pages as grounding to generate structured state program entries, questions, and rules.
- That is much better than unguided generation, but still less deterministic than the federal feed path.

### Runtime search

- When a user searches or uses the Explorer, the app is not live-crawling the web.
- It searches the local catalog database.
- Gemini may help interpret a plain-English query, but results come from stored programs and stored official sources.

### Runtime screening

- The screener asks questions from the stored question and rule database.
- It picks the next question by scoring which unanswered question best discriminates among candidate programs.
- Eligibility results are computed deterministically from stored rules, not by Gemini.

### Practical summary

- Federal: official structured feed -> local DB -> deterministic screening
- State: official directory -> bounded crawl of official pages -> Gemini relevance filter -> Gemini grounded extraction -> local DB -> deterministic screening

## Confidence Model

Each result combines:

- rule coverage
- source authority
- source freshness
- program determinism
- amount determinism

This keeps the output explainable instead of relying on a single arbitrary score.

## Known Limitation

- The federal side uses a much more structured and deterministic source path than the state side.
- The state side is now grounded in official crawled pages, but it is still less deterministic because it relies on Gemini to filter and extract structured program data from those pages.
- The crawler is intentionally bounded. It improves source coverage, but it is not a full unrestricted crawl of every government benefits page.

## Next Expansion

- add per-state program connectors
- store richer amount formulas
- expand question coverage
- add reviewer editing tools for extracted rules
- move from SQLite to Postgres for multi-user deployment
