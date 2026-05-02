---
status: completed
created: 2026-05-02
last_updated: 2026-05-02
---

# Sprint: Workspace Clarity and Screen Economy

**Duration:** 1 week  
**Goal:** Make long-running AI work, unsaved extracted facts, and the main admin workspace state impossible to miss while reducing the amount of scrolling needed to keep context.  
**Primary surfaces:** Staging Area, Employer Fact Library, shared admin workspace shell.  
**Branch convention:** one PR per block when possible; all affected Vitest and Playwright checks green before merge.

**Status (2026-05-02):** Sprint complete. PR #20 shipped A1, B1, B2, C1, C2, and D1 plus the first A2 sweep (BrokenProfilesTab, EmployerFactsTab, KnowledgeUpdateTab, SessionInbox, SmartCanvas, ExtractedFactsModal). The follow-up pass completed the remaining A2 admin-tab audit, D2 sticky local context for the densest two-pane tools, and E1/E2 verification with focused Vitest and Playwright coverage.

---

## Problem

The admin workspace currently asks counsellors to trust hidden state.

1. In Staging Area, newly initiated session analysis only shows a text notice: "Analyzing your notes with AI...". The spinner that appears after refreshing an analyzing session is not visible during the initial flow, so the system can look passive even while work is happening.
2. Loading treatment differs across admin tabs. Employer Fact Library uses a small grey inline spinner inside the extract button that blends into the disabled control, while Staging Area uses SVG spinners and some other tabs use text-only states or skeletons.
3. In Employer Fact Library, extracted facts become local unsaved edits. The app blocks employer switching, but the save requirement is not visually strong enough. The main clue is a banner that can be above the user's current scroll position.
4. Several admin screens require enough vertical scrolling that users lose the session, selected employer, active tab, save state, or current action context.

## Sprint Goal

Ship a consistent admin interaction model:

- Long-running AI work has a visible spinner, status text, and persistent stop/retry affordance wherever the user is looking.
- Loading, saving, extracting, publishing, and analyzing states share one visual language across tabs.
- Extracted Employer Fact Library facts are clearly labelled as unsaved until saved or discarded.
- Key controls stay visible in dense workflows without taking over the screen.
- The workspace feels more like a compact workbench than a stack of long pages.

## Non-Goals

This sprint does not include:

- A full admin navigation redesign.
- Backend changes to extraction or session analysis semantics.
- New auth, optimistic locking, or multi-user edit protection.
- Rewriting every tab into a new layout system.
- Changing the data model for facts, sessions, employers, tracks, or alumni.

## Users

Primary user: counsellor/admin reviewing and publishing AI-extracted career knowledge.

Secondary user: operations/admin staff watching whether the system is actively working or waiting for input.

## Design Principles

- State should be visible at the point of work, not only in a toast or distant banner.
- Use the DESIGN.md palette: teal for trusted forward motion, amber for caution, warm neutrals for surfaces.
- Prefer sticky local toolbars and compact status rails over repeated banners.
- Do not rely on color alone. Pair spinner, label, and action availability.
- Preserve reading space. Sticky elements should be short, informative, and dismissible only when the underlying state is gone.
- Keep desktop dense and mobile stacked, with primary actions still at least 44px high.

---

## Block A - Shared Admin Status Components

### ~~A1. Add a shared loading/action status component~~  ✓ Shipped

`web/components/admin/ui/ActionStatus.tsx` now provides spinner + label + optional helper text with `active`, `caution`, and `on-dark` variants and `sm`/`md` sizes. Used across SmartCanvas, SessionInbox, EmployerFactsTab, KnowledgeUpdateTab, ExtractedFactsModal, and BrokenProfilesTab.

**Suggested file:** `web/components/admin/ui/ActionStatus.tsx`

**Visual standard:**

- Spinner size: `h-4 w-4` inline, `h-5 w-5` for standalone panels.
- Active color: `text-[var(--cl-accent)]` or `border-[var(--cl-accent)]`.
- Caution color: `text-[var(--cl-warning)]` for cancellable or delayed analysis.
- Button spinners must contrast with the button background.
- Status text uses `text-sm`; helper text uses `text-xs text-[var(--cl-muted)]`.

**Acceptance criteria:**

- No grey spinner appears inside a grey or disabled button.
- Button loading states remain legible at WCAG AA contrast.
- The shared component has accessible text via visible copy or `aria-live`.
- Existing tab-specific spinners in touched surfaces are replaced with the shared component.

**Files likely touched:**

