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
- create a review task when the upstream snapshot changes

State:

- pull the official USA.gov state social-service directory
- create one official state entry-point record per state
- version those records and track source changes

## Confidence Model

Each result combines:

- rule coverage
- source authority
- source freshness
- program determinism
- amount determinism

This keeps the output explainable instead of relying on a single arbitrary score.

## Known Limitation

The federal side uses live official benefit feed data.
The state side is fully wired as a source/update pipeline, but it currently surfaces official state entry points rather than exhaustive state-by-state program rules.

## Next Expansion

- add per-state program connectors
- store richer amount formulas
- expand question coverage
- add reviewer editing tools for extracted rules
- move from SQLite to Postgres for multi-user deployment
