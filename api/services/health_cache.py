# api/services/health_cache.py
"""Module-level cache for expensive KB health computations.

high_overlap_pairs is O(n_chunks x Qdrant_search) and acceptable at pre-launch
scale (< 30 docs, < 5s). It is computed on first health request and cached in
memory. The cache is invalidated on every ingest so the dashboard stays current.

Thread-safety: FastAPI runs sync endpoints in a thread pool. All reads and writes
to the module-level globals are protected by a Lock.  ``compute_if_needed`` uses
a check-lock-check pattern with a ``_computing`` sentinel so that only one thread
ever runs the expensive computation at a time.  Concurrent callers that arrive
while a computation is in flight receive the stale (or empty) cached value
immediately rather than queuing up and all computing.

Usage:
    from services import health_cache

    # Replaces the old pattern of calling get/set around an inline computation.
    cached = health_cache.compute_if_needed(lambda: _compute_overlap_pairs(store))

    # After any ingest:
    health_cache.invalidate_overlap_cache()
"""
import threading
from typing import Callable, Optional

_lock = threading.Lock()
_overlap_pairs: Optional[list[dict]] = None
_overlap_valid: bool = False
_computing: bool = False


def get_overlap_pairs() -> Optional[list[dict]]:
    """Return cached overlap pairs, or None if cache is invalid/empty."""
    with _lock:
        if not _overlap_valid:
            return None
        return _overlap_pairs


def set_overlap_pairs(pairs: list[dict]) -> None:
    """Store computed overlap pairs in the cache."""
    global _overlap_pairs, _overlap_valid
    with _lock:
        _overlap_pairs = pairs
        _overlap_valid = True


def compute_if_needed(compute_fn: Callable[[], list[dict]]) -> list[dict]:
    """Return cached overlap pairs, computing them if necessary.

    Uses check-lock-check with a ``_computing`` sentinel to guarantee that only
    one thread runs ``compute_fn`` at a time.  Concurrent callers that arrive
    while a computation is in progress receive the current stale value (or an
    empty list on first call) immediately.
    """
    global _overlap_pairs, _overlap_valid, _computing

    # Fast-path: already valid — grab under lock for a consistent read.
    with _lock:
        if _overlap_valid:
            return _overlap_pairs  # type: ignore[return-value]
        # Someone else is already computing — return stale/empty now.
        if _computing:
            return _overlap_pairs or []
        _computing = True

    # This thread owns the computation.  Run it outside the lock.
    try:
        result = compute_fn()
    finally:
        with _lock:
            _computing = False

    set_overlap_pairs(result)
    return result


def invalidate_overlap_cache() -> None:
    """Invalidate the cache. Called after any ingest operation."""
    global _overlap_valid
    with _lock:
        _overlap_valid = False
