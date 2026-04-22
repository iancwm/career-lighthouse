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

## Technical design

### Collection separation

Add a new insight domain alongside the existing knowledge collection:

- **knowledge Qdrant collection** (`kb_cfg["storage"]["collection"]`): uploaded source docs for chat grounding
- **student insight Qdrant collection** (`settings.student_chat_collection_name`): counsellor-only semantic retrieval over student messages

These must be separate at the config, service, and API levels. The insight collection is never queried by the student-facing chat path.

### Config additions (`api/config.py` Settings class)

Add to the `Settings` class:

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `student_chat_insights_enabled` | `bool` | `False` | Feature toggle; entire write path is skipped when false |
| `student_chat_collection_name` | `str` | `"student_chat_insights"` | Qdrant collection name |
| `student_chat_top_k_default` | `int` | `10` | Default result count for counsellor search (Sprint 3) |
| `student_chat_embedding_min_chars` | `int` | `20` | Messages shorter than this are not indexed |
| `student_chat_store_background` | `bool` | `False` | Allow storing `background` field from intake context |
| `student_chat_store_region` | `bool` | `False` | Allow storing `region` field from intake context |
| `student_chat_store_interest` | `bool` | `False` | Allow storing `interest` field from intake context |

The `store_background/region/interest` flags control gradual rollout of optional student context fields. Defaulting to `False` means only career-type and resume-presence are captured until explicitly enabled via environment variable.

### Payload schema

Each point in the student insight collection has this payload:

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `message_id` | `str` | `uuid4` generated at index time | Index artifact stored in Qdrant metadata; not present in `ChatRequest`. Allows linking search results back to the original message. |
| `timestamp` | `str` | Server-side UTC ISO 8601 | Set at index time, not from client |
| `role` | `"user"` | Literal constant | Always `"user"` in v1 |
| `text` | `str` | `req.message` | Student message text |
| `active_career_type` | `str \| None` | Resolved from chat flow | Career track slug |
| `background` | `str \| None` | `req.intake_context.background` | Only stored if `student_chat_store_background=True` |
| `region` | `str \| None` | `req.intake_context.region` | Only stored if `student_chat_store_region=True` |
| `interest` | `str \| None` | `req.intake_context.interest` | Only stored if `student_chat_store_interest=True` |
| `has_resume` | `bool` | `bool(req.resume_text)` | Presence flag only; resume text is never stored |
| `source_channel` | `"student_chat"` | Literal constant | Marks this as a student chat insight |
| `schema_version` | `int` | `1` | For future migration compatibility |

**Do not store:**
- Resume text (any form)
- Assistant replies
- `session_id` (dropped from v1; no source in current `ChatRequest` model)
- Full raw intake payload unless specifically allowed by config flag

### Service: `api/services/student_chat_insights.py`

Create `StudentChatInsightStore`. This service:

- **Composes `VectorStore`** internally for upserts and collection bootstrapping — `VectorStore.__init__(client, collection)` accepts any collection name, so `StudentChatInsightStore` wraps `VectorStore(client, collection=settings.student_chat_collection_name)`. This avoids duplicating Qdrant client code.
- **Uses `VectorStore` only for upserts and `ensure_collection()`**. All search/retrieval is custom code in `StudentChatInsightStore` (never routed through the KB `VectorStore` instance).
- Does not share any code path with student-facing retrieval.

Key methods:

```python
class StudentChatInsightStore:
    def __init__(self, client: QdrantClient):
        self._store = VectorStore(client=client, collection=settings.student_chat_collection_name)

    def ensure_collection(self, dim: int) -> None:
        """Idempotent. Safe to call on every app startup."""
        self._store.ensure_collection(dim=dim)

    def index_message(
        self,
        text: str,
        embedder: Embedder,
        active_career_type: str | None,
        intake_context: IntakeContext | None,
        has_resume: bool,
    ) -> str:
        """Build payload, embed text, upsert to insight collection. Returns message_id.

        Pass message_id as p["id"] in the upsert call — VectorStore.upsert() applies
        _to_uuid() internally (see api/services/vector_store.py:69), so the raw uuid4
        string is the correct value to pass.
        """
        ...

    def build_payload(
        self,
        text: str,
        active_career_type: str | None,
        intake_context: IntakeContext | None,
        has_resume: bool,
    ) -> StudentChatInsightPayload:
        """Apply privacy gates. Called by index_message and by tests."""
        ...
```

