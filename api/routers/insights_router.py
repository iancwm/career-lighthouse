from fastapi import APIRouter, Depends
from qdrant_client.models import DatetimeRange, FieldCondition, Filter, MatchValue

from config import settings
from dependencies import get_embedder, get_student_insight_store, require_admin_key
from models_insights import (
    StudentQuestionResult,
    StudentQuestionSearchRequest,
    StudentQuestionSearchResponse,
)
from services.embedder import Embedder
from services.student_chat_insights import StudentChatInsightStore

router = APIRouter(prefix="/api/insights", dependencies=[Depends(require_admin_key)])


def build_filters(req: StudentQuestionSearchRequest) -> Filter | None:
    """Convert a StudentQuestionSearchRequest into a Qdrant Filter, omitting fields disabled by feature flags."""
    must: list[FieldCondition] = []
    if req.career_type:
        must.append(FieldCondition(key="active_career_type", match=MatchValue(value=req.career_type)))
    if req.background and settings.student_chat_store_background:
        must.append(FieldCondition(key="background", match=MatchValue(value=req.background)))
    if req.region and settings.student_chat_store_region:
        must.append(FieldCondition(key="region", match=MatchValue(value=req.region)))
    if req.date_from or req.date_to:
        must.append(
            FieldCondition(
                key="timestamp",
                range=DatetimeRange(gte=req.date_from, lte=req.date_to),
            )
        )
    return Filter(must=must) if must else None


def _filters_applied(req: StudentQuestionSearchRequest) -> dict:
    """Build the filters_applied echo dict for the search response, masking fields disabled by feature flags."""
    return {
        "career_type": req.career_type,
        "date_from": req.date_from,
        "date_to": req.date_to,
        "background": req.background if settings.student_chat_store_background else None,
        "region": req.region if settings.student_chat_store_region else None,
    }


def _as_optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


@router.post("/student-questions/search", response_model=StudentQuestionSearchResponse)
def search_student_questions(
    req: StudentQuestionSearchRequest,
    insight_store: StudentChatInsightStore = Depends(get_student_insight_store),
    embedder: Embedder = Depends(get_embedder),
) -> StudentQuestionSearchResponse:
    supports_background_filter = settings.student_chat_store_background
    supports_region_filter = settings.student_chat_store_region

    if not settings.student_chat_insights_enabled:
        return StudentQuestionSearchResponse(
            results=[],
            total_returned=0,
            filters_applied=_filters_applied(req),
            insights_enabled=False,
            supports_background_filter=supports_background_filter,
            supports_region_filter=supports_region_filter,
        )

    top_k = req.top_k or settings.student_chat_top_k_default
    filters = build_filters(req)

    # Embedder/query vector must stay model-compatible with indexed points.
    # If the embedding model changes, re-index the insight collection.
    query_vector = embedder.encode(req.query)
    raw_results = insight_store.search(vector=query_vector, top_k=top_k, filters=filters)

    results: list[StudentQuestionResult] = []
    for row in raw_results:
        payload = row.get("payload") or {}
        results.append(
            StudentQuestionResult(
                message_id=str(payload.get("message_id") or ""),
                text=str(payload.get("text") or ""),
                timestamp=str(payload.get("timestamp") or ""),
                active_career_type=_as_optional_str(payload.get("active_career_type")),
                background=_as_optional_str(payload.get("background")),
                region=_as_optional_str(payload.get("region")),
                score=float(row.get("score") or 0.0),
                source_label="Student chat",
            )
        )

    return StudentQuestionSearchResponse(
        results=results,
        total_returned=len(results),
        filters_applied=_filters_applied(req),
        insights_enabled=True,
        supports_background_filter=supports_background_filter,
        supports_region_filter=supports_region_filter,
    )
