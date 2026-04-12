# api/routers/chat_router.py
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from config import settings
from dependencies import get_embedder, get_vector_store
from models import ChatRequest, ChatResponse, Citation, TrackRegistryEntry
from services import llm
from services.career_profiles import (
    CareerProfileStore,
    canonicalize_career_type_slug,
    get_career_profile_store,
    profile_to_context_block,
    resolve_career_type_from_intake,
)
from services.employer_store import EmployerEntityStore, get_employer_store
from services.embedder import Embedder
from services.vector_store import VectorStore
from services.track_drafts import TrackDraftStore

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


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
        scores = [c["score"] for c in chunks]
        doc_matched = chunks[0]["payload"]["source_filename"] if chunks else None
        top_docs = [c["payload"]["source_filename"] for c in chunks]
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "query_text": message,
            "scores": scores,
            "doc_matched": doc_matched,
            "top_docs": top_docs,
            "career_type": active_career_type,
        }
        with open(settings.query_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
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
        req_slug = canonicalize_career_type_slug(req.active_career_type)
        # Validate client-provided slug — get_profile logs WARNING and returns None on miss
        if req_slug and profile_store.get_profile(req_slug) is not None:
            active_slug = req_slug

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


@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    query_vec = embedder.encode(req.message)
    chunks = store.search(query_vec, top_k=5)

    # Career type resolution: intake → cosine → client fallback
    active_career_type = _resolve_career_type(req, query_vec, profile_store)

    # Profile injection: load YAML and format as context block (None → no injection)
    career_context: Optional[str] = None
    if active_career_type:
        profile = profile_store.get_profile(active_career_type)
        if profile:
            career_context = profile_to_context_block(profile)

    # Employer injection: include track-matched employers plus any employer the
    # student explicitly names in the current message.
    employer_block = employer_store.to_context_block(
        active_career_type=active_career_type,
        query_text=req.message,
    )
    employer_context: Optional[str] = employer_block if employer_block else None

    citations = [
        Citation(filename=c["payload"]["source_filename"],
                 excerpt=c["payload"]["text"][:150])
        for c in chunks
    ]
    response_text = llm.chat_with_context(
        message=req.message,
        resume_text=req.resume_text,
        chunks=chunks,
        history=[m.model_dump() for m in req.history],
        career_context=career_context,
        employer_context=employer_context,
    )
    _log_query(req.message, chunks, active_career_type)
    return ChatResponse(
        response=response_text,
        citations=citations,
        active_career_type=active_career_type,
    )
