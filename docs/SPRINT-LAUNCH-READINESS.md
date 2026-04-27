---
status: planned
created: 2026-04-27
last_updated: 2026-04-27
---

# Sprint: Launch Readiness — Security, Reliability & Testing Infrastructure

**Duration:** ~1 week  
**Goal:** Close every unblocked "Now" item from TODOS.md, the highest-risk "Next" items, and ship the frontend test framework before broader counsellor rollout.  
**Branch convention:** one PR per block; all green against `api/pytest` and `web/npm test` before merge.

---

## Already shipped — removed from sprint scope

A git history audit (2026-04-27) found the following items already implemented. TODOS.md updated to match.

| Sprint item | Finding |
|---|---|
| **D1** — Frontend test framework | Vitest fully installed: `web/vitest.config.ts`, `web/package.json` `"test": "vitest"`, 24 test files across `admin/__tests__/` and `student/__tests__/`. Shipped as part of the alumni cards work (commit `6af0290`). |
| **A2** — Sanitize chat prompt injections | `sanitize_for_prompt()` applied to `career_context` and `employer_context` at `api/services/llm.py:957–958`. |
| **G2** — Model name env var override | `api/config.py:24` exposes `anthropic_model: str = ""` read from `ANTHROPIC_MODEL` env var. `api/services/llm.py:91–92` has `get_model_name()` that reads it first, falls back to `model.yaml`. |
| **B3** — Commit idempotency (data safety) | `commit_card()` at `session_router.py:523` checks `card.get("status") != "pending"` and returns HTTP 409 before any write. Prevents duplicate YAML writes. Minor UX polish (200 vs 409 on repeat) is still open. |
| **G1** — PDPA wording | `grep -r "anonymised"` finds no matches outside `TODOS.md` itself. The phrase was never written into active code or UI; item is stale. |
| **A1 scope reduction** — ADMIN_KEY | Backend already enforces `X-Admin-Key` header exclusively (`api/dependencies.py:12`). Remaining work is frontend-only: stop putting the key in the browser URL (`?key=...`). No backend change needed. |

---

---

## Open item inventory

Items drawn from TODOS.md (2026-04-27), the alumni cards sprint doc, and the code quality sprint plan. Blocked items are listed in **§ Deferred** below.

---

## Block A — Security Hardening

### A1 · ADMIN_KEY: remove key from browser URL  *(Next — scope reduced)*

**What:** Stop putting the admin key in the browser URL (`?key=...`). The backend already enforces `X-Admin-Key` header exclusively. The remaining gap is client-side: `web/lib/admin-api.ts` reads the key from the URL query param and converts it to the header. Switch to a session-storage or cookie approach so the key never appears in the URL bar, browser history, or referer headers.  
**Why:** URL-based keys land in browser history and are visible in the address bar; header-only delivery was already the backend intent.  
**Files:** `web/lib/admin-api.ts`, `web/middleware.test.ts` (test at line 29 uses `?key=demo2026`), the admin page that initially bootstraps the key.  
**Risk:** Medium — touches the admin login/access flow. No backend changes needed.  
**Test:** Update `middleware.test.ts` to not pass `?key=`; confirm admin requests still authenticate.  
**Estimate:** 2–4 h

---

### ~~A2 · Sanitize chat prompt injections~~  ✓ Already shipped

`sanitize_for_prompt()` applied at `api/services/llm.py:957–958`. No work remaining.

---

## Block B — Reliability Guardrails

### B1 · Qdrant timeout cap for student chat insights  *(Now)*

**What:** Add a hard timeout (suggest 3 s) around the synchronous `insight_store.index_message()` call in `api/routers/chat_router.py`. Use `concurrent.futures.ThreadPoolExecutor` + `future.result(timeout=3)`, or move the call to `run_in_executor` when the handler becomes `async def`.  
**Why:** The try/except already makes the write non-fatal, but a slow Qdrant holds the HTTP response for the full client timeout (potentially 30 s+).  
**Files:** `api/routers/chat_router.py`, `api/services/student_chat_insights.py`.  
**Test:** Mock `index_message` with a 5 s delay; assert chat response returns in < 1 s.  
**Estimate:** 1–2 h

