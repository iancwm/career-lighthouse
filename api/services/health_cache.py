# api/services/health_cache.py
"""Module-level cache for expensive KB health computations.

high_overlap_pairs is O(n_chunks x Qdrant_search) and acceptable at pre-launch
scale (< 30 docs, < 5s). It is computed on first health request and cached in
memory. The cache is invalidated on every ingest so the dashboard stays current.

Usage:
    from services import health_cache

    cached = health_cache.get_overlap_pairs()
    if cached is None:
        cached = compute_expensive_thing()
        health_cache.set_overlap_pairs(cached)

    # After any ingest:
    health_cache.invalidate_overlap_cache()
"""
from typing import Optional

_overlap_pairs: Optional[list[dict]] = None
_overlap_valid: bool = False


def get_overlap_pairs() -> Optional[list[dict]]:
    """Return cached overlap pairs, or None if cache is invalid/empty."""
    if not _overlap_valid:
        return None
    return _overlap_pairs


def set_overlap_pairs(pairs: list[dict]) -> None:
    """Store computed overlap pairs in the cache."""
    global _overlap_pairs, _overlap_valid
    _overlap_pairs = pairs
    _overlap_valid = True


def invalidate_overlap_cache() -> None:
    """Invalidate the cache. Called after any ingest operation."""
    global _overlap_valid
    _overlap_valid = False
