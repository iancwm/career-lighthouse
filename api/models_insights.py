from typing import Literal

from pydantic import BaseModel, Field


class StudentChatInsightPayload(BaseModel):
    """Stored metadata for counsellor-only semantic search over student messages."""

    message_id: str
    timestamp: str
    role: Literal["user"] = "user"
    text: str
    active_career_type: str | None = None
    background: str | None = None
    region: str | None = None
    interest: str | None = None
    has_resume: bool
    source_channel: Literal["student_chat"] = "student_chat"
    schema_version: int = 1


class StudentQuestionSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    date_from: str | None = None
    date_to: str | None = None
    career_type: str | None = None
    background: str | None = None
    region: str | None = None
    top_k: int | None = Field(default=None, ge=1)


class StudentQuestionResult(BaseModel):
    message_id: str
    text: str
    timestamp: str
    active_career_type: str | None = None
    background: str | None = None
    region: str | None = None
    score: float
    source_label: str = "Student chat"


class StudentQuestionSearchResponse(BaseModel):
    results: list[StudentQuestionResult]
    total_returned: int
    filters_applied: dict
    insights_enabled: bool
    supports_background_filter: bool
    supports_region_filter: bool
