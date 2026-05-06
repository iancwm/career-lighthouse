# TODOS

This backlog is ordered by execution priority:
- `Now` = highest-risk gaps before broader launch
- `Next` = important follow-ups once the core security and publishing flows are stable
- `Later` = useful cleanup or scale work that can wait
- `Done` = shipped items kept here for context

Active sprint specs:
- `docs/unified_session_and_quality/SPRINT.md` — Unified session pipeline + backlog close-out sprint. Covers Staging Area create-state trust, live queue updates, malformed JSON/workflow evidence hardening, SmartCanvas scroll reduction, alumni-card reliability verification, and remaining session-loop stabilization work. Started 2026-05-06.

Recently archived:
- `docs/archived/code_quality_finish/SPRINT.md` — Code Quality Finish & Backlog Close-out. Verified and archived on 2026-05-06 with Phase 1 plus the Phase 3 `llm.py` decomposition shipped. Follow-up artifacts E1/F3 and Langfuse eval-sync have since landed; the remaining structural follow-up is Phase 2 router split.
- `docs/archived/code_quality_sprint/` — structural cleanup Phase 0 and partial Phase 1. Remaining P1-4 onward, Phase 2, and Phase 3 items live in this backlog. Shipped 2026-05-03.
- `docs/archived/langfuse_observability_sprint/` — Langfuse observability sprint. Workflow summary/detail and admin debugging shipped 2026-05-04; remaining eval dataset sync follow-up lives in this backlog and the archived code-quality finish sprint notes.
- `docs/archived/SPRINT-UX-WORKSPACE-CLARITY.md` — counsellor workspace UX sprint. Remaining A2 admin-tab sweep, D2 sticky local context, and E1/E2 verification shipped 2026-05-02.
- `docs/archived/SPRINT-LAUNCH-READINESS.md` — security/reliability/KB-perf/alumni-followups sprint. Residual items (B3 UX, E1 accuracy artifact, F3 alumni verification) live in this backlog.
- `docs/archived/alumni_schema/SPRINT-ALUMNI-CARDS.md` — alumni cards sprint. Residual manual verification lives in this backlog.

## Now

### Unified session pipeline + backlog close-out sprint
**What:** Fix the Staging Area and SmartCanvas loop so session creation immediately shows up in `Analyzing now`, analysis starts from the create path, workflow detail exposes enough repair/alumni evidence to debug malformed-JSON and zero-card runs, and SmartCanvas no longer requires repeated scrolling to commit the next card.
**Why:** The current session publishing flow is still not performing to spec; major refactor debt is reduced, so this sprint now centers on reliability and operator trust in the active session loop.
**Files:** `docs/unified_session_and_quality/SPRINT.md`, `web/components/admin/SessionInbox.tsx`, `web/components/admin/SmartCanvas.tsx`, `web/components/admin/TraceExplorerTab.tsx`, `api/routers/session_router.py`, `api/services/llm.py`, `api/services/trace_adapter.py`, `scripts/sync_langfuse_eval_dataset.py`.
**Depends on:** None. This is now the active source-of-truth sprint for the session-card loop plus residual close-out work.

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

### ~~Structured Facts Phase 2: LLM extraction accuracy testing (E1)~~ ✓ Done (2026-05-06)
Shipped: accuracy report at `docs/sprint_cq_finish/E1_accuracy_report.md` documents methodology, test inputs (Grab/DBS/Accenture notes), scoring rubric (≥ 80%), expected fact types, prompt-refinement candidates, and manual write-path validation steps. Live LLM run requires `ANTHROPIC_API_KEY` in staging env.

### ~~Alumni cards — manual end-to-end verification of the four failure modes (F3)~~ ✓ Done (2026-05-06)
Shipped: all four failure modes verified. Mode 2 test (`test_commit_alumni_card_surfaces_company_links_discrepancy`) added to `test_session_router.py`. `SmartCanvas.tsx:437` confirmed to render `company_links_warning`. Full verification record at `docs/sprint_cq_finish/F3_alumni_verification.md`.

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

### ~~Student chat insight write — add Qdrant timeout cap~~ ✓ Done (2026-04-30)
Shipped: `api/routers/chat_router.py` now wraps `insight_store.index_message()` in a module-level `_INSIGHT_EXECUTOR` (`ThreadPoolExecutor`) and applies `future.result(timeout=_INSIGHT_WRITE_TIMEOUT_SECS)`. A slow Qdrant no longer holds up the chat response.