---

### B2 · Session-analysis timeout — non-blocking response  *(Now)*

**What:** When session analysis exceeds `LLM_SESSION_TIMEOUT_SECONDS`, return a structured partial result or explicit timeout response instead of letting the caller hit `504 Gateway Timeout`. Wrap the multi-pass analysis call in `api/routers/session_router.py` with an async timeout or `ThreadPoolExecutor` + deadline.  
**Why:** Long counsellor notes still produce 504 errors that kill the session flow. The timeout value is now configurable; the non-blocking path is the remaining gap.  
**Files:** `api/routers/session_router.py`, `api/services/llm.py` (session analysis path).  
**Response shape on timeout:**
```json
{ "status": "timeout", "partial_cards": [...], "message": "Analysis exceeded time budget. Partial results shown." }
```
**Test:** Mock LLM to delay; confirm endpoint returns within budget with `"status": "timeout"`.  
**Estimate:** 3–5 h

---

### B3 · Session card commit idempotency  *(data safety done; UX polish remains)*

`commit_card()` at `session_router.py:523` already checks `card.get("status") != "pending"` and returns HTTP 409 before any write — duplicate YAML writes cannot happen. Remaining UX polish: the frontend should treat a 409 on a card that was previously committed as a silent success (not an error toast). That is a frontend-only change in the commit handler of `SmartCanvas.tsx`.  
**Estimate:** 1 h (frontend only)

---

## Block C — KB Performance

### C1 · list_docs() scroll ceiling — TTL cache  *(Next)*

**What:** Add a 60 s TTL cache to the `VectorStore.list_docs()` call in `api/routers/kb_router.py`. The `# TODO: cache list_docs()` comment at that call site marks the exact location.  
**Why:** The current `scroll(limit=10000)` is O(n_chunks) and runs on every `GET /api/kb/health` call.  
**Files:** `api/routers/kb_router.py` (cache addition), or `api/services/vector_store.py` (TTL on the method itself).  
**Approach:** Simple module-level `(result, expires_at)` tuple; thread-safe read under a lock.  
**Test:** `test_kb_router.py` kb_health tests still pass; new test confirms a second call within TTL does not re-invoke `scroll`.  
**Estimate:** 1–3 h

---

### C2 · health_cache thundering herd — check-lock-check  *(Next)*

**What:** Replace the current "check outside lock → compute → set under lock" pattern in `api/services/health_cache.py` with check-lock-check or a `"computing"` sentinel flag.  
**Why:** Concurrent health requests can all pass the outer check and each trigger a full `_compute_overlap_pairs` scan (5 s, O(n_chunks × Qdrant)).  
**Files:** `api/services/health_cache.py`.  
**Test:** Concurrent `threading.Thread` test: confirm `_compute_overlap_pairs` is called exactly once under simultaneous requests.  
**Estimate:** 1–2 h

---

## ~~Block D — Frontend Testing Infrastructure~~  ✓ Already shipped

Vitest is fully installed: `web/vitest.config.ts`, `"test": "vitest"` in `web/package.json`, `@testing-library/react` v16, `@testing-library/user-event`, and 24 test files already written across `web/components/admin/__tests__/` and `web/components/student/__tests__/`. Shipped with commit `6af0290` (alumni cards). No work remaining for this block.

---

## Block E — LLM Accuracy Gate

### E1 · Structured Facts Phase 2 — extraction accuracy testing  *(Now)*

