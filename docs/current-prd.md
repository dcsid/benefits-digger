# Benefits Digger Current-State PRD

## 1. Document Status

This PRD describes the product as it exists today.

It is not a future roadmap document. It captures current scope, current behavior, current technical assumptions, and current limitations.

## 2. Product Summary

Benefits Digger is a rules-based U.S. government benefits screening web app.

It helps a user:

- choose federal, state, or both
- answer adaptive questions
- review likely or possible benefit matches
- understand why a match happened
- see official government sources only
- compare scenarios
- explore the program catalog
- move from discovery toward application readiness

The current product is a browser app served by a FastAPI backend with SQLite persistence and optional Gemini-assisted state enrichment.

## 3. Problem Statement

People who may qualify for public benefits often face three problems:

1. They do not know which programs exist
2. They do not know which rules matter to them
3. They do not know which source to trust or where to apply

The current product aims to reduce those three problems by combining:

- adaptive screening
- official-source-only evidence
- explainable confidence
- structured next steps

## 4. Target Users

### Primary Users

- Individuals trying to find benefits for themselves
- Family members helping another person navigate benefits
- People who know their life situation but not program names

### Secondary Users

- Caseworker-like helpers or advocates using the tool informally
- Operators maintaining source freshness and review tasks

## 5. Core User Jobs

The current product is designed to help users:

- discover benefits they may qualify for
- separate federal and state opportunities
- understand why a program was matched
- identify what information is still missing
- see official government sources behind a result
- get pointed to the official next step for pursuing a benefit
- test life-change scenarios without losing the base session

## 6. Product Goals

The current product goals are:

- Provide a trustworthy first-pass benefits screener
- Keep federal and state paths clearly separated
- Use official government sources only for displayed evidence and application paths
- Make result quality explainable instead of black-box
- Turn matches into an action-oriented planning experience
- Maintain traceability when upstream source content changes

## 7. Non-Goals

The current product does not aim to:

- guarantee program approval
- submit applications into government systems
- replace legal or caseworker judgment
- provide exhaustive 50-state deterministic rule coverage
- maintain user accounts or cross-device saved histories
- provide a fully bilingual backend data model

## 8. Current Experience

### 8.1 Home and Session Creation

The user starts on the Home page and selects:

- scope: `Federal`, `State`, or `Federal and state`
- state, when needed
- depth
- one or more categories

The system then creates an anonymous screening session and starts an adaptive question flow.

### 8.2 Adaptive Screening

The screener selects questions from the local catalog and asks them based on expected usefulness for narrowing possible programs.

Depth affects:

- how many questions are asked
- how aggressively deeper follow-up questions are introduced
- which question variant is shown

### 8.3 Results

Results are split into federal and state sections.

Each result can include:

- program name
- summary
- eligibility status
- confidence score
- certainty breakdown
- matched reasons
- missing facts
- official sources
- how-to-get links
- documents

### 8.4 Planning Dashboard

The dashboard converts the current result set into:

- overview metrics
- benefit stack
- missing-fact priorities
- recommended next actions
- official source hub
- document checklist
- planning notes

### 8.5 What-If Lab

The What-If Lab lets a user compare predefined scenario changes against the current session without overwriting the base answers.

### 8.6 Program Explorer

The Explorer supports:

- keyword search
- plain-English need descriptions
- federal/state filtering
- state filtering

It is grounded in the stored local catalog rather than live web search.

### 8.7 Source Refresh and Review Queue

Admin-style tools let an operator:

- manually refresh official source data
- review detected source changes

This supports source freshness and traceability.

### 8.8 Spanish Support

The product currently includes a client-side English and Spanish interface toggle.

Coverage is broad across page UI and many dynamic strings, but not every possible backend-generated string is guaranteed to be localized.

### 8.9 Export

The current product supports:

- print from the Results page
- PDF export from Results and Dashboard

## 9. Current Functional Requirements

### 9.1 Session and Screening

The system must:

- create an anonymous screening session from selected scope, state, categories, and depth
- return the next best question after each answer
- stop asking questions when the session reaches its stopping condition
- preserve answered questions within the session

### 9.2 Federal and State Separation

