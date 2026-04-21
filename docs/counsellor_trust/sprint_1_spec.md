# Counsellor Trust Sprint 1 Spec

Status: Draft  
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
3. Knowledge Review diff view

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
- updated by
- superseded by
- audit link

### Audit-link targets

- Employer Facts should link to the originating YAML diff.
- Knowledge Review items should link to the review history.
- Admin workspace cards should link to the in-app action history when that exists.

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
- Limit inline history to three entries.
- Put older history behind a `view history` action.

## Scope

### Admin workspace landing cards

Add a concise purpose line and visible provenance summary to the cards counsellors use to discover tools.

### Employer Facts detail view

Expose the active/superseded state and the full provenance panel for employer facts, since this is where counsellors inspect actual knowledge records.

### Knowledge Review diff view

Expose source and revision context so counsellors can tell what changed and why before they publish or accept a change.

## Success Criteria

Sprint 1 is successful if:

- In five observed counsellor sessions, at least four can answer what a tool does, what changed, and whether content is current within 30 seconds without asking the developer.
- In those same sessions, at least four can identify active versus superseded content without opening raw YAML.
- Henry Yeo can review the surfaces and explain them to another person without adding his own interpretation.
- Missing provenance is never shown as a blank mystery state.
- The first three target surfaces each have a clear purpose line and a visible provenance summary.

## Implementation Notes

- YAML remains the canonical knowledge source.
- Existing audit and revision patterns should be reused instead of introducing a parallel provenance system.
- The spec should stay compatible with the current admin workspace shape.
- Any copy expansion should stay limited to the top three confusing tools first.

## Open Questions

- Which fields are computed from YAML and git history versus explicitly authored?
- How much history should be visible by default on each surface?
- Should the tone be strictly plain or slightly guided for first-time counsellors?

## Deliverable Shape

The delivered UI should make it obvious, from the same screen:

- what this tool or record does
- whether the content is active
- where it came from
- when it last changed
- where to inspect the audit trail

If a counsellor still needs the developer to explain those basics, Sprint 1 has not done its job.
