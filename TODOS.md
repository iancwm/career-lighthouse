# TODOS

This backlog is ordered by execution priority:
- `Now` = highest-risk gaps before broader launch
- `Next` = important follow-ups once the core security and publishing flows are stable
- `Later` = useful cleanup or scale work that can wait
- `Done` = shipped items kept here for context

## Now

### Rate limiting on public endpoints
**What:** Add `slowapi` middleware to `POST /api/chat`, `POST /api/brief`, `POST /api/ingest` (token-bucket per IP).
**Why:** Unbounded endpoints can exhaust Anthropic API quota or spike Fargate costs.
**Recommended limits:** 10 req/min on `/api/chat`, 5 req/min on `/api/ingest`.
**Depends on:** None. Self-contained FastAPI middleware addition.

### Request timeout on LLM calls
**What:** Set `timeout=30.0` on `anthropic.Anthropic()` client; add FastAPI `BackgroundTasks` for long operations.
**Why:** LLM calls can hang indefinitely if Anthropic is slow, occupying all Uvicorn workers.
**Depends on:** None.

### FastAPI auth on KB endpoints
**What:** Add `Depends()` auth guards to the read and write `/api/kb/*` endpoints.
**Why:** Next.js middleware alone is not enough defense in depth; direct HTTP calls can bypass it.
**Depends on:** The broader API auth strategy.

### ~~Validate profile field names in commit-analysis~~ ✓ Done (2026-04-12)
Shipped: `ALLOWED_PROFILE_FIELDS` enforcement already existed with skip+warn; test coverage added
to lock in the guarantee. `session_router.py` inspected — has parallel `ALLOWED_CARD_PROFILE_FIELDS`
guard. Empty field map returns 200 cleanly.

### Session Cleanup Script
**What:** Delete completed sessions older than 30 days.
**Why:** Prevents `logs/sessions/` from growing forever.
**Depends on:** None.

### Counsellor RBAC
**What:** Replace string `counsellor_id` with real authenticated user context.
**Why:** Session ownership must be enforced, not passed around as an untrusted string.
**Depends on:** Broader auth/user model.

### Basic multi-user edit protection
**What:** Add optimistic locking or version checks on structured KB writes so concurrent counselors do not silently overwrite each other.
**Why:** Last-write-wins breaks trust fast, especially in a small office where two people can edit the same entity in one day.
**Depends on:** Revision metadata on structured facts.

## Next

### ADMIN_KEY passed as query param — migrate to header or cookie
**What:** Replace `?key=...` query param with `Authorization: Bearer` header or session cookie.
**Why:** Query params appear in ALB access logs and browser history, exposing the admin key.
**Depends on:** None. Breaking change for API consumers.

### Sanitize chat prompt injections
**What:** Apply `sanitize_for_prompt()` to career context and employer facts injected into live chat prompts in `llm.py`.
**Why:** Counsellor-authored YAMLs are lower risk but should receive the same treatment as ingested chunks.
**Depends on:** None.

### Session card commit idempotency
**What:** Store `committed: true` on cards and check before writing to prevent duplicate YAML updates on retry.
**Why:** Browser refresh during commit can apply the same card twice, producing duplicate YAML fields.
**Depends on:** None.

### Path to multi-instance scaling
**What:** Replace file-based query log with CloudWatch Logs or SQS; move Qdrant to standalone container; remove `WEB_CONCURRENCY=1`.
**Why:** Single-worker constraint blocks horizontal scaling; file-based log corrupts with multiple writers.
**Depends on:** Infrastructure decision (managed Qdrant vs sidecar).

### Consolidate field allowlists
**What:** Move `ALLOWED_PROFILE_FIELDS` and `ALLOWED_EMPLOYER_FIELDS` to shared constants module.
**Why:** Currently duplicated in `kb_router.py` and `session_router.py`; adding fields to one but not other causes silent divergence.
**Depends on:** None.

### Model name env var override
**What:** Make `model.yaml` model name overridable via env var (e.g., `ANTHROPIC_MODEL`).
**Why:** When Anthropic deprecates a model, requires YAML edit + redeployment currently.
**Depends on:** None.

