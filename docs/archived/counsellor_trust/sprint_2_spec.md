# Counsellor Trust Sprint 2 Spec

Status: Approved (2026-04-22)  
Owner: Counsellor Trust track  
Audience: product, design, engineering, and sponsor review  
Related backlog: [sprint_list.md](./sprint_list.md)

## Purpose

Sprint 2 turns the existing counselor review surface into a narrow replacement workflow. Sprint 1 already made the system explain what is active and what has been superseded. Sprint 2 makes the counselor action itself understandable, so Henry Yeo can replace one employer fact, publish the update, and trust the result without being pushed into a generic content-management model.

## Problem

Today the counselor path is still too close to "review a diff and commit changes." That works for an engineer. It does not work well for a head of career services who needs to update guidance quickly and tell what is live after publish.

The missing piece is not a bigger publishing system. The missing piece is a counselor-friendly replace flow for one employer fact, with a clear before/after confirmation and a recovery path if something fails.

## Sprint Goal

Make the smallest useful replacement flow obvious and shippable:

1. Open employer facts
2. Select one active fact to replace
3. Review proposed changes
4. Publish the update
5. See a clear confirmation that says what changed, what is now active, and what was superseded

## Non-Goals

This sprint does not include:

- auth hardening
- timeout handling
- optimistic locking
- a new CMS or publishing platform
- a redesign of the entire admin IA
- new provenance UI
- student-facing chat changes
- retrieval-policy cleanup
- bulk publishing across many facts at once

The goal is workflow clarity on the current surfaces, not a new product shape.

## Users

Primary user: Henry Yeo and the counselors who publish employer guidance for him.

Sponsor user: Henry Yeo, who needs the system to be credible, low-friction, and easy to defend.

## Design Principles

- Show the replacement flow where people already work.
- Reuse the trust model from Sprint 1 instead of rebuilding it.
- Prefer plain English over system jargon.
- Make the success state and the failure state equally obvious.
- Keep the workflow small enough that a counselor can use it without a walkthrough.
- Keep actions and touch targets large enough to work on mobile.

## Workflow Model

The replace flow stays inside the existing admin surfaces. `EmployerFactsTab` is the entry point for the counselor. `KnowledgeUpdateTab` is the review and commit surface. Provenance and history stay collapsed or secondary. They support the workflow, but they are not the workflow.

```text
EmployerFactsTab
  -> select one active fact
  -> open replace workflow
  -> KnowledgeUpdateTab review
  -> edit proposed change
  -> publish update
  -> confirmation banner + updated active/superseded state
```

### What the user sees, in order

1. The employer detail view and its facts list.
2. The selected fact and the replacement input.
3. The review diff with source timestamps.
4. The publish action and confirmation.
5. The updated fact state after publish.

### What stays secondary

- provenance details
- audit history
- source timestamp metadata
- old versions that are already clearly superseded

## Scope

### Employer Facts detail view

Allow the counselor to start from one active employer fact and route into the replacement flow. The detail view should keep the active/superseded list visible, because counselors need to see what is current before they replace it.

### Review proposed changes / `KnowledgeUpdateTab`

Preserve the current review-and-commit surface, but make it feel like a publish step rather than a raw diff commit. The diff should show the counselor what changed, and the commit payload should preserve source metadata through the review.

### Post-action confirmation

After publish, show a clear inline confirmation that says:

- what changed
- what is now active
- what was superseded
- when it was updated

After the confirmation window, reset the review surface back to idle so the counselor can start the next replacement cleanly.

## Interaction States

