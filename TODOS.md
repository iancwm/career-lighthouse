# TODOS

## Performance

### list_docs() scroll ceiling — optimize for large KBs
**What:** Switch `VectorStore.list_docs()` from `scroll(limit=10000)` to per-doc `count()` calls, or add a 60s TTL cache in `kb_router.py`.
**Why:** The current scroll is O(n_chunks) and runs on every `GET /api/kb/health` call. Acceptable at < 200 docs; becomes noticeable above that.
**Pros:** Eliminates O(n) scan; health endpoint stays fast as KB grows.
**Cons:** Per-doc `count()` requires one Qdrant call per document (still bounded at pre-launch scale). TTL cache adds module-level state.
**Context:** Added during Sprint 1 KB Observability eng review (2026-03-22). The inline `# TODO: cache list_docs()` comment in `kb_router.py` marks the exact call site. Trigger: when KB consistently exceeds 200 docs.
**Depends on:** None. Self-contained change to `vector_store.py` or `kb_router.py`.

### health_cache thundering herd — check-lock-check pattern
**What:** Replace the current "check outside lock → compute → set under lock" pattern with a proper check-lock-check or "computing" flag so concurrent health requests don't all trigger the 5-second `_compute_overlap_pairs` scan simultaneously.
**Why:** Current `threading.Lock` prevents torn writes but not thundering herd — N concurrent health refreshes each acquire the lock in `get_overlap_pairs()`, see `None`, release it, compute independently, and each call `set_overlap_pairs()`. At pre-launch scale (1-2 admins) this is benign. With 10+ concurrent users it could spike Qdrant load.
**Pros:** Limits overlap computation to one in-flight at a time; eliminates duplicate O(n_chunks × Qdrant) scans.
**Cons:** Adds locking complexity; a "computing" sentinel state must be handled gracefully (return empty or stale rather than blocking callers indefinitely).
**Context:** Found during adversarial review in Ship 2 (2026-03-23). The Lock in `health_cache.py` (added in v0.1.1.1) already prevents data corruption — this is a performance optimization only.
**Depends on:** None. Self-contained change to `api/services/health_cache.py` and the `kb_health` endpoint.

---

## Sprint 2 — Career Profiles

### Document structured: YAML block intent
**What:** Add a comment to `api/services/career_profiles.py` (CareerProfileStore) and to the YAML schema section in the design doc confirming that `structured:` is intentional forward-looking infrastructure — not dead code. Purpose: machine-readable metadata for the admin `/career-profiles` endpoint today, and tool-call / structured LLM access in a future sprint.
**Why:** Without documentation, a future cleanup PR will remove it as "unused." This was confirmed by Ian during Sprint 2 eng review (2026-03-23).
**Pros:** Preserves the architectural intent; costs 2 lines of comments.
**Cons:** None.
**Context:** `structured:` contains `sponsorship_tier`, `compass_points_typical`, `salary_min_sgd`, `salary_max_sgd`, `ep_realistic`. Currently read by `GET /api/kb/career-profiles` for the admin profile list. Future use: expose via tool calls so the LLM can query structured facts directly rather than extracting them from prose.
**Depends on:** None. Add the comment during Sprint 2 implementation.

### Replace cosine career type switching with keyword matching
**What:** Implement keyword-based career type detection in `CareerProfileStore.match_career_type()` (or a new method). Each YAML profile would have a `match_keywords` list — if any keyword appears in the user message, that track is activated. Current cosine threshold is set to 1.01 (disabled) because all-MiniLM-L6-v2 scored ≤ 0.52 on test questions.
**Why:** Cosine similarity against keyword-list descriptions produces unreliable scores for conversational questions. Keyword matching is deterministic, debuggable, and produces zero false positives for firm/role name mentions. Example: if message contains "Goldman" or "IBD" or "bulge bracket" → switch to investment_banking.
**Pros:** Reliable for the key use case (student pivots tracks by naming firms/roles). Fast. No model call needed.
**Cons:** Doesn't handle semantic pivots ("what about a less stressful career?" won't trigger). Keywords must be maintained per profile. Misses novel firm names.
**Context:** Threshold validation 2026-03-23 showed cosine approach not viable at current scale with all-MiniLM-L6-v2. Full validation output: `cd api && uv run python ../scripts/validate_profiles.py --threshold-check`. The `match_keywords` field can be added to each YAML alongside `match_description`.
**Depends on:** None. Self-contained change to `career_profiles.py` + YAML additions.

