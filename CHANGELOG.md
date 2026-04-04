# Changelog

All notable changes to this project will be documented in this file.

## [0.1.3.0] - 2026-04-04

### Added
- **Knowledge Update tab**: new admin tab ("Update Knowledge") with a diff-first KB ingestion flow — counsellors paste a note or upload a file, review exactly what would change in the knowledge base (new chunks, profile field updates, already-covered content), edit inline, then confirm. Nothing writes to the KB until the counsellor approves.
- **`POST /api/kb/analyse`**: accepts counsellor note text or file upload, retrieves top-10 semantically similar KB chunks, calls Claude to produce a structured diff (`KBAnalysisResult`), and returns it for review — no writes.
- **`POST /api/kb/commit-analysis`**: accepts a counsellor-approved `KBCommitRequest`, upserts new chunks to Qdrant (with `delete_by_filename` dedup for re-submitted files), atomically writes updated YAML fields to career profile files, and invalidates both the health cache and the profile store.
- **Six new Pydantic models**: `ProfileFieldChange`, `NewChunk`, `AlreadyCovered`, `KBAnalysisResult`, `KBCommitRequest`, `KBCommitResponse`.

### Fixed
- **Note chunk_id clobbering**: switched to content-based `uuid5` keys (`source_label::text[:120]`) so distinct notes on the same day accumulate rather than overwrite each other.
- **File dedup on re-commit**: `commit-analysis` now calls `store.delete_by_filename()` before upsert for `source_type="file"`, matching the existing `ingest_router` dedup convention.
- **commit-analysis input validation**: added guards for `source_type`, chunk count (max 10), and chunk text size (max 4000 chars) to prevent oversized or malformed payloads.

## [0.1.2.1] - 2026-04-03

### Added
- **Config externalization**: all hardcoded constants moved to `api/cfg/` YAML files — `model.yaml` (LLM model, embedding dim, history window, prompt templates, school name), `kb.yaml` (Qdrant collection, KB thresholds, log window), `career_profiles.yaml` (match threshold, required fields, intake map). Thin `api/cfg.py` loader exposes them as module-level dicts.
- **`CareerProfileStore.invalidate()`**: resets in-memory profile cache on demand; counsellor-updated YAML files are picked up on next request without API restart.

### Fixed
- **Filename sanitization at ingest boundary**: `_sanitize_filename()` in `ingest_router.py` rejects null bytes, control chars, path separators, and shell metacharacters; allowlist: alphanumeric + `. - _ ` (space); max 255 chars; returns HTTP 400 on violation.
- **Career profile cache after upload**: calling `/api/ingest` now invalidates `CareerProfileStore` so new YAML files written during a session are reflected immediately.

## [0.1.2.0] - 2026-03-25

### Added
- **Guided Entry flow**: new landing screen replaces blank chat box with 4 option cards ("I don't know where to start", "Exploring a specific career", "Understanding the Singapore market", "I have an interview") — addresses primary UX gap for disoriented students
- **Intake flow**: 2-step pill-selection questionnaire (background, region, interest area) that captures career context without storing personal data (PDPA-compliant)
- **Career profile YAML injection**: 5 career profile YAML files (investment_banking, consulting, tech_product, public_sector, general_singapore) loaded at startup and injected into LLM system prompt as structured `=== CAREER CONTEXT ===` blocks; first response now includes specific employers, EP sponsorship levels, COMPASS scores, recruiting timelines, and salary ranges
- **`CareerProfileStore` service**: singleton with startup loading, career type name embeddings for cosine matching, `get_profile()`, `match_career_type()`, and `list_profiles()` methods; gracefully skips malformed or incomplete YAML files with warnings
- **`GET /api/kb/career-profiles`** endpoint: admin endpoint listing loaded profiles with completeness indicators
- **`resolve_career_type_from_intake()`**: rule-based intake-to-career-type mapping (finance → investment_banking, consulting → consulting, tech → tech_product, etc.)
- **`active_career_type` stateless persistence**: server returns resolved career type slug in response; client echoes it on subsequent requests as fallback; cosine similarity match can override at query time
- **Profile badge in chat**: `Advising on: <Career Type>` pill shown in chat header once a career type is active
- **Chat error state**: inline "Something went wrong — please try again." message on API failure; `intake_context` only marked consumed after successful response (not before fetch) so retries correctly re-send career context
- **DESIGN.md**: documents emerging design system (blue-600 primary, gray palette, rounded-xl cards, 44px touch targets, focus:ring-2 focus:ring-blue-400, responsive grid breakpoints)
- **Back navigation**: `← Back` link on intake screen returns to guided entry
- **Test coverage**: full test suite for `CareerProfileStore`, `resolve_career_type_from_intake`, `profile_to_context_block`, chat router career profile integration, and all new frontend components (GuidedEntry, IntakeFlow, ChatInterface career type state + error handling + retry)

