# TODOS

This backlog is ordered by execution priority:
- `Now` = highest-risk gaps before broader launch
- `Next` = important follow-ups once the core security and publishing flows are stable
- `Later` = useful cleanup or scale work that can wait
- `Done` = shipped items kept here for context

## Now

### ~~Structured Facts Phase 2: Complete fact-entry UI (EmployerFactsTab)~~ ✓ Done (2026-04-20)
Shipped: FactEditor component with type-specific field schemas for all 5 fact types; FactCard display component; EmployerFactsTab refactored with Details/Facts tabs; manual fact entry working with UI persistence to YAML.

### ~~UI Clarity Mini-Sprint (items 1–7)~~ ✓ Done (2026-04-24)
Shipped: BriefGenerator removed from Career Wire Documents; Review & Publish renamed and shortened; navigation locked while unsaved employer facts are pending; Profile Repair banner replaced with proper in-progress state; student chat markdown fixed for quote blocks and italics; resume upload moved to first screen; Smart Counsellor docx/txt intake added with heading and action repositioned. Item 8 from the original request remains outstanding.

### ~~Counsellor Trust Sprint 1: Fix FactCard delete button touch target~~ ✓ Done (2026-04-22)
Shipped: delete affordance is now at least 44px on mobile and desktop in `web/components/admin/forms/FactCard.tsx`.

### ~~Counsellor Trust Sprint 1: Remap FactCard type badge colors to DESIGN.md tokens~~ ✓ Done (2026-04-22)
Shipped: fact type badges now use the DESIGN.md palette instead of the old purple/blue Tailwind defaults.

### ~~Counsellor Trust Sprint 1: Fix lifecycle filter in to_context_block() — critical bug~~ ✓ Done (2026-04-22)
Shipped: `api/services/employer_store.py` now filters context blocks to active facts only, so superseded and archived records no longer reach student-facing prompts.

### ~~FastAPI auth on KB endpoints~~ ✓ Done (2026-04-23)
Shipped: `/api/kb/*`, `/api/insights/*`, and `/api/sessions/*` routers already carry `require_admin_key` at the router level, so the KB surfaces are protected in the backend now.

### ~~Counsellor Trust Sprint 1: Split EmployerFactsTab.tsx before provenance wiring~~ ✓ Done (2026-04-22)
Shipped: the employer facts surface now carries the lifecycle/provenance UI directly, with the supporting logic split across smaller shared pieces.

### ~~Counsellor Trust Sprint 1: Extract shared Fact type to web/types/facts.ts~~ ✓ Done (2026-04-22)
Shipped: `web/types/facts.ts` is now the shared source of truth for fact shape, lifecycle, and provenance helpers.

### ~~Counsellor Trust Sprint 1: Extract shared ProvenancePanel component~~ ✓ Done (2026-04-22)
Shipped: provenance now renders through a reusable `ProvenancePanel` with the visible toggle, source metadata, and audit link.

### Structured Facts Phase 2: LLM extraction accuracy testing
**What:** Test extraction end-to-end on real Stripe notes; refine extraction prompt if accuracy < 80%; write 3–5 sample facts via UI (manual + extraction).
**Why:** Extraction endpoint is now fully functional (three bugs fixed 2026-04-20/21: wrong method name, JSON array parsing, repair function signature). Accuracy testing is the remaining gate before Phase 3.
**Depends on:** ExtractedFactsModal, extraction endpoint, llm.extract_facts_from_prose — all implemented and working as of 2026-04-21.

### ~~Structured Facts Phase 3: Build `/api/kb/facts` query endpoint~~ ✓ Done (2026-04-23)
Shipped: `GET /api/kb/facts` and `GET /api/kb/facts/grouped` now load employer and career-profile facts, apply filters for type/employer/school/year/source/confidence, and exclude deleted records by default.

### ~~Counsellor Trust Sprint 1: provenance panel and plain-English tool explainer~~ ✓ Done (2026-04-22)
Shipped: the admin landing cards, employer facts view, and knowledge review diff flow now surface purpose copy plus visible provenance summaries.

### ~~Structured Facts Phase 1 Validation: Stripe pilot + LLM extraction test~~ ✓ Done (2026-04-21)
Shipped: manual facts confirmed writing correctly to employer and career profile YAMLs; full Stripe document uploaded to validate LLM extraction pipeline end-to-end.

