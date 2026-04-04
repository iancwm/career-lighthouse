# api/routers/kb_router.py
"""KB observability and diff-first ingestion endpoints.

POST /api/kb/test-query       — test a query, returns top-5 chunks with scores
GET  /api/kb/health           — KB health metrics for the admin dashboard
POST /api/kb/analyse          — analyse counsellor input, return diff (no writes)
POST /api/kb/commit-analysis  — commit a counsellor-approved diff to KB and YAMLs

Auth note: These endpoints are protected by Next.js middleware (web/middleware.ts)
which blocks unauthenticated requests to /admin. No FastAPI-level auth guard is
implemented here — accepted risk for pre-launch private network deployment.
TODO: Add Depends() auth guard before any public-facing deployment.
      See TODOS.md: "FastAPI-level auth on /api/kb/* endpoints"
"""
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import yaml
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from dependencies import get_embedder, get_vector_store
from models import (
    AlreadyCovered,
    DocCoverageItem,
    KBAnalysisResult,
    KBCommitRequest,
    KBCommitResponse,
    KBHealthResponse,
    LowConfidenceQuery,
    NewChunk,
    OverlapPair,
    ProfileFieldChange,
    TestQueryResult,
)
from services import health_cache
from services.career_profiles import CareerProfileStore, get_career_profile_store
from services.embedder import Embedder
from services.ingestion import chunk_text, parse_file
from services.vector_store import VectorStore
from services import llm as llm_service
from config import settings
from cfg import kb_cfg

router = APIRouter(prefix="/api/kb")
logger = logging.getLogger(__name__)

_thresholds = kb_cfg["thresholds"]
_COVERAGE_THIN_THRESHOLD = _thresholds["coverage_thin"]
_LOW_CONFIDENCE_THRESHOLD = _thresholds["low_confidence"]
_OVERLAP_SCORE_THRESHOLD = _thresholds["overlap_score"]
_OVERLAP_PCT_THRESHOLD = _thresholds["overlap_pct"]
_LOG_WINDOW_DAYS = kb_cfg["log_window_days"]
_MAX_LOW_CONF_QUERIES = kb_cfg["max_low_conf_queries"]


class TestQueryRequest(BaseModel):
    query: str


# ---------------------------------------------------------------------------
# Sprint 3 helpers
# ---------------------------------------------------------------------------

def _first_sentence(text: str, max_chars: int = 120) -> str:
    """Extract first sentence up to max_chars — mirrors notebook spec."""
    if not text:
        return ""
    text = str(text).strip()
    dot = text.find(".")
    if dot != -1 and dot < max_chars:
        return text[: dot + 1]
    return text[:max_chars]


def _build_profile_summary(store: CareerProfileStore) -> str:
    """Build the CURRENT CAREER PROFILE FIELDS block for the diff prompt."""
    profiles = store.list_profiles()
    lines = []
    for meta in profiles:
        slug = meta["slug"]
        profile = store.get_profile(slug)
        if not profile:
            continue
        ep = _first_sentence(str(profile.get("ep_sponsorship", "")))
        compass = _first_sentence(str(profile.get("compass_score_typical", "")))
        timeline = _first_sentence(str(profile.get("recruiting_timeline", "")))
        notes = _first_sentence(str(profile.get("notes", "")))
        lines.append(
            f"{slug}: ep_sponsorship={ep} | compass={compass} | "
            f"recruiting_timeline={timeline} | notes={notes}"
        )
    return "\n".join(lines)


def _profiles_dir() -> Path:
    return Path(os.environ.get(
        "CAREER_PROFILES_DIR",
        str(Path(__file__).parent.parent.parent / "knowledge" / "career_profiles"),
    ))


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


