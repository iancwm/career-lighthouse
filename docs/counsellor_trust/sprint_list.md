**Career Lighthouse is a counsellor-trust system first.**
YAML is the canonical career intelligence layer; Qdrant is supporting retrieval for voluminous source material. Content should be auditable, supersession should be explicit, and students should see a full visible context panel in chat. Sprints 1 through 4 are now implemented; the next sprint cycle should focus on follow-up hardening work, not the core trust model.

That fits the current codebase well:

* session-first admin workspace already exists 
* student guided entry/intake/chat already exists, but context visibility is still lightweight   
* YAML already acts as editable structured knowledge while Qdrant stores uploaded document chunks 
* your backlog already points toward provenance, stale chunk handling, and durable source management 
* your user notes consistently emphasize traceability, freshness, source visibility, and confidence in what is active 

## What I would do next

I would structure the work into **4 sprints**.

## ~~Sprint 1 — Canonical content lifecycle and supersession model~~ ✓ Done

Goal: make “what is active” and “what has been superseded” explicit in the backend and admin UI.

See the working spec in [sprint_1_spec.md](./sprint_1_spec.md).

### Scope

* define content lifecycle states for counsellor-managed knowledge

  * active
  * superseded
  * archived
* introduce a durable source document ledger for uploaded documents
* retain source file metadata for audit

  * uploaded by
  * uploaded at
  * source filename
  * linked knowledge object
  * superseded status
* define and implement supersession rules:

  * YAML remains canonical
  * old content should no longer be presented as active
  * Qdrant content linked to superseded sources must be excluded or marked non-retrievable for student answers
* expose active/superseded status in admin surfaces

### Why first

This directly addresses the counsellor trust problem and the Head of Service governance problem.

### Acceptance criteria

* counsellor can identify the current active version of a knowledge item
* superseded items remain visible for audit, but are clearly non-active
* source metadata shows source + updated date
* system behavior follows “YAML first, Qdrant support only”

---

## Sprint 2 — Counsellor update workflow: replace, review, publish

Goal: turn ingestion into a trustworthy workflow instead of a generic upload action.

See the final spec in [sprint_2_spec.md](./sprint_2_spec.md).

### Scope

* create a guided “replace current content” workflow for first-class knowledge items
* distinguish:

  * first-class career intelligence in YAML
  * supporting source documents in Qdrant/ledger
* add review/publish UI language aligned to counsellor intent

  * replace current FAQ / source
  * review proposed changes
  * publish updated content
* add clear post-action confirmation

  * what changed
  * what is now active
  * what was superseded
  * updated date
* add admin affordances to inspect source provenance at the item level

### Why second

You already have admin knowledge surfaces, but they are still too close to implementation details and not strong enough as a publishing workflow .

### Acceptance criteria

* counsellor knows where to go to replace content
* counsellor can tell which content is live after publish
* outdated content is visibly superseded, not ambiguously “somewhere in the system”
* active career intelligence remains YAML-backed and inspectable

### Sprint 2 test requirements

* add a regression test that walks the full replace/review/publish flow and asserts the post-action confirmation state, including the published result and reset back to idle
* cover both analysis input modes, note and file, so the workflow does not regress to one path only
* cover the error paths for analysis failure and commit failure so counsellors get a clear recovery path instead of a silent drop
* assert that source provenance is preserved through the review payload, even though Sprint 2 should not rebuild the provenance UI itself

### Sprint 1 impact on Sprint 2

Sprint 1 already shipped the trust-model plumbing that Sprint 2 depends on:

* active/superseded/archived lifecycle states
* readable provenance summaries and audit/history links
* review proposed changes language in `KnowledgeUpdateTab`
* source timestamps carried through the review flow

Sprint 2 should now focus on the remaining guided replace/publish workflow and clearer post-action confirmation without reworking the provenance foundation again.

---

## Sprint 3 — Student trust surfaces and visible context panel

Goal: make chat personalization inspectable and credible.

