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

- `resume_text`
- Assistant response text
- Full conversation transcript in v1

### Metadata source

Use fields already available in the request/flow:

- `timestamp` = server-side current UTC
- `active_career_type` = resolved value returned by `_resolve_career_type(...)`
- Intake-derived fields only if config allows and request has them
- `has_resume` = `bool(req.resume_text)`

### Failure semantics

If indexing fails:

- Log warning/error
- Do not fail the chat request
- Do not change chat response payload

This mirrors the repo's current non-fatal query logging philosophy.

---

## Suggested implementation tasks

### Backend integration

1. Inject or instantiate the student-chat insight service in the chat router path.
2. After `response_text` is produced and before returning, attempt an insight write.
3. Pass:
   - Student message text
   - Resolved career type
   - Allowed intake metadata
   - Resume-presence flag
   - Timestamp
4. Ensure write is skipped if feature flag is disabled.
5. Ensure write is skipped for empty/short messages below configured min chars.

### Logging/observability

6. Add structured log lines:
   - Indexing attempted
   - Indexing succeeded
   - Indexing failed
7. Include collection name and message id/session id where available.

### Tests

8. Integration test: successful chat triggers one student insight write.
9. Integration test: indexing disabled causes no writes.
10. Integration test: indexing failure does not fail `/api/chat`.
11. Integration test: stored payload excludes resume text.

---

## Suggested code touchpoints

Likely areas:

- `api/routers/chat_router.py`
- New service in `api/services/`
- `config.py` or equivalent settings surface
- Tests for chat router and service integration

---

## Proposed acceptance criteria

- Successful `/api/chat` requests write one student-message insight record when enabled.
- Indexed content includes message text and approved metadata only.
- Indexing failure does not change chat success/failure behavior.
- No resume text is stored.
- No assistant text is stored.

---

## Test cases

- `POST /api/chat` with enabled insights writes exactly one point.
- `POST /api/chat` with disabled insights writes none.
- `POST /api/chat` with `resume_text` still stores only `has_resume=true`.
- Indexing exception returns normal chat response to caller.
- Intake fields appear only if allowed by config.
- Active career type stored matches returned `active_career_type`.

---

## Coding-agent spec prompt

Extend the `/api/chat` flow so that each successful student message is embedded and written to the dedicated student-chat Qdrant collection created in Sprint 1. Store only the student message text and approved metadata. Do not store resume text or assistant responses. Writes must be feature-flagged and non-fatal: if indexing fails, chat must still succeed. Add integration tests around enabled, disabled, and failed-write behavior.

---

## Recommended implementation order

1. Integrate service into chat router
2. Add feature-flag checks
3. Add non-fatal failure handling
4. Add logs
5. Integration tests
