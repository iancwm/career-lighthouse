# Sprint 1 — Define and scaffold the student-chat insight collection

## Sprint goal

Create the architectural foundation for indexing student chat questions into a dedicated Qdrant collection that is fully separated from canonical YAML knowledge and from student-facing retrieval.

## Why this sprint exists

Right now the repo already:

- logs student queries to JSONL for KB health
- uses Qdrant for document chunk storage/retrieval
- treats intake context as transient and non-persistent

Before adding any write path, the system needs a clean contract for:

- what gets indexed
- what metadata is allowed
- what collection it goes into
- what is explicitly forbidden

---

## Shared guardrails (apply across Sprints 1–3)

- YAML remains canonical for career intelligence.
- Student-chat Qdrant data is counsellor-insight only.
- Student-facing chat must never retrieve from the student-chat collection.
- Resume text must not be indexed into the student-chat insight collection.
- Assistant messages are out of scope for indexing in v1.
- Auth hardening is out of scope for this cycle.
- Timeout handling is out of scope for this cycle.
- Optimistic locking is out of scope for this cycle.

---

## In scope

- Define a dedicated Qdrant collection for student chat insight
- Define the metadata schema for indexed chat records
- Add config for the new collection and feature toggle
- Create service-layer scaffolding for indexing
- Create typed models for insight records
- Document privacy/retention boundaries in code and docs
- Ensure no student-facing path can accidentally use this collection

## Out of scope

- Actual indexing from `/api/chat`
- Counsellor search UI
- Clustering/theme detection
- Retention jobs
- Analytics dashboards

---

## User story

As a product engineer, I need a dedicated and clearly bounded storage model for student chat insight so that future semantic search features cannot contaminate canonical knowledge or student-facing retrieval.

---

## Technical design target

### New conceptual layer

Add a new insight domain:

- **knowledge Qdrant collection**: uploaded source docs for chat grounding
- **student insight Qdrant collection**: counsellor-only semantic retrieval over student messages

These must be separate at the config, service, and API levels.

### Proposed new config

Add to config/YAML or settings model:

| Key | Type |
|-----|------|
| `student_chat_insights_enabled` | `bool` |
| `student_chat_collection_name` | `str` |
| `student_chat_top_k_default` | `int` |
| `student_chat_embedding_min_chars` | `int` |
| `student_chat_store_background` | `bool` |
| `student_chat_store_region` | `bool` |
| `student_chat_store_interest` | `bool` |

**Default stance:**

- `enabled: false` in initial config until wired
- `store_background` / `store_region` / `store_interest`: `false` unless explicitly approved by config

### Proposed indexed payload schema

Each point in the new collection should include:

| Field | Type | Notes |
|-------|------|-------|
| `message_id` | `str` | |
| `session_id` | `str \| None` | |
| `timestamp` | `str` | |
| `role` | `"user"` | always literal |
| `text` | `str` | student message text |
| `active_career_type` | `str \| None` | |
| `background` | `str \| None` | only if allowed by config |
| `region` | `str \| None` | only if allowed by config |
| `interest` | `str \| None` | only if allowed by config |
| `has_resume` | `bool` | |
| `source_channel` | `"student_chat"` | always literal |
| `schema_version` | `int` | |

**Do not store:**

- Resume text
- Assistant replies
- Full raw intake payload unless specifically allowed by config
- Any canonical knowledge references as if this were source-of-truth content

### Proposed service boundaries

Create a dedicated service, for example:

```
api/services/student_chat_insights.py
```

Responsibilities:

- Create/ensure collection
- Build payload from chat request context
- Upsert points into Qdrant
- Expose collection-specific search methods later

Avoid reusing generic KB vector-store methods if that would blur the separation.

---

## Suggested implementation tasks

### Backend

1. Add config/settings entries for student chat insights.
2. Add typed models:
   - `StudentChatInsightRecord`
   - `StudentChatInsightPayload`
3. Add a dedicated service: `StudentChatInsightStore` or similar.
4. Add collection bootstrap logic:
   - Ensure collection exists
   - Verify vector size matches embedder output
5. Add payload builder with privacy gates:
   - Redacts/excludes disallowed fields
6. Add code comments and docstrings clarifying:
   - Not canonical knowledge
   - Not used for student answer retrieval

### Documentation

7. Add a short ADR or markdown note covering:
   - Purpose
   - Scope
   - Privacy rules
   - Non-goals

### Tests

8. Unit tests for payload-building rules.
9. Unit tests that resume text is never present.
10. Unit tests for config-gated intake-field persistence.

---

## Proposed acceptance criteria

- There is a dedicated student-chat insight collection config and service.
- The insight payload schema is typed and tested.
- Resume text cannot enter the payload.
- Assistant messages are not part of the design contract.
- Documentation clearly states that this collection is counsellor-only and non-canonical.

---

## Test cases

- Payload contains message text, timestamp, career type, source channel.
- Payload omits resume text even when `resume_text` is present in request.
- Payload includes background/region/interest only when enabled in config.
- Collection bootstrap succeeds with current embedding dimensions.
- Feature-toggle disabled path does not initialize or write.

---

## Coding-agent spec prompt

Build the student-chat insight storage foundation. Add config, typed models, and a dedicated Qdrant-backed service for counsellor-only semantic retrieval over student messages. The service must be strictly separate from canonical KB retrieval. Resume text must never be stored. Assistant messages are out of scope. Add tests covering payload construction, privacy gates, and feature-toggle behavior.

---

## Recommended implementation order

1. Config
2. Typed models
3. Service scaffold
4. Collection bootstrap
5. Tests
6. Docs
