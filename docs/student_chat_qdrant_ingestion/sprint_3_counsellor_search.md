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

## API design

### New router: `api/routers/insights_router.py`

```python
from fastapi import APIRouter, Depends
from dependencies import get_student_insight_store, get_embedder, require_admin_key

router = APIRouter(prefix="/api/insights", dependencies=[Depends(require_admin_key)])
```

**Auth:** This router uses `Depends(require_admin_key)` — same pattern as `api/routers/kb_router.py` and `api/routers/session_router.py`. All search endpoints are admin-protected. Student-facing chat has no access to this router.

Register this router in `api/main.py` alongside the other routers.

### Endpoint

```
POST /api/insights/student-questions/search
```

### Request body

| Field | Type | Notes |
|-------|------|-------|
| `query` | `str` | Counsellor's natural-language search query |
| `date_from` | `str \| None` | ISO 8601 date; filter results on or after this date |
| `date_to` | `str \| None` | ISO 8601 date; filter results on or before this date |
| `career_type` | `str \| None` | Career track slug to filter on `active_career_type` |
| `background` | `str \| None` | Filter on `background` field (only useful if stored) |
| `region` | `str \| None` | Filter on `region` field (only useful if stored) |
| `top_k` | `int \| None` | Number of results; defaults to `settings.student_chat_top_k_default` |

### Response

```json
{
  "results": [
    {
      "message_id": "...",
      "text": "...",
      "timestamp": "...",
      "active_career_type": "...",
      "background": "...",
      "region": "...",
      "score": 0.87,
      "source_label": "Student chat"
    }
  ],
  "total_returned": 5,
  "filters_applied": {
    "career_type": "software_engineering",
    "date_from": null,
    "date_to": null
  }
}
```

### Embedding the counsellor query

The search endpoint must embed the counsellor's query using the same `Embedder` instance from `get_embedder()`. This is the same model used to embed student messages in Sprint 2. Mismatched embedding models will produce incorrect similarity scores.

```python
@router.post("/student-questions/search")
def search_student_questions(
    req: StudentQuestionSearchRequest,
    insight_store: StudentChatInsightStore = Depends(get_student_insight_store),
    embedder: Embedder = Depends(get_embedder),
):
    query_vector = embedder.encode(req.query)  # encode(), not embed() — see api/services/embedder.py:56
    results = insight_store.search(
        vector=query_vector,
        top_k=req.top_k or settings.student_chat_top_k_default,
        filters=build_filters(req),
    )
    return StudentQuestionSearchResponse(...)
```

> **Embedder model dependency:** If the embedding model ever changes (e.g., `model.yaml` updated), all existing indexed messages become incompatible with new query vectors. The collection must be re-indexed. Add a comment in the insights router noting this dependency.

### Filter behavior

Use Qdrant metadata filters where available:

- `date_from` / `date_to` → filter on `timestamp` field
- `career_type` → match on `active_career_type` field
- `background` → match on `background` field (graceful if not stored)
- `region` → match on `region` field (graceful if not stored)

If an intake field was not stored (because the config flag was `False` at index time), the filter for that field returns no additional restriction and the endpoint documents this gracefully. Do not error.

### Filter construction

`build_filters()` is a module-level helper in `api/routers/insights_router.py`. Use the same Qdrant filter imports as `api/services/vector_store.py:15-18`:

```python
from qdrant_client.models import Filter, FieldCondition, MatchValue, DatetimeRange

def build_filters(req: StudentQuestionSearchRequest) -> Filter | None:
    must = []
    if req.career_type:
        must.append(FieldCondition(key="active_career_type", match=MatchValue(value=req.career_type)))
    # Only filter on optional intake fields if the store flag was True at index time.
    # Records indexed when the flag was False will have that field as None — filtering by
    # exact match would silently exclude them from results.
    if req.background and settings.student_chat_store_background:
        must.append(FieldCondition(key="background", match=MatchValue(value=req.background)))
    if req.region and settings.student_chat_store_region:
        must.append(FieldCondition(key="region", match=MatchValue(value=req.region)))
    if req.date_from or req.date_to:
        # DatetimeRange accepts ISO 8601 strings and parses them.
        # Do NOT use Range here — Range only works on numeric payloads.
        must.append(FieldCondition(
            key="timestamp",
            range=DatetimeRange(gte=req.date_from, lte=req.date_to)
        ))
    return Filter(must=must) if must else None
```

