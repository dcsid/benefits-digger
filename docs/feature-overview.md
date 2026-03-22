# Benefits Digger Feature Overview

This document explains the current product from two angles:

- A user view: what each feature does and why someone would use it
- A developer view: how the feature works at a mid-level without diving into every implementation detail

This is intended to describe the app as it exists today, not the long-term ideal.

## 1. Start Screening

### User View

The Home page is where a user starts a benefits screening session.

The user chooses:

- whether they want `Federal`, `State`, or `Federal and state`
- a state, if state benefits are included
- a screening depth
- one or more benefit categories

Once they click `Apply selections`, the app creates a screening session and begins asking questions that are meant to narrow down likely programs.

### Developer View

This feature is served from the `/` route and rendered by the Home page files.

- Frontend page: `app/static/index.html`
- Frontend logic: `app/static/home.js`
- Session state and shared utilities: `app/static/shared.js`
- Backend endpoint: `POST /api/v1/sessions`

The session payload includes:

- `scope`
- `state_code`
- `categories`
- `depth_value`

The backend stores the session in `screening_sessions`, then selects the first question based on the current catalog, rules, and unanswered facts.

## 2. Adaptive Question Flow and Depth

### User View

The question flow is adaptive, which means the app does not ask every user the same sequence.

It tries to ask questions that are most useful for narrowing down possible programs. The depth slider changes how far the screening goes:

- `Quick` asks fewer questions and stops earlier
- `Standard` gives a balanced screen
- `Deep` goes further and unlocks more detailed follow-ups

This lets a user choose between speed and completeness.

### Developer View

Questions are not pulled live from the web at runtime. They come from the local catalog database.

At a mid-level, the flow works like this:

1. The app loads stored `questions` and `eligibility_rules`
2. It looks at the current session answers
3. It scores which unanswered question would best distinguish among remaining programs
4. It returns that question to the frontend

Depth affects:

- how many questions can be asked before stopping
- which `question_variants` are used
- how quickly more sensitive or detailed prompts appear

Key backend logic lives in:

- `app/services.py`
- `app/rules.py`
- `app/seed_data.py`

## 3. Federal and State Coverage

### User View

The app separates federal and state benefits on purpose.

Users can screen only federal programs, only state programs, or both. When both are selected, the results are shown in separate sections so it is clear which matches come from nationwide programs and which come from state-administered or state-specific programs.

### Developer View

Federal and state coverage use different source paths.

Federal:

- starts from the official USA.gov benefits feed
- is normalized into programs, questions, rules, amounts, and sources

State:

- starts from the official USA.gov state social-services directory
- uses official state pages as crawl seeds
- may use Gemini to extract state program structure from official pages

At runtime, both federal and state programs are screened through the same local rule engine, but the ingestion path is more deterministic for federal than for state.

Key modules:

- `app/catalog.py`
- `app/gov_crawl.py`
- `app/gemini.py`
- `app/services.py`

## 4. Results Page

### User View

The Results page shows the programs the user may qualify for after answering questions.

Each result card is designed to answer practical questions:

- What is this program?
- How likely is the match?
- Why did it match?
- What information is still missing?
- Where did the data come from?
- How do I actually pursue it?

Results are split into `Federal Results` and `State Results`.

### Developer View

The Results page is rendered from:

- `app/static/results.html`
- `app/static/results-page.js`

The data comes from:

- `GET /api/v1/sessions/{id}/results`

The backend computes results by:

1. loading the session answers
2. filtering the catalog by scope, state, and category
3. evaluating each program's rules against the current answers
4. computing eligibility status and certainty data
5. attaching official source links, application links, and document data

The frontend uses shared card rendering logic from `app/static/shared.js`.

## 5. Confidence Scoring

### User View

Instead of showing a black-box yes or no, the app gives each match a confidence score with a visible breakdown.

This helps the user understand whether a result is strong because the rules are clearly satisfied, or weak because some important information is still missing.

### Developer View

Confidence is computed on the backend as a composite score. It is meant to be explainable rather than magical.

The breakdown currently includes factors such as:

- rule coverage
- source authority
- source freshness
- program determinism
- amount determinism

The frontend shows the overall score and expandable mini-meters for the individual factors.

The certainty computation and result assembly live primarily in `app/services.py`.

## 6. Data Gathered From Official Government Websites

### User View

Each result shows where the information came from and links the user back to official government pages. This is a trust feature.

The goal is that a user can see the official basis for a match and go directly to the source that supports it.

### Developer View

This feature is backed by stored `sources` attached to programs.

The ingestion pipeline:

- imports official seed sources
- crawls bounded official government pages
- snapshots source content
- associates source records with programs

At result time, the app returns only official government links for source evidence and application guidance.

The logic is mainly in:

- `app/catalog.py`
- `app/gov_crawl.py`
- `app/services.py`

## 7. How To Get This Benefit

### User View

The app does not stop at "you may qualify." It also tries to show what to do next.

Each result includes a `How to get this benefit` section with official next-step links, such as an application page or official program page.

### Developer View

This is built from the official source set attached to a program.

At a mid-level:

- if the program has an official `apply_url`, that is used
- otherwise the app falls back to official source pages that can act as the next best application path
- result cards render these links as structured action items

This logic lives in `app/services.py`, with the final presentation in `app/static/shared.js`.

## 8. Planning Dashboard

### User View

The Planning Dashboard turns a set of matches into a more actionable overview.

It helps answer:

- How many likely and possible programs do I have?
- Which benefit areas look strongest?
- What facts are still blocking confidence?
- What should I do next?
- Which official pages should I keep open?
- What documents might I need?

### Developer View

The Dashboard is a separate page:

