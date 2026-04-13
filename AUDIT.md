# Production Readiness Audit
**Repository:** career-lighthouse  **Version:** 0.1.5.0  **Date:** 2026-04-13

---

## Part 1 — Cybersecurity Threat Analysis

### OWASP Top 10 Coverage

| # | Risk | Status | Detail |
|---|------|--------|--------|
| A01 | Broken Access Control | **FIXED** | `/api/kb/*` and `/api/sessions/*` now require `X-Admin-Key`; `web/middleware.ts` reads from env instead of hardcoded `demo2026` |
| A02 | Cryptographic Failures | Acceptable | API key in SSM SecureString; no plaintext secrets in logs or env files; YAML uses `safe_load` |
| A03 | Injection | Good | Filename allowlist (`^[A-Za-z0-9._\-()\[\] ]+$`); slug validation (`_slug_is_safe`); field allowlists on all YAML writes; no SQL used |
| A04 | Insecure Design | Partial | No RBAC model yet — `counsellor_id` is an untrusted string in session payloads; session ownership not enforced |
| A05 | Security Misconfiguration | **FIXED** | Non-root users in both Dockerfiles; CORS scoped to `ALLOWED_ORIGINS`; `WEB_CONCURRENCY=1` explicit |
| A06 | Vulnerable Components | Acceptable | All major deps current as of 2026-04; no known CVEs in lockfiles; no SBOM or automated audit in CI |
| A07 | Auth Failures | **FIXED** | Defence-in-depth: FastAPI `Depends(require_admin_key)` + Next.js middleware both enforce `ADMIN_KEY` |
| A08 | Software/Data Integrity | Gap | No SBOM; no supply-chain scan (Trivy/Grype) in CI/CD pipeline |
| A09 | Logging & Monitoring | Gap | Query log functional; no structured JSON logging; no Sentry/APM; no alert thresholds |
| A10 | SSRF | Low risk | No user-supplied URLs processed; Anthropic API calls use hardcoded SDK endpoints |

### Remaining Threat Vectors

**Rate limiting — not implemented**
All public endpoints (`POST /api/chat`, `POST /api/brief`, `POST /api/ingest`) are unbounded. A single client can exhaust Anthropic API quota or spike Fargate costs. Mitigations to add:
- FastAPI middleware using `slowapi` (token-bucket per IP)
- ALB WAF rate rule as outer layer
- Recommended limits: 10 req/min on `/api/chat`, 5 req/min on `/api/ingest`

**Request timeout — not enforced at API level**
LLM calls (`/api/chat`, `/api/brief`, `/api/kb/analyse`) can hang indefinitely if Anthropic is slow. No `timeout` is set on the `anthropic` client. Risk: all Uvicorn workers occupied, service unresponsive. Fix: `anthropic.Anthropic(timeout=30.0)` + FastAPI `BackgroundTasks` for long ops.

**Prompt injection surface**
Career context and employer facts are interpolated as raw strings into the system prompt. A malicious document uploaded via `/api/ingest` could contain adversarial instructions. Current mitigations: upload size limit (10 MB), chunk size cap (~512 tokens). Additional hardening needed: sanitise angle-brackets and `<|` tokens from chunk text before prompt injection; consider a content moderation pre-pass.

**Session fixation / IDOR**
Session IDs are `uuid4` values stored in `/logs/sessions/{id}.json`. The session API accepts any `session_id` from the caller — no ownership binding to an authenticated user. Any counsellor who guesses or intercepts a UUID can read or commit cards from another counsellor's session. Fix: bind session to `counsellor_id` at creation and verify on every subsequent call.

**Concurrent write race — last-write-wins**
Two counsellors editing the same career profile YAML simultaneously will silently overwrite each other's changes. No ETag, version field, or advisory lock exists. Fix: add a `version: int` field to YAML frontmatter; reject writes where submitted version ≠ stored version (HTTP 409).

**Hardcoded counsellor_contact placeholders**
Several career profile YAMLs contain `[TODO: Fill in SMU career centre contact…]`. If `counsellor_contact` is ever injected into prompts, placeholder text leaks into student-facing responses. Fix: gate injection on non-empty, non-placeholder values.

**Missing HTTP security headers**
FastAPI does not set `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, or `Content-Security-Policy`. These should be added as middleware or at the ALB/CloudFront layer before public exposure.

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
- No credentials in Git history (`.env` gitignored; `.env.example` contains no real values).
- Embedding model baked into Docker image — no runtime download credentials needed.

### Configuration drift risks

1. **`cfg/model.yaml` model name** — `claude-sonnet-4-6` is hardcoded in YAML. When Anthropic deprecates a model, this requires a YAML edit + redeployment. Consider making it an env var override.
2. **Field allowlist duplication** — `ALLOWED_PROFILE_FIELDS` and `ALLOWED_EMPLOYER_FIELDS` are defined independently in `kb_router.py` and `session_router.py`. If a field is added to one but not the other, behaviour diverges silently. Consolidate into a shared constants module.
3. **Qdrant version pinned in Compose but not Terraform** — `docker-compose.yml` pins `qdrant/qdrant:v1.13.2`; Terraform has no equivalent pin for any sidecar or separate Qdrant service.
4. **Counsellor contact placeholders** — `[TODO: Fill in SMU career centre contact…]` in YAML profiles will leak into LLM prompts if `counsellor_contact` is ever injected. Add a startup warning that flags placeholder values.