**Note:** `DatetimeRange` (not `Range`) is required for timestamp filtering. `Range` only works on numeric payloads and will throw if given ISO strings. `DatetimeRange` auto-parses RFC3339/ISO 8601 strings.

---

## Pydantic models (`api/models_insights.py`)

```python
class StudentQuestionSearchRequest(BaseModel):
    query: str
    date_from: str | None = None
    date_to: str | None = None
    career_type: str | None = None
    background: str | None = None
    region: str | None = None
    top_k: int | None = None

class StudentQuestionResult(BaseModel):
    message_id: str
    text: str
    timestamp: str
    active_career_type: str | None = None
    background: str | None = None
    region: str | None = None
    score: float
    source_label: str = "Student chat"

class StudentQuestionSearchResponse(BaseModel):
    results: list[StudentQuestionResult]
    total_returned: int
    filters_applied: dict
```

---

## Frontend design

### Placement

New component: `web/components/admin/StudentInsightsTab.tsx`

In `AdminWorkspace.tsx` and `ToolsDrawer.tsx`, the full list of touch points (verified from the actual source):

1. **`web/components/admin/ToolsDrawer.tsx:6`** — Add `"student-insights"` to the `DrawerSurface` type union.
2. **`web/components/admin/ToolsDrawer.tsx:DRAWER_ITEMS`** — Add an entry: `{ id: "student-insights", label: "Student Insights", purpose: "Search what students have been asking.", provenance: "Source: student chat · Last updated: live" }`.
3. **`web/components/admin/AdminWorkspace.tsx:DRAWER_SURFACES`** — Add `"student-insights"` to the array.
4. **`web/components/admin/AdminWorkspace.tsx:VIEW_ORDER`** — Add `{ id: "student-insights", label: "Student Insights", description: "Semantically search recent student questions." }`.
5. **`web/components/admin/AdminWorkspace.tsx:isDrawerView`** — Add `value === "student-insights"` to the type guard condition.
6. **`web/components/admin/AdminWorkspace.tsx:DIRECTIVE_BANNERS`** — Add a `"student-insights"` entry with appropriate label, whatYouDo, and whatHappens strings.
7. **`web/components/admin/AdminWorkspace.tsx`** — Add import: `import StudentInsightsTab from "@/components/admin/StudentInsightsTab"`
8. **`web/components/admin/AdminWorkspace.tsx` render block** — Add:
   ```tsx
   {view === "student-insights" && <StudentInsightsTab />}
   ```

### UI elements

**Search input:**
- Placeholder: `"Search what students have been asking…"`

**Optional filters:**
- Date range (date_from, date_to)
- Career track (career_type)
- Background (background) — hidden or disabled if `student_chat_store_background=False`
- Region (region) — hidden or disabled if `student_chat_store_region=False`

**Result cards:**
- Student question text
- Asked date (`timestamp`)
- Active career type chip (if present)
- Similarity score (optional, low visual prominence)
- Label: `Source: Student chat`

### States

| State | Behavior |
|-------|----------|
| Idle (no query submitted) | Explain what the feature does |
| Loading | Spinner/skeleton |
| Empty results | "No student questions matched your search." |
| Backend error | "Search failed. Try again." |
| Feature disabled (`student_chat_insights_enabled=False`) | Show disabled state with explanation |

---

## Implementation tasks

### Backend

1. Add `StudentQuestionSearchRequest`, `StudentQuestionResult`, `StudentQuestionSearchResponse` Pydantic models.
2. Add `search()` method to `StudentChatInsightStore`:
   - Accepts query vector, top_k, and metadata filters
   - Searches the insight collection only (not the KB collection)
   - Copy the `.search()` / `.query_points()` compat shim from `VectorStore.search()` at `api/services/vector_store.py:86-99` — the embedded Qdrant client uses `.query_points()`, the server client uses `.search()`
