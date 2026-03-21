# Benefits Digger — Code Audit & Enhancement Changelog

## Phase 1: Critical Bug Fixes (Correctness & Security)

| # | Fix | File | What Changed |
|---|-----|------|--------------|
| 1.1 | Eligibility scoring logic | `app/rules.py` | Mixed pass+fail now returns `"possibly_eligible"` instead of `"likely_ineligible"`. Only all-fail returns ineligible. |
| 1.2 | State referral status | `app/services.py` | State referrals matching user's state now show `"likely_eligible"` instead of `"possibly_eligible"`. |
| 1.3 | CORS vulnerability | `app/main.py` | Set `allow_credentials=False` to fix wildcard origin + credentials security issue. |
| 1.4 | Admin endpoint auth | `app/main.py`, `app/config.py` | Added `require_admin_key` dependency checking `X-Admin-Key` header against `BENEFITS_DIGGER_ADMIN_KEY` env var. |
| 1.5 | Slug collision | `app/catalog.py` | Empty/special-char slugs now get MD5 hash suffix instead of all resolving to `"item"`. |
| 1.6 | Float comparison | `app/rules.py` | Uses `math.isclose()` instead of `==` for numeric eligibility checks. |
| 1.7 | SQLite foreign keys | `app/db.py` | Added `PRAGMA foreign_keys=ON` via SQLAlchemy event listener. |
| 1.8 | N+1 queries | `app/services.py` | Batched snapshot lookups in `compute_source_freshness_score()` and `get_program_sources()` via subqueries. |
| 1.9 | XSS prevention | `app/static/app.js` | Added `escapeHtml()` helper applied to all dynamic text in `innerHTML` across all render functions. |
| 1.10 | Sync atomicity | `app/services.py` | Wrapped federal + state sync in single transaction with rollback on failure. |

## Phase 2: UX, Edge Cases & Polish

| # | Fix | File | What Changed |
|---|-----|------|--------------|
| 2.1 | Loading indicators | `app/static/app.js`, `app/static/styles.css` | `setLoading()` helper + `.loading` CSS class with opacity and disabled state. |
| 2.2 | Form debouncing | `app/static/app.js` | Submit buttons disabled during async operations to prevent duplicate requests. |
| 2.3 | State validation | `app/static/app.js`, `app/schemas.py` | Client-side and server-side validation requiring state when scope is `"state"` or `"both"`. |
| 2.4 | Null/undefined guards | `app/static/app.js` | `decision_certainty ?? 0` and `estimated_amount?.display ?? "Not available"` prevent broken rendering. |
| 2.5 | Better empty states | `app/static/app.js` | Unified, helpful empty state messages with suggested actions. |
| 2.6 | Explorer debounce | `app/static/app.js` | Minimum 2-character query length enforced before searching. |
| 2.7 | Real health check | `app/main.py` | `/health` now queries DB with `SELECT 1`, returns 503 if database is unavailable. |
| 2.8 | Cascade deletes | `app/models.py` | Added `cascade="all, delete-orphan"` on Program→Versions, Program→Sources, Source→Snapshots, Session→Answers. |
| 2.9 | Rule data validation | `app/services.py` | Skips rules with non-list `expected_values_json` instead of crashing. |
| 2.10 | Empty answers handling | `app/rules.py` | All-unknown outcomes now return `"unclear"` via improved scoring logic. |

## Phase 3: New Features (Hackathon Differentiation)

### 3.1 Life Event Wizard
**Files:** `app/static/index.html`, `app/static/app.js`, `app/static/styles.css`

Six clickable life event cards that replace the manual category/scope setup:
- "I just lost my job" → unemployment, food, cash assistance, housing
- "A family member passed away" → survivor benefits, funeral assistance
- "I'm turning 65" → retirement, Medicare, Social Security
- "I had a baby" → family benefits, WIC, health coverage
- "I became disabled" → disability, SSI, SSDI, medical assistance
- "I served in the military" → veterans benefits, VA health care

Each card auto-selects categories, sets depth mode, and pre-fills relevant answers before starting the adaptive question flow.

### 3.2 Confidence Explainer
**Files:** `app/static/app.js`, `app/static/styles.css`

The confidence meter bar on each result card is now clickable and expands to show an interactive breakdown of all 5 certainty components:
- Rule coverage
- Source authority
- Source freshness
- Program determinism
- Amount determinism

Each component displays as a labeled mini progress bar with its score.

### 3.3 Shareable Summary Card (Print Export)
**Files:** `app/static/index.html`, `app/static/app.js`, `app/static/styles.css`

- "Export Results" button in the Results section header
- Triggers `window.print()` with `@media print` styles that hide forms, buttons, and navigation
- Produces a clean, readable printout of benefit matches, confidence levels, and next steps