| Feature | Loading | Empty | Error | Success | Partial |
|---------|---------|-------|-------|---------|---------|
| Employer facts list | Skeleton rows while employers load | Warm empty state with `+ Add first fact` | Inline "History unavailable - try refreshing" if the history endpoint fails | Selected fact updates to active/superseded and stays visible | Partial provenance shows `Unknown` explicitly |
| Review proposed changes | Status text while analysis runs | Prompt to add note or choose file before analysis | "Could not prepare the review" with retry path | Diff renders and publish button becomes available | Source timestamps still render even if some source labels are missing |
| Publish action | Button disabled while committing | N/A | "Could not save this update yet" with retry path | Confirmation banner shows the published result and then resets to idle | If the publish succeeds but some display metadata is missing, the counselor still sees the published state |
| Provenance panel | Collapsed by default | N/A | Non-blocking error if history is unavailable | Shows source, date, last updated, superseded by, and audit link | Unknown fields are rendered as `Unknown` |

## Success Criteria

Sprint 2 is successful if:

- Henry can replace one employer fact end-to-end without asking the developer to translate the UI.
- A counselor can tell what changed and what is live after publish within 30 seconds.
- The workflow gives a clear recovery path when analysis fails or publish fails.
- Both note mode and file mode work through the same replace flow.
- The success state resets cleanly so the next replacement starts from a clean idle state.
- The review payload keeps source provenance intact, even though Sprint 2 does not rebuild provenance UI.

## Implementation Notes

- Reuse `EmployerFactsTab` as the entry point.
- Reuse `KnowledgeUpdateTab` for review and commit.
- Preserve source timestamps through the review payload.
- Do not create a separate publishing system or a new provenance surface.
- Keep the copy specific to counselors, not to engineers.
- Use the current admin workspace shape rather than adding new global navigation.
- Keep the publish confirmation concise, but include the employer name and the fact summary so the counselor knows what actually changed.

## Design Decisions

Resolved during design review on 2026-04-22. These are binding for implementation.

### Architecture choice

Use the minimal replace/publish wrapper, not a separate publish state machine.

- The counselor workflow remains inside the existing admin surfaces.
- The diff and commit flow stays in `KnowledgeUpdateTab`.
- The employer fact list remains the starting point.
- Provenance and history stay as support surfaces, not new primary UI.

### Confirmation pattern

After publish, keep the counselor on the employer detail view and show an inline confirmation banner.

- The banner should include the employer name and the fact summary.
- The banner should state what changed, what is now active, and what was superseded.
- The banner should time out back to idle after a short interval, so the next action is obvious.

### Copy pattern

Use plain-English action language:

- "Replace current content"
- "Review proposed changes"
- "Publish updated content"

Do not introduce product-y CMS language. Counselors are replacing a fact, not operating a publishing backend.

### Scope boundary

Do not expand Sprint 2 into a broader publishing platform.

- No bulk replace flow.
- No new approval queue.
- No draft state machine.
- No separate authoring workspace.

### Provenance handling

Preserve source provenance through the payload and the confirmation state, but do not rebuild the provenance panel.

## Responsive & Accessibility

- Keep the admin workspace readable on mobile by stacking the employer list and detail area intentionally.
- Keep primary actions at least 44px high.
- Use visible focus states on every interactive element.
- Maintain WCAG AA contrast for text, helper copy, and status treatments.
- Keep review and publish controls usable with one hand on a phone.
- Preserve `aria-expanded` behavior on any collapsible helper surface reused from Sprint 1.

## Test Requirements

Sprint 2 needs coverage for the full counselor journey, not just the happy path.

- Add a regression test that walks the full replace, review, publish flow and asserts the post-action confirmation state, including the published result and reset back to idle.
- Cover both analysis input modes, note and file, so the workflow does not regress to one path only.
- Cover analysis failure and commit failure so counselors get a clear recovery path instead of a silent drop.
- Assert that source provenance is preserved through the review payload.
- Keep the existing provenance UI tests from Sprint 1, but do not expand them into a second publishing system.

## Deliverable Shape

The delivered workflow should make it obvious, from the same screen:

- what the counselor is replacing
- what was changed
- what is now active
- what was superseded
- how to recover if the review or publish step fails

If a counselor still needs the developer to explain those basics, Sprint 2 has not done its job.

## Open Questions

None. The design decision is to keep this as a minimal wrapper around the existing workflow.
