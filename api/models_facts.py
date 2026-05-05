from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# Sprint 5 — Structured facts schema


class Fact(BaseModel):
    """Structured fact about employer or career track: timeline, alumni, interview, compensation, skills."""

    slug: str  # stripe-aditya-mehta or stripe-aditya-mehta-20260420 on collision
    type: Literal[
        "timeline_phase",
        "alumni",
        "interview_stage",
        "compensation",
        "skill_requirement",
    ]
    timestamp: str  # ISO-8601 datetime
    source: Literal["counselor", "inferred", "direct_from_alumni"]  # provenance
    confidence: int  # 1–100; confidence in this fact
    trace_id: Optional[str] = None  # Langfuse trace ID if extracted by LLM
    lifecycle: Literal["active", "superseded", "archived"] = "active"
    deleted: bool = False  # soft delete; queries filter out by default
    last_updated: str | None = None
    source_timestamp: str | None = None
    source_label: str | None = None
    source_type: str | None = None
    superseded_by: str | None = None
    audit_url: str | None = None
    data: dict[str, Any] = {}  # Type-specific fields (name, degree, school, etc.)


class ExtractFactsRequest(BaseModel):
    """Request to extract facts from employer/track notes."""

    pass  # Notes read from employer entity; endpoint handles reading


class FactQueryResponse(BaseModel):
    """Response from /api/kb/facts endpoint."""

    facts: list[Fact]
    total: int
    filters_applied: dict[str, Any] = {}


class FactGroupResponse(BaseModel):
    """Response from /api/kb/facts/grouped endpoint."""

    by: Literal["employer", "type"]
    groups: dict[str, list[Fact]] = Field(default_factory=dict)
    total: int
    filters_applied: dict[str, Any] = Field(default_factory=dict)
