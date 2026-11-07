# Simulation Setup Redesign Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement these tasks in the active Preptiva checkout.

**Goal:** Redesign the new-simulation form from the user's approved reference while preserving session creation.
**Architecture:** A page-specific Jinja partial, scoped stylesheet, and local device-preview controller. Existing API field names and interview-room checks remain intact.
**Tech Stack:** FastAPI/Jinja2, vanilla JavaScript/CSS, MediaStream, Playwright.
**Spec:** User reference image and request dated 2026-11-07: horizontal top bar, camera preview on the left, interviewer controls on the right, typography matching the current logo, orange brand accents.

## Global Constraints

- Continue the user's running checkout and preserve existing logo changes and local configuration.
- DM Sans, white surfaces, quiet gray background, charcoal type, orange primary action. ENERGY 1 / RHYTHM 1 / MOTION 1.
- Keep all required CV/JD, candidate, role, language, question-count and consent fields.
- Preview stays local, is never recorded/uploaded, and releases devices on navigation.
- No paid provider calls during verification.

## Review Focus

- Required inputs inside collapsed details must open before validation focuses them.
- Camera and microphone permission denial must be recoverable and must not block form entry.
- Camera/mic must toggle independently and stop on navigation, including pending requests.
- 320px layouts and keyboard operation must retain all controls.
- Session POST payload and error recovery must stay compatible with the existing API.

## Tasks

- [x] Add and run a browser check for reference layout, device lifecycle, validation and intercepted POST error recovery; confirm it fails before implementation.
- [x] Add `app/templates/partials/session-setup.html`, `app/static/css/session-setup.css`, and `app/static/js/session-setup.js`; connect them only to the form page through `app/templates/app.html`.
- [x] Preserve the submit button's markup while pending/failing in `app/static/js/app.js`.
- [x] Run browser checks with synthetic camera/mic, regression tests, syntax and diff checks. Inspect desktop/mobile screenshots, record the implemented behavior in docs.

## Execution record

- Baseline and integrated backend suite: 21/21 passed. Initial new-page test failed because the requested layout was absent; full setup smoke now passes.
- Lifecycle regression: a delayed permission response after pagehide/pageshow initially left the camera live. Generation invalidation fixed it; the regression now verifies ended tracks.
- Independent review found short-desktop clipping after permission denial. The reproducer measured privacy bottom 803.94 and actions bottom 835.94 beyond shell bottom 738. Preview scroll/min-height correction makes the same browser check pass.
- Mobile actions follow content rather than floating over persona cards, verified by a bounds assertion and screenshot inspection.
- Full interview Chrome smoke passed with fake providers in a scratch copy so original data/artifacts were preserved. Native keyboard, payload/error recovery, expanded mobile form and permission denial checks passed.
- Review boundaries: physical hardware and non-Chromium browsers were not exercised. No deferred code findings remain.

## Follow-up: custom dropdowns

- [x] Replace the three native selects with reusable macro/CSS/controller and API-compatible hidden inputs.
- [x] Unify down-chevron geometry, sizes and expanded rotations with the accordion controls.
- [x] Verify pointer/touch, keyboard/typeahead, cancel/Tab, single popup, portal bounds, FormData and reset; the initial test failed on three native selects and now passes.
- [x] Verify setup device/form regression and the complete mocked interview flow. Independent review found no actionable bugs; screen-reader announcements and non-Chromium browsers remain untested.
