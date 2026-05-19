# TODOS

This file tracks only active backlog items. Sprint specs live under `docs/`, and significant shipped feature changes belong in `CHANGELOG.md`.

This backlog is ordered by execution priority:
- `Now` = highest-risk gaps before broader launch
- `Next` = important follow-ups once the core security and publishing flows are stable
- `Later` = useful cleanup or scale work that can wait
- `Done` = shipped items kept here for context

Recently archived:
- `docs/archived/SPRINT-UX-POLISH-2026-05-10.md` — friendly-feedback sprint for the Staging Area. Archived on 2026-05-10 after the header polish, optimistic session creation, history section, status-copy cleanup, and focused `SessionInbox` regression pass were verified.
- `docs/archived/session_pipeline_stabilization/SPRINT-2026-05-07.md` — unified session pipeline + backlog close-out sprint. Archived on 2026-05-07 after the session loop, workflow evidence, scorecard, E1, F3, and Langfuse eval-sync artifacts shipped.
- `docs/archived/code_quality_finish/SPRINT.md` — Code Quality Finish & Backlog Close-out. Verified and archived on 2026-05-06 with Phase 1 plus the Phase 3 `llm.py` decomposition shipped. Follow-up artifacts E1/F3 and Langfuse eval-sync have since landed; the remaining structural follow-up is Phase 2 router split.
- `docs/archived/code_quality_sprint/` — structural cleanup Phase 0 and partial Phase 1. Remaining P1-4 onward, Phase 2, and Phase 3 items live in this backlog. Shipped 2026-05-03.
- `docs/archived/langfuse_observability_sprint/` — Langfuse observability sprint. Workflow summary/detail and admin debugging shipped 2026-05-04; remaining eval dataset sync follow-up lives in this backlog and the archived code-quality finish sprint notes.
- `docs/archived/SPRINT-UX-WORKSPACE-CLARITY.md` — counsellor workspace UX sprint. Remaining A2 admin-tab sweep, D2 sticky local context, and E1/E2 verification shipped 2026-05-02.
- `docs/archived/SPRINT-LAUNCH-READINESS.md` — security/reliability/KB-perf/alumni-followups sprint. Residual items (B3 UX, E1 accuracy artifact, F3 alumni verification) live in this backlog.
- `docs/archived/alumni_schema/SPRINT-ALUMNI-CARDS.md` — alumni cards sprint. Residual manual verification lives in this backlog.

Active sprint planning:
- `docs/SPRINT-SECURITY-RELIABILITY-2026-05-15.md` — current security/reliability close-out sprint. Most code-level hardening items have shipped; the remaining open work is Claude retry/circuit-breaker handling plus the missing `/api/chat` leg of prompt-injection coverage.

## Now

### Complete `/api/chat` coverage in prompt-injection pipeline tests
**What:** Extend `api/tests/test_prompt_injection_e2e.py` so it actually exercises `/api/chat` with retrieved dirty chunks and asserts injected directives do not reach the LLM system prompt or the final response.
**Why:** The test file exists, but today it only verifies ingest-time sanitization. The chat-time helper is stubbed out without a corresponding assertion, so the end-to-end guarantee is incomplete.
**Depends on:** Nothing.

### Circuit breaker and retry backoff on Claude API calls
**What:** Wrap all Anthropic SDK calls in `api/services/llm.py` with `tenacity` retry logic (3 attempts, exponential backoff 2–10 s) on `APITimeoutError`. Add a circuit-breaker so repeated failures stop generating new calls rather than queuing them.
**Why:** A degraded Anthropic API currently exhausts the uvicorn thread pool with blocked coroutines, causing cascading latency across all endpoints. See review PERF-1.
**Depends on:** Nothing; `tenacity` is a small addition to `pyproject.toml`.

### Blocked or decision-gated launch risk
These remain top-tier risks, but they need upstream decisions or broader model changes before they become a good execution sprint.

### Counsellor RBAC
**What:** Replace the advisory `X-Counsellor-ID` header with JWT-verified identity. `_get_counsellor_id()` in `api/routers/session_router.py:64` currently reads the header value at face value — any caller can impersonate any counsellor and access or corrupt their sessions.
**Why:** Session ownership cannot be a security boundary when the identity is caller-supplied. This is the single highest-risk gap before the tool is used by more than one counsellor.
**Remediation:** Add `PyJWT` to `pyproject.toml`; decode and verify a signed JWT in `_get_counsellor_id()`; reject requests with invalid/missing tokens with HTTP 401. See review CRIT-1.
**Depends on:** Broader auth/user model and a key-issuance flow.

