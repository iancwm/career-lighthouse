# Design Spec: Counsellor Knowledge Publishing Workflow

## Objective
Re-engineer the admin experience into a session-based, card-driven, diff-first publishing workflow that allows counsellors to process unstructured research notes into structured updates across multiple domains (Tracks, Employers) simultaneously.

## Core Concepts
1. **Publishing Session:** A discrete, persistent workspace initiated by a raw research note or file upload. 
2. **Intent Extraction:** The backend analyzes input and identifies multiple intents (e.g., "Update McKinsey employer facts" AND "Update Consulting track sentiment").
3. **Card-Based Diff System:** Each intent is rendered as a standalone review card.
4. **Resilience:** Sessions are persisted to the backend to survive browser refreshes.

## Architectural Changes

### 1. Backend Session Management
- **Persistence:** New `KnowledgeSession` model (file-based journal) storing `raw_input`, `status`, `intent_cards`, and `created_by`.
- **API Flow:**
    - `POST /api/sessions` (Create session with raw input)
    - `GET /api/sessions/{session_id}` (Retrieve session state)
    - `POST /api/sessions/{session_id}/analyze` (Extract intents and generate diff cards)
    - `POST /api/sessions/{session_id}/cards/{card_id}/commit` (Commit individual card diff)

### 2. Frontend UX
- **Landing Page:** A "Session Inbox" listing all active sessions by timestamp.
- **Session View (Smart Canvas):** 
    - Left Column: A scrollable sequence of "Analysis Cards."
    - Right Column: A persistent "Diff View" that updates based on the card currently selected.
    - Research Note Alignment: Selecting a card highlights the relevant section in the original raw input.
- **Resilience:** If the user closes the tab, they return to their active session(s) in the Inbox.

### 3. Review Logic
- **Card-based:** Each card displays a specific domain diff (Employer vs Track).
- **Sequential commit:** User processes and commits cards one by one.
- **Session Completion:** A session is complete when all cards are committed or discarded.

## Observability
- Admin dashboard tab: "Active Publishing Sessions"
- Metadata: `session_id`, `counsellor`, `created_at`, `remaining_intents_count`.

## Implementation Strategy
1. **Backend:** Implement session storage (file-based journal) and intent-based analysis.
2. **Frontend:** Build the "Session Inbox" page and the "Smart Canvas" sequence.
3. **Robustness:** Add session recovery on tab load.