### list_docs() scroll ceiling — optimize for large KBs
**What:** Switch `VectorStore.list_docs()` from `scroll(limit=10000)` to per-doc `count()` calls, or add a 60s TTL cache in `kb_router.py`.
**Why:** The current scroll is O(n_chunks) and runs on every `GET /api/kb/health` call. Acceptable at < 200 docs; becomes noticeable above that.
**Pros:** Eliminates O(n) scan; health endpoint stays fast as KB grows.
**Cons:** Per-doc `count()` requires one Qdrant call per document. TTL cache adds module-level state.
**Context:** Added during Sprint 1 KB Observability eng review (2026-03-22). The inline `# TODO: cache list_docs()` comment in `kb_router.py` marks the call site.
**Depends on:** None. Self-contained change to `vector_store.py` or `kb_router.py`.

### health_cache thundering herd — check-lock-check pattern
**What:** Replace the current "check outside lock → compute → set under lock" pattern with a proper check-lock-check or "computing" flag.
**Why:** Concurrent health requests can all trigger the 5-second `_compute_overlap_pairs` scan simultaneously.
**Pros:** Limits overlap computation to one in-flight at a time; eliminates duplicate O(n_chunks × Qdrant) scans.
**Cons:** Adds locking complexity; a "computing" sentinel state must be handled gracefully.
**Context:** Found during adversarial review in Ship 2 (2026-03-23). The Lock in `health_cache.py` already prevents data corruption.
**Depends on:** None. Self-contained change to `api/services/health_cache.py` and the `kb_health` endpoint.

### ~~File upload size limit — /api/ingest and /api/kb/analyse~~ ✓ Done (2026-04-12)
Shipped: `Content-Length` pre-read guard on both endpoints (413 if > 10MB). Shared
`settings.max_upload_bytes` in `config.py`. Parametrized tests on both endpoints.

### Stale chunk deprecation on employer entity update
**What:** When an employer entity changes, scan for stale Qdrant chunks and surface them for deletion.
**Why:** YAML is authoritative, but old chunks still retrieve and can confuse the LLM.
**Depends on:** Employer entity CRUD already shipping.

### Restore path for disabled employer entities
**What:** Add an API and UI path to restore `.yaml.disabled` employer records.
**Why:** DELETE currently disables, but there is no restore path without manual filesystem edits.
**Depends on:** Employer entity CRUD.

### Unsaved changes warning — KnowledgeUpdateTab mid-flow navigation
**What:** Warn before leaving KnowledgeUpdateTab while a diff is loaded.
**Why:** Counsellors can lose several seconds of analysis work if they navigate away.
**Depends on:** None. Add when the current pre-launch scale no longer makes silent loss acceptable.

### ~~structured: values diverge from prose field edits after profile editor write~~ ✓ Done (2026-04-12)
Shipped: `_derive_structured_fields()` helper extracts numeric values from prose (e.g. salary
ranges) using `setdefault` to preserve manual entries. Wired into `publish_draft()` and
`commit_analysis()` so both write paths stay in sync. 4 tests cover parsing, K-suffix, TBD,
and manual-value preservation.

### PDPA wording — query digest is not "anonymised aggregates"
**What:** Replace "anonymised aggregates" with "query aggregates" in docs and UI copy.
**Why:** The digest contains raw student query text, which is not anonymised.
**Depends on:** None.

## Later

### SessionInbox empty state copy
**What:** "No active sessions. Create one above." — add brief context about what a session is for (multi-entity memo intake that extracts per-entity update cards) and a warmer tone.
**Why:** Counsellors encountering the empty state for the first time have no orientation. The surrounding heading "New Publishing Session" helps, but the empty list below it is bare.
**Depends on:** None. One-liner copy change in `web/components/admin/SessionInbox.tsx`.

### Re-ingest documents with improved chunking
**What:** Re-upload documents that contain tables or structured data so they get re-chunked with the new semantic-aware strategy.
**Why:** The new chunking strategy only affects new uploads. Existing Qdrant chunks from old word-boundary splitting remain and may still miss table content.
**Depends on:** New chunking strategy shipped (this sprint).

### Replace cosine career type switching with keyword matching
**What:** Use keyword-based career type detection in `CareerProfileStore.match_career_type()`.
**Why:** Cosine similarity against short career-type descriptions is unreliable for conversational questions.
**Depends on:** None.

### Fill in counselor_contact fields in all YAML profiles
**What:** Replace the `[TODO: Fill in SMU career centre contact…]` placeholders in each profile YAML.
**Why:** Placeholder text will leak into prompts if `counselor_contact` is injected later.
**Depends on:** Getting the actual contact details from SMU career centre.