@router.post("/analyse", response_model=KBAnalysisResult)
def analyse(
    text: str = Form(None),
    source_type: str = Form("note"),
    file: UploadFile = File(None),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    """Analyse counsellor input and return a structured KB diff.

    Accepts either a text note (form field 'text') or a file upload.
    Does NOT write to the KB — returns KBAnalysisResult for counsellor review.

    Auth note: protected by Next.js middleware only (same as /health).
    TODO: Add Depends() auth guard — see TODOS.md.
    """
    # --- 1. Extract counsellor input text ---
    if source_type == "file" and file is not None:
        raw_bytes = file.file.read()
        fname = file.filename or "upload.txt"
        try:
            counsellor_input = parse_file(raw_bytes, fname)
        except Exception as exc:
            logger.warning("analyse: failed to parse uploaded file %r: %s", fname, exc)
            raise HTTPException(status_code=422, detail="Could not extract text from the uploaded file.")
        source_label = fname
    else:
        if not text or not text.strip():
            raise HTTPException(status_code=422, detail="Provide either 'text' or a file upload.")
        counsellor_input = text.strip()
        source_label = "counsellor_note"

    # --- 2. Embed and retrieve top-10 KB chunks ---
    try:
        chunks_for_query = chunk_text(counsellor_input, max_tokens=256)
        query_text = chunks_for_query[0] if chunks_for_query else counsellor_input
        query_vec = embedder.encode(query_text)
        retrieved = store.search(query_vec, top_k=10)
    except Exception as exc:
        logger.error("analyse: KB search failed: %s", exc)
        raise HTTPException(status_code=503, detail="KB unavailable")

    # --- 3. Build profile summary for the diff prompt ---
    profile_summary = _build_profile_summary(profile_store)

    # --- 4. Call Claude ---
    try:
        raw = llm_service.analyse_kb_input(counsellor_input, retrieved, profile_summary)
    except ValueError as exc:
        logger.warning("analyse: Claude returned malformed JSON: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="Analysis failed — please try again or rephrase your input.",
        )
    except Exception as exc:
        logger.error("analyse: LLM call failed: %s", exc)
        raise HTTPException(status_code=503, detail="Analysis service unavailable")

    # --- 5. Validate and fill chunk_ids ---
    try:
        result = KBAnalysisResult(**raw)
    except Exception as exc:
        logger.warning("analyse: Pydantic validation failed: %s | raw=%r", exc, str(raw)[:300])
        raise HTTPException(
            status_code=422,
            detail="Analysis failed — please try again or rephrase your input.",
        )

    for i, chunk in enumerate(result.new_chunks):
        chunk.source_label = source_label
        chunk.source_type = source_type if source_type in ("note", "file") else "note"
        # Content-based chunk_id: same text → same ID (idempotent re-commit),
        # different text → different ID (no clobbering across distinct notes).
        content_key = chunk.text.strip()[:120]
        chunk.chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{source_label}::{content_key}"))

    return result


@router.post("/commit-analysis", response_model=KBCommitResponse)
def commit_analysis(
    req: KBCommitRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
):
    """Commit a counsellor-approved KB diff.

    Upserts new chunks to Qdrant, writes updated YAML fields to profile files,
    then invalidates caches so changes are reflected immediately.

    Auth note: protected by Next.js middleware only (same as /health).
    TODO: Add Depends() auth guard — see TODOS.md.
    """
    # Basic input validation — guard against malformed or outsized payloads
    _MAX_CHUNKS = 10
    _MAX_CHUNK_TEXT = 4000  # chars
    if len(req.new_chunks) > _MAX_CHUNKS:
        raise HTTPException(status_code=422, detail=f"Too many chunks (max {_MAX_CHUNKS}).")
    for chunk in req.new_chunks:
        if chunk.source_type not in ("note", "file"):
            raise HTTPException(status_code=422, detail="Invalid source_type.")
        if len(chunk.text) > _MAX_CHUNK_TEXT:
            raise HTTPException(status_code=422, detail=f"Chunk text exceeds {_MAX_CHUNK_TEXT} chars.")

    profiles_updated: list[str] = []

    # --- 1. Upsert new chunks ---
    timestamp = datetime.now(timezone.utc).isoformat()
    points = []
    # Track file source_filenames that need dedup-delete before upsert
    file_source_filenames: set[str] = set()
    for chunk in req.new_chunks:
        if not chunk.text.strip():
            continue
        if not chunk.chunk_id:
            chunk.chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{chunk.source_label}-{id(chunk)}"))
        # Derive source_filename from source_label (matches list_docs() convention)
        if chunk.source_type == "note":
            date_suffix = datetime.now(timezone.utc).strftime("%Y%m%d")
            source_filename = f"counsellor_note_{date_suffix}"
        else:
            source_filename = chunk.source_label
            file_source_filenames.add(source_filename)

        try:
            vector = embedder.encode(chunk.text)
        except Exception as exc:
            logger.warning("commit-analysis: embed failed for chunk %r: %s", chunk.chunk_id, exc)
            raise HTTPException(status_code=503, detail="Embedding service unavailable")

        points.append({
            "id": chunk.chunk_id,
            "vector": vector,
            "payload": {
                "source_filename": source_filename,
                "chunk_index": 0,
                "upload_timestamp": timestamp,
                "text": chunk.text,
                "career_type": chunk.career_type,
            },
        })

    if points:
        # Delete previous version of any re-submitted files before upserting
        for fn in file_source_filenames:
            try:
                store.delete_by_filename(fn)
            except Exception as exc:
                logger.warning("commit-analysis: delete_by_filename(%r) failed: %s", fn, exc)
        try:
            store.upsert(points)
        except Exception as exc:
            logger.error("commit-analysis: Qdrant upsert failed: %s", exc)
            raise HTTPException(status_code=503, detail="KB unavailable")

    # --- 2. Write profile YAML updates ---
    pdir = _profiles_dir()
    for slug, field_changes in req.profile_updates.items():
        yaml_path = pdir / f"{slug}.yaml"
        if not yaml_path.exists():
            logger.warning("commit-analysis: profile %r not found on disk — skipping", slug)
            continue
        try:
            with open(yaml_path, encoding="utf-8") as f:
                profile = yaml.safe_load(f) or {}
            for field_name, change in field_changes.items():
                profile[field_name] = change.new
            # Atomic write: write to temp file then rename
            tmp = yaml_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                yaml.safe_dump(profile, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            tmp.replace(yaml_path)
            profiles_updated.append(slug)
            logger.info("commit-analysis: updated profile %r fields: %s", slug, list(field_changes.keys()))
        except Exception as exc:
            logger.error("commit-analysis: failed to write profile %r: %s", slug, exc)
            raise HTTPException(status_code=500, detail=f"Failed to write profile '{slug}'")

    # --- 3. Invalidate caches ---
    health_cache.invalidate_overlap_cache()
    profile_store.invalidate()

    return KBCommitResponse(
        status="ok",
        chunks_added=len(points),
        profiles_updated=profiles_updated,
    )


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
