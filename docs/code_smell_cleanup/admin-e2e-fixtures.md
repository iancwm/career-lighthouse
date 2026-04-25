# Admin E2E Fixtures Cleanup Spec

**Status:** done (2026-04-24)

## Problem

[`web/e2e/admin-workspace.e2e.ts`](../../web/e2e/admin-workspace.e2e.ts) hardcodes large alumni, employer, and preview payloads inline. That creates a second source of truth for schemas that already exist elsewhere in the app.

The result is a test file that is harder to read, harder to update, and more brittle when the app schema evolves.

## Goal

Move repeated fixture payloads into shared builders so the Playwright spec only describes behavior.

## In Scope

- Extract alumni fixture data into a reusable test-data helper.
- Extract employer and preview payload builders into the same shared area.
- Keep the behavior assertions in the E2E file focused on the user journey.

## Not In Scope

- Changing the test flow itself.
- Changing the admin workspace UI to fit the tests.
- Adding a new fixture library if a lightweight local helper is enough.

## Existing Building Blocks

- The admin workspace unit tests already cover the major route transitions.
- The app already has domain models and structured payloads for these surfaces.

## Proposed Shape

- Add a small `web/e2e/fixtures/` or `web/test-data/` helper module.
- Export builders like `makeAlumniRecord()`, `makeEmployerRecord()`, and `makePreviewCard()`.
- Keep the Playwright spec focused on the workspace behavior and smoke assertions.

## Acceptance Criteria

- The E2E file is shorter and easier to scan.
- Fixture shape changes happen in one place.
- The test still covers the same admin workspace flows.

## Test Plan

- Run the Playwright admin workspace spec after the fixture move.
- Keep the current smoke path and route assertions intact.
- Verify the test data builders produce the same payloads the app expects.

## Risks

- Shared test builders can become their own junk drawer if they are not kept tight.
- A fixture refactor can hide real behavior differences if the builders become too magical.
