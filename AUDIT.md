# Production Readiness Audit
**Repository:** career-lighthouse  **Version:** 0.1.5.3  **Date:** 2026-04-20

---

## Schema Foundation Status (2026-04-20 Assessment)

**Phase Status:** Design approved (Phase 1) → Phase 2 implementation in progress (UI + extraction complete, testing next)

**Done:**
- Schema design and field triage finalized (SCHEMA-FOUNDATION.md, docs/schema/*)
- Fact-shell model infrastructure (slug, type, timestamp, source, confidence) in api/models.py
- LLM hardening for extraction (Langfuse tracing, JSON repair, Pydantic validation)
- Career profile `structured:` sections populated with P0 fields (15+ tracks)
- Employer YAML reads/writes preserve `structured:` blocks in kb_router

**In Progress:**
- Phase 2: EmployerFactsTab fact-entry form COMPLETE (Details/Facts tabs, FactEditor, FactCard, manual entry UI)
- Phase 2: LLM extraction COMPLETE and working (ExtractedFactsModal, extraction endpoint, llm.extract_facts_from_prose — three blocking bugs resolved 2026-04-20/21)
- Need: accuracy validation on real counselor notes; refine prompt if < 80%

**Unblocked (previously blocked):**
- Phase 1 validation (Stripe pilot + LLM extraction test) — extraction endpoint now functional
- Phase 3 student query surface (`/api/kb/facts` endpoint) — ready to start once accuracy validated

**Next Actions:**
1. Test extraction on real Stripe/DBS notes; measure accuracy against ground truth
2. Write 3–5 sample facts for Stripe via UI (manual + extraction)
3. Add `/api/kb/facts` query endpoint (list, filter by type/employer/confidence/source)
4. Move to `/plan-eng-review` for Phase 3 architecture once Phase 1 validation passes

---

---

## Changelog since v0.1.5.2 (2026-04-19)

| Spec | Change | Status |
|------|--------|--------|
| Spec 1 | Per-endpoint rate limiting — `@limiter.limit()` decorators on `POST /api/chat` (10/min), `/api/ingest` and `/api/brief` (5/min) | **FIXED** |
| Spec 3 | Field allowlist consolidation — `ALLOWED_PROFILE_FIELDS` and `ALLOWED_EMPLOYER_FIELDS` unified in `api/constants/profile_fields.py`; 15 fields (up from 7/12); `salary_levels`, `visa_pathway_notes`, `track_name` added | **FIXED** |
| Spec 4 | Structured metadata sync — session card commits now call `_derive_structured_fields()`, eliminating prose↔structured field drift | **FIXED** |
| Spec 5 | Session cleanup script — `scripts/cleanup_sessions.py` for deleting completed/cancelled sessions older than N days | **ADDED** |
| Spec 6 | LLM observability — structured trace logging, live session state, session-scoped Langfuse export, and an admin Trace Explorer | **IMPROVED** |
| Spec 7 | Session analysis tuning — env-driven timeout and multi-pass chunking thresholds | **IMPROVED** |
| Spec 8 | Session-intent cleanup — JSON-only extraction, retired `<thought>` plumbing, and removed dead `thought` fields from session models/router/tests | **FIXED** |
| Spec 9 | Session-analysis schema hardening — Langfuse-first trace reads, transient repair retries, and intent-card payload type alignment | **FIXED** |

---

## Part 1 — Cybersecurity Threat Analysis

### OWASP Top 10 Coverage

| # | Risk | Status | Detail |
|---|------|--------|--------|
| A01 | Broken Access Control | **FIXED** | `/api/kb/*` and `/api/sessions/*` now require `X-Admin-Key`; `web/middleware.ts` reads from env instead of hardcoded `demo2026` |
| A02 | Cryptographic Failures | Acceptable | API key in SSM SecureString; no plaintext secrets in logs or env files; YAML uses `safe_load` |
| A03 | Injection | **IMPROVED** | Filename allowlist; slug validation; field allowlists on YAML writes; **new:** `sanitize_for_prompt()` strips angle-bracket directives and jailbreak phrases from all ingested chunks before embedding/storage |
| A04 | Insecure Design | **IMPROVED** | Sessions now bound to `counsellor_id` at creation; ownership verified on every read/write (HTTP 403 on mismatch, logged); sessions stored in counsellor-scoped directories (`sessions/{id}/{session_id}.json`). Remaining gap: `counsellor_id` is still an untrusted header — no JWT/RBAC yet |
| A05 | Security Misconfiguration | **FIXED** | Non-root users in both Dockerfiles; CORS scoped to `ALLOWED_ORIGINS`; `WEB_CONCURRENCY=1` explicit |
| A06 | Vulnerable Components | Acceptable | All major deps current as of 2026-04; no known CVEs in lockfiles; no SBOM or automated audit in CI |
| A07 | Auth Failures | **FIXED** | Defence-in-depth: FastAPI `Depends(require_admin_key)` + Next.js middleware both enforce `ADMIN_KEY` |
| A08 | Software/Data Integrity | Gap | No SBOM; no supply-chain scan (Trivy/Grype) in CI/CD pipeline |
| A09 | Logging & Monitoring | **IMPROVED** | Query log functional; structured LLM lifecycle traces now land in JSONL and Langfuse with `session_id` grouping, live Trace Explorer, and background flushes. The Trace Explorer reads Langfuse first and falls back to JSONL only when Langfuse is unavailable; no alert thresholds or centralized APM yet |
| A10 | SSRF | Low risk | No user-supplied URLs processed; Anthropic API calls use hardcoded SDK endpoints |

### Remaining Threat Vectors

**Rate limiting — FIXED**
Per-endpoint `@limiter.limit()` decorators now enforce 10 req/min on `POST /api/chat` and 5 req/min on `POST /api/ingest` and `POST /api/brief`. The `slowapi` token-bucket limiter was already wired globally in `main.py`; these decorators add tighter per-endpoint budgets. Remaining gap: no ALB WAF rate rule as an outer layer — add for production hardening.

**LLM request timeout — still user-visible**
LLM calls now use configurable timeouts, and the live UI immediately shows `started`/`error` traces when a request hangs, but session analysis and brief generation can still hit `504 Gateway Timeout` when the note is large or the Anthropic call is slow. The remaining gap is the model call itself, not the tracing path. The observability stack now proves that the request is alive while it is waiting, and Langfuse is now the first place we look for trace truth.

**Prompt injection surface — FIXED**
`api/utils/sanitization.py` (`sanitize_for_prompt`) is now applied to every chunk in `ingestion.prepare_document()` before embedding and storage. It removes angle-bracket directives (`<|...|>`, `<...>`) and redacts known jailbreak phrases (`ignore previous instructions`, `system prompt override`, etc.). Remaining gap: career context and employer facts injected into the live chat prompt are not yet sanitized at the call site in `llm.py` — those values come from counsellor-authored YAMLs (lower risk) but should receive the same treatment as a follow-up. Content moderation pre-pass (e.g. Azure Content Safety) not yet added.

**Session fixation / IDOR — FIXED**
Sessions are now bound to a `counsellor_id` (stored as `created_by` on `KnowledgeSession`) at creation time. All session read/write endpoints (`GET /{id}`, `POST /{id}/analyze`, `POST /{id}/cards/.../commit`, `POST /{id}/cards/.../discard`) verify ownership against the `X-Counsellor-ID` request header and return HTTP 403 on mismatch; all denials are logged. Sessions are stored in counsellor-scoped sub-directories (`sessions/{counsellor_id}/{session_id}.json`) for physical isolation. Legacy flat-file sessions are migrated on first access with `created_by` backfilled to `"unknown"`. Remaining gap: `X-Counsellor-ID` is an untrusted client header — production hardening requires replacing it with JWT-based auth so the counsellor identity is cryptographically verified.

**Concurrent write race — last-write-wins**
Two counsellors editing the same career profile YAML simultaneously will silently overwrite each other's changes. No ETag, version field, or advisory lock exists. Fix: add a `version: int` field to YAML frontmatter; reject writes where submitted version ≠ stored version (HTTP 409).

**Hardcoded counsellor_contact placeholders**
Several career profile YAMLs contain `[TODO: Fill in SMU career centre contact…]`. If `counsellor_contact` is ever injected into prompts, placeholder text leaks into student-facing responses. Fix: gate injection on non-empty, non-placeholder values.

**Missing HTTP security headers — FIXED**
`api/middleware/security_headers.py` (`SecurityHeadersMiddleware`) is registered in `api/main.py` and adds `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, and `Content-Security-Policy: default-src 'self'` to every API response. `Strict-Transport-Security` is emitted only when `APP_ENV=prod` to avoid breaking local HTTP development. Equivalent headers are configured in `web/next.config.js` via `async headers()`. Remaining gap: CSP is intentionally restrictive (`default-src 'self'`) and will need loosening if the frontend loads assets from a CDN or external origin.

---

## Part 2 — Cloud Readiness

### Architecture fit for AWS ECS Fargate

| Concern | Status | Notes |
|---------|--------|-------|
| Stateless API container | Partial | API is stateless for chat/brief but stateful for Qdrant embedded client and file-based query log. Single-worker constraint (`WEB_CONCURRENCY=1`) prevents horizontal scaling |
| Persistent storage | Acceptable | Qdrant data on EFS (encrypted). Knowledge YAMLs and logs now on EFS (fixed in this audit) |
| Secrets | Good | `ANTHROPIC_API_KEY` and `ADMIN_KEY` in SSM SecureString; injected at task launch, never in image layers |
| Health checks | **FIXED** | ECS container health check added to task definition; Dockerfiles include `HEALTHCHECK` directives |
| Log aggregation | Good | CloudWatch via `awslogs` driver; log group with 30-day retention added |
| Multi-AZ | Not configured | EFS and ALB should span at least 2 AZs; Terraform `subnet_ids` variable needs populating |
| Auto-scaling | Missing | No ECS Service Auto Scaling policy; no target tracking on CPU/memory |
| Backup | Missing | No `aws_efs_backup_policy`; no S3 snapshot of knowledge YAMLs |
| CDN / caching | Missing | No CloudFront in front of ALB; Amplify handles Next.js but no edge caching for API |

### Single-worker constraint is the primary scaling blocker

The file-based query log (`query_log.jsonl`) uses sequential appends with no locking. Running more than one Uvicorn worker — or two ECS tasks mounting the same EFS path — risks log corruption. Until resolved, horizontal scaling is unsafe.

**Path to multi-instance:**
1. Replace `query_log.jsonl` with a CloudWatch Logs structured sink (one log stream per task) or an SQS queue with a Lambda consumer
2. Move Qdrant to a standalone container or managed Qdrant Cloud instance so API containers are truly stateless
3. Remove `WEB_CONCURRENCY=1` constraint; run multiple workers per task

### NEXT_PUBLIC_API_URL baked at build time

The Next.js image embeds the API URL at `docker build` time via `ARG`. Changing the ALB endpoint requires rebuilding the web image. For production, consider Next.js rewrites (`/api/proxy` → ALB) so the frontend URL stays stable and the backend URL is a runtime env var.

### Missing Terraform resources

| Resource | Gap |
|----------|-----|
| `aws_ecs_service` | Task definition exists but no ECS Service to run it |
| `aws_lb_listener` | ALB stub present but no HTTPS listener (port 443, ACM cert) |
| `aws_lb_target_group` | No target group wiring tasks to ALB |
| `aws_efs_backup_policy` | No automated EFS backup |
| `aws_wafv2_web_acl` | No WAF for rate limiting or geo-blocking |
| `aws_appautoscaling_*` | No auto-scaling policy |
| VPC / subnets / SGs | Referenced as variables but not defined in module |

---

## Part 3 — Configuration Management

### Environment variable inventory

| Variable | Service | Required in prod | Source | Notes |
|----------|---------|-----------------|--------|-------|
| `ANTHROPIC_API_KEY` | API | Yes | SSM SecureString | Never log; rotate on compromise |
| `ADMIN_KEY` | API + Web | Yes | SSM SecureString | Must match on both services; rotate regularly |
| `ALLOWED_ORIGINS` | API | Yes | ECS env | Comma-separated; must match Amplify domain |
| `LLM_TIMEOUT_SECONDS` | API | Yes | ECS env | Base timeout for normal chat/brief requests |
| `LLM_SESSION_TIMEOUT_SECONDS` | API | Yes | ECS env | Higher timeout for session analysis |
| `LLM_SESSION_MULTI_PASS_THRESHOLD_CHARS` | API | No | ECS env | Cutover for chunked session extraction |
| `LLM_SESSION_MULTI_PASS_CHUNK_TOKENS` | API | No | ECS env | Session extraction chunk size |
| `LLM_SESSION_MULTI_PASS_OVERLAP_TOKENS` | API | No | ECS env | Session extraction overlap |
| `LANGFUSE_PUBLIC_KEY` | API | No | ECS env | Required when exporting traces to Langfuse |
| `LANGFUSE_SECRET_KEY` | API | No | ECS env | Keep internal-only; grants trace write access |
| `LANGFUSE_BASE_URL` | API | No | ECS env | Self-hosted Langfuse endpoint |
| `LANGFUSE_HOST` | API | No | ECS env | Canonical Langfuse SDK endpoint, useful for cloud/self-hosted parity |
| `LANGFUSE_TIMEOUT_SECONDS` | API | No | ECS env | SDK HTTP timeout for Langfuse export calls |
| `LANGFUSE_FLUSH_AT` | API | No | ECS env | Batch size before the Langfuse SDK flushes |
| `LANGFUSE_FLUSH_INTERVAL` | API | No | ECS env | Background flush interval for the Langfuse SDK |
| `LANGFUSE_TRACING_ENVIRONMENT` | API | No | ECS env | Labels traces by environment |
| `QDRANT_URL` | API | Yes | ECS env | Set to standalone container URL in ECS |
| `DATA_PATH` | API | Yes | ECS env | `/data/qdrant` on EFS mount |
| `CAREER_PROFILES_DIR` | API | Yes | ECS env | `/app/knowledge/career_profiles` on EFS |
| `EMPLOYERS_DIR` | API | Yes | ECS env | `/app/knowledge/employers` on EFS |
| `QUERY_LOG_PATH` | API | Yes | ECS env | `/app/logs/query_log.jsonl` on EFS |
| `WEB_CONCURRENCY` | API | Yes | ECS env | Must be `1`; multi-worker corrupts query log |
| `SENTENCE_TRANSFORMERS_HOME` | API | Yes | ECS env | `/app/.cache`; model baked into image |
| `NEXT_PUBLIC_API_URL` | Web | Yes | Build arg | Baked at image build; must match ALB URL |

### Idempotency analysis

| Operation | Idempotent | Risk |
|-----------|-----------|------|
| Qdrant collection creation (`ensure_collection`) | Yes | Uses `recreate=False`; safe on restart |
| Document ingest | Partial | Dedup warns but allows re-upload; chunks not deduplicated by content hash |
| Career profile YAML write | Yes | Atomic temp-file + rename; safe to rerun |
| Employer YAML write | Yes | Same atomic pattern |
| Session card commit | Partial | No idempotency key; double-submitting creates duplicate YAML update |
| Query log append | Yes (single worker) | Append-only; safe for single writer only |
| Terraform apply | Yes | Declarative; reapply is safe |

**Key non-idempotent risk: session card double-commit.** A retry or browser refresh during commit can apply the same card twice, producing duplicate YAML fields. Fix: store `committed: true` on the card and check before writing.

### Secrets hygiene checklist

- `ANTHROPIC_API_KEY` — in SSM, not in any log line. **Gap:** no rotation policy or expiry alert.
- `ADMIN_KEY` — in SSM (added this audit). **Gap:** key passed as URL query param (`?key=...`) which appears in ALB access logs and browser history. Consider migrating to a session cookie or HTTP `Authorization` header.
- `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` — when enabled, keep them in SSM or ECS secrets, not in repo files. Traces can contain prompt content, so the Langfuse project should stay internal-only.
- No credentials in Git history (`.env` gitignored; `.env.example` contains no real values).
- Embedding model baked into Docker image — no runtime download credentials needed.

### Configuration drift risks

1. **`cfg/model.yaml` model name** — `claude-sonnet-4-6` is hardcoded in YAML. When Anthropic deprecates a model, this requires a YAML edit + redeployment. Consider making it an env var override.
2. ~~**Field allowlist duplication and divergence — CRITICAL**~~ — **FIXED (2026-04-18)**: `api/constants/profile_fields.py` now defines a single `ALLOWED_PROFILE_FIELDS` frozenset (15 fields) and `ALLOWED_EMPLOYER_FIELDS` (8 fields). Both `kb_router.py` and `session_router.py` import from this shared module. The 7-vs-12 field divergence and silent `track_name` data loss are eliminated.
3. ~~**Missing Sprint 4 Field Support**~~ — **FIXED (2026-04-18)**: `salary_levels`, `visa_pathway_notes`, and `track_name` added to the unified allowlist in `api/constants/profile_fields.py`. All three write paths (Knowledge Update, Session Editor, Track Builder) can now update these fields.
4. **Qdrant version pinned in Compose but not Terraform** — `docker-compose.yml` pins `qdrant/qdrant:v1.13.2`; Terraform has no equivalent pin for any sidecar or separate Qdrant service.
5. **Counsellor contact placeholders** — `[TODO: Fill in SMU career centre contact…]` in YAML profiles will leak into LLM prompts if `counselor_contact` is ever injected. Add a startup warning that flags placeholder values.

---

## Part 4 — Code Smell Findings (docstring pass, 2026-04-24)

Observations from `api/routers/` and `api/services/`. None of these are bugs; they are structural debt to address in a future cleanup sprint.

### CS-01 · `_atomic_yaml_write` copy-pasted across 5+ files
`employer_store.py`, `source_ledger.py`, `track_drafts.py`, `alumni_store.py`, and `session_store.py` (via `tmp_path.replace(path)`) all reimplement write-to-`.tmp`-then-rename. `services/shared_yaml.py` already exports `atomic_yaml_write` but is only imported in `alumni_store.py`. Consolidate all callers to use the shared version.

### CS-02 · `_fact_payload` and `_fact_lifecycle` duplicated across `employer_store.py` and `fact_store.py`
Both modules define nearly identical private helpers for extracting a fact's data dict and resolving its lifecycle enum. The employer-store versions exist because that file predates `fact_store.py`. Move the canonical implementations to `fact_store.py` (or a new `services/fact_utils.py`) and import them.

### CS-03 · Singleton `__new__` pattern hand-rolled in every store class
`AlumniEntityStore`, `EmployerEntityStore`, `CareerProfileStore`, `VectorStore`, `SourceLedgerStore`, `SessionStore`, and `TrackDraftStore` all copy-paste the same `_instance = None; __new__` idiom. Consider a shared `Singleton` base class or a `@singleton` decorator to eliminate the repetition and make the pattern explicit.

### CS-04 · `_slug_is_safe` defined independently in at least 4 files
`kb_router.py`, `alumni_router.py`, `alumni_store.py`, and `track_drafts.py` each define their own `_slug_is_safe` with minor variations in the character allowlist. Move a single authoritative implementation to `services/shared_yaml.py` (a `safe_slug_is_valid` function) and replace all copies.

### CS-05 · `_version_stamp` defined independently in at least 4 files
`employer_store.py`, `source_ledger.py`, `track_drafts.py`, and `shared_yaml.py` all define `_version_stamp()`. The `shared_yaml.py` export (`version_stamp`) is imported in `alumni_store.py` but unused in the others. Remove the duplicates and import from `shared_yaml`.

### CS-06 · `_normalize_profile_payload` exists in both `alumni_router.py` and `alumni_store.py`
The router-layer function (in `alumni_router.py`) strips `company_links` and aliases legacy field names. The service-layer function (in `alumni_store.py`) does the same, plus coerces enums and validates referral consent. The router version should be deleted; call the service version instead.

### CS-07 · `kb_router.py` is ~2,000 lines with 40+ endpoints and unrelated concerns
The file handles KB health metrics, diff analysis, track publishing, employer CRUD, alumni endpoints, structured facts, Langfuse trace explorer, and LLM trace parsing. Each concern should be a separate sub-router (e.g. `trace_router.py`, `employer_router.py`, `track_router.py`). The file is currently the single largest maintenance surface in the codebase.

### CS-08 · `_observation_to_trace_entries` in `kb_router.py` is ~200 lines
This single function handles 15+ Langfuse SDK response shapes with deeply nested attribute fallbacks. It mixes SDK shape normalization with domain-model construction. Should be extracted to a `services/trace_adapter.py` module so it can be tested independently.

### CS-09 · `analyze_session` in `session_router.py` is a 150-line function mixing HTTP and business logic
The endpoint loads profiles, calls LLM, logs traces, handles multi-pass chunking, writes JSONL, and updates session state — all in one function. The core analysis logic (profile context assembly + LLM invocation) should live in a service function so the router can stay thin.

### CS-10 · `_safe_int` / `_safe_float` helpers are ad-hoc per file
`kb_router.py` defines `_safe_int` and `_safe_float`. `alumni_store.py` and `fact_store.py` contain inline `try/except (TypeError, ValueError)` casts. A shared `services/type_coerce.py` (or addition to `shared_yaml.py`) would unify these.

### CS-11 · `_collect_chunked_results` in `llm.py` takes 13 parameters
The function's signature carries all chunk-splitting configuration as individual arguments. A small dataclass (`ChunkedExtractionConfig`) would reduce callsite complexity and make the grouping explicit.

### CS-12 · `_latest_query_hits` in `source_ledger.py` is a pure analytics function on a stateful singleton
`SourceLedgerStore._latest_query_hits` does not access `self._records` or any mutable state; it operates entirely on its arguments. Placing a pure function on a singleton class obscures testability. Move to a module-level helper.

### CS-13 · LLM JSON repair retries have no circuit-breaker or escalation
`llm.py` retries JSON parse failures up to 3 times with increasingly explicit "repair" prompts. There is no timeout budget shared across retry attempts — a slow model response on attempt 3 can triple the total elapsed time while silently consuming API credits. Consider a shared deadline that spans the full retry loop.

### CS-14 · `_merge_source_refs` in `kb_router.py` is defined once but called from three different flows
The function deduplicates source reference lists. It is defined in the middle of `kb_router.py` (line 233) with no sibling helpers and is called from both track generation and alumni extraction paths. As a domain utility, it belongs in a shared service or model layer, not a router file.
