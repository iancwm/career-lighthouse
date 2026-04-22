# Sprint 3 — Counsellor semantic search over student questions

## Sprint goal

Give counsellors a backend endpoint and admin UI surface to semantically search student questions stored in the dedicated Qdrant insight collection.

## Why this sprint exists

This is the first visible product value from the epic. It lets counsellors ask:

- What students are asking about interviews
- What worries are surfacing about international hiring
- What recent concerns relate to a specific career track

This matches the proposed use for Qdrant and leverages the data created in Sprint 2.

---

## In scope

- Create counsellor-only search endpoint over student-chat insight collection
- Support semantic query + metadata filtering
- Add admin UI for entering search prompts and viewing results
- Show human-readable provenance in results
- Support basic empty/error states

## Out of scope

- Clustering/theme summaries
- Saved searches
- Dashboards
- Trendlines
- Direct YAML gap analysis

---

## User story

As a counsellor, I want to semantically search recent student questions so I can understand what students are concerned about without manually reading raw chatlogs.

---

## Proposed API design

### Endpoint

```
POST /api/insights/student-questions/search
```

### Request body

| Field | Type |
|-------|------|
| `query` | `str` |
| `date_from` | `str \| None` |
| `date_to` | `str \| None` |
| `career_type` | `str \| None` |
| `background` | `str \| None` |
| `region` | `str \| None` |
| `top_k` | `int \| None` |

### Response

```
{
  "results": [
    {
      "message_id": str,
      "session_id": str,
      "text": str,
      "timestamp": str,
      "active_career_type": str,
      "background": str,        // if available
      "region": str,            // if available
      "score": float,
      "source_label": "Student chat"
    }
  ],
  "total_returned": int,
  "filters_applied": {...}
}
```

### Filter behavior

Use metadata filters where available:

- Date range
- Active career type
- Background
- Region

If some intake metadata was not stored because config disallowed it, the endpoint should handle that gracefully and document the omission.

---

## Proposed UI design

### Placement

Do not create a wholly separate app surface. Add this as:

- Either a new counsellor insight panel under an existing admin area, or
- A contained new tab in the current admin workspace

Use the existing admin workspace structure rather than inventing another shell.

### UI elements

**Search input:**
- Placeholder: `"Search what students have been asking…"`

**Optional filters:**
- Date range
- Career track
- Background
- Region

**Result cards:**
- Student question text
- Asked date
- Active career type chip (if present)
- Metadata row
- Similarity score (optional, low prominence)
- Label: `Source: Student chat`

### States

| State | Behavior |
|-------|----------|
| Idle | Explain what the feature does |
| Loading | Spinner/skeleton |
| Empty results | Empty state message |
| Backend error | Error state message |

---

## Suggested implementation tasks

### Backend

1. Add Pydantic request/response models for student-question search.
2. Add search method to student-chat insight service:
   - Embed counsellor query
   - Search in dedicated collection
   - Apply metadata filters
3. Add new router endpoint under `/api/insights/...`
4. Normalize returned payloads for UI consumption.

### Frontend

5. Add admin component for student-question search.
6. Add form state and filter controls.
7. Call new endpoint and render results.
8. Show readable provenance:
   - Source = `Student chat`
   - Updated/asked date = timestamp

### Tests

9. Backend tests for semantic search endpoint.
10. Backend tests for filters.
11. Frontend tests for idle/loading/results/error states.
12. Frontend test for filter serialization.

---

## Proposed acceptance criteria

- Counsellor can submit a semantic search query from the admin UI.
- Backend returns semantically matched student questions from the dedicated collection.
- Results can be filtered by at least date range and active career type.
- Results are clearly labeled as student-chat insight, not official knowledge.
- Empty and error states are handled cleanly.

---

## Test cases

- Search returns relevant results for similar phrasings.
- Filter by career type restricts results.
- Filter by date range restricts results.
- Empty dataset returns empty state, not error.
- Disabled feature flag returns safe not-enabled response or hides UI.
- Student-facing surfaces have no access to this endpoint.

---

## Coding-agent spec prompt

Implement counsellor-only semantic search over the dedicated student-chat Qdrant collection. Add a backend endpoint for searching student questions with filters for date range and career type at minimum, plus background/region when available. Add an admin UI surface inside the existing admin workspace to submit searches and render result cards with readable provenance ("Student chat", asked date, active career type). This feature must not affect student-facing chat retrieval or YAML knowledge behavior. Add backend and frontend tests for search, filters, and UI states.

---

## Recommended implementation order

1. Backend search models and endpoint
2. Service search method
3. Admin UI component
4. Filters
5. UI states
6. Tests

---

## Definition of done (Sprints 1–3)

By the end of Sprint 3:

- Student messages are flowing into a dedicated Qdrant collection.
- The collection is clearly separated from KB retrieval.
- Counsellors can semantically search what students have been asking.
- The feature has explicit privacy guardrails.
- No new canonical knowledge system has been introduced.
