from fastapi import APIRouter, HTTPException, Depends
from models import KnowledgeSession, CreateSessionRequest
from services.session_store import SessionStore
from typing import List

router = APIRouter(prefix="/api/sessions")

def get_session_store():
    return SessionStore()

@router.post("", response_model=KnowledgeSession, status_code=201)
def create_session(req: CreateSessionRequest, store: SessionStore = Depends(get_session_store)):
    return store.create_session(req.raw_input, created_by=req.counsellor_id)

@router.get("/{session_id}", response_model=KnowledgeSession)
def get_session(session_id: str, store: SessionStore = Depends(get_session_store)):
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/{session_id}/analyze")
def analyze_session(session_id: str, store: SessionStore = Depends(get_session_store)):
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # Intent extraction logic will be integrated in Task 3
    return {"message": "Analysis triggered", "session_id": session_id}