### ~~Rate limiting on public endpoints~~ ✓ Done (2026-04-18)
Shipped: explicit `@limiter.limit()` decorators applied to `POST /api/chat` (10/min), `POST /api/ingest`
(5/min), and `POST /api/brief` (5/min). The `slowapi` infrastructure was already wired in `main.py`;
per-endpoint decorators now enforce tighter budgets to protect Anthropic API quota and Fargate costs.

### ~~Admin workspace IA: manifest-driven navigation and workstreams~~ ✓ Done (2026-04-23)
Shipped: `adminNavManifest.ts` defines all tabs/tools declaratively; `AdminWorkspace.tsx` and `ToolsDrawer.tsx` drive routing from the manifest; Playwright config, E2E fixtures, and Vitest config aligned to the new structure.

### ~~Alumni first-class admin workflow~~ ✓ Done (2026-04-23)
Shipped: `api/routers/alumni_router.py` with LLM-backed extraction and CRUD endpoints; `api/services/alumni_store.py` managing alumni YAML files; `AlumniFactsTab.tsx` full admin UI with detection modal, staging, and handoff to SessionInbox; `AlumniDetectionModal.tsx`; test coverage across store and router.

### ~~Facts dashboard: `/api/kb/facts` query endpoint and admin UI~~ ✓ Done (2026-04-24)
Shipped: `api/services/fact_store.py` loads employer and career-profile facts; `GET /api/kb/facts` and `GET /api/kb/facts/grouped` endpoints with type/employer/school/year/source/confidence filters; `FactsDashboardTab.tsx` admin view; 248 lines of new test coverage.

### ~~Admin shell split and session auth hardening~~ ✓ Done (2026-04-24)
Shipped: `AdminWorkspace.tsx` split into shell + `AdminWorkspaceContent.tsx` + `AdminWorkspaceHeader.tsx`; `useAdminWorkspace.ts` hook extracted; `web/app/student/useStudentPage.ts` extracted; E2E fixtures separated into `admin-workspace.fixtures.ts`; code smell docs added in `docs/code_smell_cleanup/`.

### ~~Harden audit paths and same-origin proxies~~ ✓ Done (2026-04-24)
Shipped: `web/lib/api-proxy.ts` and both Next.js route handlers hardened against path traversal and SSRF; session timeout propagated; alumni, chat, insights, and KB routers patched with traversal guards; career profile and service docstrings added.

### ~~Backend utility consolidation (Sprint 2)~~ ✓ Done (2026-04-25)
Shipped: 8 copy-pasted helper families consolidated into `api/services/shared_yaml.py` — `atomic_yaml_write`, `version_stamp`, `safe_slug_is_valid`, `safe_int`, `safe_float`, `fact_payload`, `fact_lifecycle`. Private copies removed from `employer_store`, `source_ledger`, `track_drafts`, `kb_router`, `alumni_router`, and `alumni_store`. Duplicate `_normalize_profile_payload` deleted from `alumni_router`. `SourceLedgerStore._latest_query_hits` moved to module level. `scripts/validate_profiles.py` sys.path surgery removed. 276 backend tests green.

### ~~Student Chat Insights Sprint 1: Scaffold the insight collection~~ ✓ Done (2026-04-24)
**What:** Add 7 config fields to `api/config.py` (both the `BaseSettings` class and the fallback `@dataclass`), create `StudentChatInsightPayload` in `api/models_insights.py`, implement `StudentChatInsightStore` in `api/services/student_chat_insights.py` (`ensure_collection`, `index_message`, `build_payload`), and register `get_student_insight_store()` in `api/dependencies.py`.
**Why:** Establishes the schema, privacy gates, and DI scaffolding before any data flows. This sprint ships no user-visible feature — it's the foundation Sprint 2 and Sprint 3 build on.
**Context:** Full spec at `docs/archived/student_chat_qdrant_ingestion/sprint_1_scaffold.md`. Key decisions: `message_id` is uuid4 generated at index time (pass as `p["id"]` to `VectorStore.upsert()`); `StudentChatInsightRecord` model removed as unused; `intake_context=None` with store flags True must return None gracefully (not AttributeError).
**Depends on:** Nothing.

