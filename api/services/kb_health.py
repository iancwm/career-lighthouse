# api/services/kb_health.py
import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from qdrant_client.models import Filter, FieldCondition, MatchValue

from config import settings
from cfg import kb_cfg
from models_kb import (
    DocCoverageItem,
    KBHealthResponse,
    LowConfidenceQuery,
    OverlapPair,
)
from services import health_cache
from services.source_ledger import get_source_ledger_store
from services.vector_store import VectorStore

logger = logging.getLogger(__name__)

_thresholds = kb_cfg["thresholds"]
_COVERAGE_THIN_THRESHOLD = _thresholds["coverage_thin"]
_LOW_CONFIDENCE_THRESHOLD = _thresholds["low_confidence"]
_OVERLAP_SCORE_THRESHOLD = _thresholds["overlap_score"]
_OVERLAP_PCT_THRESHOLD = _thresholds["overlap_pct"]
_LOG_WINDOW_DAYS = kb_cfg["log_window_days"]
_MAX_LOW_CONF_QUERIES = kb_cfg["max_low_conf_queries"]

# --- list_docs() TTL cache ------------------------------------------------
_docs_cache_lock = threading.Lock()
_docs_cache: Optional[list[dict]] = None
_docs_cache_expires: Optional[datetime] = None
_DOCS_CACHE_TTL = timedelta(seconds=60)


def _get_cached_docs(store: VectorStore) -> list[dict]:
    """Return list_docs() result, using a 60 s TTL cache."""
    global _docs_cache, _docs_cache_expires
    now = datetime.now(timezone.utc)
    with _docs_cache_lock:
        if (
            _docs_cache is not None
            and _docs_cache_expires is not None
            and now < _docs_cache_expires
        ):
            return _docs_cache
    # Cache miss — fetch outside lock so we don't block other readers while scrolling.
    docs = store.list_docs()
    with _docs_cache_lock:
        _docs_cache = docs
        _docs_cache_expires = datetime.now(timezone.utc) + _DOCS_CACHE_TTL
    return docs


def invalidate_docs_cache() -> None:
    global _docs_cache, _docs_cache_expires
    with _docs_cache_lock:
        _docs_cache = None
        _docs_cache_expires = None


def _read_query_log(since: datetime) -> list[dict]:
    """Read JSONL query log, returning entries within the time window.

    Malformed lines are skipped with a warning (never raises).
    Returns empty list if log file is absent or empty.
    """
    entries = []
    try:
        if not os.path.exists(settings.query_log_path):
            return []
        with open(settings.query_log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts_str = entry["ts"]
                ts = datetime.fromisoformat(ts_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts >= since:
                    entries.append(entry)
            except (json.JSONDecodeError, KeyError, ValueError):
                logger.warning("Skipping malformed query log line: %r", line[:120])
    except Exception:
        logger.warning("Failed to read query log", exc_info=True)
    return entries


def _compute_overlap_pairs(store: VectorStore) -> list[dict]:
    """Compute document pairs with high content overlap.

    For each document, samples its chunk vectors (via Qdrant scroll) and searches
    the KB for near-duplicates. Pairs where > 30% of sampled chunks score ≥ 0.85
    against a chunk in another document are flagged.

    Acceptable at pre-launch scale (< 30 docs ≈ < 5 seconds).
    """
    docs = store.list_docs()
    if len(docs) < 2:
        return []

    pairs: list[dict] = []
    checked: set[frozenset] = set()

    for doc in docs:
        filename = doc["filename"]

        # Retrieve chunk vectors for this document via a filtered scroll
        chunk_points, _ = store._client.scroll(
            collection_name=store._collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="source_filename", match=MatchValue(value=filename)
                    )
                ]
            ),
            limit=200,
            with_vectors=True,
            with_payload=True,
        )
        if not chunk_points:
            continue

        sample = chunk_points

        overlap_against: dict[str, int] = {}
        for pt in sample:
            vec = np.array(pt.vector, dtype=np.float32)
            results = store.search(vec, top_k=2)
            for r in results:
                matched_fn = r["payload"].get("source_filename", "")
                if (
                    matched_fn
                    and matched_fn != filename
                    and r["score"] >= _OVERLAP_SCORE_THRESHOLD
                ):
                    overlap_against[matched_fn] = overlap_against.get(matched_fn, 0) + 1

        for other_fn, count in overlap_against.items():
            pct = count / len(sample)
            if pct >= _OVERLAP_PCT_THRESHOLD:
                pair_key = frozenset([filename, other_fn])
                if pair_key not in checked:
                    checked.add(pair_key)
                    pairs.append(
                        {
                            "doc_a": filename,
                            "doc_b": other_fn,
                            "overlap_pct": round(pct, 2),
                            "recommendation": "merge or remove one",
                        }
                    )

    return pairs