### ~~Session-analysis timeout handling~~ ✓ Done (2026-04-30)
Shipped: `api/routers/session_router.py` now uses `_SESSION_INTENTS_EXECUTOR` and `future.result(timeout=_deadline)` to bound the multi-pass analysis call; long notes return inside the deadline instead of hitting a gateway timeout. `LLM_SESSION_TIMEOUT_SECONDS` and `LLM_SESSION_MULTI_PASS_*` remain env-tunable.

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

### ~~Install frontend test framework (vitest + react-testing-library)~~ ✓ Done (2026-04-26)
Shipped: `web/vitest.config.ts`, `"test": "vitest"` in `web/package.json`, `@testing-library/react` v16, and 24 test files across `web/components/admin/__tests__/` and `web/components/student/__tests__/`. Landed with alumni cards sprint (commit `6af0290`).

## Next

### ~~Normalize employer YAMLs: headcount_estimate → singapore_headcount_estimate~~ ✓ Done (2026-04-23)
Shipped: all active employer YAMLs now use `singapore_headcount_estimate`, and the employer allowlist / prompt references were updated to match the API read path.

### ~~ADMIN_KEY: remove key from browser URL~~ ✓ Done (2026-04-28)
Shipped: `web/middleware.ts` accepts `?key=...` once on first hit, validates against `ADMIN_KEY`, sets an HttpOnly session cookie, and redirects to the clean URL so the key is stripped from the address bar after the first navigation. `web/lib/admin-api.ts` relies on the cookie; the proxy forwards it as `X-Admin-Key`. `web/middleware.test.ts` covers the redirect-and-cookie-set path.

### ~~Sanitize chat prompt injections~~ ✓ Done (2026-04-27)
Shipped: `sanitize_for_prompt()` applied to `career_context` and `employer_context` at `api/services/llm.py:957–958`.

### ~~Session card commit idempotency — SmartCanvas 409 silent success (B3 UX polish)~~ ✓ Done (2026-05-06 verification)
Shipped: `web/components/admin/SmartCanvas.tsx` now treats `409` responses from commit, discard, and cancel flows as reload-and-sync outcomes instead of false failures. Re-verified during the archived code-quality finish sprint review.

### ~~Code quality sprint — Phase 1 finish (kb_health extract, prompt externalization, inline-import lift)~~ ✓ Done (2026-05-06 verification)
Shipped: `api/services/kb_health.py` now owns KB-health assembly and query-log metrics; `api/cfg/prompts.yaml` now carries `auto_complete_profile`; `api/services/llm.py` exposes `auto_complete_profile_fields(...)`; and the relevant imports in `session_router.py` / `kb_router.py` are lifted to module scope. Re-verified with `pytest api/tests/test_kb_router.py api/tests/test_session_router.py api/tests/test_alumni_detection.py -q` (`100 passed`) plus `python -m compileall api/routers api/services api/tests`.

### Code quality sprint — Phase 2 router split
**What:** Split `kb_router.py` into `profile_router`, `tracks_router`, `employers_router`, `facts_router`, and `kb_admin_router`; register all five in `main.py`. Then split `tests/test_kb_router.py` into per-router test files. URL paths do not change.
**Why:** After Phase 1, `kb_router.py` should be ~600 lines of thin endpoint handlers; splitting becomes a mechanical move. Defined in `docs/code_quality_sprint/implementation_plan.md` (P2-1, P2-2).
**Depends on:** None. Phase 1 was verified complete on 2026-05-06.

### ~~Code quality sprint — Phase 3 services/llm.py decomposition~~ ✓ Done (2026-05-06 verification)
Shipped: `api/services/llm_tracing.py`, `api/services/llm_json.py`, and `api/services/llm_budgets.py` now own the tracing, structured-JSON, and budgeting/config seams that used to live inside `api/services/llm.py`; `LLMTraceRecorder` now drives `_call_with_trace`, and `MergeSpec` plus `merge_chunked_results(...)` unify the three chunk-merge paths. Re-verified with `cd api && uv run pytest tests/test_llm_hardening.py tests/test_llm_observability.py tests/test_session_intents.py tests/test_kb_analyse.py -q` (`41 passed`) plus `uv run python -m py_compile services/llm.py services/llm_budgets.py services/llm_json.py services/llm_tracing.py tests/test_llm_hardening.py`.

