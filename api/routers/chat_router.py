# api/routers/chat_router.py
from fastapi import APIRouter, Depends
from models import ChatRequest, ChatResponse, Citation
from services.embedder import Embedder
from services.vector_store import VectorStore
from services import llm
from dependencies import get_embedder, get_vector_store

router = APIRouter(prefix="/api")


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
    return ChatResponse(response=response_text, citations=citations)
