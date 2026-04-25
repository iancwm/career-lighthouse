# Student Page Shell Cleanup Spec

**Status:** done (2026-04-24)

## Problem

[`web/app/student/page.tsx`](../../web/app/student/page.tsx) currently combines storage hydration, guided entry, intake flow control, chat transition logic, and page composition in one client component.

The page is still small, but the state machine already has multiple modes. That makes future student-flow changes harder to reason about than they need to be.

## Goal

Keep the page component thin by moving persistence and flow transitions into reusable hooks or helpers.

## In Scope

- Extract `sessionStorage` hydration and persistence into a dedicated hook.
- Extract guided entry and flow transition logic into a separate controller.
- Keep the page component focused on composition and presentation.

## Not In Scope

- Redesigning the student experience.
- Changing the storage key format unless a bug forces it.
- Reworking the chat or intake API contracts.

## Existing Building Blocks

- `web/app/student/page.test.tsx` already covers resume restore behavior.
- `web/app/student/__tests__/StudentPage.test.tsx` already covers the guided entry, reset, and restart flows.

## Proposed Shape

- `useStudentSessionStorage()` owns persistence and hydration.
- `useStudentFlow()` owns the mode transitions.
- `StudentPage` renders the current mode and passes callbacks through.

That keeps the page as a composition layer and avoids a growing pile of local state.

## Acceptance Criteria

- The student flow behaves exactly the same for users.
- Session restore, reset, and restart still work.
- The page component has fewer responsibilities and fewer side effects.

## Test Plan

- Keep the existing page tests passing.
- Add coverage for the extracted hook if needed.
- Verify the reset and restore path still works after reload.

## Risks

- If the hooks are over-split, the page may become harder to follow instead of easier.
- Persistence changes must not break existing `sessionStorage` restores.
