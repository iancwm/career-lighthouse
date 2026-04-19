# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.1.5.2] - 2026-04-19

### Added
- **LLM hardening sweep**: shared JSON repair, staged extraction, tighter prompt budgets, and richer LLM trace metadata now cover chat, brief, KB analysis, track drafting, session intent extraction, and profile auto-complete.
- **Trace diagnostics**: LLM trace rows now record feature, pre-trim and sent input sizes, KB chunk counts, parse attempts, repair attempts, and partial-result flags so admin traces can explain where a call got expensive or failed.
- **Budget tightening**: session extraction and chunked extraction defaults are now materially smaller, which keeps multi-pass prompts bounded instead of letting a single note balloon into a long call.

### Added
- **Per-endpoint rate limiting**: explicit `@limiter.limit()` decorators on `POST /api/chat` (10/min), `POST /api/ingest` (5/min), and `POST /api/brief` (5/min) to protect Anthropic API quota and Fargate costs. The `slowapi` infrastructure was already wired in `main.py`; these decorators enforce tighter per-endpoint budgets.
- **Session cleanup script**: `scripts/cleanup_sessions.py` deletes `completed` and `cancelled` sessions older than `--days` (default 30). Supports `--dry-run`, `--sessions-dir`, and `SESSIONS_DIR` env var. Handles both flat and counsellor-scoped (`counsellor_id/session_id.json`) directory layouts.
- **Shared field allowlist constants**: `api/constants/profile_fields.py` consolidates `ALLOWED_PROFILE_FIELDS` (15 fields, up from 7 in `kb_router` and 12 in `session_router`) and `ALLOWED_EMPLOYER_FIELDS` (8 fields) into a single source of truth. Added missing fields: `salary_levels`, `visa_pathway_notes`, and `track_name`.
- **Langfuse-backed LLM observability**: optional self-hosted Langfuse profile in Docker Compose, lazy API export when `LANGFUSE_*` env vars are set, and shutdown flush so in-flight traces are not lost.
- **Langfuse session grouping**: `session_id` now propagates through live session analysis, so Langfuse groups traces into session views instead of leaving them as isolated requests.
- **Trace Explorer**: the admin panel now exposes a session-scoped trace explorer with filters for session, operation, and status.
- **Configurable session analysis tuning**: session timeout and multi-pass chunking thresholds are now env-driven, so long notes can be tuned without code changes.
- **Structured LLM lifecycle traces**: trace logging now records `started`, `ok`, and `error` events with session and chunk metadata instead of only failures.
- **Admin observability workflow**: the admin panel now shows live LLM run state, trace history, and stop/retry controls for session analysis.

### Changed
- `just` now includes Langfuse helper recipes for bringing the observability stack up, listing its containers, and tailing its logs.
- Langfuse export now stays off the request path. The API schedules flushes in the background and shuts down cleanly so trace delivery does not become the thing that times out.

### Fixed
- **Structured metadata drift in session card commits**: `_derive_structured_fields()` is now called in `session_router.py _apply_field_updates_to_profile`, so session card commits populate `salary_min_sgd`/`salary_max_sgd` from prose salary ranges, matching the behavior already present in `kb_router.py commit_analysis()`.
- The live API container now picks up the Langfuse instrumentation helper correctly, so session traces actually appear in the self-hosted Langfuse project after rebuilds.

## [0.1.5.1] - 2026-04-14

### Added
- **Config externalization**: all hardcoded thresholds moved to YAML configs (`model.yaml`, `kb.yaml`, `track_guidance.yaml`, `prompts.yaml`) for easier tuning without code changes.
- **Structured LLM prompts**: system prompts for `analyse_kb_input`, `generate_track_draft`, `generate_session_intents` externalized to `prompts.yaml`.
- **Multi-pass extraction support**: large documents (>30k chars) split into chunks for session intent extraction with configurable chunk sizes and overlap.
- **`generate_brief()` function**: pre-meeting brief generator for counselors, combining resume text with KB chunks for actionable talking points.
- **Comprehensive docstrings**: added module-level documentation to all services (`ingestion`, `llm`, `session_store`, `track_guidance`, `vector_store`).