### Fill in counselor_contact fields in all YAML profiles
**What:** Replace `[TODO: Fill in SMU career centre contact…]` placeholder in `investment_banking.yaml`, `consulting.yaml`, `tech_product.yaml` (and future profiles) with actual career centre contact name, email, and office hours for each track.
**Why:** `counselor_contact` is not currently injected into the LLM context block, so this doesn't affect answer quality today. But when it is added to `profile_to_context_block()`, placeholder text will be injected verbatim into the prompt.
**Pros:** Provides genuine institutional knowledge; closes a data gap before the feature is enabled.
**Cons:** Requires Ian to get contacts from the SMU career centre — not a code task.
**Context:** Found during Sprint 2 eng review (2026-03-23). The `counselor_contact` field exists in the schema but `profile_to_context_block()` does not emit it yet. Add before expanding context injection in Sprint 3.
**Depends on:** Getting contact info from SMU career centre. When ready, also add `counselor_contact` to `profile_to_context_block()` in `career_profiles.py`.

---

## Security

### FastAPI-level auth on /api/kb/* endpoints
**What:** Add `Depends()` auth guard to `POST /api/kb/test-query` and `GET /api/kb/health`.
**Why:** Currently protected only by Next.js middleware (`web/middleware.ts`), which can be bypassed by direct HTTP calls to the API. These endpoints expose raw KB chunk content and similarity scores.
**Pros:** Defense in depth; safe to expose API publicly without relying on frontend middleware.
**Cons:** Requires an auth scheme (API key header or JWT) — coordinate with whatever auth the rest of the API uses at that point.
**Context:** Accepted risk for pre-launch private network deployment. The design doc (iancwm-main-design-20260322-160902.md) contains an explicit risk acceptance note. Must resolve before any public-facing deployment.
**Depends on:** Broader API auth strategy — do this when auth is added to the rest of the API, not in isolation.

### ~~Sanitize file.filename at ingest boundary~~ ✓ Done (v0.1.2.1)
`_sanitize_filename()` added to `ingest_router.py`. Allowlist: alphanumeric + `.-_ `. Rejects null bytes, control chars, path separators, shell metacharacters. Returns HTTP 400. 13 parametrized tests cover attack vectors and valid inputs.