- `web/components/admin/SmartCanvas.tsx`
- `web/components/admin/SessionInbox.tsx`
- `web/components/admin/EmployerFactsTab.tsx`
- `web/components/admin/KnowledgeUpdateTab.tsx` if scope allows
- `web/components/admin/LLMObservabilityTab.tsx`
- `web/components/admin/TraceExplorerTab.tsx`
- `web/components/admin/StudentInsightsTab.tsx`
- `web/components/admin/FactsDashboardTab.tsx`
- `web/components/admin/TrackBuilderTab.tsx`
- `web/components/admin/ResumeReviewTab.tsx`
- Tests under `web/components/admin/__tests__/`

**Estimate:** 0.5 day

### ~~A2. Audit every admin tab for loading-state consistency~~  ✓ Shipped

**Shipped in PR #20:** Staging Area / SmartCanvas, Employer Fact Library, Knowledge Review, SessionInbox session-row spinner, ExtractedFactsModal, and BrokenProfilesTab now use `ActionStatus` instead of bespoke SVG spinners.

**Completed in follow-up:** Source Documents / KB Health, Student Insights, Facts Dashboard, Alumni Records, Track Builder, Resume Review, LLM Observability, and Trace Explorer now use the shared `ActionStatus` treatment for long-running work, while intentional skeleton states also carry accessible loading text.

**What:** Sweep all admin tabs and standardize their long-running states. Use the shared spinner/status component for action-level work and keep skeletons only where they represent content layout loading.

**Tabs in scope:**

- Staging Area / SmartCanvas ✓
- Employer Fact Library ✓
- Knowledge Review ✓
- Source Documents / KB Health ✓
- Student Insights ✓
- Facts Dashboard ✓
- Alumni Records ✓
- Track Builder ✓
- Resume Review ✓
- LLM Observability ✓
- Trace Explorer ✓

**Acceptance criteria:**

- Every loading, saving, extracting, publishing, searching, analyzing, and generating state has a consistent spinner/status treatment or an intentional skeleton state.
- Any intentional skeleton state has accompanying accessible loading text.
- No tab has a text-only long-running AI state.
- No tab uses old blue/grey spinner colors that conflict with DESIGN.md.

**Estimate:** 0.5-1 day

---

## Block B - Staging Area Analysis Visibility

### ~~B1. Show the same spinner during initial analysis and refreshed analysis~~  ✓ Shipped

`SmartCanvas.tsx` now sets `isAnalyzingNow` when `analyzeSession()` starts, threads it into `isInFlight`, and renders the shared `ActionStatus` (md size) inside the loading panel. The visual state during initial analyze, refresh-mid-analyze, and retry now share the same component and copy.

**What:** When a session analysis is initiated from Staging Area, show the same visible spinner users currently see after refreshing an analyzing session.

**Current behavior:** `SmartCanvas.analyzeSession()` sets `notice` to "Analyzing your notes with AI..." but the spinner path only appears when `loading` is true or when the refreshed session status is `in-progress` / `analyzing`.

**Target behavior:**

- Immediately after analysis starts, the canvas header shows spinner + "Analyzing notes with AI...".
- The in-flow status panel remains visible until analysis finishes, fails, is cancelled, or times out.
- The stop analysis button remains available while the request is in flight.
- If the user refreshes mid-analysis, the visual state matches the initial analysis state.

**Acceptance criteria:**

- Starting a new session analysis shows a spinner without requiring page refresh.
- Re-analyze, retry, and initial analysis all use the same component and wording.
- The status is announced through an `aria-live="polite"` region.
- Existing SmartCanvas tests are updated to assert spinner/status visibility during active analysis.

**Files likely touched:**

- `web/components/admin/SmartCanvas.tsx`
- `web/components/admin/__tests__/SmartCanvas.test.tsx`
- `web/e2e/admin-workspace.e2e.ts` if an end-to-end state is practical with mocks

**Estimate:** 0.5-1 day

### ~~B2. Standardize session list row status~~  ✓ Shipped

`SessionInbox.tsx` session rows now render `ActionStatus` (caution variant, sm) for `in-progress` / `analyzing` rows in place of the old inline SVG spinner.

**What:** Align Staging Area session rows with the same loading language so users can tell which sessions are analyzing before opening them.

**Target behavior:**

- In-progress/analyzing rows use spinner + "Analyzing..." with consistent amber/teal treatment.
- Stop controls remain visible and keep their current minimum target size.

**Files likely touched:**

- `web/components/admin/SessionInbox.tsx`
- `web/components/admin/__tests__/SessionInbox.test.tsx` if present or new focused test

**Estimate:** 0.5 day

---

## Block C - Employer Fact Library Save Clarity

### ~~C1. Promote unsaved extracted facts to a persistent local state rail~~  ✓ Shipped

