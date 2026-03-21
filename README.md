# Benefits Digger

Benefits Digger is a working MVP for a government-benefits screening product.
It includes:

- a FastAPI backend
- SQLite persistence with source snapshots and review tasks
- a rule-based federal screener
- state social-service directory ingestion for state entry points
- a browser UI for session creation, adaptive questions, and result review
- a remote sync endpoint that pulls the official USA.gov benefit feed and state directory

## What It Does Today

- Seeds a local starter catalog so the app boots even without network access.
- Tries to upgrade itself from official USA.gov sources on startup when network access is available.
- Separates federal results from state results.
- Uses explainable confidence factors instead of a single arbitrary confidence guess.
- Creates review tasks when the official source snapshots change.

## Current Scope

The federal layer can ingest the official USA.gov benefit-finder feed.
The state layer currently ingests the official USA.gov state social-services directory and turns each state entry into an official referral result.
That means the state architecture is fully wired, but the per-state program catalog is still connector-ready rather than exhaustive.

## Run It

```bash
cd [redacted-path] project/benefits-digger
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## API Endpoints

- `GET /health`
- `GET /api/v1/jurisdictions/states`
- `POST /api/v1/sessions`
- `POST /api/v1/sessions/{session_id}/answers`
- `GET /api/v1/sessions/{session_id}/results`
- `GET /api/v1/programs/{slug}`
- `GET /api/v1/admin/review-tasks`
- `POST /api/v1/admin/sync`

## Tests

```bash
cd [redacted-path] project/benefits-digger
pytest
```
