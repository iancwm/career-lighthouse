# Plan: Refactor `api/routers/kb_router.py`

## Objective
Refactor the monolithic `api/routers/kb_router.py` (83KB, ~2000 lines) to improve maintainability, testability, and separation of concerns. This file is currently a single point of failure and mixes business logic, file system operations, and LLM interactions with route handling.

## Key Files & Context
- `api/routers/kb_router.py`: The target file for refactoring.
- `api/services/`: Existing services where logic should be moved.
- `api/main.py`: The entry point where routers are registered.

## Proposed Changes

### 1. Extract Business Logic to Services
- **LLM Observability**: Create `api/services/llm_observability.py` to handle Langfuse observation mapping and LLM trace log reading.
  - Move `_observation_to_trace_entries`, `_read_langfuse_trace_log`, `_read_llm_trace_log` here.
- **KB Ingestion Service**: Create `api/services/kb_ingestion_service.py` to handle analysis and commit logic.
  - Move `analyse` and `commit_analysis` logic here.
  - Extract hardcoded prompts and logic for building profile/employer summaries.
- **KB Health Service**: Create `api/services/kb_health.py` to handle health metrics and overlap analysis.
  - Move `_compute_overlap_pairs` and `kb_health` logic here.
- **Utility Functions**: Move common utilities to `api/services/shared_yaml.py` or a new `api/utils/converters.py`.
  - Move `_coerce_mapping`, `_coerce_sequence`, `_get_value`, `_format_timestamp`, etc.

### 2. Split the Router
Split `kb_router.py` into smaller routers based on functional areas:
- `api/routers/profiles_router.py`: `/career-profiles` endpoints.
- `api/routers/tracks_router.py`: `/tracks` and `/draft-tracks` endpoints.
- `api/routers/employers_router.py`: `/employers` endpoints.
- `api/routers/facts_router.py`: `/facts` endpoints.
- `api/routers/kb_admin_router.py`: Core KB admin endpoints (`/analyse`, `/commit-analysis`, `/test-query`, `/health`, `/llm-traces`).

### 3. Refactor and Clean Up
- Remove inline business logic from route handlers.
- Use dependencies for the new services.
- Move hardcoded LLM prompts to a configuration file or constants within the service.

## Verification & Testing
- **Unit Tests**: Ensure that extracted service logic is covered by unit tests.
- **Integration Tests**: Run existing tests in `api/tests/` (e.g., `test_kb_router.py`, `test_alumni_router.py`, etc.) to ensure no regressions.
- **Manual Verification**: Use the admin dashboard in the web UI to verify that all KB-related features still work as expected.

## Phase 1: Preparation & Utilities
1.  Identify all utility functions in `kb_router.py` and move them to `api/services/shared_yaml.py` or `api/utils/`.
2.  Create `api/services/llm_observability.py` and migrate tracing logic.

## Phase 2: Splitting Routers (Incremental)
1.  Extract `profiles_router.py`.
2.  Extract `employers_router.py`.
3.  Extract `tracks_router.py`.
4.  Extract `facts_router.py`.
5.  Extract `kb_admin_router.py`.

## Phase 3: Service Extraction & Integration
1.  Move KB ingestion logic to `kb_ingestion_service.py`.
2.  Move health logic to `kb_health.py`.
3.  Update `api/main.py` and remove the old `kb_router.py`.
