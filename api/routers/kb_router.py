# api/routers/kb_router.py
"""KB observability endpoints.

POST /api/kb/test-query  — test a query, returns top-5 chunks with scores
GET  /api/kb/health      — KB health metrics for the admin dashboard

Auth note: These endpoints are protected by Next.js middleware (web/middleware.ts)
which blocks unauthenticated requests to /admin. No FastAPI-level auth guard is
implemented here — accepted risk for pre-launch private network deployment.
TODO: Add Depends() auth guard before any public-facing deployment.
      See TODOS.md: "FastAPI-level auth on /api/kb/* endpoints"
"""
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dependencies import get_embedder, get_vector_store
from models import (
    DocCoverageItem,
    KBHealthResponse,
    LowConfidenceQuery,
    OverlapPair,
    TestQueryResult,
)
from services import health_cache
from services.career_profiles import CareerProfileStore, get_career_profile_store
from services.embedder import Embedder  # used by test-query only
from services.vector_store import VectorStore
from config import settings

router = APIRouter(prefix="/api/kb")
logger = logging.getLogger(__name__)

# Thresholds
_COVERAGE_THIN_THRESHOLD = 20       # chunks; below this → "thin"
_LOW_CONFIDENCE_THRESHOLD = 0.35    # max_score below this → low-confidence query
_OVERLAP_SCORE_THRESHOLD = 0.85     # similarity score that indicates duplicate chunk
_OVERLAP_PCT_THRESHOLD = 0.30       # fraction of chunks that must overlap to flag pair
_LOG_WINDOW_DAYS = 7                # rolling window for query log metrics
_MAX_LOW_CONF_QUERIES = 20          # max items in low_confidence_queries list


class TestQueryRequest(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

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
            for line in f:
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
                    logger.warning(
                        "Skipping malformed query log line: %r", line[:120]
                    )
    except Exception:
        logger.warning("Failed to read query log", exc_info=True)
    return entries


def _compute_overlap_pairs(store: VectorStore) -> list[dict]:
    """Compute document pairs with high content overlap.

    For each document, samples its chunk vectors (via Qdrant scroll) and searches
    the KB for near-duplicates. Pairs where > 30% of sampled chunks score ≥ 0.85
    against a chunk in another document are flagged.

    Acceptable at pre-launch scale (< 30 docs ≈ < 5 seconds).
    TODO: cache this result; invalidate on each ingest when KB exceeds 30 docs.
          The invalidation hook is already wired in ingest_router.py via health_cache.
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue

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
                must=[FieldCondition(key="source_filename", match=MatchValue(value=filename))]
            ),
            limit=200,
            with_vectors=True,
            with_payload=True,
        )
        if not chunk_points:
            continue

        # Note: scroll is capped at limit=200 so len(chunk_points) <= 200 always.
        # Sampling for very large docs would require Qdrant scroll pagination; deferred
        # until KB exceeds pre-launch scale. Use all retrieved chunks for now.
        sample = chunk_points

        overlap_against: dict[str, int] = {}
        for pt in sample:
            vec = np.array(pt.vector, dtype=np.float32)
            results = store.search(vec, top_k=2)
            for r in results:
                matched_fn = r["payload"].get("source_filename", "")
                if matched_fn and matched_fn != filename and r["score"] >= _OVERLAP_SCORE_THRESHOLD:
                    overlap_against[matched_fn] = overlap_against.get(matched_fn, 0) + 1

        for other_fn, count in overlap_against.items():
            pct = count / len(sample)
            if pct >= _OVERLAP_PCT_THRESHOLD:
                pair_key = frozenset([filename, other_fn])
                if pair_key not in checked:
                    checked.add(pair_key)
                    pairs.append({
                        "doc_a": filename,
                        "doc_b": other_fn,
                        "overlap_pct": round(pct, 2),
                        "recommendation": "merge or remove one",
                    })

    return pairs


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/career-profiles")
def career_profiles(
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    """List all loaded career profiles with metadata (admin use only).

    Returns structured metadata from the 'structured:' YAML block alongside
    basic completeness indicators. Does not return the full profile content.

    Auth note: protected by Next.js middleware same as /health and /test-query.
    See TODOS.md: "FastAPI-level auth on /api/kb/* endpoints"
    """
    return profile_store.list_profiles()


@router.post("/test-query", response_model=list[TestQueryResult])
def test_query(
    req: TestQueryRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
):
    """Test a query against the KB. Returns top-5 chunks with similarity scores.

    Admin test queries are NOT logged to the query log — this is intentional.
    Logging admin probes would pollute the low-confidence query analysis with
    queries that don't reflect real student usage.
    """
    try:
        query_vec = embedder.encode(req.query)
        chunks = store.search(query_vec, top_k=5)
        return [
            TestQueryResult(
                source_filename=c["payload"]["source_filename"],
                excerpt=c["payload"]["text"][:300],
                score=round(c["score"], 4),
            )
            for c in chunks
        ]
    except Exception as e:
        logger.error("Qdrant unavailable during test-query: %s", e)
        raise HTTPException(status_code=503, detail="KB unavailable")


@router.get("/health", response_model=KBHealthResponse)
def kb_health(
    store: VectorStore = Depends(get_vector_store),
):
    """KB health metrics for the admin dashboard.

    Returns doc coverage, query log metrics, and overlap pair analysis.
    If Qdrant is unavailable, returns HTTP 503.
    """
    try:
        # TODO: cache list_docs() result (60s TTL) when KB exceeds ~200 documents.
        # Currently O(n_chunks) scroll on every call — acceptable at pre-launch scale.
        docs = store.list_docs()
    except Exception as e:
        logger.error("Qdrant unavailable during kb_health: %s", e)
        raise HTTPException(status_code=503, detail="KB unavailable")

    total_docs = len(docs)
    total_chunks = sum(d["chunk_count"] for d in docs)

    # --- Overlap pairs (cached) ---
    cached = health_cache.get_overlap_pairs()
    if cached is None:
        try:
            cached = _compute_overlap_pairs(store)
            health_cache.set_overlap_pairs(cached)
        except Exception:
            logger.warning("Failed to compute overlap pairs", exc_info=True)
            cached = []

    overlapping_filenames = {p["doc_a"] for p in cached} | {p["doc_b"] for p in cached}

    doc_coverage = [
        DocCoverageItem(
            filename=d["filename"],
            chunk_count=d["chunk_count"],
            coverage_status="good" if d["chunk_count"] >= _COVERAGE_THIN_THRESHOLD else "thin",
            has_overlap_warning=d["filename"] in overlapping_filenames,
        )
        for d in docs
    ]

    high_overlap_pairs = [OverlapPair(**p) for p in cached]

    # --- Query log metrics ---
    window_start = datetime.now(timezone.utc) - timedelta(days=_LOG_WINDOW_DAYS)
    entries = _read_query_log(since=window_start)

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
        lc = [e for e in entries if e.get("scores") and e["scores"][0] < _LOW_CONFIDENCE_THRESHOLD]
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
    )