See the working spec in [sprint_3_spec.md](./sprint_3_spec.md).

### Scope

* add a visible context panel in student chat showing:

  * intake background
  * region
  * interest
  * resolved active career type
  * whether resume is present
* make the first assistant response explicitly acknowledge the selected context
* give student a way to edit/reset context from chat
* improve source display from raw citation badges toward readable provenance

  * source name
  * updated date
* ensure citations prefer active, non-superseded sources
* keep the resume presence visible so students can tell what influenced the first answer

### Why third

The current chat already shows a lightweight `Advising on` chip, but that is not enough for your stated goal of visible context state.

### Acceptance criteria

* student can see the full active context influencing the conversation
* student can tell whether their intake choices actually shaped the chat
* answers show readable source name and updated date, not raw filename chips
* students can edit or reset context from the chat surface itself
* no citation or retrieval path surfaces superseded content as current

### Sprint 3 test requirements

* add a regression test that renders the visible context panel with background, region, interest, resolved career type, and resume presence
* cover the first assistant response so it explicitly acknowledges the selected context in plain English
* cover edit and reset behavior so the chat can return to a clean idle state without a full page refresh
* cover the new provenance rendering so citations show readable source information instead of only raw filenames
* assert that active sources are preferred and superseded sources do not appear as current student citations

### Sprint 2 impact on Sprint 3

Sprint 2 already shipped the trust-model plumbing that Sprint 3 can reuse:

* active/superseded lifecycle semantics
* readable provenance summaries and audit/history links
* source timestamps carried through review and publish flows

Sprint 3 should focus on surfacing that trust model to students and making the current context visibly editable, without reworking the counselor workflow again.

---

## ~~Sprint 4 — Retrieval-policy cleanup and trust instrumentation~~ ✓ Done

Shipped: source-ledger-backed retrieval filtering, active-only citations in student chat, admin source-state summary metrics, stale-source detection, and ledger-aware document inventory.

Goal: make the architecture behave consistently with the product promise.

See the working spec in [sprint_4_spec.md](./sprint_4_spec.md).

### Scope

* codify retrieval rules around superseded documents
* add retrieval filtering based on source lifecycle state
* add admin observability for:

  * active vs superseded source counts
  * retrieval hits by active status
  * stale source detection
* implement lightweight checks to detect when old Qdrant chunks are still eligible after a source has been superseded
* tighten the contract between YAML entities and source ledger entries

### Why fourth

This makes the backend trustworthy after the UI/workflow model is established.

### Acceptance criteria

* retrieval does not return superseded content in normal student flows
* admin can inspect whether active knowledge is backed by current sources
* Qdrant’s role is now bounded and explainable: support layer, not truth layer

---

# The resulting sprint sequence in plain English

1. **Define and implement what “active” and “superseded” mean**
2. **Turn counsellor updates into a review-and-publish workflow**
3. **Expose full visible context and readable provenance in student chat**
4. **Align retrieval behavior and observability with the trust model**

---

# What I would not include in this sprint cycle

Per your direction:

* auth hardening
* session timeout handling
* optimistic locking

I would also avoid a major admin IA restructure for now, since you explicitly want to defer that.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | 1 architecture issue, 1 test gap, 0 performance issues |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**UNRESOLVED:** 0
**VERDICT:** Sprint 1 is done. Sprint 2 scope is trimmed and ready to implement, but the full replace/review/publish regression should be added before coding.

## NOT in scope

* auth hardening, because Sprint 2 is about workflow, not access control.
* session timeout handling, because it is a separate reliability task.
* optimistic locking, because it is a broader concurrency problem than this sprint needs.

## What already exists

* `KnowledgeUpdateTab` already handles review, edit, commit, source timestamps, and success/error states.
* `EmployerFactsTab` already handles active/superseded lifecycle, provenance, history links, and undo on soft delete.
* Track Builder already has a publish/rollback workflow, so Sprint 2 should not rebuild a second publishing model.
