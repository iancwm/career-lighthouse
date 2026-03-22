# TODOS

## Performance

### list_docs() scroll ceiling — optimize for large KBs
**What:** Switch `VectorStore.list_docs()` from `scroll(limit=10000)` to per-doc `count()` calls, or add a 60s TTL cache in `kb_router.py`.
**Why:** The current scroll is O(n_chunks) and runs on every `GET /api/kb/health` call. Acceptable at < 200 docs; becomes noticeable above that.
**Pros:** Eliminates O(n) scan; health endpoint stays fast as KB grows.
**Cons:** Per-doc `count()` requires one Qdrant call per document (still bounded at pre-launch scale). TTL cache adds module-level state.
**Context:** Added during Sprint 1 KB Observability eng review (2026-03-22). The inline `# TODO: cache list_docs()` comment in `kb_router.py` marks the exact call site. Trigger: when KB consistently exceeds 200 docs.
**Depends on:** None. Self-contained change to `vector_store.py` or `kb_router.py`.

---

## Security

### FastAPI-level auth on /api/kb/* endpoints
**What:** Add `Depends()` auth guard to `POST /api/kb/test-query` and `GET /api/kb/health`.
**Why:** Currently protected only by Next.js middleware (`web/middleware.ts`), which can be bypassed by direct HTTP calls to the API. These endpoints expose raw KB chunk content and similarity scores.
**Pros:** Defense in depth; safe to expose API publicly without relying on frontend middleware.
**Cons:** Requires an auth scheme (API key header or JWT) — coordinate with whatever auth the rest of the API uses at that point.
**Context:** Accepted risk for pre-launch private network deployment. The design doc (iancwm-main-design-20260322-160902.md) contains an explicit risk acceptance note. Must resolve before any public-facing deployment.
**Depends on:** Broader API auth strategy — do this when auth is added to the rest of the API, not in isolation.
