# Plan: Sprint 4 Finalization: Dynamic Track Integration

## Objective
Finalize the "Track Publishing Workflow" (Sprint 4) by making the student UI dynamically consume newly published tracks from the registry, rather than using hardcoded lists.

## Background & Motivation
Sprint 4 introduced the ability for counsellors to create, edit, and publish career tracks (e.g., Data Science). While the admin UI and backend registry are largely functional, the student-facing onboarding (`IntakeFlow.tsx`) and advisor labels (`ChatInterface.tsx`) are still using hardcoded arrays. This means a newly published track is not discoverable by students through the guided entry flow.

## Implementation Steps

### Task 1: Add Dynamic Tracks Public API
- **Endpoint:** `GET /api/tracks`
- **Location:** `api/routers/chat_router.py` (student-facing)
- **Model:** `list[TrackRegistryEntry]`
- **Logic:** Call `TrackDraftStore().list_registry()` and filter for `status == "active"`.
- **Why:** Allows the student UI to fetch the authoritative list of available guidance tracks.

### Task 2: Update Student Onboarding (IntakeFlow.tsx)
- **Action:** Replace hardcoded `INTERESTS` array with data fetched from `GET /api/tracks`.
- **Logic:**
  - Fetch tracks on mount.
  - Map `slug` to `value` and `label` to `label`.
  - Append a "Not sure / Other" option to the end.
- **Why:** Newly published tracks automatically appear as options in the student intake flow.

### Task 3: Update Advisor Label (ChatInterface.tsx)
- **Action:** Replace hardcoded `CAREER_TYPE_LABELS` with a dynamic mapping.
- **Logic:**
  - Fetch tracks to build a local map of `slug -> label`.
  - Use this map to display the "Advising on: <Label>" badge correctly for any published track.
- **Why:** Correct branding/labeling for newly created fields like `dsai`.

### Task 4: Verify Integration
- **Action:** Publish a new dummy track (or use existing `dsai`) and verify it appears in the student UI.
- **Tooling:** Use `gstack browse` to walk through the student onboarding flow.
- **Tests:** Add a basic integration test in `test_chat_router.py` for the new `/api/tracks` endpoint.

## Verification & Testing
- **API:** `curl http://localhost:8000/api/tracks` should return the registry list.
- **Frontend:** `IntakeFlow.tsx` should render buttons for all active tracks from the registry.
- **Flow:** Selecting a newly published track should set the `active_career_type` correctly in the subsequent chat.
