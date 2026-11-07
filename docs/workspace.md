# Dashboard and history

The dashboard and history pages share the horizontal navigation, DM Sans typography, neutral background, and orange primary action used by simulation setup. Their partials live in `app/templates/partials/dashboard.html` and `history.html`; `workspace.css` and `workspace.js` load only on these two pages.

## Data and interaction

- `GET /api/sessions` is the shared data snapshot. History filters and pagination run locally without further requests.
- Completed sessions include every `done` session. Average, best, change, and chart points include only completed sessions with finite numeric scores.
- Scores are stored on a 0–5 scale and displayed on a 0–100 scale. Missing scores are shown as `-`, not zero.
- The change compares the latest and earliest measured sessions. The chart shows up to eight measured sessions ordered by completion time, falling back to creation time. Chart points open their result pages and support keyboard focus.
- Practice focus reads the latest measured session's result and shows up to three lowest measured competencies with positive assessment weight. A focus failure can be retried without hiding the other dashboard information.
- History searches role, company, and interviewer; filters all/completed/active/closed and interviewer; sorts newest/oldest/highest score; and paginates eight entries. Active includes preparing, ready, running, scoring, and deferred evaluation. Panel rows display their members, and interviewer filters match any panel member. Filters reset pagination; unmeasured scores sort after measured scores.
- Done, scoring, and `evaluation_failed` sessions link to results, where deferred evaluation can be retried. Other statuses link to their room. Listing data never starts or closes a session.
- Dropdowns reuse the simulation setup custom-select component. Empty, loading, error/retry, sparse-score, and filtered-empty states are explicit.

## Verification

Run `.venv/bin/python tests/workspace_smoke.py` for isolated Chrome checks. The test creates a temporary database and fixture assessments, checks score/ordering semantics, filters, sorting, pagination, keyboard dropdowns, retry behavior, and layouts from 320 to 1440 px. Pass `--screenshots-dir <directory>` to save stress screenshots. It does not call interview or provider APIs.

The existing Python test suite can be run with `.venv/bin/python -m unittest discover -s tests -q`.
