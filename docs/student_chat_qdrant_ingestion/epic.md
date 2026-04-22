# Epic: Qdrant for counsellor insight over student demand

## What this epic is

Right now, every student question disappears after the chat response is sent. The system logs query activity for KB health, but nothing captures what students are actually asking in a form that counsellors can explore.

This epic adds a dedicated semantic memory layer for student messages — separate from the canonical YAML knowledge base and invisible to student-facing retrieval — so that counsellors can ask questions like:

- What are students worried about regarding international hiring?
- What questions keep coming up for students on the software track?
- What concerns surfaced in the last two weeks?

The answer is not a dashboard or a report. It is a counsellor-facing semantic search over real student questions, powered by a dedicated Qdrant collection that is built up automatically as students chat.

---

## Why a dedicated collection

The system already uses Qdrant for document chunk storage — uploaded source docs that ground student-facing chat responses. That collection is canonical knowledge. It must remain clean.

Student questions are a different kind of signal. They are demand-side: what students need, worry about, and cannot find answers to. Mixing them into the knowledge collection would contaminate retrieval quality and blur the line between what the system knows and what students are asking.

The architectural choice here is deliberate: **two collections, two purposes, zero crossover**.

| Collection | Purpose | Readable by |
|---|---|---|
| Knowledge (existing) | Source docs for student chat grounding | Student-facing chat |
| Student insight (new) | Semantic index of student questions | Counsellors only |

---

## Guardrails that apply across the entire epic

These constraints are not negotiable and apply in every sprint:

- YAML remains canonical for career intelligence. The new collection does not replace or supplement it.
- Student-chat Qdrant data is counsellor-insight only. No student-facing path may query it.
- Resume text is never indexed, in any form.
- Assistant messages are out of scope for indexing in v1.
- Auth hardening, timeout handling, and optimistic locking are out of scope for this cycle.

---

## The three sprints

### Sprint 1 — Define and scaffold the collection

**[→ Full spec](sprint_1_scaffold.md)**

Before writing a single message, the system needs a clean contract. Sprint 1 establishes:

- A dedicated Qdrant collection config, separate from KB config
- A typed payload schema with explicit privacy gates (resume text blocked, intake fields gated by config flags)
- A service layer (`StudentChatInsightStore`) with no shared code paths to KB retrieval
- Feature toggle defaulting to disabled
- Unit tests for payload construction and privacy rules

Nothing flows into Qdrant at the end of this sprint. The foundation is laid and tested.

---

### Sprint 2 — Index messages from the live chat flow

**[→ Full spec](sprint_2_indexing.md)**

Sprint 2 turns the scaffold into a live write path. After each successful `/api/chat` response, the student's message is embedded and upserted into the insight collection.

Key design choices:

- **Post-response only**: indexing happens after the chat succeeds, so failed or rejected requests are never indexed
- **Non-fatal**: if indexing throws, the chat response is unaffected — the failure is logged and swallowed
- **Feature-flagged**: the entire write path is skipped when `student_chat_insights_enabled` is false
- **Min-length gate**: very short messages (below `student_chat_embedding_min_chars`) are skipped

At the end of Sprint 2, student messages are accumulating in the dedicated collection in the background, and counsellors have a growing corpus to search.

---

### Sprint 3 — Counsellor semantic search

**[→ Full spec](sprint_3_counsellor_search.md)**

Sprint 3 is where the data becomes useful. A new endpoint (`POST /api/insights/student-questions/search`) lets counsellors submit a natural-language query and receive semantically matched student questions, filterable by date range, career type, background, and region.

The endpoint is paired with a new admin UI panel — added inside the existing admin workspace, not as a separate app — with result cards that clearly label each result as `Source: Student chat` to prevent confusion with official knowledge content.

Empty states, error states, and disabled-feature states are all handled explicitly.

---

## How the sprints connect

```
Sprint 1                Sprint 2                Sprint 3
─────────────────       ─────────────────       ─────────────────
Define what gets        Wire the write path      Expose the data
stored and how          into /api/chat           to counsellors

Config + models    →    Embed + upsert      →    Search + filter
Service scaffold        on every success         Admin UI
Privacy gates           Non-fatal writes         Result provenance
Tests                   Integration tests        Backend + UI tests
```

Sprint 2 depends on Sprint 1's service and schema being in place. Sprint 3 depends on Sprint 2 having produced real data and confirmed the collection structure. The sprints are strictly ordered.

---

## Definition of done

The epic is complete when:

- Student messages are flowing automatically into a dedicated Qdrant collection
- The collection is provably separate from KB retrieval at config, service, and API levels
- Counsellors can semantically search what students have been asking from the admin UI
- Privacy guardrails are enforced by code and tested
- No new canonical knowledge system has been introduced
