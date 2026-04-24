# Cleanup Sprint Implementation Plan

**Status:** proposed

## Sprint Focus

This sprint covers the highest-value, lowest-coupling cleanup lane first:

1. `admin-workspace-shell.md`
2. `student-page-shell.md`
3. `admin-e2e-fixtures.md`

The remaining docs in this folder are real work, but they are better treated as separate follow-up PRs because they cross deeper backend or infra boundaries.

## Why This Order

### 1. Admin workspace shell first

[`web/components/admin/AdminWorkspace.tsx`](../../web/components/admin/AdminWorkspace.tsx) is the largest and riskiest frontend shell. Cleaning it first gives the biggest maintainability win and creates a better boundary for the rest of the admin UI.

### 2. Student page shell second

[`web/app/student/page.tsx`](../../web/app/student/page.tsx) is smaller, but it already has a state machine. Extracting the page logic after the admin shell keeps the frontend cleanup focused while the team is already thinking about shell/state boundaries.

### 3. Admin E2E fixtures third

[`web/e2e/admin-workspace.e2e.ts`](../../web/e2e/admin-workspace.e2e.ts) should be cleaned once the shell boundaries are stable. That makes it easier to align the test fixtures with the new component structure instead of refactoring them against a moving target.

## What Not To Do In This Sprint

- Do not split `api/models.py` yet.
- Do not module-split `terraform/main.tf` yet.
- Do not refactor `scripts/validate_profiles.py` unless a change in the frontend work makes it obviously necessary.
- Do not redesign any user-facing workflows while extracting the shell and state logic.

## Suggested Work Phases

### Phase 1: Admin workspace extraction

- Extract URL and routing state into a hook or controller.
- Keep the current URL behavior unchanged.
- Preserve existing unit test coverage and add tests for the extracted logic if needed.

### Phase 2: Student page extraction

- Move session storage hydration and the flow state machine into hooks.
- Keep the page as a thin composition component.
- Verify the resume restore and reset paths still pass.

### Phase 3: E2E fixture cleanup

- Move repeated payloads into shared test-data builders.
- Keep the Playwright spec focused on behavior.
- Make sure the builders match the current app schemas.

## Definition Of Done

- Each of the first three lane docs is reflected in code or test structure.
- The admin shell is smaller and easier to extend.
- The student page is thinner and easier to reason about.
- The admin E2E file no longer owns fixture payloads as inline source-of-truth data.
- Existing tests still pass, and no user-visible behavior changes were introduced.

## Test Gates

- `web/components/admin/__tests__/AdminWorkspace.test.tsx`
- `web/app/student/page.test.tsx`
- `web/app/student/__tests__/StudentPage.test.tsx`
- `web/e2e/admin-workspace.e2e.ts`

## Follow-Up Queue

After this sprint, the next likely refactors are:

1. `validate-profiles-cli.md`
2. `api-models-split.md`
3. `terraform-module-split.md`

Those should each be handled as separate tasks so the review surface stays manageable.
