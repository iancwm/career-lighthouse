**Career Lighthouse is a counsellor-trust system first.**
YAML is the canonical career intelligence layer; Qdrant is supporting retrieval for voluminous source material. Content should be auditable, supersession should be explicit, and students should see a full visible context panel in chat. The next sprint cycle should avoid auth hardening, timeout handling, and optimistic locking for now.

That fits the current codebase well:

* session-first admin workspace already exists 
* student guided entry/intake/chat already exists, but context visibility is still lightweight   
* YAML already acts as editable structured knowledge while Qdrant stores uploaded document chunks 
* your backlog already points toward provenance, stale chunk handling, and durable source management 
* your user notes consistently emphasize traceability, freshness, source visibility, and confidence in what is active 

## What I would do next

I would structure the work into **4 sprints**.

## Sprint 1 — Canonical content lifecycle and supersession model

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

---

## Sprint 3 — Student trust surfaces and visible context panel

Goal: make chat personalization inspectable and credible.

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

### Why third

The current chat already shows a lightweight “Advising on” chip, but that is not enough for your stated goal of visible context state .

### Acceptance criteria

* student can see the full active context influencing the conversation
* student can tell whether their intake choices actually shaped the chat
* answers show readable source + updated information
* no citation or retrieval path surfaces superseded content as current

---

## Sprint 4 — Retrieval-policy cleanup and trust instrumentation

Goal: make the architecture behave consistently with the product promise.

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