### Dependency injection (new in `api/dependencies.py`)

```python
@lru_cache
def get_student_insight_store() -> StudentChatInsightStore:
    client = get_qdrant_client()   # reuses the cached Qdrant client
    store = StudentChatInsightStore(client=client)
    store.ensure_collection(dim=model_cfg["embedding"]["dim"])  # idempotent
    return store
```

`model_cfg` is already imported in `dependencies.py` (same source used by `get_vector_store()`). This follows the existing pattern exactly: service created, collection bootstrapped, then cached for the app lifetime. The knowledge collection and the insight collection are bootstrapped independently.

### Typed models (`api/models_insights.py`)

```python
class StudentChatInsightPayload(BaseModel):
    message_id: str
    timestamp: str
    role: Literal["user"] = "user"
    text: str
    active_career_type: str | None = None
    background: str | None = None
    region: str | None = None
    interest: str | None = None
    has_resume: bool
    source_channel: Literal["student_chat"] = "student_chat"
    schema_version: int = 1

```

---

## Implementation tasks

### Backend

1. Add config settings entries for student chat insights (7 fields above).
   **Note:** `api/config.py` defines `Settings` twice — once as a pydantic `BaseSettings` subclass and once as a fallback `@dataclass` (lines 63–103) for lightweight test envs. Add all 7 fields to **both** classes.
2. Add typed model `StudentChatInsightPayload` in `api/models_insights.py`.
3. Create `api/services/student_chat_insights.py` with `StudentChatInsightStore`:
   - `ensure_collection(dim)`
   - `index_message(text, embedder, active_career_type, intake_context, has_resume) -> str`
   - `build_payload(...) -> StudentChatInsightPayload`
4. Add `get_student_insight_store()` to `api/dependencies.py` following the `get_vector_store()` pattern.
5. Add code comments in the service clarifying:
   - This collection is not canonical knowledge
   - This collection is never queried by student-facing chat

### Documentation

6. Update this spec to reflect APPROVED decisions (done).
7. Add inline comments in `student_chat_insights.py` that document the privacy rules and non-goals.

### Tests

8. Unit test: `build_payload` includes `message_id`, `text`, `timestamp`, `source_channel`.
9. Unit test: `build_payload` never includes resume text even when `has_resume=True`.
10. Unit test: `background/region/interest` only appear in payload when config flags are `True`.
11. Unit test: `background/region/interest` are `None` in payload when config flags are `False`.
11a. Unit test: `build_payload` with `intake_context=None` and all store flags `True` — background/region/interest are `None`, no `AttributeError`. (Guards against crash when store flags are enabled but chat requests lack intake context.)
12. Unit test: feature-toggle `student_chat_insights_enabled=False` — no collection bootstrap, no write.

---

## Acceptance criteria

- There is a dedicated student-chat insight collection config and service.
- The insight payload schema is typed and tested.
- Resume text cannot enter the payload.
- `session_id` is not in the schema (dropped from v1).
- `message_id` is generated server-side as `uuid4` at index time.
- Assistant messages are not part of the design contract.
- Documentation clearly states this collection is counsellor-only and non-canonical.
- `get_student_insight_store()` follows the existing `get_vector_store()` pattern in `dependencies.py`.

---

## Test cases

- Payload contains `message_id` (uuid4 format), `text`, `timestamp`, `source_channel="student_chat"`.
- Payload omits resume text even when `resume_text` is present in request (only `has_resume=True`).
- Payload includes `background/region/interest` only when the corresponding config flag is `True`.
- Payload excludes `background/region/interest` when config flags are `False` (default).
- `build_payload` with `intake_context=None` and store flags `True` — background/region/interest are `None`, no `AttributeError`.
- `ensure_collection()` succeeds with current embedding dimensions.
- `ensure_collection()` is idempotent — safe to call twice with the same dim.
- Feature-toggle disabled path does not call `ensure_collection()` or write.

---

## Recommended implementation order

1. Config (7 new fields in `Settings`, both classes)
2. Typed model (`StudentChatInsightPayload` in `api/models_insights.py`)
3. Service scaffold (`StudentChatInsightStore` with `ensure_collection` and `build_payload`)
4. Dependency injection (`get_student_insight_store` in `dependencies.py`)
5. Tests (payload construction, privacy gates, feature-toggle)
6. Docstring clarifications