### Path to multi-instance scaling
**What:** Replace file-based query log with CloudWatch Logs or SQS; move Qdrant to standalone container; remove `WEB_CONCURRENCY=1`.
**Why:** Single-worker constraint blocks horizontal scaling; file-based log corrupts with multiple writers.
**Depends on:** Infrastructure decision (managed Qdrant vs sidecar).

### ~~Consolidate field allowlists~~ ✓ Done (2026-04-18)
Shipped: covered by "Synchronize and expand profile field allowlists" above — same change, same commit.

### ~~Model name env var override~~ ✓ Done (2026-04-27)
Shipped: `api/config.py:24` exposes `anthropic_model: str = ""` from `ANTHROPIC_MODEL` env var. `api/services/llm.py:91–92` `get_model_name()` reads it first and falls back to `model.yaml`.

### ~~list_docs() scroll ceiling — TTL cache~~ ✓ Done (2026-04-28)
Shipped: `api/routers/kb_router.py` wraps `VectorStore.list_docs()` in a 60 s module-level TTL cache (`_docs_cache`, `_docs_cache_expires`, `_DOCS_CACHE_TTL`) protected by `_docs_cache_lock`. The cache is invalidated on every ingest via `health_cache.invalidate_overlap_cache`, and `_get_cached_docs(store)` is the single read entry point.

### ~~health_cache thundering herd — check-lock-check pattern~~ ✓ Done (2026-04-28)
Shipped: `api/services/health_cache.py` now uses a check-lock-check pattern with a `_computing` sentinel so only one thread runs the 5-second `_compute_overlap_pairs` scan; concurrent callers wait for the in-flight computation rather than triggering parallel scans.

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

### ~~Unsaved changes warning — KnowledgeUpdateTab mid-flow navigation~~ ✓ Done (2026-04-28)
Shipped: `web/components/admin/KnowledgeUpdateTab.tsx` registers a `beforeunload` listener while a diff is loaded and removes it after commit or discard.

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

### ~~Sync canonical card-debug fixtures into the Langfuse eval dataset~~ ✓ Done (2026-05-06)
Shipped: `scripts/sync_langfuse_eval_dataset.py` now upserts canonical fixtures from `api/tests/fixtures/eval_queries.jsonl` into a Langfuse dataset, with `--dry-run` and clear exit codes. Operator runbook at `docs/sprint_cq_finish/langfuse_eval_sync.md` documents prerequisites, usage, verification, and schema.

### Test a softer non-technical alias for `Debug Workflow`
**What:** Run a product-language experiment for non-technical operators once they become real users, testing an alias such as `What happened?` or `Explain this run` for the workflow-debug entrypoint.
**Why:** The current sprint correctly keeps `Debug Workflow` as the technical troubleshooting CTA, but the design review identified a likely future need for a less intimidating doorway when the observability flow is handed off to non-technical operators.
**Context:** Approved during `/plan-design-review` on 2026-05-03 for the Langfuse-first card extraction debugging sprint. The plan now includes a two-layer workflow-detail view with a plain-English `What happened` layer, so this follow-up is specifically about whether the entrypoint label should soften later, not about redesigning the underlying screen.
**Effort:** S
**Priority:** P3
**Depends on:** Actual non-technical operator adoption

### ~~PDPA wording — query digest is not "anonymised aggregates"~~ ✓ Stale (2026-04-27)
The phrase "anonymised aggregates" does not appear in any active code or UI file — it was never written into the product. No action needed.

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

### ~~SessionInbox empty state copy~~ ✓ Done (2026-04-28)
Shipped: `web/components/admin/SessionInbox.tsx` renders a "No sessions yet" state with explanatory copy ("Paste your meeting notes or upload a document above to get started. The system will extract individual update cards…") instead of the bare prior wording.

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

### ~~Workspace clarity sprint — remaining A2 sweep, D2 sticky local context, and E1/E2 verification~~ ✓ Done (2026-05-02)
Shipped: the remaining admin tabs now use the shared `ActionStatus` loading language (or accessible skeleton text), Employer Fact Library / SmartCanvas / Track Builder now keep local context and primary actions visible inside constrained split panes, and the focused Vitest + Playwright regression pass is green. See `docs/archived/SPRINT-UX-WORKSPACE-CLARITY.md`.

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
