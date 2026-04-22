# Counsellor Trust Sprint 1 Spec

Status: Implemented (2026-04-22)
Owner: Counsellor Trust track  
Audience: product, design, engineering, and sponsor review  
Related backlog: [sprint_list.md](./sprint_list.md)

## Purpose

Sprint 1 makes the system explain itself. Counsellors should be able to tell what a tool does, what content is active, and what content has been superseded without asking the developer. This is a trust and transparency sprint, not an auth or workflow-rewrite sprint.

The sponsor concern is real: if Henry Yeo is backing the project, the product has to look understandable and useful enough that it does not read like hidden effort with unclear value.

## Problem

The current UI gives counsellors one-line labels and thin status cues. That is not enough for non-technical users to understand:

- what a tool is for
- what it changes
- whether the content they are looking at is current
- whether an older record is still active or only kept for audit

As a result, counsellors ask the developer to translate the UI for them. That creates support drag, weakens confidence, and makes the product feel more complicated than it needs to be.

## Sprint Goal

Make the three highest-friction counsellor surfaces self-explanatory:

1. Admin workspace landing cards
2. Employer Facts detail view
3. Review proposed changes / `KnowledgeUpdateTab`

These are the first surfaces where counsellors should be able to understand purpose, status, and provenance at a glance.

## Non-Goals

This sprint does not include:

- auth hardening
- timeout handling
- optimistic locking
- a global coach mode
- a full onboarding rewrite
- a redesign of the entire admin IA

The goal is transparency on the current surfaces, not a new product shape.

## Users

Primary user: non-technical counsellors who need the UI to explain itself.

Sponsor user: Henry Yeo, who needs the system to be credible, low-friction, and easy to defend.

## Design Principles

- Show state where people already work.
- Prefer plain English over system jargon.
- Never hide missing provenance; say when data is unknown.
- Keep superseded content visible for audit, but clearly non-active.
- Use a consistent explanation pattern across tools and records.

## Trust Model

### Lifecycle states

- Active: the current live version a counsellor should treat as truth.
- Superseded: a prior version that remains visible for audit, but is no longer current.
- Archived: a retired item kept for reference, with no expectation that it should be used again.

Employer facts use explicit lifecycle metadata so the UI can show whether a fact is active or superseded instead of inferring state from whether it still appears in the current list.

### Lifecycle rule

A record is active when it is the current live version for that employer or review item. A record is superseded when a newer record exists that replaces it or points back to it in history. Archived is reserved for records that are intentionally retired.

### Missing data rule

If a provenance field is unknown, the UI must show `Unknown` explicitly and explain why it is unknown where possible. Blank provenance is not acceptable.

## UI Contract

### Two-level disclosure model

Sprint 1 uses a summary card plus a detail panel.

Card summary:

- status
- source date
- last updated

Detail panel:

- status
- source
- source date
- last updated
- superseded by
- audit link

`updated by` is deferred until proper login/auth exists. Do not invent it from git history or container metadata.

For Review proposed changes, source timestamps must travel through the diff contract so counsellors can see where a change came from before they save it.

### Audit-link targets

- Employer Facts should link to the employer history endpoint that resolves to the originating YAML diff.
- Knowledge Review items should link to the review history.
- Admin workspace cards should link to the in-app action history when that exists.

Employer Facts need a real employer history endpoint, not a guessed file path.

### Copy contract for tool explainer text

Use the same structure everywhere:

1. What the tool is for
2. What it changes
3. When to use it
4. What it does not do

Only the top three most confusing tools get the full four-sentence explainer. Other cards get a one-sentence purpose line.

### Interaction rules

- Show a status badge on list cards.
- Show the full provenance panel in detail views.
- Keep superseded items visible but collapsed by default.
- Soft-delete facts so history stays visible when a fact is no longer active.
- Limit inline history to three entries.
- Put older history behind a `view history` action.

## Scope

### Admin workspace landing cards

Add a concise purpose line and visible provenance summary to the cards counsellors use to discover tools.

### Employer Facts detail view

Expose the active/superseded state and the full provenance panel for employer facts, since this is where counsellors inspect actual knowledge records.

### Review proposed changes / `KnowledgeUpdateTab`

Expose source and revision context so counsellors can tell what changed and why before they publish or accept a change. This surface is the existing `KnowledgeUpdateTab`, and the primary action label is `Review proposed changes`.

## Success Criteria

Sprint 1 is successful if:

- In five observed counsellor sessions, at least four can answer what a tool does, what changed, and whether content is current within 30 seconds without asking the developer.
- In those same sessions, at least four can identify active versus superseded content without opening raw YAML.
- Henry Yeo can review the surfaces and explain them to another person without adding his own interpretation.
- Missing provenance is never shown as a blank mystery state.
- The first three target surfaces each have a clear purpose line and a visible provenance summary.
- The review flow preserves source timestamps on proposed changes.
- Employer facts can be retired without deleting their history.

## Implementation Notes

- YAML remains the canonical knowledge source.
- Existing audit and revision patterns should be reused instead of introducing a parallel provenance system.
- The spec should stay compatible with the current admin workspace shape.
- Any copy expansion should stay limited to the top three confusing tools first.
- Split the large admin components before wiring in the new provenance panel and lifecycle UI.
- Add contract tests for provenance, lifecycle, audit, soft-delete, and source timestamp behavior.

## Design Decisions

Resolved during design review (2026-04-21). These are binding for implementation.

### Visual Hierarchy — per surface