3. Add `api/routers/insights_router.py` with `POST /api/insights/student-questions/search`:
   - Protected by `Depends(require_admin_key)`
   - Embeds the counsellor query using `Depends(get_embedder)`
   - Calls `StudentChatInsightStore.search()`
4. Register `insights_router` in `api/main.py`.
5. Normalize returned payloads for UI consumption (handle missing optional fields gracefully).

### Frontend

6. Create `web/components/admin/StudentInsightsTab.tsx` with search form and result cards.
7. Add form state, filter controls, and submission handler.
8. Call `POST /api/insights/student-questions/search` and render results.
9. Implement all four UI states (idle, loading, empty, error).
10. Add the tab to `AdminWorkspace.tsx` following the pattern described above.

### Tests

**Test isolation pattern:** Use `app.dependency_overrides` to inject a mock `StudentChatInsightStore` — same pattern as `get_vector_store` in existing tests:
```python
mock_insight_store = MagicMock()
app.dependency_overrides[dependencies.get_student_insight_store] = lambda: mock_insight_store
```
This prevents backend tests from requiring a live Qdrant instance. Do NOT use `lru_cache.cache_clear()`.

11. Backend: `POST /api/insights/student-questions/search` without a valid `X-Admin-Key` header returns `401`.
12. Backend: search endpoint returns semantically relevant results for related queries.
13. Backend: `career_type` filter restricts results.
14. Backend: `date_from` / `date_to` filter restricts results.
15. Backend: empty collection returns empty results array, not an error.
16. Backend: `student_chat_insights_enabled=False` — returns safe not-enabled response or `404`.
17. Backend: results with missing optional fields (`background=None`, `region=None`) return those as `null`, not an error.
18. Frontend: idle state renders without errors.
19. Frontend: loading state renders spinner/skeleton.
20. Frontend: results state renders result cards with correct fields.
21. Frontend: error state renders error message.
22. Frontend: filter fields serialize correctly to the request body.

---

## Acceptance criteria

- Counsellor can submit a semantic search query from the admin UI.
- Backend returns semantically matched student questions from the dedicated insight collection only.
- Results can be filtered by at least `date_from/date_to` and `active_career_type`.
- Results are clearly labeled `Source: Student chat`.
- Empty and error states are handled cleanly.
- The endpoint is protected by `require_admin_key` — student-facing surfaces have no access.
- Counsellor query is embedded using the same `Embedder` as the indexed messages.

---

## Test cases

- `POST /api/insights/student-questions/search` returns semantically relevant results for related phrasings.
- Filtering by `career_type` restricts results to matching records.
- Filtering by `date_from/date_to` restricts results to the specified range.
- Empty dataset returns `{"results": [], "total_returned": 0}`, not an error.
- `student_chat_insights_enabled=False` → safe disabled response (or 404).
- Student-facing `POST /api/chat` has no access to `POST /api/insights/*` (no shared route, no shared service path).
- Missing optional fields (`background`, `region`) in stored records are returned as `null`, not an error.

---

## Recommended implementation order

1. Pydantic models for request/response
2. `StudentChatInsightStore.search()` method
3. `api/routers/insights_router.py` endpoint + register in `main.py`
4. Backend tests (search, filters, empty state, auth)
5. `StudentInsightsTab.tsx` component
6. `AdminWorkspace.tsx` integration (import, nav item, render block)
7. Frontend tests (states, filter serialization)

---

## Definition of done (Sprints 1–3)

By the end of Sprint 3:

- Student messages are flowing into a dedicated Qdrant collection.
- The collection is clearly separated from KB retrieval at config, service, and API levels.
- Counsellors can semantically search what students have been asking from the admin UI.
- The feature has explicit privacy guardrails (no resume text, no assistant messages, no student-facing access).
- No new canonical knowledge system has been introduced.