### Fixed
- `_load_profiles()` NameError: `career_type_name` undefined at `logger.info()` call — caused misleading "failed to load" warnings for every successfully-loaded profile; fixed to use `profile.get("career_type", slug)`
- `setIntakeConsumed(true)` called before `await fetch()` — on API failure, intake context was permanently consumed and never re-sent on retry; moved to success path only
- `test_career_context_injected_into_llm`: weak `or`-based assertion replaced with direct `assert kwargs.get("career_context") is not None`

### Changed
- Student page header (h1 + subtitle) now hidden after guided_entry state to maximise chat area on mobile
- Guided entry grid: `grid-cols-2` → `grid-cols-1 sm:grid-cols-2` for correct layout at 320px
- Touch targets: pill buttons and skip link bumped to min 44px height
- All interactive buttons now have `focus:outline-none focus:ring-2 focus:ring-blue-400` keyboard focus rings

## [0.1.1.1] - 2026-03-23

### Added
- `KnowledgeUpload` test suite: success, error (non-ok response), similarity warning banner, and `onUploaded` callback coverage

### Fixed
- Ingest router: `prepare_document` now runs before `delete_by_filename`, preventing data loss if embedding fails; empty-document uploads now return `status="error_empty"` instead of silent `chunk_count=0` success
- `DocList`: document deletion now checks the HTTP response before removing the item from the UI; failed deletes no longer silently show the document as gone
- `health_cache`: all reads and writes to module-level globals wrapped in `threading.Lock` to prevent torn writes and race conditions in the thread pool
- `KnowledgeUpload`: upload error responses (non-ok HTTP status) now show a failure message instead of crashing on missing `chunk_count`
- `kb_router`: removed unreachable `len(chunk_points) > 200` sampling condition; added clarifying comment that scroll pagination is deferred

## [0.1.1.0] - 2026-03-23

### Added
- **KB Observability Dashboard** — new admin panel section showing live KB health metrics
- `GET /api/kb/health` endpoint: total docs/chunks, 7-day rolling avg match score, retrieval diversity score, low-confidence query log, doc coverage (good/thin), and overlap pair detection
- `POST /api/kb/test-query` endpoint: test arbitrary queries against the KB with per-chunk similarity scores (admin probe queries are not logged)
- Query logging: every student chat query is appended to `./logs/query_log.jsonl` with timestamp, scores, and matched docs; failures are non-fatal
- Deduplication check on ingest: warns when > 30% of a new document's chunks score ≥ 0.85 against content from an existing document
- Overlap cache (`health_cache.py`): caches expensive overlap pair computation; invalidated on every ingest or delete
- **StatCards** component: 5-stat summary with color thresholds (low score → amber, low diversity → red, high weak query count → red)
- **TestQueryBox** component: inline query tester with color-coded score badges (green ≥ 0.5, amber ≥ 0.35, red < 0.35)
- **DocCoverageList** component: per-document coverage status with good/thin pills and overlap warning badges
- **LowConfidenceLog** component: rolling 7-day list of weak queries with score bar and null/empty state distinction
- **RedundancyPanel** component: overlap pair list with overlap percentage and recommendation text
- FastAPI `lifespan` handler: creates log directory at startup, warns on multi-worker deployments

### Changed
- `ingest_document` refactored into `prepare_document` (parse + chunk + embed → points list) + explicit `store.upsert()` call, enabling pre-storage dedup checks
- `DELETE /api/docs/{doc_id}` now invalidates the overlap cache immediately
- `DocList` component accepts optional `onDeleted` callback; admin page triggers KB Health refresh on document deletion
- `KnowledgeUpload` component shows inline amber warning banner when `similarity_warning` is returned by the ingest API

### Fixed
- Dedup check exception after delete no longer causes silent data loss (wrapped in try/except, document always stored)
- Startup `os.makedirs` wrapped in try/except so read-only filesystem does not crash the API
- `TestQueryBox` now handles non-array 503 responses without throwing `.map is not a function`
- KB Health endpoint no longer unnecessarily initializes the embedding model

## [0.1.0.0] - 2026-03-22

### Added
- Initial release: RAG-powered career advice chat with Qdrant vector store
- Document ingest (PDF, DOCX, TXT), chunk embedding, and similarity search
- Admin dashboard: file upload, document list, brief generator
- FastAPI backend with Anthropic Claude integration
- Next.js frontend with student chat and admin interfaces
- Vitest + pytest test suites
- Docker Compose deployment with Qdrant
