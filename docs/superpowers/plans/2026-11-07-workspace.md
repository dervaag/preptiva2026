# Dashboard and history implementation plan

**Goal:** Make training progress and previous sessions immediately useful, using the user's dashboard reference and the approved Preptiva visual direction.

**Architecture:** Keep the current FastAPI endpoints. Render Jinja page partials inside the setup page's horizontal navigation shell. A page-scoped stylesheet and controller handle dashboard statistics, chart, session rows, history search, filters, and pagination.

**Tech stack:** Jinja, CSS, vanilla JavaScript, SVG, existing custom select component, Playwright.

## Design direction

Reading this as a practice workspace for interview candidates, in Preptiva's understated neutral-and-orange visual language. ENERGY 2 / RHYTHM 2 / MOTION 1. DM Sans ties the typography to the approved wordmark. The main action is starting another simulation; the large score values and score trend make actual progress the content focal point.

- Use a horizontal header shared with simulation setup; existing navigation destinations stay the same.
- Use a single grouped statistics surface for comparison, followed by a wider trend panel and a narrower practice-focus panel. No marketing hero or decorative badges.
- Show real completed-session counts, average/best scores, and an explicitly labelled latest-versus-first change. Convert stored 0–5 scores to 0–100 only for display. Missing measurements remain empty, never zero.
- The chart answers how scores changed across the latest eight completed, scored sessions. Straight segments preserve actual observations; each point links to its result.
- Practice focus comes from the latest scored session's measured competencies, without mixing older sessions or claiming missing STAR percentages.
- History prioritizes role/company, interviewer, date, status, and score. Search, status filters, interviewer filtering, sorting, and pagination operate on existing session data.
- Orange identifies primary actions and the score series. Neutral surfaces and thin separators organize content. Semantic status colors always include text. Small radii distinguish controls from larger content panels; no floating-card shadows.
- Reuse the existing custom dropdown with keyboard behavior. Responsive rows become readable stacked entries instead of shrinking a desktop table.

## Tasks

- [x] Add dashboard/history partials, shared header integration, and workspace CSS; leave room, setup, authentication, and result behavior intact.
- [x] Add workspace controller, replacing the legacy dashboard/history handlers. Include loading, empty, filtered-empty, error, and retry states.
- [x] Verify with isolated fixture data, search/filter/sort/pagination, score semantics, keyboard dropdowns, mobile layout, and screenshots. Review current live pages through read-only access only.
- [x] Record verification evidence and screenshots. No production API writes, provider calls, server restart, commit, or push is required.
