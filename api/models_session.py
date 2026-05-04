from typing import Any

from pydantic import BaseModel

from models_kb import TrackGuidance


class KnowledgeSession(BaseModel):
    id: str
    status: str  # "in-progress" | "analyzing" | "analyzed" | "completed" | "failed" | "cancelled"
    raw_input: str
    intent_cards: list[dict] = []
    already_covered: list[dict] = []
    track_guidance: TrackGuidance | None = None
    analysis_error: str | None = None
    analysis_workflow: dict[str, Any] | None = None
    created_by: str = "counsellor"
    created_at: str
    updated_at: str


class CreateSessionRequest(BaseModel):
    raw_input: str
    counsellor_id: str = "counsellor"


class CardCommitRequest(BaseModel):
    diff: dict | None = None  # Optional override for edited values


class CardCommitResponse(BaseModel):
    card_id: str
    domain: str
    status: str
    message: str


class CardDiscardResponse(BaseModel):
    card_id: str
    status: str = "discarded"
