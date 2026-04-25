from typing import Optional

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class IntakeContext(BaseModel):
    """Transient intake answers passed with the first chat message.

    Never persisted — used only to resolve the initial career type slug,
    then discarded. PDPA: no personal identity data collected here.
    """
    background: Optional[str] = None   # "undergrad" | "masters" | "professional"
    region: Optional[str] = None       # "sea" | "south_asia" | "east_asia" | "other"
    interest: Optional[str] = None     # "finance" | "consulting" | "tech" | "public_sector" | "not_sure"


class ChatRequest(BaseModel):
    message: str
    resume_text: Optional[str] = None
    history: list[ChatMessage] = []
    # Sprint 2: guided entry + career profile injection
    intake_context: Optional[IntakeContext] = None   # message 1 only; server resolves career type then discards
    active_career_type: Optional[str] = None         # client echoes back slug from previous response


class Citation(BaseModel):
    filename: str
    excerpt: str
    source_name: Optional[str] = None
    updated_at: Optional[str] = None
    source_lifecycle: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    citations: list[Citation]
    active_career_type: Optional[str] = None  # resolved career type slug; client stores and echoes on next request


class BriefRequest(BaseModel):
    resume_text: str


class BriefResponse(BaseModel):
    brief: str