`EmployerFactsTab.tsx` now tracks `pendingExtractedCount`, increments it when extracted facts are added, and threads it into the sticky save area so the count and copy reflect unsaved extracted facts. Save and discard paths reset the count and dirty state.

**What:** When extracted facts are added from the modal, show a sticky local state rail in Employer Fact Library until the user saves or discards.

**Current behavior:** `handleAddExtractedFacts()` sets `hasUnsavedChanges` and blocks switching employers. A warning appears near the top of the right panel and a small lock banner appears in the left panel, but both can be out of sight.

**Target behavior:**

- The sticky bottom save bar explicitly says what is unsaved, for example: "3 extracted facts are not saved yet."
- The save button label changes to "Save 3 extracted facts" when extracted facts are the only dirty change, or "Save employer updates" for mixed edits.
- A secondary "Discard unsaved changes" action is available in the sticky area.
- The left employer list lock remains, but it becomes supporting evidence rather than the main cue.
- Switching employers while dirty opens the existing confirmation path, with copy that names the unsaved extracted facts.

**Acceptance criteria:**

- After adding extracted facts, the user can see the save requirement without scrolling to the top.
- The sticky save area includes both save and discard actions when unsaved changes exist.
- Navigating to another employer is blocked and explains why at the click location or in the sticky area.
- Save success clears the dirty state, extracted-fact count, lock banner, and discard action.
- Discard restores the selected employer's last saved facts and clears the dirty state.

**Files likely touched:**

- `web/components/admin/EmployerFactsTab.tsx`
- `web/components/admin/modals/ExtractedFactsModal.tsx` only if modal copy needs a handoff note
- `web/components/admin/__tests__/EmployerFactsReplace.test.tsx`
- New or expanded `EmployerFactsTab` tests for extracted facts and dirty-state navigation

**Estimate:** 1-1.5 days

### ~~C2. Add a beforeunload guard for unsaved employer facts~~  ✓ Shipped

`EmployerFactsTab.tsx` registers a `beforeunload` listener while `hasUnsavedChanges` is true and removes it after save or discard.

**What:** Add a browser-level guard when `hasUnsavedChanges` is true in Employer Fact Library.

**Acceptance criteria:**

- Closing or refreshing the tab with unsaved facts prompts the browser warning.
- The guard is removed after save or discard.
- The guard does not trigger for clean employer switching.

**Estimate:** 0.25 day

---

## Block D - Workspace Screen Economy

### ~~D1. Make the admin header and workspace controls less vertically expensive~~  ✓ Shipped

`AdminWorkspaceHeader.tsx` was rewritten as a two-row, compact header: row 1 carries wordmark + active page label + Staging Area / Traces / Browse shortcuts; the verbose tagline and stacked "Active page" card were removed. `DirectiveBanner.tsx` was tightened in the same PR. The active surface label remains visible above the fold at common desktop widths.

**What:** Reduce the persistent admin header footprint so each tool starts higher on the page without losing navigation context.

**Target behavior:**

- Current page, Staging Area shortcut, Trace Explorer shortcut, and Browse button stay visible.
- Workstream cards collapse into a compact segmented/workstream selector on desktop after initial load, or become a one-line control by default.
- Page-level directive remains visible but compact, with the job-to-be-done text shortened.

**Acceptance criteria:**

- On a 1440x900 viewport, the selected tool's first interactive region appears without scrolling.
- The active page label remains visible above the fold.
- No text overlaps or truncates in the header at 1024px and mobile widths.

**Files likely touched:**

- `web/components/admin/AdminWorkspaceHeader.tsx`
- `web/components/admin/DirectiveBanner.tsx`
- `web/components/admin/adminNavManifest.ts`
- `web/components/admin/__tests__/AdminWorkspace.test.tsx`

**Estimate:** 1 day

### ~~D2. Add sticky local context to dense two-pane tools~~  ✓ Shipped

Employer Fact Library, SmartCanvas, and Track Builder now behave like local workbenches instead of long stacked pages. Each keeps the active record summary, dirty/analyzing state, and primary actions close to the work with constrained split-pane layouts on desktop and active-work-first stacking on mobile.

**What:** Keep the selected record and primary actions visible inside dense admin tools instead of relying on page-level scrolling.

**Priority surfaces:**

1. Employer Fact Library: selected employer, Details/Facts tabs, dirty state, save/discard.
2. Staging Area SmartCanvas: session status, selected card summary, commit/discard actions.
3. Track Builder if time remains: selected track and publish/revert actions.

**Target behavior:**

