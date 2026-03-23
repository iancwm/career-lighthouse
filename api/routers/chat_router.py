# api/routers/chat_router.py
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from config import settings
from dependencies import get_embedder, get_vector_store
from models import ChatRequest, ChatResponse, Citation
from services import llm
from services.embedder import Embedder
from services.vector_store import VectorStore

router = APIRouter(prefix="/api")
logger = logging.getLogger(__name__)


def _log_query(message: str, chunks: list[dict]) -> None:
    """Append a query log entry to JSONL. Failures are non-fatal — chat must not break.

    Schema: { ts, query_text, scores, doc_matched, top_docs }
    - scores: all top-k similarity scores, descending
    - doc_matched: filename of the top-1 result (or null)
    - top_docs: filenames of all top-k results (for diversity analysis)

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
        }
        with open(settings.query_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        logger.warning("Failed to write query log entry — chat unaffected", exc_info=True)


@router.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
):
    query_vec = embedder.encode(req.message)
    chunks = store.search(query_vec, top_k=5)
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
    )
    _log_query(req.message, chunks)
    return ChatResponse(response=response_text, citations=citations)
