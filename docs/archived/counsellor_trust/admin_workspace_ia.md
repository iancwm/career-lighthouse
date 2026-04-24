# Admin Workspace IA

Status: draft

## Problem

The current admin surface behaves like a toolbox of API-adjacent features. That makes the UI hard to scan, hard to teach, and hard to use under time pressure.

The real user jobs are workflow-shaped:

- bring in meeting notes, alumni conversations, and research
- turn raw material into trusted career knowledge
- use that knowledge to prepare for a specific student
- keep the system healthy and inspect observability data

The UI should reflect those jobs directly.

## Goal

Replace the flat button set with a workflow-first information architecture that:

- reduces visible clutter
- gives each surface a clear purpose
- separates knowledge creation from student prep
- keeps observability and policy work out of the main daily path

## Recommended Model

Use three top-level workstreams:

1. Career Wire
2. Smart Counsellor
3. Admin Room

This is the recommended default because it matches how counselors think about the work.

## Workstream Definitions

### Career Wire

For all work related to adding career knowledge and reviewing what is on the backend.

This is the inbound and publishing lane. Counselors bring in notes, alumni conversations, and research, then decide what becomes part of the trusted knowledge base.

### Smart Counsellor

For leveraging knowledge for a particular student.

This is the student-specific prep lane. The counselor uses the career knowledge base to get ready for a conversation, review the right context, and move quickly.

### Admin Room

For LLM observability, policy documents, and other non-counselling operations.

This is the machine room. It exists so the system can be monitored, audited, and maintained without polluting the counselor workflows.

## Page Map

### Career Wire

- Staging Area
- Review & Publish
- Employer Records
- Track Builder
- Profile Repair

### Smart Counsellor

- Session Prep
- Resume Review

### Admin Room

- LLM Observability
- Trace Explorer
- Policy Documents
- System Health

## Why These Names

### Career Wire

This name gives the workspace a sense of active incoming information. It feels current without sounding like an API bucket or a generic content library.

### Staging Area

This is the prominent entry page for meeting notes, research, and incoming material.

The name works because it describes the state of the work:

- raw material has arrived
- it is not yet finalized
- it is waiting to be reviewed and turned into something trusted

### Review & Publish

This is better than `Review Updates` because it describes the actual job rather than the data shape.

It makes the workflow explicit:

- review the incoming material
- decide what matters
- publish what becomes true

### Employer Records

`Employer Facts` sounds like an internal data structure.

`Employer Records` sounds like an owned surface where counselors maintain structured employer knowledge over time.

### Smart Counsellor

This name makes the job obvious. The counselor is using the knowledge base for one student, not editing the source of truth.

### Admin Room

This name keeps observability and policy work in a clearly separate lane. It should feel operational, not counselor-facing.

## What Happens To The Old Sessions Area

The old `Sessions` workflow is not student prep.

It is the knowledge intake and publishing flow where counselors upload meeting notes, alumni conversations, and research, then convert that into durable career knowledge.

In the new IA, that work lives in:

- Career Wire
- Staging Area

This is a deliberate rename, not just a re-label.

## What Gets Moved Out Of The Flat Toolbox

The current toolbar mixes too many jobs into one visual layer. In the new model:

- `Documents` should split by intent
  - career knowledge goes through Career Wire
  - policy docs go into Admin Room
- `Trace Explorer` should not compete as a top-level peer to the workflow cards
  - it belongs in Admin Room
  - it can still be linked from Smart Counsellor when a counselor needs it
- `Review Updates` should become `Review & Publish`
- `Employer Facts` should become `Employer Records`
- `Sessions` should become `Staging Area` under Career Wire

## Recommended Navigation Hierarchy

### Level 1

Show three large cards or tabs:

- Career Wire
- Smart Counsellor
- Admin Room

### Level 2

Inside each workstream, show the relevant pages only.

Do not expose the whole toolbox at once.

### Level 3

Use secondary links, helpers, or contextual shortcuts for niche surfaces like trace inspection.

## Default Landing

The default landing area should be Career Wire, with Staging Area as the first surface inside it.

Why:

- it is the most workflow-heavy and high-value path
- it is where raw material enters the system
- it matches the user's mental model of bringing in new knowledge first

## Current Button Mapping

| Current Surface | New Home |
|---|---|
| Sessions | Career Wire -> Staging Area |
| Review Updates | Career Wire -> Review & Publish |
| Employer Facts | Career Wire -> Employer Records |
| Track Builder | Career Wire |
| Career Tracks | Career Wire, likely folded into Track Builder or a dedicated subpage if needed |
| Broken Profiles | Career Wire -> Profile Repair |
| Resume Review | Smart Counsellor |
| LLM Observability | Admin Room |
| Trace Explorer | Admin Room |
| Documents | Split by intent between Career Wire and Admin Room |

## Design Principles

- Name the workflow, not the data object.
- Put the highest-frequency job first.
- Keep knowledge creation separate from student-specific usage.
- Keep observability and policy work out of the daily counselor path.
- Show fewer choices at once.

## What Already Exists

- `SessionInbox` already covers the intake and publishing flow for counsellor notes.
- `KnowledgeUpdateTab` already covers note and file review before KB writes.
- `TrackBuilderTab` already covers draft, publish, rollback, and track history.
- `EmployerFactsTab` already covers structured employer maintenance and audit history.
- `LLMObservabilityTab` already covers trace and retrieval health.
- `TraceExplorerTab` already covers drill-down trace inspection.
- `AdminWorkspace` and `ToolsDrawer` already provide the single admin shell the new IA should reuse.

## Not In Scope

- Rewriting backend knowledge retrieval or source-ledger logic.
- Changing the current query-param admin shell into a multi-route app.
- Renaming the internal `view=` slugs right away.
- Making `Trace Explorer` a primary top-level workflow card.
- Rebuilding the underlying intake, publish, or track editor components from scratch.

## Resolved Decisions

1. Keep the current `view=` slugs for compatibility, and change only the visible labels plus the grouping.
2. Keep the current one-page admin workspace, with the three workstreams presented as large cards or tabs.
3. Make `Trace Explorer` a secondary deep link from the main workstreams, not a top-level card.
4. Fold `Career Tracks` into `Track Builder` rather than keeping a separate peer button.
5. Split the old `sessions` screen into sibling views for `Career Wire` and `Smart Counsellor`.
6. Use a shared nav manifest so the workspace header and drawer do not drift apart.
7. Add a Playwright E2E for the admin landing flow and the legacy URL compatibility cases.

## Recommendation

Ship the three-workstream model as the default admin IA:

1. Career Wire
2. Smart Counsellor
3. Admin Room

Use `Staging Area` as the prominent first page in Career Wire.

That gives the UI a clear story:

- raw material comes in
- counselors make it true
- counselors use it for a student
- ops keeps the system healthy

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAN | 7 decisions locked, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |

- **UNRESOLVED:** 0
- **VERDICT:** ENG CLEARED, ready to implement
