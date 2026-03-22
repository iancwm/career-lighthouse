# api/routers/ingest_router.py
from fastapi import APIRouter, UploadFile, File, Depends
from models import IngestResponse
from services.ingestion import ingest_document
from services.embedder import Embedder
from services.vector_store import VectorStore
from dependencies import get_embedder, get_vector_store

router = APIRouter(prefix="/api")


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    file: UploadFile = File(...),
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
):
    content = await file.read()
    filename = file.filename or "upload.txt"
    # Delete existing chunks for this filename before re-ingesting
    store.delete_by_filename(filename)
    chunk_count = ingest_document(content, filename, embedder, store)
    return IngestResponse(doc_id=filename, chunk_count=chunk_count, status="ok")