### ~~Student Chat Insights Sprint 2: Index student messages from the chat flow~~ ✓ Done (2026-04-24)
**What:** After each successful `POST /api/chat` response, write the student message into the student-chat insight collection. Feature-gated by `student_chat_insights_enabled`. Failure must be non-fatal (chat request must still return 200).
**Why:** Produces the data corpus that Sprint 3's counsellor search needs. No user-visible change — silent indexing in the background.
**Context:** Full spec at `docs/archived/student_chat_qdrant_ingestion/sprint_2_indexing.md`. Key decisions: synchronous write (no `await`) mirroring the `_log_query()` pattern; test isolation via `app.dependency_overrides[dependencies.get_student_insight_store]`; `intake_context=None` integration test added (test 12a).
**Depends on:** Sprint 1.

### ~~Student Chat Insights Sprint 3: Counsellor semantic search~~ ✓ Done (2026-04-24)
**What:** Add `POST /api/insights/student-questions/search` (admin-protected via `require_admin_key`), implement `StudentChatInsightStore.search()` with Qdrant filters, and build `StudentInsightsTab.tsx` with all 8 AdminWorkspace/ToolsDrawer touch points.
**Why:** First visible product value from the epic. Lets counsellors ask "what are students worried about with international hiring?" without reading raw chatlogs.
**Context:** Full spec at `docs/archived/student_chat_qdrant_ingestion/sprint_3_counsellor_search.md`. Key decisions: `DatetimeRange` (not `Range`) for timestamp filtering; `embedder.encode()` (not `embed()`); `build_filters()` gates background/region conditions on `student_chat_store_*` config flags; 8 AdminWorkspace touch points including ToolsDrawer.tsx.
**Depends on:** Sprint 1 (service + DI). Can be parallelized with Sprint 2 after Sprint 1 ships.

### Student chat insight write — add Qdrant timeout cap
**What:** Add a timeout cap to the synchronous `insight_store.index_message()` call in `chat_router.py`, or move the write to `run_in_executor` when `chat()` is refactored to `async def`.
**Why:** The write is wrapped in try/except (non-fatal) but has no timeout. If Qdrant is slow or unresponsive, the chat response is held up by the full Qdrant client timeout (potentially 30s+). Timeout handling was explicitly OOS for Sprint 1–3; this is the natural follow-up once the feature is observable in Langfuse traces.
**Depends on:** Student chat insights Sprint 1–2 shipped.

### Session-analysis timeout handling
**What:** Tune `LLM_SESSION_TIMEOUT_SECONDS` and `LLM_SESSION_MULTI_PASS_*` via env vars, and add a better non-blocking execution model when session analysis still exceeds the budget.
**Why:** The timeout is now configurable, Langfuse confirms the request stays alive while it waits, and the structured JSON repair path now retries transient overloads. Long notes can still hit `504 Gateway Timeout` and occupy the user's session flow until they fail.
**Depends on:** None.

### ~~Validate profile field names in commit-analysis~~ ✓ Done (2026-04-12)
Shipped: `ALLOWED_PROFILE_FIELDS` enforcement already existed with skip+warn; test coverage added
to lock in the guarantee. `session_router.py` inspected — has parallel `ALLOWED_CARD_PROFILE_FIELDS`
guard. Empty field map returns 200 cleanly.

### ~~Configurable session analysis tuning~~ ✓ Done (2026-04-18)
Shipped: `LLM_TIMEOUT_SECONDS`, `LLM_SESSION_TIMEOUT_SECONDS`, `LLM_SESSION_MULTI_PASS_THRESHOLD_CHARS`,
`LLM_SESSION_MULTI_PASS_CHUNK_TOKENS`, and `LLM_SESSION_MULTI_PASS_OVERLAP_TOKENS` now come from env
vars, so session extraction can be tuned without code edits.

### ~~Session Cleanup Script~~ ✓ Done (2026-04-18)
Shipped: `scripts/cleanup_sessions.py` deletes `completed` and `cancelled` sessions older than `--days`
(default 30). Supports `--dry-run`, `--sessions-dir`, and `SESSIONS_DIR` env var. Handles both flat
and counsellor-scoped (`counsellor_id/session_id.json`) directory layouts.

### Counsellor RBAC
**What:** Replace string `counsellor_id` with real authenticated user context.
**Why:** Session ownership must be enforced, not passed around as an untrusted string.
**Depends on:** Broader auth/user model.

