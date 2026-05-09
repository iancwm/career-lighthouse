"""KB ingestion, health, and observability endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.requests import Request

from config import settings as config_settings
from dependencies import get_embedder, get_vector_store, require_admin_key
from models_kb import (
    KBAnalysisResult,
    KBCommitRequest,
    KBCommitResponse,
    KBHealthResponse,
    LLMTraceEntry,
    LLMWorkflowDetail,
    LLMWorkflowSummary,
    TestQueryResult,
)
import routers.kb_router as kb_router_compat
from routers.kb_router_shared import TestQueryRequest, logger
from services import health_cache, kb_health as kb_health_service
from services.career_profiles import CareerProfileStore, get_career_profile_store
from services.employer_store import EmployerEntityStore, get_employer_store
from services.embedder import Embedder
from services.kb_health import assemble_kb_health, invalidate_docs_cache
from services.kb_ingestion_service import analyse_counsellor_input
from services.kb_writer import apply_employer_diff, apply_profile_diff, upsert_kb_chunks
from services.trace_adapter import (
    get_workflow_detail,
    list_recent as list_recent_llm_traces,
    list_workflow_summaries,
)
from services.vector_store import VectorStore

router = APIRouter(prefix="/api/kb", dependencies=[Depends(require_admin_key)])


@router.post("/analyse", response_model=KBAnalysisResult)
def analyse(
    request: Request,
    text: str = Form(None),
    source_type: str = Form("note"),
    file: UploadFile = File(None),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Analyse counsellor input and return a structured KB diff."""
    if source_type == "file" and file is not None:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > kb_router_compat.settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds maximum upload size ({kb_router_compat.settings.max_upload_bytes // (1024 * 1024)}MB).",
            )

    return analyse_counsellor_input(
        text=text,
        source_type=source_type,
        file=file,
        embedder=embedder,
        store=store,
        profile_store=profile_store,
        employer_store=employer_store,
    )


@router.post("/commit-analysis", response_model=KBCommitResponse)
def commit_analysis(
    req: KBCommitRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
    profile_store: CareerProfileStore = Depends(get_career_profile_store),
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Commit a counsellor-approved KB diff."""
    max_chunks = 10
    max_chunk_text = 4000
    if len(req.new_chunks) > max_chunks:
        raise HTTPException(
            status_code=422, detail=f"Too many chunks (max {max_chunks})."
        )
    for chunk in req.new_chunks:
        if chunk.source_type not in ("note", "file"):
            raise HTTPException(status_code=422, detail="Invalid source_type.")
        if len(chunk.text) > max_chunk_text:
            raise HTTPException(
                status_code=422, detail=f"Chunk text exceeds {max_chunk_text} chars."
            )

    chunk_result = upsert_kb_chunks(
        req.new_chunks, vector_store=store, embedder=embedder, source="commit-analysis"
    )

    profiles_updated: list[str] = []
    for slug, field_changes in req.profile_updates.items():
        result = apply_profile_diff(
            slug,
            field_changes,
            create_missing=False,
            skip_invalid=True,
            source="commit-analysis",
        )
        if result.changed_fields:
            profiles_updated.append(slug)
            logger.info(
                "commit-analysis: updated profile %r fields: %s",
                slug,
                result.changed_fields,
            )
        elif not result.skipped_missing:
            logger.info("commit-analysis: profile %r had no valid field updates", slug)

    employers_updated: list[str] = []
    for slug, field_changes in req.employer_updates.items():
        result = apply_employer_diff(
            slug,
            field_changes,
            create_missing=False,
            snapshot=True,
            skip_invalid=True,
            source="commit-analysis",
        )
        if result.changed_fields:
            employers_updated.append(slug)
            logger.info(
                "commit-analysis: updated employer %r fields: %s",
                slug,
                result.changed_fields,
            )
        elif not result.skipped_missing:
            logger.info("commit-analysis: employer %r had no valid field updates", slug)

    health_cache.invalidate_overlap_cache()
    invalidate_docs_cache()
    profile_store.invalidate()
    employer_store.invalidate()

    return KBCommitResponse(
        status="ok",
        chunks_added=chunk_result.chunks_added,
        profiles_updated=profiles_updated,
        employers_updated=employers_updated,
    )


@router.post("/test-query", response_model=list[TestQueryResult])
def test_query(
    req: TestQueryRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
):
    """Test a query against the KB. Returns top-5 chunks with similarity scores."""
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
    except Exception as exc:
        logger.error("Qdrant unavailable during test-query: %s", exc)
        raise HTTPException(status_code=503, detail="KB unavailable")


@router.get("/health", response_model=KBHealthResponse)
def kb_health(
    store: VectorStore = Depends(get_vector_store),
):
    """KB health metrics for the admin dashboard."""
    try:
        if (
            kb_health_service.settings is config_settings
            and kb_router_compat.settings is not config_settings
        ):
            kb_health_service.settings = kb_router_compat.settings
        return assemble_kb_health(store)
    except Exception as exc:
        if "Qdrant" in str(exc) or "VectorStore" in str(type(exc).__name__):
            logger.error("KB health failed: %s", exc)
            raise HTTPException(status_code=503, detail="KB unavailable")
        raise


@router.get("/llm-traces", response_model=list[LLMTraceEntry])
def llm_traces(
    limit: int = 50,
    session_id: str | None = None,
    operation: str | None = None,
    status: str | None = None,
):
    """Return recent structured LLM trace entries for admin debugging."""
    if limit < 1:
        raise HTTPException(status_code=422, detail="limit must be at least 1")
    if limit > 200:
        limit = 200
    return list_recent_llm_traces(
        limit=limit,
        session_id=session_id,
        operation=operation,
        status=status,
        trace_path=getattr(kb_router_compat.settings, "llm_trace_log_path", ""),
    )


@router.get("/workflow-summaries", response_model=list[LLMWorkflowSummary])
def workflow_summaries(
    limit: int = 25,
    session_id: str | None = None,
    status: str | None = None,
):
    """Return lean session-analysis workflow summaries for polling surfaces."""
    if limit < 1:
        raise HTTPException(status_code=422, detail="limit must be at least 1")
    if limit > 200:
        limit = 200
    return list_workflow_summaries(limit=limit, session_id=session_id, status=status)


@router.get("/workflow-detail", response_model=LLMWorkflowDetail)
def workflow_detail(
    session_id: str | None = None,
    workflow_id: str | None = None,
):
    """Return a normalized session-analysis workflow detail object."""
    if not session_id and not workflow_id:
        raise HTTPException(
            status_code=422, detail="session_id or workflow_id is required"
        )
    detail = get_workflow_detail(session_id=session_id, workflow_id=workflow_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Workflow detail not found")
    return detail