### FastAPI-level auth on new /api/kb/* write endpoints (Sprint 3)
**What:** Sprint 3 adds write endpoints (`POST /api/kb/analyse`, `POST /api/kb/commit-analysis`, `PUT /api/kb/career-profiles/{slug}`, `DELETE /api/kb/career-profiles/{slug}`) with no FastAPI-level auth guard — only Next.js middleware blocks unauthenticated access.
**Why:** Write endpoints that modify the KB, YAML profiles, and Qdrant are higher risk than the existing read-only endpoints. A direct HTTP call bypassing the frontend can commit arbitrary chunks or delete profiles.
**Pros:** Defense in depth; safe to expose API without trusting frontend auth alone.
**Cons:** Same as above — requires a system-wide auth scheme first.
**Context:** Found during Sprint 3 eng review (2026-04-02). Confirmed by Codex outside voice. All new /api/kb/* endpoints have the same `TODO: Add Depends() auth guard` comment as existing endpoints. Accepted risk for pre-launch pilot deployment.
**Depends on:** Broader API auth strategy. Resolve together with existing `/api/kb/health` and `/api/kb/test-query` auth TODO.

### File upload size limit — /api/ingest and /api/kb/analyse
**What:** Neither `/api/ingest` nor the planned `/api/kb/analyse` enforce a maximum file size. A large PDF (100MB+) would block a thread pool worker for minutes.
**Why:** Pre-launch counsellor-only tool means no adversarial users, so risk is low. But an accidental large upload during a demo would be jarring.
**Pros:** Simple FastAPI size check (e.g., `if len(await file.read()) > 10_000_000: raise HTTPException(400)`). Fast to implement.
**Cons:** None significant.
**Context:** Found during Sprint 3 eng review (2026-04-02). Apply to both endpoints in one PR. The filename sanitization work (v0.1.2.1) is the natural precedent.
**Depends on:** None. Self-contained change to both router files.

---

## Data / Deployment

### structured: values diverge from prose field edits after profile editor write
**What:** When a counsellor edits prose fields (e.g., `ep_sponsorship`) via the Career Profile Editor, the `structured:` sub-block (e.g., `sponsorship_tier`) is preserved unchanged — the form doesn't manage those fields. Over time, `structured:` and prose fields describe different realities.
**Why:** `structured:` is reserved for machine-readable access (tool calls, future filtering). After Sprint 3, `list_profiles()` drops `ep_tier` etc. from the response shape, so divergence is invisible. But if Sprint 4 exposes `structured:` via tool calls, stale values would produce wrong answers.
**Pros of fixing:** Consistent machine-readable metadata; prevents silent errors in tool-call access.
**Cons:** Requires mapping between prose field changes and `structured:` equivalents (e.g., ep_sponsorship text → sponsorship_tier). Non-trivial.
**Context:** Found during Sprint 3 eng review (2026-04-02). Accepted as tech debt for Sprint 3 (`yaml.safe_dump` also strips YAML comments on first save — documented). Also note: `yaml.safe_dump` strips all inline comments from profile YAMLs on first write via the editor. Comments are developer orientation only; field values survive.
**Depends on:** Sprint 3 Profile Editor (Feature 2). Address in Sprint 4 if `structured:` fields are actively consumed.

### PDPA wording — query digest is not "anonymised aggregates"
**What:** The design doc and code describe the Student Interaction Digest as "anonymised aggregates". In reality, `top_queries` and `gap_queries` contain raw student query text. The existing `query_log.jsonl` stores raw query text and timestamps; `LowConfidenceLog` already renders them in the admin UI.
**Why:** Student query text ("How do I get into Goldman Sachs?") is not personally identifiable under PDPA, so this is not a compliance breach. However, calling it "anonymised" is technically inaccurate and could cause friction during a formal SMU IT review for pilot onboarding.
**Pros of fixing:** Accurate documentation; no surprises in a PDPA review.
**Cons:** Wording change only — no code impact.
**Context:** Found during Sprint 3 eng review (2026-04-02). Fix: replace "anonymised aggregates" with "query aggregates" in the design doc, code comments, and any admin UI copy that uses this phrase. Resolve before any formal pilot deployment with SMU IT involvement.
**Depends on:** None. Wording change in design doc + UI copy.

---

## UX / Polish

### Unsaved changes warning — KnowledgeUpdateTab mid-flow navigation
**What:** When the counsellor has a diff loaded in KnowledgeUpdateTab and clicks to another admin tab, the diff state is silently discarded. Add a browser `beforeunload`-style warning or an inline "You have unsaved changes — leave anyway?" confirmation dialog.
**Why:** At pre-launch scale (1-2 counsellors), silent state loss is acceptable. But if analysis takes 5-10 seconds and the counsellor accidentally navigates away, they lose the diff and must re-run analysis.
**Pros:** Prevents accidental work loss; standard UX for forms with unsaved state.
**Cons:** React router tab-switching doesn't trigger `beforeunload` — requires a custom `useEffect` on route change or a tab-change interceptor. Minor complexity.
**Context:** Found during Sprint 3 design review (2026-04-03). The plan explicitly notes state is discarded on tab switch. Deferred at pre-launch scale.
**Depends on:** None. Add to KnowledgeUpdateTab when multi-counsellor use increases or after first counsellor reports losing a diff.

### Validate profile field names in commit-analysis
**Priority:** P2
**What:** `/api/kb/commit-analysis` accepts arbitrary `field_name` keys from the client in `profile_updates`. The server writes them verbatim to YAML. A hallucinated or malicious field name (e.g. `structured`) could corrupt the profile YAML and break `CareerProfileStore.list_profiles()`.
**Why:** Field names come from Claude via `/analyse` (constrained by prompt), then echoed by the client. Both Claude and the client are untrusted. A reserved key like `structured` being overwritten would crash downstream list/inject code.
**Fix:** Add an allowlist of writable fields per slug (top-level prose fields only: `ep_sponsorship`, `compass_score_typical`, `recruiting_timeline`, `notes`, etc.). Reject any `field_name` not in the allowlist with HTTP 422.
**Context:** Found during adversarial review (v0.1.3.0 ship). Low risk at pre-launch scale (admin-only access), but must fix before any public-facing deployment.
**Depends on:** None.

---

## Completed

### ~~KnowledgeUpdateTab — diff-first KB ingestion (Sprint 3 Feature 1)~~ ✓ Done (v0.1.3.0)
Shipped: `POST /api/kb/analyse`, `POST /api/kb/commit-analysis`, KnowledgeUpdateTab React component, admin tab nav. Content-based chunk_id idempotency, delete_by_filename dedup for file re-commits, input validation on commit payload. Validated by The Assignment (3 test cases) before build.