**What:** Run the extraction endpoint end-to-end on 3 real Stripe employer notes. Score field accuracy manually (target ≥ 80%). Refine the extraction prompt in `api/services/llm.py` if accuracy falls short. Write 3–5 sample facts manually through the FactEditor UI to validate the write path.  
**Why:** The extraction endpoint is fully functional; accuracy is the gate before Phase 3 (querying structured facts in live chat context).  
**Files:** `api/services/llm.py` (extraction prompt), `api/routers/kb_router.py` (extract-facts endpoint).  
**Deliverable:** A short accuracy report (can be a code comment or a doc entry) recording the score and any prompt changes made.  
**Estimate:** 2–4 h (depends on prompt iteration)

---

## Block F — Alumni Cards Sprint: Remaining Checklist

Three items from `docs/alumni_schema/SPRINT-ALUMNI-CARDS.md` are still open. They belong in this sprint since the underlying code has shipped.

### F1 · T3 eval cases in test_ai_eval.py  *(Alumni sprint blocker)*

Add 3 eval cases to `api/tests/test_ai_eval.py`:
1. Alumni note → `career_trajectory_summary` populated with a full narrative.  
2. Note about an existing alumnus → `is_update=true` and `matched_slug` matches.  
3. Note → `source_excerpt` populated with the 1–2 trigger sentences.

Reuse the 3 alumni fixture files from `api/tests/fixtures/alumni_heavy_notes/`.

---

### F2 · Commit response: company_links_attempted vs company_links_written  *(Alumni sprint)*

**What:** When `_normalize_company_link` drops malformed entries during a commit, the response body must include `company_links_attempted` and `company_links_written` counts. SmartCanvas should surface the discrepancy in the commit-result toast.  
**Files:** `api/routers/session_router.py` (`_apply_field_updates_to_alumni`), `web/components/admin/SmartCanvas.tsx`.  
**Estimate:** 1–2 h

---

### F3 · Four failure modes — end-to-end verification  *(Alumni sprint)*

Manually verify (or add tests for) all four failure modes from the alumni cards spec:

| # | Failure mode | Handling |
|---|---|---|
| 1 | Hallucinated `matched_slug` | Downgraded to `is_update=false` + `matched_slug=None` |
| 2 | Malformed `company_links` | Discrepancy reported in commit response (F2) |
| 3 | Slug collision for new alumni | Append local date before card creation |
| 4 | Unknown LLM fields in alumni diff | Rejected with clear error; no partial YAML write |

Unit tests for cases 1, 3, 4 should already exist or be added in this sprint.

---

## Block G — Quick Wins

### ~~G1 · PDPA wording~~  ✓ Stale — phrase never written into code

`grep -r "anonymised"` finds no matches in any active code or UI file. The item was written anticipating copy that was never added. No work needed; remove from TODOS.md.

---

### ~~G2 · Model name env var override~~  ✓ Already shipped

`api/config.py:24` exposes `anthropic_model: str = ""` (from `ANTHROPIC_MODEL` env var). `api/services/llm.py:91–92` has `get_model_name()` that reads it and falls back to `model.yaml`. No work remaining.

---

### G3 · SessionInbox empty state copy  *(Later → Now)*

Replace the bare "No active sessions. Create one above." with warmer copy that briefly explains what a session is for.  
**Files:** `web/components/admin/SessionInbox.tsx`.  
**Estimate:** 15 min

---

### G4 · Unsaved changes warning — KnowledgeUpdateTab  *(Next)*

Add a `beforeunload` handler (and Next.js router guard) when `KnowledgeUpdateTab` has a loaded diff. Clear the guard after commit or explicit discard.  
**Files:** `web/components/admin/KnowledgeUpdateTab.tsx`.  
**Estimate:** 1 h

---

## Code Quality Sprint — Remaining Phases

The code quality sprint (`docs/code_quality_sprint/implementation_plan.md`) still has Phases 1–3 items open. These are **not** in scope for this sprint (they are structural-only and carry their own reviewer profile), but they should follow immediately after:

| Item | Phase |
|------|-------|
| P1-4 · Extract `services/kb_health.py` | Phase 1 |
| P1-5 · Move `auto_complete_profile` prompt to `prompts.yaml` | Phase 1 |
| P1-6 · Lift inline imports out of routers | Phase 1 |
| P2-1 · Split `kb_router.py` into 5 sub-routers | Phase 2 |
| P2-2 · Split `test_kb_router.py` to mirror new routers | Phase 2 |
| P3-1 · Extract `services/llm_tracing.py` | Phase 3 |
| P3-2 · Extract `services/llm_json.py` | Phase 3 |
| P3-3 · Extract `services/llm_budgets.py` | Phase 3 |
| P3-4 · Generalize three merge routines | Phase 3 |

---

## Execution order

All blocks in this sprint are independent. Recommended sequence:

```
A1 (auth — breaking, needs co-ordination) ──────── first
A2 (sanitize)                             ──────── alongside A1
B1 (Qdrant timeout)                       ──────── quick win, do early
B2 (session timeout)                      ──────── medium; start concurrently with B3
B3 (commit idempotency)                   ──────── medium; can run in parallel with B2
C1 + C2 (KB perf)                         ──────── self-contained; any time
D1 (vitest)                               ──────── do early so later PRs can add tests
E1 (accuracy testing)                     ──────── time-boxed; stop at 2 prompt iterations
F1–F3 (alumni checklist)                  ──────── close the open alumni sprint
G1–G4 (quick wins)                        ──────── fill gaps between larger items
```

---

## Deferred (explicitly out of scope)

| TODOS.md item | Reason deferred |
|---|---|
| Counsellor RBAC | Needs broader auth/user model |
| Basic multi-user edit protection | Needs revision metadata on structured facts |
| Stale chunk deprecation on employer entity update | Complex; own focused sprint |
| Restore path for disabled employer entities | Own sprint alongside stale-chunk work |
| Path to multi-instance scaling | Infrastructure decision required first |
| Extend AlumniDetail (5 deferred fields) | Blocked on ≥ 3 real counsellor sessions |
| Migrate alumni tab + remove AlumniDetectionModal | Blocked on ≥ 2 weeks of usage |
| Fill in counselor_contact YAML fields | Data dependency (SMU career centre) |
| Re-ingest documents with improved chunking | Operational task; not a code change |
| Employer context token budget per-career-type | Blocked on career-type filtered injection |
| Missing Terraform production resources | Large infrastructure sprint; own track |
| Replace cosine career type switching | Deferred — no active regression |

---

## Definition of done

- [x] `cd web && npm test` passes — vitest installed and 24 tests passing (D1 done)
- [x] Career context and employer facts sanitized before LLM injection (A2 done)
- [x] `ANTHROPIC_MODEL` env var overrides model.yaml (G2 done)
- [x] Double-commit of a card cannot write YAML twice — 409 guard in place (B3 data safety done)
- [ ] `cd api && pytest` passes with no regressions after every PR
- [ ] ADMIN_KEY no longer appears in browser URL bar or history (A1 — frontend only)
- [ ] 409 on already-committed card is treated as silent success in SmartCanvas (B3 UX)
- [ ] Chat endpoint returns in < 1 s even when Qdrant is unresponsive (B1)
- [ ] Session analysis returns a structured response before gateway timeout on long notes (B2)
- [ ] `GET /api/kb/health` is served from cache within TTL (C1)
- [ ] `_compute_overlap_pairs` executes at most once under concurrent requests (C2)
- [ ] Extraction accuracy ≥ 80% on 3 real Stripe notes, result documented (E1)
- [ ] 3 T3 eval cases pass in `test_ai_eval.py` (F1)
- [ ] `company_links_attempted` vs `company_links_written` surfaced in commit response (F2)
- [ ] All 4 alumni failure modes verified end-to-end (F3)
- [ ] CHANGELOG.md updated