### ~~Synchronize and expand profile field allowlists~~ ✓ Done (2026-04-18)
Shipped: `api/constants/profile_fields.py` unifies `ALLOWED_PROFILE_FIELDS` (15 fields, up from 7 in
`kb_router` and 12 in `session_router`) and `ALLOWED_EMPLOYER_FIELDS` (8 fields) into a single source
of truth. Added `salary_levels`, `visa_pathway_notes`, and `track_name`. Both routers import from the
shared module, eliminating silent divergence and Sprint 4 field loss.

### ~~Sync structured metadata in Session Card commits~~ ✓ Done (2026-04-18)
Shipped: `_derive_structured_fields()` now called in `session_router.py` `_apply_field_updates_to_profile`
after field updates, matching the existing behavior in `kb_router.py commit_analysis()`. Prose salary
ranges in session card commits now populate `salary_min_sgd`/`salary_max_sgd` via `setdefault`.

### Basic multi-user edit protection
**What:** Add optimistic locking or version checks on structured KB writes so concurrent counselors do not silently overwrite each other.
**Why:** Last-write-wins breaks trust fast, especially in a small office where two people can edit the same entity in one day.
**Depends on:** Revision metadata on structured facts.

### Install frontend test framework (vitest + react-testing-library)
**What:** Install `vitest` + `@testing-library/react` for the `web/` workspace, set up `web/__tests__/`, write a baseline component test, wire it into CI.
**Why:** No frontend test framework exists today (no `jest.config`, no `vitest.config`, no test directories). Every frontend PR ships without component-level coverage — relies on manual QA only. Surfaced by `/plan-eng-review` of the alumni cards design 2026-04-26: SmartCanvas alumni variant, AlumniDetectionModal, and admin components have no path to regression tests.
**Pros:** Unlocks regression tests for SmartCanvas, modal flows, all admin/. Would catch UI bugs before counsellors do.
**Cons:** Infrastructure decision benefits the whole frontend, not just one feature — needs its own focused PR. Wrong pick (Jest vs Vitest for Next.js) is hard to undo.
**Context:** Next.js 14 app, Tailwind, `web/` workspace. Vitest is the modern default for Next; @testing-library/react for component tests. Playwright optional for later E2E.
**Depends on:** Nothing structural.

## Next

### ~~Normalize employer YAMLs: headcount_estimate → singapore_headcount_estimate~~ ✓ Done (2026-04-23)
Shipped: all active employer YAMLs now use `singapore_headcount_estimate`, and the employer allowlist / prompt references were updated to match the API read path.

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

### ~~Consolidate field allowlists~~ ✓ Done (2026-04-18)
Shipped: covered by "Synchronize and expand profile field allowlists" above — same change, same commit.

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

### ~~Langfuse-backed LLM observability~~ ✓ Done (2026-04-18)
Shipped: structured `started`/`ok`/`error` trace logging, optional self-hosted Langfuse export when
`LANGFUSE_*` env vars are present, shutdown flush on API exit, and admin surfacing for recent traces
and live session state.

### ~~Langfuse session grouping and Trace Explorer~~ ✓ Done (2026-04-18)
Shipped: `session_id` now propagates through live session analysis, Langfuse groups traces into
session views, and the admin Trace Explorer filters traces by session, operation, and status. The
stale API build issue that initially hid traces was fixed during verification.

### PDPA wording — query digest is not "anonymised aggregates"
**What:** Replace "anonymised aggregates" with "query aggregates" in docs and UI copy.
**Why:** The digest contains raw student query text, which is not anonymised.
**Depends on:** None.

### Extend AlumniDetail with deferred career-trajectory fields
**What:** Add `career_trajectory_pattern`, `seniority_level`, `salary_band_estimate`, `experience_diversity` to `AlumniDetail` (and `ALLOWED_ALUMNI_FIELDS` + the alumni extraction prompt). Reconcile `profile_tier` with the existing `completeness` field — pick one.
**Why:** Scope reduction in `/plan-eng-review` 2026-04-26 cut 5 of the 7 fields proposed in the alumni cards design, shipping only `career_trajectory_summary` and `home_country` on day 1. The user identified career trajectory as the highest-value field; the rest were "would also be useful." Wait for real counsellor sessions to surface which fields they actually want.
**Pros:** Avoids overengineering; fields land with proven demand. Each field is a ~10-line schema bump once the wiring is in place.
**Cons:** If a counsellor wants seniority or salary data on day 1, they're blocked. Salary bands are often the question students ask first.
**Context:** Office-hours design [iancwm-main-design-20260426-130438.md](/home/iancwm/.gstack/projects/iancwm-career-lighthouse/iancwm-main-design-20260426-130438.md) section 1. After the day-1 ALLOWED_ALUMNI_FIELDS extension, this is purely additive — model + constant + prompt's allowed-fields render.
**Depends on:** Day-1 alumni card flow shipping; ≥3 counsellor sessions using it.

