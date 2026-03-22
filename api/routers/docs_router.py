# api/routers/docs_router.py
from fastapi import APIRouter, Depends
from models import DocInfo, DeleteResponse
from services.vector_store import VectorStore
from dependencies import get_vector_store

router = APIRouter(prefix="/api")


@router.get("/docs", response_model=list[DocInfo])
def list_docs(store: VectorStore = Depends(get_vector_store)):
    return [DocInfo(**d) for d in store.list_docs()]


@router.delete("/docs/{doc_id}", response_model=DeleteResponse)
def delete_doc(doc_id: str, store: VectorStore = Depends(get_vector_store)):
    docs = store.list_docs()
    if not any(d["filename"] == doc_id for d in docs):
        return DeleteResponse(status="not_found")
    store.delete_by_filename(doc_id)
    return DeleteResponse(status="deleted")