**Admin workspace tool cards:** Purpose-first hierarchy.
- Row 1: tool name (title-md, Instrument Sans 22px) + lifecycle badge right-aligned
- Row 2: purpose line (body-sm, Instrument Sans 14px, muted #5F6B76)
- Row 3: provenance summary in IBM Plex Mono meta (12px): source date · last updated
- Status badge does not dominate the card. It confirms state; the purpose line orients.

**Employer Facts detail view:** Type and lifecycle share the first row.
- Row 1: `[fact-type badge]  [● Active]` — type badge left, lifecycle badge immediately after
- Row 2: key field value (body-md, ink #1F2937)
- Row 3: `▸ Provenance` — collapsed by default, click to expand
- Superseded facts: same layout, muted #5F6B76 text throughout, `○ Superseded` badge

**KnowledgeUpdateTab — Review proposed changes:** Source timestamp is per-field inline.
- Each proposed field change shows: old value → new value, then source and date below in IBM Plex Mono meta
- Example: `ep_requirement: "2.8 GPA" → "3.0 GPA"` / `Source: Counselor note · 21 Apr 2026`

### Lifecycle Badge Design

Use a dot + label pill pattern, not a colored left-border card.

- `● Active` — teal `#0F766E` dot, teal label, pill background `#0F766E` at 10% opacity
- `○ Superseded` — muted `#5F6B76` dot, muted label, pill background neutral
- `◦ Archived` — amber `#B45309` dot, amber label, pill background `#B45309` at 10% opacity

Badge label: Instrument Sans body-sm (14px). Pill border-radius: 9999px (DESIGN.md pill). No colored left-border on cards.

### Fact Type Badge Colors

Remap from Tailwind color utilities to DESIGN.md tokens:

| Fact type | Badge color |
|-----------|-------------|
| alumni | teal `#0F766E` (primary) |
| timeline_phase | amber `#B45309` (secondary) |
| interview_stage | ink `#1F2937` (neutral) |
| compensation | amber `#B45309` (secondary) |
| skill_requirement | muted `#5F6B76` (neutral) |

### Provenance Panel

The full provenance panel (source, source date, last updated, superseded by, audit link) is expandable on click, not always visible.

- Collapsed: `▸ Provenance` trigger in body-sm, muted
- Expanded: `▾ Provenance` with fields in IBM Plex Mono meta (12px / 1.4)
- Panel container: surface `#FFFDFC`, border `line #D8D0C4`, border-radius md (14px)
- Audit link: Instrument Sans body-sm, teal `#0F766E`, `→` suffix, opens in new tab

### Interaction States

**Empty state (Employer Facts, no facts yet):**
Show warm message and primary CTA — do not show a blank list.
> "No facts yet for [Employer Name]. Facts you add here are shared with students who ask about this employer."
> `[ + Add first fact ]` — teal primary button

**Loading state:** Skeleton placeholder matching fact card dimensions. Do not use a spinner alone.

**Error state (history endpoint unavailable):** Inline non-blocking message: "History unavailable — try refreshing." Do not fail the whole fact view; the fact content remains visible.

**Partial provenance (some fields unknown):** Show `Unknown` explicitly per the missing data rule. Do not leave fields blank.

### Soft-Delete UX

When a counsellor deletes a fact, it transitions in-place to Superseded — it does not disappear.

1. Fact badge changes immediately from `● Active` to `○ Superseded`
2. Fact text transitions to muted `#5F6B76`
3. A 5-second undo toast appears: `Undo · 4s  ×`
4. After undo window: the fact remains in the list as Superseded, collapsed by default

This makes the lifecycle model tangible at the moment of action.

### Sponsor Demonstration Surface

The Employer Facts detail view is the primary surface for demonstrating the trust model to Henry Yeo. A complete fact with `● Active` badge, expandable provenance panel showing source and date, and an audit link should be the first thing shown in any sponsor walkthrough. Build this surface to that standard.

### Responsive & Accessibility

Mobile scope for Sprint 1: readable on mobile, no intentional layout changes.
- Provenance panel fields stack vertically on narrow screens; no horizontal overflow
- All interactive elements (delete, provenance toggle, audit link) must be minimum 44px touch target
- Fix `FactCard` delete button: currently ~28px, must be padded to 44px

A11y baseline (DESIGN.md):
- Visible focus states on all interactive elements (provenance toggle, delete, audit link)
- WCAG AA contrast for all text including muted provenance fields
- `aria-expanded` on provenance toggle

### Design System Token Reference

For implementers — explicit DESIGN.md token mappings for all new Sprint 1 elements:

| Element | Token |
|---------|-------|
| Purpose line text | `muted #5F6B76`, Instrument Sans body-sm 14px |
| Provenance fields | IBM Plex Mono meta 12px / 1.4 |
| Badge label | Instrument Sans body-sm 14px |
| Panel background | `surface #FFFDFC` |
| Panel border | `line #D8D0C4` |
| Panel border-radius | `md` (14px) |
| Active dot/text | `#0F766E` |
| Superseded dot/text | `#5F6B76` |
| Archived dot/text | `#B45309` |
| Audit link | `#0F766E`, → suffix, `target="_blank"` |

## Open Questions

- Should the tone be strictly plain or slightly guided for first-time counsellors?

(Resolved: history visible by default = 3 entries inline, then `view history`. Decided in UI Contract section.)

## Deliverable Shape

The delivered UI should make it obvious, from the same screen:

- what this tool or record does
- whether the content is active
- where it came from
- when it last changed
- where to inspect the audit trail

If a counsellor still needs the developer to explain those basics, Sprint 1 has not done its job.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAN (PLAN) | 3 critical decisions (F/G/H): lifecycle filter bug in to_context_block(), source_timestamp via metadata injection, 30-YAML schema drift. 9 backend + 8 frontend + 2 E2E tests specified. |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAN (PLAN) | score: 5/10 → 9/10, 11 decisions |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**UNRESOLVED:** 0
**VERDICT:** Design Review CLEARED. Eng Review CLEARED. Implementation may begin.