The system must:

- allow federal-only, state-only, and combined sessions
- require a state when the session includes state screening
- show federal and state results separately

### 9.3 Result Explainability

The system must:

- compute a status per program
- attach matched reasons and missing facts
- attach official government source links
- attach an official application path when available
- expose confidence as a multi-factor breakdown

### 9.4 Planning

The system must:

- summarize the current session into a planning dashboard
- show grouped benefit stack information
- highlight top missing facts
- provide next-step links and a source hub
- show document checklist data when available

### 9.5 Scenario Comparison

The system must:

- accept scenario answer overrides
- compare them to the current baseline session
- show new or improved opportunities without mutating the base session

### 9.6 Explorer

The system must:

- search the stored catalog
- support plain-English discovery input
- optionally use Gemini to interpret that discovery input
- keep final results grounded in stored programs and official sources

### 9.7 Source Maintenance

The system must:

- sync official seed data
- snapshot source content
- detect source changes
- create review tasks for changed sources

### 9.8 Localization

The system must:

- support English and Spanish UI switching at runtime
- rerender static page labels and major dynamic UI strings when the locale changes

## 10. Current Data and Trust Model

### 10.1 Official Source Policy

Displayed evidence and application paths are intended to come only from official government domains.

This is a core credibility rule for the product.

### 10.2 Federal Ingestion

Federal benefits currently start from the official USA.gov benefits feed and are normalized into the local catalog.

This is the most deterministic data path in the system today.

### 10.3 State Ingestion

State discovery currently starts from the official USA.gov state social-services directory.

The system then:

- crawls bounded official state pages
- optionally uses Gemini to filter for relevant pages
- optionally uses Gemini to extract state program structure

This path is grounded, but less deterministic than the federal path.

### 10.4 Runtime Screening

The app does not live-crawl the web during a user's screening session.

Runtime eligibility evaluation is based on stored local programs, questions, and rules.

## 11. AI Requirements and Boundaries

The current product uses Gemini in bounded, optional ways:

- for state program generation
- for relevance filtering over crawled official pages
- for hybrid Explorer query interpretation

The current product does not rely on Gemini as the final source of truth for runtime eligibility results.

Eligibility screening is still computed against stored rules in the local database.

If Gemini is unavailable, the product can still run with a seeded local catalog and fallback behavior, but state enrichment and some hybrid interpretation will be reduced.

## 12. Current Technical Shape

### Backend

- FastAPI
- SQLAlchemy
- SQLite

### Frontend

- Vanilla HTML
- Vanilla CSS
- Vanilla JavaScript

### Key Pages

- `/`
- `/results`
- `/dashboard`
- `/whatif`
- `/explorer`

### Key APIs

- `POST /api/v1/sessions`
- `POST /api/v1/sessions/{id}/answers`
- `GET /api/v1/sessions/{id}/results`
- `GET /api/v1/sessions/{id}/plan`
- `POST /api/v1/sessions/{id}/compare`
- `POST /api/v1/explorer/search`
- `GET /api/v1/admin/review-tasks`
- `POST /api/v1/admin/sync`

## 13. Current Constraints and Limitations

The most important current limitations are:

- state coverage is not exhaustive across all programs and all states
- state extraction is less deterministic than the federal feed path
- there are no user accounts or durable user profiles
- document checklist completion is client-side only
- some dynamically generated content may still appear in English even when Spanish is selected
- current persistence and migration strategy are still lightweight for a multi-user production deployment

## 14. Current Success Definition

At the current stage, the product is successful if it helps a user:

- start from a life situation rather than a program name
- get to a credible shortlist of programs
- understand why those programs matched
- identify what to do next on official government sites

Operationally, the current product is also successful if:

- source refresh works reliably
- review tasks appear when upstream sources change
- core API endpoints stay functional
- the app remains useful without requiring a full live web search during user sessions

## 15. Immediate Next-Level Opportunities

These are not required to describe the current product, but they are the most obvious next extensions from today's baseline:

- more deterministic state connectors
- richer amount formulas
- fuller multilingual coverage
- user accounts and saved histories
- reviewer editing tools
- stronger production deployment and migration tooling
