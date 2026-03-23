# Changelog

All notable changes to this project will be documented in this file.

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