### Secure admin key management
**What:** Move `ADMIN_KEY` from a bare environment variable to a secrets manager (AWS Secrets Manager, GCP Secret Manager, or equivalent). Add key-access audit logging (IP, endpoint, timestamp). Use `hmac.compare_digest()` instead of string equality in the auth check.
**Why:** A leaked env var has no invalidation path. There is no current mechanism to rotate the key without a redeploy. See review CRIT-2.
**Depends on:** Infrastructure / deployment environment decisions.

### Langfuse data egress compliance audit
**What:** Audit what content is included in Langfuse trace `input`/`output` payloads (KB chunks, counsellor notes, student chat context). Confirm Langfuse's DPA covers SMU's PDPA obligations.
**Why:** Semantic content of student career discussions is leaving the system. PII masking is implemented but does not cover KB content. See review SEC-1.
**Depends on:** DPA/legal review and an owner for policy sign-off.

### Basic multi-user edit protection
**What:** Add optimistic locking or version checks on structured KB writes so concurrent counselors do not silently overwrite each other.
**Why:** Last-write-wins breaks trust fast, especially in a small office where two people can edit the same entity in one day.
**Depends on:** Revision metadata on structured facts.

## Next

### Path to multi-instance scaling
**What:** Replace file-based query log with CloudWatch Logs or SQS; move Qdrant to standalone container; remove `WEB_CONCURRENCY=1` constraint.
**Why:** Single-worker constraint blocks horizontal scaling; file-based log corrupts with multiple writers.
**Depends on:** Infrastructure decision (managed Qdrant vs sidecar). Prerequisite: the shipped single-worker startup guard in `api/main.py`.

### Stale chunk deprecation on employer entity update
**What:** When an employer entity changes, scan for stale Qdrant chunks and surface them for deletion.
**Why:** YAML is authoritative, but old chunks still retrieve and can confuse the LLM.
**Depends on:** Employer entity CRUD already shipping.

