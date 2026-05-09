from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Sprint 3 Addendum — Employer Entity YAML models


class EmployerDetail(BaseModel):
    """Single employer entity. Persisted as knowledge/employers/{slug}.yaml."""

    slug: str
    employer_name: str
    tracks: list[str] = []
    ep_requirement: str | None = None
    intake_seasons: list[str] = []
    singapore_headcount_estimate: str | None = None
    application_process: str | None = None
    counsellor_contact: str | None = None
    notes: str | None = None
    structured: dict[str, Any] = {}
    source_documents: list[dict[str, Any]] = []
    last_updated: str | None = None
    completeness: str = "amber"  # computed by server: "green" | "amber"

    @field_validator("singapore_headcount_estimate", mode="before")
    @classmethod
    def _coerce_singapore_headcount_estimate(cls, value: Any) -> Any:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return value


class EmployerHistoryVersion(BaseModel):
    version: str
    recorded_at: str
    filename: str


class AlumniFieldProposal(BaseModel):
    value: Any = None
    confidence: int = 0
    evidence: list[str] = Field(default_factory=list)
    rationale: str | None = None


class AlumniCompanyLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_slug: str | None = None
    company_name: str | None = None
    relationship: str | None = None
    role_title: str | None = None
    notes: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    link_type: Literal["current", "former", "advisory"] = "current"
    confidence: int | None = None
    evidence: list[str] = Field(default_factory=list)
    rationale: str | None = None
    source_type: str | None = None
    source_label: str | None = None
    source_timestamp: str | None = None


class AlumniCompanyLink(BaseModel):
    link_id: str
    alumni_slug: str
    company_slug: str
    company_name: str | None = None
    relationship: str | None = None
    role_title: str | None = None
    notes: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    link_type: Literal["current", "former", "advisory"] = "current"
    confidence: int | None = None
    evidence: list[str] = Field(default_factory=list)
    rationale: str | None = None
    source_type: str | None = None
    source_label: str | None = None
    source_timestamp: str | None = None
    source_signature: str | None = None
    lifecycle: Literal["active", "superseded", "archived"] = "active"
    deleted: bool = False
    superseded_by: str | None = None
    recorded_at: str | None = None
    last_updated: str | None = None
    archived_at: str | None = None


class AlumniDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    full_name: str
    name: str | None = None
    degree: str | None = None
    graduation_school: str | None = None
    school: str | None = None
    graduation_program: str | None = None
    graduation_year: str | int | None = None
    current_title: str | None = None
    current_company: str | None = None
    home_country: str | None = None
    career_trajectory_summary: str | None = None
    career_trajectory_pattern: str | None = None
    seniority_level: str | None = None
    salary_band_estimate: str | None = None
    experience_diversity: str | None = None
    available_for_mentoring: bool | None = None
    notes: str | None = None
    career_goals_domains: list[str] = Field(default_factory=list)
    help_capacity: str | None = None
    can_refer: Literal["yes", "maybe", "no"] = "maybe"
    can_refer_confidence: int | None = None
    can_refer_evidence: list[str] = Field(default_factory=list)
    can_refer_rationale: str | None = None
    network_strength: Literal["low", "medium", "high"] | None = None
    mentoring_modes: list[str] = Field(default_factory=list)
    communication_style: str | None = None
    preferred_student_traits: list[str] = Field(default_factory=list)
    common_interests: list[str] = Field(default_factory=list)
    consent_for_referrals: bool | None = None
    consent_scope_notes: str | None = None
    source_type: str | None = None
    source_label: str | None = None
    source_timestamp: str | None = None
    trace_id: str | None = None
    lifecycle: Literal["active", "superseded", "archived"] = "active"
    deleted: bool = False
    superseded_by: str | None = None
    archived_at: str | None = None
    last_confirmed_at: str | None = None
    last_updated: str | None = None
    company_links: list[AlumniCompanyLink] = Field(default_factory=list)
    company_link_count: int = 0
    completeness: str = "amber"


class AlumniHistoryVersion(BaseModel):
    version: str
    recorded_at: str
    filename: str


class AlumniLinkVersion(BaseModel):
    version: str
    recorded_at: str
    filename: str
    link_id: str
    lifecycle: Literal["active", "superseded", "archived"] = "active"


class AlumniExtractionRequest(BaseModel):
    notes: str
    source_type: str = "note"
    source_label: str = "counsellor_note"
    alumni_slug: str | None = None


class AlumniExtractionPreview(BaseModel):
    summary_bullets: list[str] = Field(default_factory=list)
    profile_proposals: dict[str, AlumniFieldProposal] = Field(default_factory=dict)
    company_link_proposals: list[AlumniCompanyLinkInput] = Field(default_factory=list)
    fit_triad: dict[str, AlumniFieldProposal] = Field(default_factory=dict)
    source_label: str | None = None
    source_type: str | None = None