### Migrate alumni tab to card-shaped data + remove AlumniDetectionModal
**What:** Migrate `web/components/admin/AlumniFactsTab.tsx` to call a new `POST /api/kb/alumni/extract` endpoint that returns card-shaped data, render through the same `SmartCanvas` component used by sessions, then remove `AlumniDetectionModal` from `SessionInbox`.
**Why:** Office-hours called for a single UI for all knowledge editing. Day-1 satisfies the "shared extraction prompt for modularity" requirement (`generate_alumni_extraction()` in `llm.py`). UI consolidation is value-add but not required for the wedge — better to wait until the card flow has proven itself with real counsellor usage.
**Pros:** One UI for all knowledge editing. Less code (modal is ~600 lines of duplicate). Fewer paths to maintain.
**Cons:** Migration risk if alumni-tab users have muscle memory for the existing modal.
**Context:** Modal at `web/components/admin/modals/AlumniDetectionModal.tsx`, used in [SessionInbox.tsx:364](web/components/admin/SessionInbox.tsx#L364). Tab at [AlumniFactsTab.tsx](web/components/admin/AlumniFactsTab.tsx). Existing endpoint [alumni_router.py:242](api/routers/alumni_router.py#L242) `extract-preview` stays in place during migration.
**Depends on:** Day-1 card flow shipping; ≥2 weeks of counsellor usage to confirm card flow is the preferred path.

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

### ~~Durable source document ledger~~ ✓ Done (2026-04-22)
Shipped: uploaded source files now persist in the source ledger, document deletions archive rather than erase lifecycle history, retrieval only treats active sources as current, and KB health surfaces active/superseded/stale source signals for admin review.

### Missing Terraform resources for production deployment
**What:** Define ECS Service, ALB HTTPS listener, target groups, EFS backup policy, WAF, auto-scaling, VPC/subnets/SGs.
**Why:** Current Terraform has task definition but no service to run it, no HTTPS listener, no auto-scaling, no WAF for rate limiting.
**Depends on:** AWS infrastructure design decisions.

## Done

### ~~Session-intent thought plumbing cleanup~~ ✓ Done (2026-04-19)
Shipped: session analysis now uses a JSON-only prompt, the retired `<thought>` block is no longer parsed or stored, and dead `thought` fields were removed from the session models, router, and hardening tests.

### ~~Config externalization, structured prompts, and briefing utilities~~ ✓ Done (0.1.5.1)
Shipped: hardcoded thresholds moved into YAML configs (`model.yaml`, `kb.yaml`, `track_guidance.yaml`, `prompts.yaml`), system prompts externalized to `prompts.yaml`, large document session extraction now uses multi-pass chunking, `generate_brief()` ships a counselor brief generator, and service docstrings were added across ingestion, LLM, session store, track guidance, and vector store modules.

### ~~Session-first admin workflow and tab guidance~~ ✓ Done (2026-04-12)
Shipped: `/admin` starts in Session Editor, the surrounding tabs now explain their purpose, and the workflow copy makes it clear when counsellors should use Track Builder versus the review surfaces.

### ~~Safe markdown rendering in student replies~~ ✓ Done (2026-04-12)
Shipped: assistant messages now render through a safe markdown subset instead of raw HTML.

### ~~Track Builder published reference, history, and bootstrap refresh~~ ✓ Done (2026-04-12)
Shipped: Track Builder shows the published reference summary, keeps archived working copies separate, and bootstraps a draft from the live published profile when a counsellor refreshes a track that does not yet have a draft file.

### ~~Track Builder registry backfill and draft self-healing~~ ✓ Done (2026-04-20)
Shipped: the draft store now seeds missing draft files from valid published profiles and backfills the track registry from published profiles on load, so tracks added through another workflow still appear in Track Builder.

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