def assemble_kb_health(store: VectorStore) -> KBHealthResponse:
    """Assembles the full KB health metrics response."""
    try:
        docs = _get_cached_docs(store)
    except Exception as e:
        logger.error("Qdrant unavailable during kb_health: %s", e)
        # Re-raise with a stable message so the router can translate it to HTTP 503.
        raise RuntimeError("Qdrant unavailable") from e

    total_docs = len(docs)
    total_chunks = sum(d["chunk_count"] for d in docs)

    # --- Overlap pairs (cached, thundering-herd-safe) ---
    try:
        cached = health_cache.compute_if_needed(lambda: _compute_overlap_pairs(store))
    except Exception:
        logger.warning("Failed to compute overlap pairs", exc_info=True)
        cached = []

    overlapping_filenames = {p["doc_a"] for p in cached} | {p["doc_b"] for p in cached}

    doc_coverage = [
        DocCoverageItem(
            filename=d["filename"],
            chunk_count=d["chunk_count"],
            coverage_status="good"
            if d["chunk_count"] >= _COVERAGE_THIN_THRESHOLD
            else "thin",
            has_overlap_warning=d["filename"] in overlapping_filenames,
        )
        for d in docs
    ]

    high_overlap_pairs = [OverlapPair(**p) for p in cached]

    # --- Query log metrics ---
    window_start = datetime.now(timezone.utc) - timedelta(days=_LOG_WINDOW_DAYS)
    entries = _read_query_log(since=window_start)
    source_state = get_source_ledger_store().summarize_source_state(docs, entries)

    avg_match_score: Optional[float] = None
    retrieval_diversity_score: Optional[float] = None
    low_confidence_queries: list[LowConfidenceQuery] = []

    if entries:
        # avg_match_score: mean of top-1 scores across all queries in window
        all_top_scores = [e["scores"][0] for e in entries if e.get("scores")]
        if all_top_scores:
            avg_match_score = round(sum(all_top_scores) / len(all_top_scores), 4)

        # retrieval_diversity_score: avg distinct doc count in top-k results
        diversity_vals = []
        for e in entries:
            top_docs = e.get("top_docs", [])
            if top_docs:
                diversity_vals.append(len(set(top_docs)))
        if diversity_vals:
            retrieval_diversity_score = round(
                sum(diversity_vals) / len(diversity_vals), 2
            )

        # low_confidence_queries: recent queries with top score < threshold
        lc = [
            e
            for e in entries
            if e.get("scores") and e["scores"][0] < _LOW_CONFIDENCE_THRESHOLD
        ]
        lc.sort(key=lambda e: e.get("ts", ""), reverse=True)
        low_confidence_queries = [
            LowConfidenceQuery(
                ts=e["ts"],
                query_text=e["query_text"],
                max_score=round(e["scores"][0], 4),
                doc_matched=e.get("doc_matched"),
            )
            for e in lc[:_MAX_LOW_CONF_QUERIES]
        ]

    return KBHealthResponse(
        total_docs=total_docs,
        total_chunks=total_chunks,
        avg_match_score=avg_match_score,
        retrieval_diversity_score=retrieval_diversity_score,
        low_confidence_queries=low_confidence_queries,
        doc_coverage=doc_coverage,
        high_overlap_pairs=high_overlap_pairs,
        source_state=source_state,
        active_sources=source_state.active_source_count,
        active_source_count=source_state.active_source_count,
        superseded_sources=source_state.superseded_source_count,
        superseded_source_count=source_state.superseded_source_count,
        stale_sources=source_state.stale_source_count,
        stale_source_count=source_state.stale_source_count,
        active_hits=source_state.active_hit_count,
        active_hit_count=source_state.active_hit_count,
        superseded_hits=source_state.superseded_hit_count,
        superseded_hit_count=source_state.superseded_hit_count,
        last_refreshed_at=source_state.last_refreshed_at,
        updated_at=source_state.last_refreshed_at,
        stale_source_evidence=source_state.stale_source_evidence,
    )
