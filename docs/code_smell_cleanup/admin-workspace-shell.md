# Admin Workspace Shell Cleanup Spec

**Status:** done (2026-04-24)

## Problem

[`web/components/admin/AdminWorkspace.tsx`](../../web/components/admin/AdminWorkspace.tsx) has become the frontend equivalent of a router megafile. It owns URL parsing, workspace routing, panel selection, health loading, drawer state, and chrome composition for many tabs.

That makes the workspace hard to extend, hard to test in isolation, and easy to regress when a new tab or state branch is added.

## Goal

Split orchestration from rendering so the admin shell stays small and the workstream tabs can evolve independently.

## In Scope

- Move URL parsing and route normalization into a dedicated hook or controller.
- Move workstream selection and tab-to-surface mapping out of the component body.
- Keep health-loading behavior, but isolate it behind the shell controller.
- Split major tab rendering into smaller route-level pieces where it lowers coupling.

## Not In Scope

- Redesigning the admin navigation model.
- Changing the underlying admin routes or tab names.
- Reworking the business logic inside the individual tab components.

## Existing Building Blocks

- `web/components/admin/adminNavManifest.ts` already centralizes admin surface metadata.
- `web/components/admin/__tests__/AdminWorkspace.test.tsx` already covers normalization, health loading, and route transitions.

## Proposed Shape

- `useAdminWorkspaceState()` handles URL and route state.
- `AdminWorkspaceShell` renders the frame, drawer, and common chrome.
- Route-specific view components handle the actual tab bodies.

The component should become a composition layer instead of a state machine.

## Acceptance Criteria

- Existing admin workspace behavior remains unchanged from the user's point of view.
- The component body is significantly smaller and reads like a shell.
- Adding a new tab does not require editing one large conditional block in multiple places.

## Test Plan

- Keep the existing unit tests passing.
- Add or update tests for the extracted hook or controller.
- Verify the current route transitions still work for sessions, traces, alumni, and tracks.

## Risks

- A lazy-loading split could accidentally make the shell slower if it is done without care.
- URL normalization must stay exactly compatible so bookmarks and deep links do not break.
