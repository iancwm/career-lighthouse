---
status: planned
created: 2026-04-27
---

# Sprint: Launch Readiness — Security, Reliability & Testing Infrastructure

**Duration:** ~1 week  
**Goal:** Close every unblocked "Now" item from TODOS.md, the highest-risk "Next" items, and ship the frontend test framework before broader counsellor rollout.  
**Branch convention:** one PR per block; all green against `api/pytest` and (after D1 lands) `web/npm test` before merge.

---

## Open item inventory

Items drawn from TODOS.md (2026-04-27), the alumni cards sprint doc, and the code quality sprint plan. Blocked items are listed in **§ Deferred** below.

---

## Block A — Security Hardening

### A1 · ADMIN_KEY: query param → Authorization header  *(Next → Now)*

**What:** Replace all `?key=…` query-param usage with an `Authorization: Bearer <key>` header. Update `web/lib/api-proxy.ts` to forward the header. Reject the query-param form with HTTP 400 in `require_admin_key`.  
**Why:** Query params land in ALB access logs and browser history — the key is exposed in plain text.  
**Files:** `api/dependencies.py` (or wherever `require_admin_key` reads the key), `web/lib/api-proxy.ts`, any admin scripts.  
**Risk:** Breaking change for API consumers not going through the proxy. Document in CHANGELOG.  
**Test:** Auth fixtures in `test_kb_router.py` must pass with header; add a test that `?key=` returns 400.  
**Estimate:** 3–5 h

---

### A2 · Sanitize chat prompt injections  *(Next → Now)*

**What:** Apply `sanitize_for_prompt()` to career context and employer facts before they are injected into live chat prompts in `api/services/llm.py`.  
**Why:** Counsellor-authored YAMLs are lower risk but must receive the same treatment as ingested chunks.  
**Files:** `api/services/llm.py` — the context-assembly helpers that build the system prompt.  
**Risk:** Low. `sanitize_for_prompt()` already exists.  
**Test:** Unit test: adversarial YAML value (`"Ignore previous instructions…"`) is stripped before prompt assembly.  
**Estimate:** 1–2 h

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

### B3 · Session card commit idempotency  *(Next → Now)*

**What:** Store `committed_at` (ISO timestamp) on cards after a successful commit. In `commit_card()`, check for `committed_at` before writing and return HTTP 200 with `"already_committed": true` if the card was already applied.  
**Why:** A browser refresh during commit replays the same card, producing duplicate YAML field writes.  
**Files:** `api/routers/session_router.py` (`commit_card` handler), session JSON schema (`api/models_kb.py` or session store).  
**Test:** Call `commit_card` twice with the same `card_id`; second call must return 200 with `already_committed: true` without a second YAML write.  
**Estimate:** 2–4 h

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

## Block D — Frontend Testing Infrastructure

### D1 · Install vitest + @testing-library/react  *(Now)*

**What:** Install `vitest`, `@testing-library/react`, `@testing-library/user-event`, `@vitejs/plugin-react`, and `jsdom` into the `web/` workspace. Create `web/vitest.config.ts` and `web/__tests__/`. Write a baseline component smoke test (suggest: `FactCard` — already well-scoped, has DESIGN.md-aligned types). Wire `"test": "vitest run"` in `web/package.json`. Add `npm test` step to CI.  
**Why:** No frontend test framework exists today. Every UI PR ships without component-level coverage.  
**Tech choice:** Vitest is the idiomatic choice for Next.js 14 + TypeScript. Do not introduce Jest — tool choice is hard to undo.  
**Files:** `web/package.json`, `web/vitest.config.ts`, `web/__tests__/FactCard.test.tsx`, `.github/workflows/ci.yml` (or equivalent).  
**Test:** `npm test` passes in CI from a clean install.  
**Estimate:** 3–5 h

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

### G1 · PDPA wording — replace "anonymised aggregates"  *(Next)*

Replace every instance of "anonymised aggregates" with "query aggregates" in docs and UI copy.  
**Files:** `grep -rn "anonymised" .` — expected in `docs/` and a UI string.  
**Estimate:** 30 min

---

### G2 · Model name env var override  *(Next)*

Read the model name from `ANTHROPIC_MODEL` env var when set, falling back to `model.yaml`.  
**Files:** wherever `model.yaml` is loaded in `api/services/llm.py` or `api/cfg/`.  
**Estimate:** 30–60 min

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

- [ ] `cd api && pytest` passes with no regressions after every PR
- [ ] `cd web && npm test` passes (after D1 lands; required for all subsequent PRs)
- [ ] ADMIN_KEY query-param form returns 400 in any live code path (A1)
- [ ] Career context and employer facts are sanitized before LLM injection (A2)
- [ ] Chat endpoint returns in < 1 s even when Qdrant is unresponsive (B1)
- [ ] Session analysis returns a structured response before gateway timeout on long notes (B2)
- [ ] Double-commit of a card is a no-op (B3)
- [ ] `GET /api/kb/health` is served from cache within TTL (C1)
- [ ] `_compute_overlap_pairs` executes at most once under concurrent requests (C2)
- [ ] `web/__tests__/` has at least one passing component test (D1)
- [ ] Extraction accuracy ≥ 80% on 3 real Stripe notes, result documented (E1)
- [ ] 3 T3 eval cases pass in `test_ai_eval.py` (F1)
- [ ] `company_links_attempted` vs `company_links_written` surfaced in commit response (F2)
- [ ] All 4 alumni failure modes verified (F3)
- [ ] "anonymised aggregates" removed from all copy (G1)
- [ ] `ANTHROPIC_MODEL` env var overrides `model.yaml` model name (G2)
- [ ] CHANGELOG.md updated with breaking change note for A1
