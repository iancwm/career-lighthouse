from fastapi import APIRouter, HTTPException, Depends
from models import KnowledgeSession, CreateSessionRequest, IntentCard
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
def analyze_session(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
):
    """Extract intents from session raw_input using LLM."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Gather existing knowledge for context
    from services.career_profiles import get_career_profile_store
    from services.employer_store import get_employer_store

    profile_store = get_career_profile_store()
    employer_store = get_employer_store()

    existing_tracks = []
    try:
        profiles = profile_store.list_profiles()
        existing_tracks = list(profiles)
    except Exception:
        pass  # Non-fatal — LLM works without track context

    existing_employers = []
    try:
        employers = employer_store.list_employers()
        existing_employers = list(employers)
    except Exception:
        pass  # Non-fatal

    # Call LLM
    from services.llm import generate_session_intents
    result = generate_session_intents(
        raw_input=session.raw_input,
        existing_tracks=existing_tracks,
        existing_employers=existing_employers,
    )

    # Build IntentCard objects
    cards = []
    for card_data in result.get("cards", []):
        card = IntentCard(**card_data)
        cards.append(card)

    already_covered = result.get("already_covered", [])

    # Store on session
    session.intent_cards = [c.model_dump() for c in cards]
    session.status = "analyzed"
    store.save_session(session)

    return {
        "session_id": session.id,
        "cards": [c.model_dump() for c in cards],
        "already_covered": already_covered,
    }
