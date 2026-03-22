# api/routers/brief_router.py
from fastapi import APIRouter, Depends
from models import BriefRequest, BriefResponse
from services.embedder import Embedder
from services.vector_store import VectorStore
from services import llm
from dependencies import get_embedder, get_vector_store

router = APIRouter(prefix="/api")


@router.post("/brief", response_model=BriefResponse)
def brief(
    req: BriefRequest,
    embedder: Embedder = Depends(get_embedder),
    store: VectorStore = Depends(get_vector_store),
):
    query_vec = embedder.encode(req.resume_text[:500])  # embed first 500 chars
    chunks = store.search(query_vec, top_k=10)
    brief_text = llm.generate_brief(resume_text=req.resume_text, chunks=chunks)
    return BriefResponse(brief=brief_text)
