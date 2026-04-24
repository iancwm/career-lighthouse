# Counsellor Trust Sprint 3 Spec

Status: Implemented (2026-04-22)  
Owner: Counsellor Trust track  
Audience: product, design, engineering, and sponsor review  
Related backlog: [sprint_list.md](./sprint_list.md)

## Implementation Status (2026-04-22)

Sprint 3 implementation has landed in the student chat flow:

- trust context now starts as a compact pill and expands inline on click/tap
- expanded context shows background, region, interest, active career type, and resume presence
- chat now supports in-surface `Edit context` and `Reset chat` actions
- citations now render readable provenance details (source name, updated date, lifecycle, excerpt)
- API citation payload now includes `source_name`, `updated_at`, and `source_lifecycle`
- regression coverage added for student page trust flow, chat reset behavior, and citation disclosure

## Purpose

Sprint 3 makes student chat state visible and credible. Students should be able to see the background, region, interest, resolved active career type, and whether a resume is present that shape the conversation. They should also be able to edit or reset that context from the chat surface itself. Answers should present readable source names and updated dates, and normal student citations should prefer active, non-superseded sources.

## Problem

The current student chat only exposes a lightweight `Advising on` badge. That tells the student that some context exists, but not what the active context actually is. The current citation chips are also too raw: they read like filenames instead of source provenance, which makes the answer feel less transparent than it should.

Without a visible context panel and a readable provenance pattern, personalization feels hidden. The student cannot easily tell what influenced the answer, whether their intake data was used, or how to reset the conversation if the context is wrong.

## Sprint Goal

Expose the active context and source provenance directly inside chat while keeping the surface simple:

1. Show the current context in one obvious place
2. Make the first assistant response acknowledge that context
3. Let the student edit or reset context from the chat
4. Render citations as readable provenance rather than raw filename chips
5. Prefer active, non-superseded sources in student answers

## Non-Goals

This sprint does not include:

- auth hardening
- timeout handling
- optimistic locking
- a new student profile editor
- a separate context management settings page
- a broad retrieval-policy rewrite
- counselor/admin workflow changes
- bulk context editing across sessions
- a new CMS or publishing platform

The goal is visible context and readable provenance on the current student surfaces, not a new product shape.

## Users

Primary user: students using chat for career guidance.

Secondary user: counsellors and sponsors who need the student experience to feel credible, explainable, and consistent with the trust model.

## Design Principles

- Show the hidden state where the student already works.
- Prefer plain English over internal slugs.
- Make it obvious when a field is unknown.
- Keep context editable in place.
- Prefer active sources and do not present superseded content as current.
- Keep the surface mobile-friendly and easy to scan.

## Workflow Model

The student experience stays inside the existing intake and chat flow. The intake step seeds the conversation context. The chat view shows that context, uses it in the first response, and lets the student revise or clear it without leaving the conversation.

```text
IntakeFlow
  -> complete intake
  -> ChatInterface shows visible context panel
  -> first assistant response acknowledges active context
  -> student edits or resets context if needed
  -> assistant responses show readable source provenance
```

### What the student sees, in order

1. Intake selections that become active chat context.
2. A visible context panel that summarizes the active state.
3. The first assistant response acknowledging the selected context.
4. A simple edit/reset path if the context is wrong.
5. Citations that read like source provenance, not raw file labels.

### What stays secondary

- internal slugs
- raw filename identifiers
- superseded sources that are already clearly non-active
- low-level retrieval mechanics

## Scope

### Visible context panel

Add a visible panel in student chat showing:

- intake background
- region
- interest
- resolved active career type
- whether a resume is present

The panel should make unknown fields explicit instead of hiding them. If a value is missing, show `Unknown`.

### Context edit and reset

Give the student an obvious in-chat way to revise or clear context. The action should not require a page reload or a trip back through the full onboarding flow.

Resetting context should clear the active career type and return the conversation to a clean state so the next answer reflects the new context, not stale state from an earlier exchange.

### First assistant response

When context is present, the first assistant response should explicitly acknowledge the selected context in plain English. The response should read like the system understood who the student is and what they care about, not like it is exposing an internal state machine.

### Readable source display