### Migrate alumni tab to card-shaped data + remove AlumniDetectionModal
**What:** Migrate `web/components/admin/AlumniFactsTab.tsx` to call a new `POST /api/kb/alumni/extract` endpoint that returns card-shaped data, render through the same `SmartCanvas` component used by sessions, then remove `AlumniDetectionModal` from `SessionInbox`.
**Why:** Office-hours called for a single UI for all knowledge editing. Day-1 satisfies the "shared extraction prompt for modularity" requirement (`generate_alumni_extraction()` in `llm.py`). UI consolidation is value-add but not required for the wedge — better to wait until the card flow has proven itself with real counsellor usage.
**Pros:** One UI for all knowledge editing. Less code (modal is ~600 lines of duplicate). Fewer paths to maintain.
**Cons:** Migration risk if alumni-tab users have muscle memory for the existing modal.
**Context:** Modal at `web/components/admin/modals/AlumniDetectionModal.tsx`, used in [SessionInbox.tsx:364](web/components/admin/SessionInbox.tsx#L364). Tab at [AlumniFactsTab.tsx](web/components/admin/AlumniFactsTab.tsx). Existing endpoint [alumni_router.py:242](api/routers/alumni_router.py#L242) `extract-preview` stays in place during migration.
**Depends on:** Day-1 card flow shipping; ≥2 weeks of counsellor usage to confirm card flow is the preferred path.

### Test a softer non-technical alias for `Debug Workflow`
**What:** Run a product-language experiment for non-technical operators once they become real users, testing an alias such as `What happened?` or `Explain this run` for the workflow-debug entrypoint.
**Why:** The current sprint correctly keeps `Debug Workflow` as the technical troubleshooting CTA, but the design review identified a likely future need for a less intimidating doorway when the observability flow is handed off to non-technical operators.
**Context:** Approved during `/plan-design-review` on 2026-05-03 for the Langfuse-first card extraction debugging sprint. The plan now includes a two-layer workflow-detail view with a plain-English `What happened` layer, so this follow-up is specifically about whether the entrypoint label should soften later, not about redesigning the underlying screen.
**Effort:** S
**Priority:** P3
**Depends on:** Actual non-technical operator adoption

## Later

### Restructure `test_kb_router.py` into focused modules
**What:** Split `api/tests/test_kb_router.py` (~1,958 lines) into `test_kb_analysis.py`, `test_kb_commit.py`, and `test_kb_health.py`. Replace repeated assertion patterns with `@pytest.mark.parametrize`.
**Why:** A single ~2K-line test file is already hard to navigate and keeps growing. Restructuring before further test additions reduces long-term debt. See review TEST-3.
**Depends on:** Nothing; pure test reorganization, no logic change.

### Re-ingest documents with improved chunking
**What:** Re-upload documents that contain tables or structured data so they get re-chunked with the new semantic-aware strategy.
**Why:** The new chunking strategy only affects new uploads. Existing Qdrant chunks from old word-boundary splitting remain and may still miss table content.
**Depends on:** New chunking strategy shipped (this sprint).

### Fill in counselor_contact fields in all YAML profiles
**What:** Replace the `[TODO: Fill in SMU career centre contact…]` placeholders in each profile YAML.
**Why:** Placeholder text will leak into prompts if `counselor_contact` is injected later.
**Depends on:** Getting the actual contact details from SMU career centre.

### Missing Terraform resources for production deployment
**What:** Define ECS Service, ALB HTTPS listener, target groups, EFS backup policy, WAF, auto-scaling, VPC/subnets/SGs.
**Why:** Current Terraform has task definition but no service to run it, no HTTPS listener, no auto-scaling, no WAF for rate limiting.
**Depends on:** AWS infrastructure design decisions.

## Done

All completed items are documented in the archived sprint files under `docs/archived/`. Key milestones:

- **2026-05-10** UX Polish Sprint — header polish, optimistic session creation, SessionInbox regression pass
- **2026-05-15** Security/reliability close-out — single-worker startup guard, magic-byte upload validation, Langfuse kill switch, YAML permission hardening, graceful executor shutdown, JSON repair audit trail, Dependabot, and security-header coverage
- **2026-05-09** Session pipeline stabilization, alumni career-trajectory fields, router split (Phase 2)
- **2026-05-06** Code Quality Finish — `llm.py` decomposition (Phase 3), E1 accuracy report, F3 alumni verification, Langfuse eval-sync, cosine→keyword career-type switching, employer context token budget
- **2026-05-04** Langfuse observability — workflow summary/detail, admin debugging, session grouping, Trace Explorer
- **2026-05-03** Code Quality Sprint Phase 0/1 — `kb_health.py` extract, prompt externalization, import lift
- **2026-05-02** Workspace clarity sprint — A2 admin-tab sweep, D2 sticky context, E1/E2 verification
- **2026-04-30** Session-analysis timeout handling, student chat insight Qdrant timeout cap
- **2026-04-28** ADMIN_KEY browser-URL strip, list_docs TTL cache, health_cache thundering-herd fix, unsaved-changes warning
- **2026-04-27** Sanitize chat prompt injections, model name env var override
- **2026-04-26** Frontend test framework (Vitest + React Testing Library)
- **2026-04-25** Backend utility consolidation (`shared_yaml.py`)
- **2026-04-24** Admin shell split, session auth hardening, same-origin proxy hardening, Student Chat Insights Sprints 1–3
- **2026-04-23** Alumni first-class admin workflow, facts dashboard, admin workspace IA, KB endpoint auth
- **2026-04-22** Alumni cards, durable source ledger, Counsellor Trust Sprint 1 (FactCard, ProvenancePanel, lifecycle filter)
- **2026-04-21** Structured Facts Phase 1 validation
- **2026-04-20** Structured Facts Phase 2 UI, Track Builder registry backfill
- **2026-04-18** Rate limiting, configurable session tuning, session cleanup script, Langfuse observability, field allowlist sync, structured field derivation
- **2026-04-12** FastAPI KB auth, file upload size limit, profile field validation, safe markdown rendering, session-first admin workflow, Track Builder history/rollback/canonicalization, filename sanitization
- **v0.1.4.0** Employer Entity YAML CRUD + admin UI
- **v0.1.3.0** KnowledgeUpdateTab diff-first KB ingestion
- **v0.1.2.1** Filename sanitization at ingest boundary
- **v0.1.5.1** Config externalization, structured prompts, briefing utilities
