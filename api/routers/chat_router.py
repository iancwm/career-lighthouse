# api/routers/chat_router.py
import json
import logging
import os
try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request

from config import settings
from dependencies import get_embedder, get_student_insight_store, get_vector_store
from models_chat import ChatRequest, ChatResponse, Citation
from models_tracks import TrackRegistryEntry
from services import llm
from services.career_profiles import (
    CareerProfileStore,
    get_career_profile_store,
    profile_to_context_block,
    resolve_career_type_from_intake,
)
from services.employer_store import EmployerEntityStore, get_employer_store
from services.embedder import Embedder
from services.student_chat_insights import StudentChatInsightStore
from services.source_ledger import filter_active_chunks, get_source_ledger_store
from services.vector_store import VectorStore
from services.track_drafts import TrackDraftStore
from limiter import limiter

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _setting_bool(name: str, default: bool = False) -> bool:
    """Read a settings attribute and coerce to bool, accepting string truthy values (1/true/yes/on)."""
    value = getattr(settings, name, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _setting_int(name: str, default: int) -> int:
    """Read a settings attribute and coerce to int, returning default on missing or non-numeric values."""
    value = getattr(settings, name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@router.get("/ping")
def ping():
    return {"ping": "pong"}


@router.get("/tracks/active", response_model=list[TrackRegistryEntry])
def list_active_tracks():
    """Return the canonical list of active career tracks for student selection."""
    store = TrackDraftStore()
    return [t for t in store.list_registry() if t.status == "active"]


def _log_query(message: str, chunks: list[dict],
               active_career_type: Optional[str] = None) -> None:
    """Append a query log entry to JSONL. Failures are non-fatal — chat must not break.

    Schema: { ts, query_text, scores, doc_matched, top_docs, career_type }
    - scores: all top-k similarity scores, descending
    - doc_matched: filename of the top-1 result (or null)
    - top_docs: filenames of all top-k results (for diversity analysis)
    - career_type: resolved career type slug for this query (null if none)

    Note: admin test queries (POST /api/kb/test-query) are NOT logged here —
    that endpoint is called directly and skips this function by design, to avoid
    polluting the query log with admin probing activity.

    Note: this is a blocking file write. Safe because chat() is a sync def that
    FastAPI runs in a thread pool. If chat() is ever converted to async def,
    switch to aiofiles or run_in_executor.
    """
    try:
        scores = []
        for chunk in chunks:
            try:
                scores.append(float(chunk["score"]))
            except (TypeError, ValueError):
                scores.append(str(chunk["score"]))
        doc_matched = None
        if chunks:
            doc_matched = str(chunks[0]["payload"]["source_filename"])
        top_docs = [str(c["payload"]["source_filename"]) for c in chunks]
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "query_text": str(message),
            "scores": scores,
            "doc_matched": doc_matched,
            "top_docs": top_docs,
            "career_type": None if active_career_type is None else str(active_career_type),
        }
        with open(settings.query_log_path, "a", encoding="utf-8") as f:
            if fcntl is not None:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(json.dumps(entry) + "\n")
                f.flush()
                os.fsync(f.fileno())
            finally:
                if fcntl is not None:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        logger.warning("Failed to write query log entry — chat unaffected", exc_info=True)


def _resolve_career_type(
    req: ChatRequest,
    query_vec,
    profile_store: CareerProfileStore,
) -> Optional[str]:
    """Determine the active career type slug for this request.

    Resolution order (from message 2 onward):
      1. Query-time cosine match >= threshold → override with matched type
      2. active_career_type from request (client echo of prior response) → use as fallback
      3. Neither → None (LLM will ask for clarification)

    On message 1:
      intake_context.interest → rule-based slug → used as active_career_type
      (Cosine also checked; if it scores >= threshold it overrides intake, which is fine.)
    """
    # Rule-based intake resolution (message 1)
    intake_slug: Optional[str] = None
    if req.intake_context and req.intake_context.interest:
        intake_slug = resolve_career_type_from_intake(req.intake_context.interest)

    if intake_slug:
        return intake_slug

    active_slug: Optional[str] = None
    if req.active_career_type:
        # Validate client-provided slug — get_profile logs WARNING and returns None on miss
        if profile_store.get_profile(req.active_career_type) is not None:
            active_slug = req.active_career_type

    # Deterministic keyword matching only runs when no active career type is set.
    if active_slug is None:
        keyword_slug = profile_store.match_career_type_keywords(req.message)
        if keyword_slug:
            return keyword_slug

    # Query-time cosine match remains as a final fallback for legacy profiles.
    cosine_slug = profile_store.match_career_type(query_vec)
    if cosine_slug:
        return cosine_slug
    return active_slug


def _humanize_source_name(filename: str) -> str:
    """Convert a source filename to a title-cased display name by stripping extension and replacing separators."""
    stem = Path(filename).stem
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    if not cleaned:
        return filename
    return cleaned.title()


def _chunk_lifecycle(payload: dict) -> str:
    """Resolve a chunk's lifecycle state from its payload, falling back to the source ledger if not embedded."""
    lifecycle = str(payload.get("lifecycle") or payload.get("status") or "").strip().lower()
    if lifecycle:
        return lifecycle
    filename = str(payload.get("source_filename") or payload.get("filename") or "").strip()
    record = get_source_ledger_store().get_record(filename)
    return str(record.get("lifecycle") or "active") if record else "active"


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10 per minute")
def chat(
    request: Request,
    req: ChatRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    insight_store: StudentChatInsightStore = Depends(get_student_insight_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    # SYNC ONLY: StudentChatInsightStore.index_message() and _log_query() are
    # blocking and thread-pool safe only while chat() remains sync def.
    query_vec = embedder.encode(req.message)
    chunks = store.search(query_vec, top_k=5)
    active_chunks = filter_active_chunks(chunks)

    # Career type resolution: intake → cosine → client fallback
    active_career_type = _resolve_career_type(req, query_vec, profile_store)

    # Profile injection: load YAML and format as context block (None → no injection)
    career_context: Optional[str] = None
    profile_top_employers: Optional[list[str]] = None
    if active_career_type:
        profile = profile_store.get_profile(active_career_type)
        if profile:
            career_context = profile_to_context_block(profile)
            profile_top_employers = profile.get("top_employers_smu") or None

    # Employer injection: include track-matched employers, profile top employers,
    # and any employer the student explicitly names in the current message.
    employer_block = employer_store.to_context_block(
        active_career_type=active_career_type,
        query_text=req.message,
        profile_top_employers=profile_top_employers,
    )
    employer_context: Optional[str] = employer_block if employer_block else None

    citations = [
        Citation(
            filename=c["payload"]["source_filename"],
            excerpt=c["payload"]["text"][:150],
            source_name=_humanize_source_name(str(c["payload"].get("source_filename", "unknown"))),
            updated_at=str(c["payload"].get("upload_timestamp") or c["payload"].get("updated_at") or ""),
            source_lifecycle=_chunk_lifecycle(c["payload"]),
        )
        for c in active_chunks
    ]
    response_text = llm.chat_with_context(
        message=req.message,
        resume_text=req.resume_text,
        chunks=active_chunks,
        history=[m.model_dump() for m in req.history],
        career_context=career_context,
        employer_context=employer_context,
    )
    if _setting_bool("student_chat_insights_enabled") and len(req.message) >= _setting_int("student_chat_embedding_min_chars", 20):
        try:
            message_id = insight_store.index_message(
                text=req.message,
                embedder=embedder,
                active_career_type=active_career_type,
                intake_context=req.intake_context,
                has_resume=bool(req.resume_text),
            )
            logger.info(
                "student insight indexed",
                extra={
                    "collection": settings.student_chat_collection_name,
                    "message_id": message_id,
                },
            )
        except Exception as exc:
            logger.warning(
                "student insight write failed: %s",
                exc,
                extra={"collection": settings.student_chat_collection_name},
            )
    _log_query(req.message, active_chunks, active_career_type)
    return ChatResponse(
        response=response_text,
        citations=citations,
        active_career_type=active_career_type,
    )