Replace the current raw citation badge pattern with a more readable provenance treatment. Each citation should show:

- source name
- updated date
- optional excerpt or hover detail

The student should not have to infer what a filename means or whether it is current.

### Active-source preference

Normal student answers should prefer active, non-superseded sources. Superseded sources should not appear as current citations in the primary student experience.

If the system cannot find active sources, it should fail visibly and honestly rather than quietly presenting stale material as current.

## Interaction States

| Feature | Loading | Empty | Error | Success | Partial |
|---------|---------|-------|-------|---------|---------|
| Visible context panel | Skeleton or placeholder rows while labels resolve | Warm empty state before intake is completed | Fallback text if labels cannot load | Shows background, region, interest, active career type, and resume presence | Unknown fields render explicitly as `Unknown` |
| Context edit/reset | Edit button disabled while the panel is updating | N/A | Inline recovery text if reset fails | Context changes immediately and the next answer uses the updated state | Partial context can still be shown while one field is missing |
| First assistant response | Thinking state while the reply is generated | N/A | Clear retry-safe error message | Response acknowledges the selected context in plain English | If one context field is missing, the acknowledgement should still be truthful |
| Citations | Placeholder while answer is streaming | N/A | Non-blocking citation fallback if provenance data is missing | Source name and updated date are shown in a readable format | Missing provenance fields render as `Unknown` |

## Success Criteria

Sprint 3 is successful if:

- A student can see the full active context influencing the conversation without leaving chat.
- A student can tell whether their intake choices actually shaped the chat.
- The first assistant response explicitly acknowledges the selected context.
- Students can edit or reset context from the chat surface itself.
- Answers show readable source name and updated date rather than raw filename chips.
- Normal student citations prefer active sources and do not present superseded content as current.
- The chat remains usable on mobile and does not feel overloaded by the added context.

## Implementation Notes

- Reuse the current `IntakeFlow` context model and `ChatInterface` active career state.
- Keep the one-time intake send behavior, but make the visible panel reflect what was actually sent.
- Do not create a separate student profile editor.
- Map active career type slugs to user-facing labels wherever they are shown.
- Let source metadata flow through the chat response shape rather than reconstructing it in the UI.
- Keep the retrieval-policy changes small in this sprint; broader backend filtering belongs in Sprint 4.
- Keep the copy student-facing and plain, not counselor- or engineer-facing.
- Make the trust pill a real button, not a styled span. It needs visible focus, `aria-expanded`, `aria-controls`, and at least a 44px touch target.
- On mobile, expanding the pill should push the chat content and composer down inline instead of opening a separate overlay.
- Use the existing DESIGN.md language for the new trust surface: warm neutrals, teal as the primary accent, Fraunces for authored headings, Instrument Sans for UI copy, and IBM Plex Mono for metadata.
- Avoid default blue badge styling for context and citation chips so the student surface stays editorial and consistent with the rest of the product.

## Test Requirements

Sprint 3 needs coverage for the full student trust flow, not just the happy path.

- Add a page-level regression test in `web/app/student/__tests__/StudentPage.test.tsx` that walks guided entry, intake, chat, and the hard reset path, then asserts the chat clears cleanly and the student can start over.
- Extend `web/components/student/__tests__/ChatInterface.test.tsx` to cover the visible context pill, first assistant acknowledgement, reset cleanup, and the fallback path where intake context is not resent after a successful first turn.
- Extend `web/components/student/__tests__/CitationBadge.test.tsx` or add the new trust-pill component test file to cover collapsed-to-expanded disclosure, footnote visibility, keyboard activation, and the mobile tap/click path.
- Cover the new provenance rendering so citations show readable source information instead of only raw filenames.
- Assert that active sources are preferred and superseded sources do not appear as current student citations.

## Deliverable Shape

The student experience should make it obvious, from the same conversation:

- who the system thinks the student is
- what context is active
- how to change that context
- which sources the answer came from
- whether those sources are current

If the student still has to guess what is influencing the answer, Sprint 3 has not done its job.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 4 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | clean | 3 issues fixed in-plan |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**UNRESOLVED:** 0
**VERDICT:** ENG + DESIGN CLEARED, ready to implement
