# Sprint 2 — Index student messages from the chat flow

## Sprint goal

Write eligible student messages into the dedicated Qdrant student-chat insight collection during normal `/api/chat` execution, without affecting user-facing chat reliability.

## Why this sprint exists

Once Sprint 1 defines the contract, the next step is to produce data automatically from real usage. The repo's current chat flow already:

- Resolves `active_career_type`
- Accepts transient intake context
- Logs query activity non-fatally

This sprint extends that behavior with safe semantic indexing.

---

## In scope

- Index student messages after successful `/api/chat` responses
- Embed the student message text
- Attach allowed metadata
- Make indexing failure non-fatal
- Add structured logs for insight write success/failure
- Add integration tests around chat + indexing behavior

## Out of scope

- Counsellor search endpoints
- UI
- Theme clustering
- Retention/cleanup
- Bulk backfill from existing JSONL logs

---

## User story

As the system, I need to capture student questions into a dedicated semantic-retrieval layer so that counsellors can later explore what students have been asking without manual tagging or extraction.

---

## Write-path behavior

### Trigger point

After a successful `/api/chat` response is generated, write the student message only into the student-chat insight collection.

**Reason:**

- Do not index failed or rejected requests
- Keep insight records aligned with real user interactions
- Keep indexing non-blocking in spirit even if implemented synchronously at first

### Indexed text

Use:
- `req.message`

Do not use:
- `resume_text` (blocked; `has_resume=bool(req.resume_text)` is the only resume signal)
- Assistant response text
- Full conversation transcript in v1

### Metadata source

| Payload field | Source |
|---|---|
| `message_id` | `uuid4` generated at index time in `StudentChatInsightStore.index_message()` |
| `timestamp` | Server-side UTC at time of indexing |
| `active_career_type` | Resolved value returned by `_resolve_career_type(...)` (same value returned in `ChatResponse`) |
| `background/region/interest` | From `req.intake_context` only if config flags allow |
| `has_resume` | `bool(req.resume_text)` |

### Failure semantics

If indexing fails:

- Log warning/error with collection name and any available `message_id`
- Do not fail the chat request
- Do not change chat response payload

This mirrors the repo's existing non-fatal query logging in `_log_query()`.

### Thread-pool safety constraint

> **SYNC ONLY.** `chat()` is a `sync def` — FastAPI runs it in a thread pool. The insight write must be synchronous (no `await`, no `asyncio`). This mirrors the existing `_log_query()` pattern (see the comment in `chat_router.py`: "this is a blocking file write. Safe because chat() is a sync def...").
>
> **If `chat()` is ever refactored to `async def`:** move the insight write to `run_in_executor` or a background task. This is a known risk.
>
> Add this comment at the top of `chat()` to make the constraint visible:
> ```python
> # SYNC ONLY: StudentChatInsightStore.index_message() and _log_query() are blocking —
> # thread-pool safe as long as this remains sync def.
> ```

---

## Placement in `api/routers/chat_router.py`

```python
# After this line:
response_text = llm.chat_with_context(...)

# Before this line:
return ChatResponse(response=response_text, ...)

# Add:
if settings.student_chat_insights_enabled:
    if len(req.message) >= settings.student_chat_embedding_min_chars:
        try:
            insight_store = get_student_insight_store()
            insight_store.index_message(   # synchronous call, no await
                text=req.message,
                embedder=embedder,         # inject via Depends(get_embedder)
                active_career_type=active_career_type,
                intake_context=req.intake_context,
                has_resume=bool(req.resume_text),
            )
            logger.info(
                "student insight indexed",
                extra={"collection": settings.student_chat_collection_name},
            )
        except Exception as e:
            logger.warning(
                "student insight write failed: %s",
                e,
                extra={"collection": settings.student_chat_collection_name},
            )
```

The `embedder` parameter is already available in the `chat()` function signature (it uses `Depends(get_embedder)`). No new dependency is needed.

---

## Suggested implementation tasks

### Backend integration

1. Import `get_student_insight_store` and `settings` in `chat_router.py`.
2. After `response_text` is produced and before returning, add the insight write block above.
3. Feature-flag and min-chars gate must both pass before any write is attempted.
4. Add the thread-pool safety comment at the top of `chat()`.

### Logging/observability

5. Structured log lines:
   - `INFO` on successful index (collection name, message_id if available)
   - `WARNING` on failure (collection name, exception message)
6. Never log `text`, `resume_text`, or intake fields in log lines.

### Tests

**Test isolation pattern:** Override `get_student_insight_store` via `app.dependency_overrides` — same pattern as `get_vector_store` in existing tests:
```python
mock_insight_store = MagicMock()
app.dependency_overrides[dependencies.get_student_insight_store] = lambda: mock_insight_store
```
This prevents tests from hitting a real Qdrant instance. Do NOT use `lru_cache.cache_clear()`.

7. Integration test: successful `POST /api/chat` with `student_chat_insights_enabled=True` triggers exactly one call to `StudentChatInsightStore.index_message`.
8. Integration test: `student_chat_insights_enabled=False` — no calls to `index_message`.
9. Integration test: message shorter than `student_chat_embedding_min_chars` — no call to `index_message`.
10. Integration test: `index_message` raises an exception — `POST /api/chat` still returns `200` with a valid response.
11. Integration test: stored payload has `has_resume=True` when `resume_text` is non-empty, but `text` contains only `req.message`, not the resume.
12. Integration test: `active_career_type` in stored payload matches `active_career_type` in `ChatResponse`.
12a. Integration test: `POST /api/chat` with no `intake_context` and `student_chat_store_background=True` — call succeeds (no `AttributeError`), background in stored payload is `None`.

---

## Suggested code touchpoints

- `api/routers/chat_router.py` — add insight write block
- `api/services/student_chat_insights.py` — `index_message()` implementation (Sprint 1 scaffold)
- `api/dependencies.py` — `get_student_insight_store()` (Sprint 1 scaffold)
- `api/config.py` — `student_chat_insights_enabled`, `student_chat_embedding_min_chars` (Sprint 1 scaffold)
- `api/tests/test_chat_router.py` or new `api/tests/test_student_insight_integration.py`

---

## Acceptance criteria

- Successful `/api/chat` requests write one student-message insight record when `student_chat_insights_enabled=True`.
- Indexed content includes `text` (message only) and approved metadata. No resume text. No assistant text.
- Indexing failure does not change chat success/failure behavior or response payload.
- No resume text is stored (only `has_resume` flag).
- No assistant text is stored.
- The write call is synchronous, matching the `_log_query()` pattern.

---

## Test cases

- `POST /api/chat` with `student_chat_insights_enabled=True` → exactly one `index_message` call.
- `POST /api/chat` with `student_chat_insights_enabled=False` → zero `index_message` calls.
- `POST /api/chat` with message `"hi"` (below `student_chat_embedding_min_chars`) → zero `index_message` calls.
- `POST /api/chat` with `resume_text` present → stored payload has `has_resume=True`, no resume text in `text` field.
- `index_message` raises → normal `ChatResponse` returned with `200`, warning logged.
- Intake fields (`background`, `region`, `interest`) appear in stored payload only if the corresponding config flag is `True`.
- `active_career_type` stored in payload equals the value returned in `ChatResponse.active_career_type`.

---

## Recommended implementation order

1. Import and inject `get_student_insight_store` in `chat_router.py`
2. Add feature-flag and min-chars gates
3. Add insight write call (synchronous)
4. Add thread-pool safety comment at top of `chat()`
5. Add structured log lines
6. Integration tests