- Left panes scroll independently from right panes.
- Local section headers stick within their panel, not the whole page.
- Primary action bars stay sticky at the bottom of the active panel.
- Long notes and raw diff previews keep their own constrained scroll areas.

**Acceptance criteria:**

- Employer list, fact list, and edit surface can scroll independently at desktop widths.
- Save/commit/discard actions remain visible during long edit reviews.
- Mobile stacks retain the active work before secondary context.
- No nested card-on-card styling is introduced.

**Files likely touched:**

- `web/components/admin/EmployerFactsTab.tsx`
- `web/components/admin/SmartCanvas.tsx`
- `web/components/admin/TrackBuilderTab.tsx` if included
- Playwright screenshots for desktop and mobile

**Estimate:** 1.5-2 days

---

## Block E - Verification and Polish

### ~~E1. Add focused regression tests~~  ✓ Shipped

Focused regression coverage now locks in the new workspace behavior:

- Vitest: SmartCanvas initial-analysis status, EmployerFactsTab sticky extracted-facts rail after modal add and after save, and the refreshed Facts Dashboard interaction path.
- Playwright: analyzing-state visibility before and after refresh, sticky employer save/discard affordances, 1440x900 control visibility, and mobile stacking for dense work surfaces.

**Vitest coverage:**

- SmartCanvas shows spinner/status during initial analysis.
- SmartCanvas shows the same status when loaded with `status: "analyzing"`.
- EmployerFactsTab shows sticky unsaved extracted facts state after modal add.
- EmployerFactsTab clears sticky dirty state after save.
- EmployerFactsTab blocks employer switching while dirty and names the unsaved work.

**Playwright coverage:**

- Desktop: Staging Area analyzing state is visible before and after refresh.
- Desktop: Employer Fact Library extracted facts show sticky save/discard without scrolling.
- Desktop: key controls visible at 1440x900.
- Mobile: controls stack without overlap and primary actions remain reachable.

**Estimate:** 1 day

### ~~E2. Visual QA checklist~~  ✓ Shipped

Completed verification on 2026-05-02:

- Targeted Vitest suite passed for SmartCanvas, EmployerFactsTab, StudentInsightsTab, FactsDashboardTab, TrackBuilderTab, ResumeReviewTab, and LLMObservabilityTab.
- Targeted Playwright admin workspace suite passed after installing the local Chromium runtime used by the test harness.
- Manual screenshot review covered desktop `1440x900` and mobile stacked layouts for the main dense-workflow surfaces.

Before shipping, verify:

- Loading states use the same spinner size, color, and copy pattern.
- Button loading spinners have enough contrast.
- Sticky bars do not cover final form fields.
- Header compaction does not hide the user's active location.
- No grey-on-grey spinner remains in Employer Fact Library.
- No new large scrolling dead zones were introduced.

**Estimate:** 0.5 day

---

## Execution Order

Recommended sequence:

```text
A1 shared status component
  -> A2 admin tab loading-state audit
  -> B1 SmartCanvas initial analysis spinner
  -> B2 SessionInbox row status
  -> C1 Employer facts sticky unsaved state
  -> C2 beforeunload guard
  -> D1 compact admin header
  -> D2 sticky local context for dense tools
  -> E1/E2 tests and visual QA
```

Rationale:

- The shared status component prevents each tab from solving loading states differently again.
- The audit pass catches secondary tabs after the main component exists.
- Staging Area and Employer Fact Library are the highest-friction user reports, so they land before broader layout polish.
- Header and sticky-panel work should happen after the state model is clear, because sticky UI needs to know which state deserves to stay visible.

---

## Definition of Done

This sprint is done when:

- [x] Starting Staging Area analysis visibly shows spinner + AI analysis status without page refresh. (B1)
- [x] All admin tabs use the shared loading/action language or an intentional skeleton state. (A2)
- [x] Employer Fact Library no longer has grey-on-grey loading treatment. (A2)
- [x] Adding extracted facts creates an always-visible unsaved state with save and discard paths. (C1)
- [x] Users cannot accidentally navigate away from unsaved extracted facts without a clear warning. (C2)
- [x] The admin workspace exposes key context and primary actions above the fold at common desktop sizes. (D1)
- [x] Sticky local context lands for dense two-pane tools. (D2)
- [x] Vitest and targeted Playwright checks cover the new behavior. (E1)
- [x] Visual QA checklist completed before ship. (E2)
- [x] `DESIGN.md` remains the source of truth for color, density, and component hierarchy.

## Deferred Follow-Ups

- Optimistic locking for concurrent employer edits.
- Full admin IA redesign.
- A cross-tab global unsaved-changes router guard.
- Broader component library extraction beyond the status and sticky action patterns introduced here.
