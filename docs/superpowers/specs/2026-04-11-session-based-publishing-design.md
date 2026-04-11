# Design Spec: Session-Based Publishing Workflow (Implementation)

## Objective
Re-engineer the admin experience into a session-based, card-driven, diff-first publishing workflow that allows counsellors to process unstructured research notes into structured updates across multiple domains (Tracks, Employers) simultaneously.

## Core Concepts
1. **Publishing Session:** A discrete, persistent workspace initiated by a raw research note or file upload.
2. **Intent Extraction:** The backend analyzes input and identifies multiple intents (e.g., "Update McKinsey employer facts" AND "Update Consulting track sentiment").
3. **Card-Based Diff System:** Each intent is rendered as a standalone review card.
4. **Resilience:** Sessions are persisted to the backend to survive browser refreshes.

## Current State (as of 2026-04-11)

### Already Implemented
- `KnowledgeSession` Pydantic model (`api/models.py`) — all fields present
- `IntentCard` and `MultiIntentAnalysisResult` models (`api/models.py`)
- `SessionStore` singleton (`api/services/session_store.py`) — file-based JSON persistence, atomic writes
- `POST /api/sessions` — creates session (buggy: accepts `raw_input` as query param, not body)
- `GET /api/sessions/{session_id}` — works correctly with 404 handling
- `POST /api/sessions/{session_id}/analyze` — stub endpoint, returns placeholder with no logic

### Not Yet Implemented
- LLM-based intent extraction (`analyze` endpoint logic)
- `POST /api/sessions/{session_id}/cards/{card_id}/commit` — endpoint does not exist
- Session status transitions (stays `"in-progress"` forever)
- Frontend: Session Inbox, Smart Canvas, admin tab integration
- Tests for session endpoints (zero coverage)

---

## Implementation Design

### 1. Backend — Intent Extraction & Card Commit

#### 1.1 Fix `POST /api/sessions`
- Change `raw_input: str` parameter to accept a Pydantic request body:
  ```python
  class CreateSessionRequest(BaseModel):
      raw_input: str
      counsellor_id: str = "counsellor"
  ```
- Pass `counsellor_id` through to `SessionStore.create_session()`.

#### 1.2 Implement `POST /api/sessions/{session_id}/analyze`
**File:** `api/routers/session_router.py`

**Flow:**
1. Retrieve session from `SessionStore`. Return 404 if not found.
2. Call `generate_session_intents(raw_input, existing_knowledge_context)` in `api/services/llm.py`.
3. LLM prompt sends the raw input + current career profile summaries + employer summaries to Claude, asking it to extract distinct intents as structured JSON.
4. Validate returned JSON against `IntentCard[]` model.
5. Store cards on the session: `session.intent_cards = cards`.
6. Transition status: `"in-progress"` → `"analyzed"`.
7. Persist via `SessionStore.save_session(session)`.
8. Return `MultiIntentAnalysisResult(session_id, cards, already_covered)`.

**`already_covered` field:** The LLM may determine that parts of the raw input are already reflected in existing knowledge (no changes needed). These are returned as `AlreadyCovered` items — informational only, no card is generated for them. Displayed in the Smart Canvas as a separate "Already Covered" section below the cards.

**LLM function:** `generate_session_intents()` in `api/services/llm.py`
- Reuses existing `get_llm_response()` pattern (same Claude model as `/api/kb/analyse`)
- System prompt: "You are a knowledge assistant. Given a counsellor's raw research notes, extract distinct update intents. Each intent targets ONE domain (track or employer). Return JSON."
- Response schema enforced via prompt + `model_validate` fallback.
- On malformed response, retry once with error feedback.

#### 1.3 Implement `POST /api/sessions/{session_id}/cards/{card_id}/commit`
**File:** `api/routers/session_router.py`

**Flow:**
1. Retrieve session from `SessionStore`. Return 404 if not found.
2. Find card by `card_id` in `session.intent_cards`. Return 404 if not found.
3. If card already committed/discarded, return 409.
4. Dispatch based on `card.domain`:
   - `"track"` → Update career profile YAML. Parse `card.diff` to extract field changes. Apply via `CareerProfileStore` (similar pattern to existing `commit-analysis` profile_updates path in `kb_router.py`).
   - `"employer"` → Update employer YAML. Apply via `EmployerEntityStore` (similar to existing `commit-analysis` employer_updates path).
5. Invalidate relevant caches (profile store `invalidate()`, health cache).
6. Mark card as `"committed"` on the session.
7. Check if ALL cards are `"committed"` or `"discarded"` → transition session status to `"completed"`.
8. Persist session.
9. Return `{ card_id, domain, status: "committed", message }`.

**Card discard (alternative to commit):** Add `POST /api/sessions/{session_id}/cards/{card_id}/discard` — marks card as `"discarded"` without writing anything, same completion check.

#### 1.4 Session Status State Machine
```
in-progress → analyzed   (after successful /analyze)
analyzed    → completed  (when all cards committed/discarded)
```
No rollback from completed — a new session would be needed for further changes.

#### 1.5 Request/Response Models (additions to `api/models.py`)
```python
class CreateSessionRequest(BaseModel):
    raw_input: str
    counsellor_id: str = "counsellor"

class CardCommitResponse(BaseModel):
    card_id: str
    domain: str
    status: str  # "committed" | "discarded"
    message: str

class CardDiscardResponse(BaseModel):
    card_id: str
    status: str = "discarded"
```

### 2. Frontend — Session Inbox + Smart Canvas

#### 2.1 Session Inbox Page
**File:** `web/components/admin/SessionInbox.tsx`