### Employer context token budget — per-career-type filter at >20 employers per track
**What:** Cap the employer context block per track once a single career type gets too many employers.
**Why:** Per-track density, not total count, becomes the token-budget bottleneck.
**Depends on:** Career-type filtered injection shipping in v1.

### Lightweight provenance badges in review surfaces
**What:** Show source and revision provenance on proposed changes and published facts.
**Why:** Counsellors trust changes more when they can see where they came from without opening raw internals.
**Depends on:** Revision history.

### Durable source document ledger
**What:** Persist uploaded source files and tie them to revisions for reprocessing and audit.
**Why:** Raw inputs should remain a durable source of truth, not just an ephemeral upload.
**Depends on:** Document storage layout decision.

### Missing Terraform resources for production deployment
**What:** Define ECS Service, ALB HTTPS listener, target groups, EFS backup policy, WAF, auto-scaling, VPC/subnets/SGs.
**Why:** Current Terraform has task definition but no service to run it, no HTTPS listener, no auto-scaling, no WAF for rate limiting.
**Depends on:** AWS infrastructure design decisions.

## Done

### ~~Config externalization, structured prompts, and briefing utilities~~ ✓ Done (0.1.5.1)
Shipped: hardcoded thresholds moved into YAML configs (`model.yaml`, `kb.yaml`, `track_guidance.yaml`, `prompts.yaml`), system prompts externalized to `prompts.yaml`, large document session extraction now uses multi-pass chunking, `generate_brief()` ships a counselor brief generator, and service docstrings were added across ingestion, LLM, session store, track guidance, and vector store modules.

### ~~Session-first admin workflow and tab guidance~~ ✓ Done (2026-04-12)
Shipped: `/admin` starts in Session Editor, the surrounding tabs now explain their purpose, and the workflow copy makes it clear when counsellors should use Track Builder versus the review surfaces.

### ~~Safe markdown rendering in student replies~~ ✓ Done (2026-04-12)
Shipped: assistant messages now render through a safe markdown subset instead of raw HTML.

### ~~Track Builder published reference, history, and bootstrap refresh~~ ✓ Done (2026-04-12)
Shipped: Track Builder shows the published reference summary, keeps archived working copies separate, and bootstraps a draft from the live published profile when a counsellor refreshes a track that does not yet have a draft file.

### ~~Legacy track slug canonicalization and session migration~~ ✓ Done (2026-04-12)
Shipped: legacy `data_science` aliases normalize to `dsai` on read and write, and old session payloads are rewritten in place.

### ~~Sanitize file.filename at ingest boundary~~ ✓ Done (v0.1.2.1)
`_sanitize_filename()` added to `ingest_router.py`. Allowlist: alphanumeric + `.-_ `. Rejects null bytes, control chars, path separators, shell metacharacters. Returns HTTP 400. 13 parametrized tests cover attack vectors and valid inputs.

### ~~Document structured: YAML block intent~~ ✓ Done (2026-04-12)
The intent is now documented in `api/services/career_profiles.py` and `DESIGN.md`.

### ~~Employer Entity YAML — CRUD API + LLM injection + Admin UI (Sprint 3 Addendum)~~ ✓ Done (v0.1.4.0)
Shipped: `EmployerEntityStore` singleton, `GET/POST/PUT/DELETE /api/kb/employers`, employer context injection in chat, employer-aware `analyse` flow with `ALLOWED_EMPLOYER_FIELDS`, `EmployerFactsTab`, `employer_updates` diff section in `KnowledgeUpdateTab`, 36 new tests, and docker-compose mounts for `knowledge/` and `logs/`.

### ~~KnowledgeUpdateTab — diff-first KB ingestion (Sprint 3 Feature 1)~~ ✓ Done (v0.1.3.0)
Shipped: `POST /api/kb/analyse`, `POST /api/kb/commit-analysis`, KnowledgeUpdateTab, admin tab navigation, content-based chunk idempotency, `delete_by_filename` dedup, and input validation on commit payload.

### ~~Track Builder revision history and rollback~~ ✓ Done (2026-04-12)
Shipped: published track versions are stored under `knowledge/career_profiles_history/`, Track Builder can inspect live published reference data, and rollback restores the previous published version.
