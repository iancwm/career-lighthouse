# Implementation Plan: Counsellor Knowledge Publishing Workflow

## Objective
Implement a session-based, card-driven, diff-first publishing workflow for counsellor knowledge management.

## Architecture
Use a file-backed `KnowledgeSession` store to persist raw researcher notes and analyze them into separate, domain-specific review cards (Track vs. Employer).

## Implementation Steps

### Task 1: Backend Session Engine
- [ ] **Task 1: Session Storage:** Create `api/services/session_store.py` for file-based session persistence in `logs/sessions/`.
- [ ] **Task 2: API Endpoints:** Implement `POST /api/sessions`, `GET /api/sessions/{id}`, `POST /api/sessions/{id}/analyze`, and `POST /api/sessions/{id}/cards/{card_id}/commit` in `api/routers/session_router.py`.
- [ ] **Task 3: Analysis Pipeline:** Extend existing LLM analysis logic to return multiple intent cards (Employer vs. Track) instead of a single diff.

### Task 2: Frontend Publishing UX
- [ ] **Task 4: Research Landing Page:** Create `web/components/admin/ResearchLanding.tsx` with a large input area and active session recovery.
- [ ] **Task 5: Card Review Sequence:** Build a component that iterates through session cards and handles commit/discard states.
- [ ] **Task 6: Admin Dashboard Observability:** Add an "Active Sessions" list to the admin dashboard.

### Task 3: Integration & Testing
- [ ] **Task 7: E2E Verification:** Walk through the full session flow: Paste research → Analyze → Commit multiple cards → Verify knowledge update.
