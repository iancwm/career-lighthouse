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

## Security

### FastAPI-level auth on /api/kb/* endpoints
**What:** Add `Depends()` auth guard to `POST /api/kb/test-query` and `GET /api/kb/health`.
**Why:** Currently protected only by Next.js middleware (`web/middleware.ts`), which can be bypassed by direct HTTP calls to the API. These endpoints expose raw KB chunk content and similarity scores.
**Pros:** Defense in depth; safe to expose API publicly without relying on frontend middleware.
**Cons:** Requires an auth scheme (API key header or JWT) — coordinate with whatever auth the rest of the API uses at that point.
**Context:** Accepted risk for pre-launch private network deployment. The design doc (iancwm-main-design-20260322-160902.md) contains an explicit risk acceptance note. Must resolve before any public-facing deployment.
**Depends on:** Broader API auth strategy — do this when auth is added to the rest of the API, not in isolation.

### Sanitize file.filename at ingest boundary
**What:** Validate and sanitize `file.filename` in `ingest_router.py` before using it as the document ID — strip path separators, enforce a max length (~255 chars), and reject filenames with null bytes or control characters.
**Why:** `file.filename` is an attacker-controlled multipart header. Currently stored verbatim in Qdrant and displayed in the admin UI. No filesystem operations key on it today, but it creates a path traversal foothold if any future code reads/writes files by this name. Reject bad inputs early rather than add guards at each future callsite.
**Pros:** Eliminates a trust boundary violation; cheap to add (3-4 lines at ingest entry point).
**Cons:** Could reject legitimate filenames with unusual characters — use a permissive allowlist (alphanumeric + `.-_`) rather than a strict blocklist.
**Context:** Found during adversarial review in Ship 2 (2026-03-23). No immediate vulnerability — no FS ops currently use this value. Add before any public-facing deployment.
**Depends on:** None. Self-contained change to `ingest_router.py`.
