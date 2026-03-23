# api/routers/ingest_router.py
import logging
import numpy as np
from fastapi import APIRouter, Depends, UploadFile, File

logger = logging.getLogger(__name__)

from dependencies import get_embedder, get_vector_store
from models import IngestResponse
from services import health_cache
from services.embedder import Embedder
from services.ingestion import prepare_document
from services.vector_store import VectorStore

router = APIRouter(prefix="/api")

# Deduplication: if > 30% of new chunks score ≥ 0.85 against a chunk from a
# DIFFERENT document, emit a similarity_warning.
_DEDUP_SCORE_THRESHOLD = 0.85
_DEDUP_OVERLAP_PCT_THRESHOLD = 0.30

# For large docs (> 200 chunks) sample every 3rd chunk to cap Qdrant query count.
# 200 chunks at ~5ms each ≈ 1s; sampling keeps overhead < 400ms in practice.
_DEDUP_SAMPLE_THRESHOLD = 200
_DEDUP_SAMPLE_STEP = 3


def _check_deduplication(
    points: list[dict], store: VectorStore, filename: str
) -> tuple[float, list[str]]:
    """Check if the new document's content overlaps with existing KB documents.

    Called BEFORE the new doc is stored, so no self-matches are possible —
    delete_by_filename has already cleared any previous version of this file.

    Returns (overlap_pct, sorted list of overlapping filenames).
    """
    if not points:
        return 0.0, []

    sample = points[::_DEDUP_SAMPLE_STEP] if len(points) > _DEDUP_SAMPLE_THRESHOLD else points

    overlapping_docs: set[str] = set()
    overlap_count = 0

    for point in sample:
        results = store.search(np.array(point["vector"]), top_k=1)
        if results and results[0]["score"] >= _DEDUP_SCORE_THRESHOLD:
            matched_fn = results[0]["payload"].get("source_filename", "")
            if matched_fn and matched_fn != filename:
                overlap_count += 1
                overlapping_docs.add(matched_fn)

    overlap_pct = overlap_count / len(sample) if sample else 0.0
    return overlap_pct, sorted(overlapping_docs)


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
):
    content = await file.read()
    filename = file.filename or "upload.txt"

    # Prepare (parse + chunk + embed) BEFORE deleting the existing version.
    # This ensures that if parsing or embedding fails, the previous document
    # is not lost — the KB is never left in a deleted-but-not-stored state.
    points = prepare_document(content, filename, embedder)

    if not points:
        # Empty file or unsupported format — do not delete the existing version.
        return IngestResponse(
            doc_id=filename,
            chunk_count=0,
            status="error_empty",
        )

    # Delete existing chunks for this filename only after successful prepare.
    # This ensures dedup check compares against OTHER documents only.
    store.delete_by_filename(filename)

    # Deduplication check against existing KB (before storing).
    # Wrapped in try/except: if the check fails (e.g., Qdrant blip after delete),
    # the document is still stored — we never leave the KB in a deleted-but-not-stored state.
    try:
        overlap_pct, overlapping_docs = _check_deduplication(points, store, filename)
    except Exception:
        logger.warning(
            "Dedup check failed for %r — skipping similarity check, storing anyway",
            filename,
            exc_info=True,
        )
        overlap_pct, overlapping_docs = 0.0, []

    # Store the document
    if points:
        store.upsert(points)
        # Invalidate the overlap pairs cache — KB has changed
        health_cache.invalidate_overlap_cache()

    # Build similarity warning if overlap exceeds threshold
    similarity_warning: str | None = None
    if overlap_pct >= _DEDUP_OVERLAP_PCT_THRESHOLD and overlapping_docs:
        doc_list = ", ".join(overlapping_docs)
        similarity_warning = (
            f"{overlap_pct:.0%} of this document's content is highly similar to: "
            f"{doc_list}. Consider removing the duplicate before using this document."
        )

    return IngestResponse(
        doc_id=filename,
        chunk_count=len(points),
        status="ok",
        similarity_warning=similarity_warning,
        overlap_pct=round(overlap_pct, 4),
        overlapping_docs=overlapping_docs,
    )