- Lists all non-completed sessions sorted by `updated_at`
- Each row: created_at timestamp, counsellor_id, status badge, remaining intents count
- "New Session" button → opens a textarea modal for raw input → calls `POST /api/sessions` → navigates to the Smart Canvas
- Auto-refresh on mount (poll every 30s for active sessions)
- Empty state: "No active sessions. Start one by pasting research notes."

#### 2.2 Smart Canvas
**File:** `web/components/admin/SmartCanvas.tsx`

**Two-column layout** (responsive: stacks on mobile):

**Left Column — Analysis Cards:**
- Scrollable list, one card per `IntentCard`
- Each card shows: domain badge (Employer/Track), entity name (extracted from summary), summary text, status pill (pending / committed / discarded)
- Clicking a card sets `selectedCardId` and updates the right column
- Already-committed/discarded cards are shown in muted styling

**Right Column — Persistent Diff View:**
- Shows `card.diff` (structured dict of field → proposed_value) as editable form fields
- Each key in `card.diff` renders as a labeled input/textarea with the proposed value pre-filled
- Counsellor can edit values before committing (e.g., tweak EP sponsorship text)
- "Commit" button → calls `POST /api/sessions/{id}/cards/{card_id}/commit` → updates card status → refreshes session
- "Discard" button → calls `POST /api/sessions/{id}/cards/{card_id}/discard` → marks card discarded
- If no card is selected, shows the session's `raw_input` for reference

**Research Note Alignment:**
- Each `IntentCard` has a `raw_input_ref` field (the original text excerpt that triggered this intent)
- When a card is selected, display the relevant raw input excerpt above the diff for context

**Session Completion Banner:**
- When all cards are processed, show a "Session Complete" banner with option to return to inbox or start a new session

#### 2.3 Route Integration
**File:** `web/app/admin/page.tsx`

- Add "Sessions" tab to the admin tab navigation
- Tab renders `SessionInbox` by default, or `SmartCanvas` when a session is selected
- URL pattern: `/admin` (inbox) → click session → `/admin?session={id}` (canvas)
- Existing "Review Updates" tab (`KnowledgeUpdateTab`) remains as the monolithic analyse/commit flow — sessions are a parallel, more granular workflow

#### 2.4 Resilience
- All state lives on the backend (`SessionStore` JSON files)
- Browser refresh → re-fetch session from `GET /api/sessions/{id}` → restore card states
- Browser close → session remains on server, visible in inbox on return
- No client-side `localStorage` needed — the backend is the source of truth

### 3. Observability + Testing

#### 3.1 Active Sessions Widget
Add a small count to the admin dashboard header or as a subtle badge on the "Sessions" tab: "N active session(s)".

#### 3.2 Tests
| File | Coverage |
|------|----------|
| `api/tests/test_session_store.py` | Unit: create, save, get, list, atomic writes, missing file handling |
| `api/tests/test_session_router.py` | Integration: create session, analyze (mocked LLM), commit card, discard card, 404s, 409s |
| `api/tests/test_session_intents.py` | Unit: `generate_session_intents()` with mocked Claude responses, malformed retry |
| `web/components/admin/__tests__/SessionInbox.test.tsx` | Render, list, click-through, empty state |
| `web/components/admin/__tests__/SmartCanvas.test.tsx` | Card selection, diff display, commit/discard flow, completion banner |

### 4. Out of Scope (Deferred)
- Session cleanup cron job (delete completed >30 days old) — TODOS.md item, separate PR
- Counsellor RBAC (real auth instead of string `counsellor_id`) — TODOS.md item, system-wide auth strategy
- FastAPI-level auth guards on session endpoints — TODOS.md item, depends on broader auth strategy
- File upload support for session creation (text only in v1)

---

## API Endpoint Summary

| Method | Endpoint | Status | Description |
|--------|----------|--------|-------------|
| POST | `/api/sessions` | Fix | Accept JSON body `CreateSessionRequest`, return 201 `KnowledgeSession` |
| GET | `/api/sessions/{id}` | Done | Retrieve session state (already works) |
| POST | `/api/sessions/{id}/analyze` | Implement | LLM intent extraction → cards on session, status → `"analyzed"` |
| POST | `/api/sessions/{id}/cards/{card_id}/commit` | New | Apply card diff to YAML, mark card committed, check completion |
| POST | `/api/sessions/{id}/cards/{card_id}/discard` | New | Mark card discarded, check completion |

## File Changes Summary

### Backend (new/modified)
| File | Change |
|------|--------|
| `api/models.py` | Add `CreateSessionRequest`, `CardCommitResponse`, `CardDiscardResponse` |
| `api/services/llm.py` | Add `generate_session_intents()` function |
| `api/services/session_store.py` | Add `counsellor_id` param to `create_session` |
| `api/routers/session_router.py` | Fix POST body, implement analyze + commit + discard endpoints |
| `api/routers/__init__.py` | Export `session_router` (currently missing) |

### Frontend (new)
| File | Change |
|------|--------|
| `web/components/admin/SessionInbox.tsx` | New component — session list + new session button |
| `web/components/admin/SmartCanvas.tsx` | New component — card list + diff view + commit/discard |
| `web/app/admin/page.tsx` | Add "Sessions" tab, wire to components |

### Tests (new)
| File | Change |
|------|--------|
| `api/tests/test_session_store.py` | Unit tests for SessionStore |
| `api/tests/test_session_router.py` | Integration tests for session endpoints |
| `api/tests/test_session_intents.py` | Unit tests for LLM intent extraction |
| `web/components/admin/__tests__/SessionInbox.test.tsx` | Frontend tests |
| `web/components/admin/__tests__/SmartCanvas.test.tsx` | Frontend tests |