### Changed
- `chunk_text()` now reads default token/overlap values from `kb.yaml` instead of hardcoded parameters.
- `generate_session_intents()` deduplication summary length configurable via `model.yaml`.
- Vector store search defaults to `kb.yaml` `vector_store.default_top_k` instead of hardcoded value.
- Track guidance thresholds (safe update, emerging signals) read from `track_guidance.yaml` instead of hardcoded values.

### Fixed
- Merge conflict in `ingestion.py` resolved (needs both `kb_cfg` import and `sanitize_for_prompt`).

## [0.1.5.0] - 2026-04-12

### Added
- **Trust-first track guidance**: session analysis now carries an explicit uncertainty payload with nearest-track clustering, recurrence-aware escalation, and counselor-facing guidance to check definitions and do their own research before creating new taxonomy.
- **Sessions-first admin workspace**: `/admin` now routes through a URL-driven shell with sessions, Track Builder, Knowledge Update, and employer facts as explicit surfaces instead of a single stateful tab container.
- **Safe student markdown rendering**: assistant replies now render through a dedicated markdown component with a safe subset of formatting and links that open in a new tab.
- **Track Builder published reference view**: published tracks now have a dedicated reference detail contract, plus an archived working-copy banner in the editor.

### Fixed
- **Employer YAML normalization**: scalar `tracks` and `intake_seasons` values are now normalized into lists so legacy employer records do not crash the employers endpoint.
- **Admin back navigation**: route changes now use push navigation so browser back returns cleanly to the inbox instead of falling through history.

## [0.1.4.0] - 2026-04-05

### Added
- **Employer Entity YAML**: fixed-schema YAML files per employer in `knowledge/employers/`. Each file captures EP requirement, intake seasons, headcount estimate, application process, counsellor contact, and notes. Three seed employers included (Goldman Sachs, McKinsey, Meta).
- **`EmployerEntityStore`**: singleton service (mirrors `CareerProfileStore`) that loads employer YAMLs, computes completeness indicators (green/amber), and exposes `to_context_block(active_career_type)` for career-type-filtered LLM injection.
- **Employer CRUD API**: five new endpoints — `GET /api/kb/employers`, `GET /api/kb/employers/{slug}`, `POST /api/kb/employers`, `PUT /api/kb/employers/{slug}`, `DELETE /api/kb/employers/{slug}`. Delete soft-disables by renaming to `.yaml.disabled` (recoverable). Path traversal guard on all slug inputs.
- **Employer context injection in chat**: employer facts injected into every chat response, filtered to the active career type. Injection order: career profile → employer facts → KB chunks, so authoritative YAML data always precedes potentially stale KB chunks.
- **Employer-aware `analyse` flow**: `POST /api/kb/analyse` now passes an employer summary to Claude alongside career profiles. Claude can propose `employer_updates` (field-level supersession) in the analysis result. `ALLOWED_EMPLOYER_FIELDS` allowlist prevents hallucinated field writes on commit.
- **`employer_updates` in `commit-analysis`**: `POST /api/kb/commit-analysis` writes approved employer field changes atomically to YAML. `KBCommitResponse` now includes `employers_updated: list[str]`.
- **Employer Facts admin tab**: new "Employer Facts" tab in the admin dashboard. Master-detail layout — left panel lists employers with completeness dots and inline delete confirmation; right panel is a form editor with pill toggles (tracks), chip/tag input (intake seasons), auto-slug generation, sticky Save, and unsaved-changes warning on employer switch.
- **`employer_updates` diff section in Update Knowledge tab**: counsellor can review and edit proposed employer field changes before committing, same UX pattern as career profile changes. Summary bar shows `+ N employer field(s) updated`.
- **36 new tests**: 15 unit tests for `EmployerEntityStore` (load, invalidate, completeness, context filtering, note truncation) and 21 integration tests for employer CRUD endpoints and commit-analysis employer write path.
- **docker-compose volume mounts**: `./knowledge:/app/knowledge` and `./logs:/app/logs` added to the api service — employer YAMLs and query logs were not persisted across container restarts.

### Fixed
- **Test isolation for query log metrics**: three `TestKBHealthQueryLog` tests now use `datetime.now()` for log timestamps rather than hardcoded dates that fell outside the 7-day window. One test now mocks `settings.query_log_path` to prevent real log file pollution.

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