- `app/static/dashboard.html`
- `app/static/dashboard.js`
- `GET /api/v1/sessions/{id}/plan`

The backend compiles a planning view from the current results into:

- overview metrics
- benefit stack
- top missing facts
- action plan
- official source hub
- document checklist
- planning notes

This is not a second eligibility engine. It is a structured summarization layer built on top of the same session and result data.

## 9. Benefit Stack

### User View

The benefit stack groups the user's strongest opportunities by category so the result set feels less like a long list and more like a plan.

It helps a user see where the most value or momentum may be.

### Developer View

The benefit stack is part of the planning payload. It aggregates result rows into grouped category summaries with counts and representative programs.

It is assembled on the backend in `app/services.py` and rendered on the dashboard.

## 10. Document Checklist

### User View

The document checklist helps a user prepare before applying. It shows common documents associated with matched programs and lets the user mark items as completed in the browser.

### Developer View

Programs can store `documents_json`, which is surfaced in both the Results view and the Dashboard.

The checkbox state is currently persisted client-side in browser storage, not in a user account.

Relevant pieces:

- stored document metadata in the `programs` table
- rendering in `app/static/shared.js` and `app/static/dashboard.js`
- local persistence in `app/static/results-page.js`

## 11. What-If Lab

### User View

The What-If Lab lets the user compare scenarios without overwriting their actual saved answers.

This is useful for questions like:

- What changes if I have limited income?
- What changes if I have a disability?
- What changes if military service applies?

It is a planning tool, not a permanent edit to the main session.

### Developer View

The What-If Lab is served from:

- `app/static/whatif.html`
- `app/static/whatif-page.js`
- `POST /api/v1/sessions/{id}/compare`

The backend takes a list of scenario answer overrides, evaluates them against the same base session, and returns comparison payloads showing:

- gained programs
- improved programs
- federal delta
- state delta
- likely and possible deltas

The base session is preserved.

## 12. Program Explorer

### User View

The Program Explorer is for discovery before or outside a screening session.

Users can:

- browse the catalog
- search by keywords
- describe their need in plain English
- filter by federal or state scope
- narrow to a state

It is helpful for users who do not know program names but do know their situation.

### Developer View

The Explorer is a hybrid search interface:

- page: `app/static/explorer.html`
- script: `app/static/explorer-page.js`
- endpoint: `POST /api/v1/explorer/search`

The search path is:

1. optionally interpret the user's description with Gemini if configured
2. convert that into structured search hints
3. search the local grounded catalog
4. return ranked programs with match reasons and official sources

This means the app does not live-crawl the web during Explorer use.

The main search logic lives in `app/hybrid_explorer.py`.

## 13. Refresh Official Sources

### User View

`Refresh Official Sources` is an admin-style action that updates the app's official source data.

It is useful when someone wants to pull the latest federal feed, refresh state directory content, and update crawl-backed source data.

### Developer View

This button calls:

- `POST /api/v1/admin/sync`

The sync pipeline:

1. refreshes official seed sources
2. updates normalized local catalog records
3. crawls bounded official government pages
4. snapshots the fetched content
5. creates review tasks if source content changed

If an admin key is configured, the request must include `X-Admin-Key`.

## 14. Review Queue

### User View

The Review Queue is a transparency and maintenance feature. It shows when official source content has changed and needs review.

This helps maintain trust by avoiding silent changes to eligibility logic.

### Developer View

The review queue is backed by:

- `source_snapshots`
- `change_events`
- `review_tasks`

The UI on the Home page reads:

- `GET /api/v1/admin/review-tasks`

When a source hash changes during sync, the app records a change event and opens a review task. This is part of the traceability model for source changes.

## 15. Language Toggle and Spanish Support

### User View

The language toggle lets the user switch the interface into Spanish.

The current implementation covers the page shell and a large portion of dynamic UI, including:

- navigation
- page titles
- question flow labels
- many screener prompts and hints
- result-card support text
- scenario labels
- dashboard labels
- explorer explanations

### Developer View

The app uses a client-side locale system:

- shared translation loader: `app/static/shared.js`
- locale dictionaries: `app/static/locales/en.json` and `app/static/locales/es.json`

The page templates use `data-i18n` for static strings, while shared JS also translates many dynamic strings and known backend-generated phrases on rerender.

This is a practical i18n layer, but not a fully locale-native backend. Newly generated text that does not match the known translation keys may still appear in English.

## 16. PDF and Print Export

### User View

Users can print results and download PDFs from the Results and Dashboard pages. This is useful for saving a plan, sharing it, or bringing it to an appointment.

### Developer View

The current export flow is browser-side:

- Results page uses `window.print()` and `html2pdf`
- Dashboard uses `html2pdf`

This is a frontend export feature, not a server-side report generation pipeline.

## 17. Admin Key Protection

### User View

Most users do not need this. It exists to protect maintenance actions like refresh and review access.

If enabled, the app lets an operator enter an admin key in the browser before using those admin functions.

### Developer View

If `BENEFITS_DIGGER_ADMIN_KEY` is set, the backend protects admin routes and expects `X-Admin-Key`.

The frontend stores the key in session storage and attaches it to admin requests from shared request helpers.

Relevant files:

- `app/main.py`
- `app/static/shared.js`
- `app/static/home.js`

## 18. Key Product Boundaries

### User View

The app is meant to help users discover and understand benefits, not to promise approval.

It is strongest when:

- the user wants a trusted starting point
- the user wants official links
- the user wants a structured plan

### Developer View

The major current boundaries are:

- no user accounts
- no server-side saved profiles beyond anonymous sessions
- no direct submission into government systems
- no full exhaustive state coverage
- no fully localized backend-generated content

Those boundaries are important to keep in mind when describing current scope.
