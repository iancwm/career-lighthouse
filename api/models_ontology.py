"""Ontology & metadata layer models — Milestone 1.

Entity/Evidence/Claim envelope for typed structured facts, additive to the
existing employer/track/alumni YAML stores. See docs/ontology/ONTOLOGY-DESIGN.md.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

ONTOLOGY_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

EntityType = Literal[
    "organization",
    "organization_unit",
    "programme",
    "role",
    "career_track",
    "person",
    "institution",
    "source_document",
]
EntityStatus = Literal["active", "merged", "archived"]


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ontology_version: str = ONTOLOGY_VERSION
    entity_id: str
    entity_type: EntityType
    canonical_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    status: EntityStatus = "active"
    parent_entity_id: str | None = None
    geography: str | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Source metadata extension (validation view over SourceLedgerStore records)
# ---------------------------------------------------------------------------

SourceKind = Literal[
    "official_employer_page",
    "institutional_report",
    "job_posting",
    "counsellor_note",
    "alumni_interview",
    "student_report",
    "secondary_article",
    "unknown",
]
AuthorityTier = Literal[
    "official_primary",
    "institutional_primary",
    "direct_participant",
    "internal_counsellor",
    "secondary_reputable",
    "anecdotal",
    "unknown",
]


class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ontology_version: str = ONTOLOGY_VERSION
    source_id: str
    filename: str
    source_kind: SourceKind = "unknown"
    publisher_name: str | None = None
    publisher_entity_id: str | None = None
    published_at: date | None = None
    retrieved_at: datetime
    jurisdiction: str | None = None
    coverage_geographies: list[str] = Field(default_factory=list)
    coverage_entity_ids: list[str] = Field(default_factory=list)
    authority_tier: AuthorityTier = "unknown"
    contains_personal_data: bool = False
    content_hash: str | None = None
    lifecycle: Literal["active", "superseded", "archived"] = "active"
    superseded_by: str | None = None


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

SupportType = Literal["directly_supports", "partially_supports", "contradicts", "context_only"]


class EvidenceLocator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int | None = None
    paragraph: int | None = None
    section: str | None = None
    character_start: int | None = None
    character_end: int | None = None


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ontology_version: str = ONTOLOGY_VERSION
    evidence_id: str
    source_id: str
    excerpt: str = Field(min_length=1, max_length=2000)
    locator: EvidenceLocator = Field(default_factory=EvidenceLocator)
    support_type: SupportType
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    trace_id: str | None = None

    @field_validator("excerpt")
    @classmethod
    def _excerpt_not_a_summary(cls, v: str) -> str:
        # Cheap heuristic guard, not a proof: reject empty/whitespace-only
        # excerpts. True "must be copied, not generated" enforcement happens
        # by construction in the extraction pipeline (offsets, not LLM text).
        if not v.strip():
            raise ValueError("excerpt must be non-empty source text")
        return v


# ---------------------------------------------------------------------------
# Claim envelope
# ---------------------------------------------------------------------------

ClaimType = Literal[
    "application_window",
    "recruitment_stage",
    "skill_requirement",
    "compensation_observation",
    "employment_relationship",
    "education_relationship",
    "programme_offering",
    "sponsorship_policy",
]
AssertionStatus = Literal[
    "asserted", "inferred", "estimated", "reported", "contradicted", "superseded",
]
ReviewStatus = Literal["proposed", "approved", "rejected"]


class ClaimScope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geography: str | None = None
    organization_unit_id: str | None = None
    programme_id: str | None = None
    role_id: str | None = None
    seniority: str | None = None
    candidate_segment: str | None = None
    academic_year: str | None = None


class ClaimValidTime(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid_from: date | None = None
    valid_until: date | None = None


class ClaimObservationTime(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_at: date | None = None
    recorded_at: datetime


class ClaimConfidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extraction: float = Field(ge=0.0, le=1.0)
    evidence_strength: float = Field(ge=0.0, le=1.0)
    source_reliability: float = Field(ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Milestone-1 typed claim payloads
# ---------------------------------------------------------------------------

DatePrecision = Literal["exact_date", "month", "quarter", "approximate"]


class ApplicationWindowPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_type: Literal["application_window"] = "application_window"
    programme_id: str | None = None
    opens_on: date | None = None
    closes_on: date | None = None
    date_precision: DatePrecision = "approximate"
    intake_year: int | None = None


StageType = Literal[
    "application",
    "online_assessment",
    "recruiter_screen",
    "technical_interview",
    "case_interview",
    "assessment_centre",
    "final_interview",
    "offer",
    "other",
]
Modality = Literal["online", "phone", "video", "onsite", "hybrid", "unknown"]


class RecruitmentStagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_type: Literal["recruitment_stage"] = "recruitment_stage"
    process_id: str | None = None
    sequence: int | None = None
    stage_name: str = Field(min_length=1)
    stage_type: StageType
    modality: Modality = "unknown"
    duration_minutes: int | None = None
    assessed_competencies: list[str] = Field(default_factory=list)


ClaimPayload = Annotated[
    Union[ApplicationWindowPayload, RecruitmentStagePayload],
    Field(discriminator="claim_type"),
]


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ontology_version: str = ONTOLOGY_VERSION
    claim_id: str
    claim_type: ClaimType
    subject_entity_id: str
    object_entity_id: str | None = None
    payload: ClaimPayload
    scope: ClaimScope = Field(default_factory=ClaimScope)
    valid_time: ClaimValidTime = Field(default_factory=ClaimValidTime)
    observation_time: ClaimObservationTime
    assertion_status: AssertionStatus = "inferred"
    confidence: ClaimConfidence
    evidence_ids: list[str] = Field(min_length=1)
    lifecycle: Literal["active", "superseded", "archived"] = "active"
    superseded_by: str | None = None
    review_status: ReviewStatus = "proposed"
    trace_id: str | None = None

    @field_validator("evidence_ids")
    @classmethod
    def _requires_evidence(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("a claim must cite at least one evidence_id")
        return v

    @field_validator("payload")
    @classmethod
    def _payload_matches_claim_type(cls, v, info):
        claim_type = info.data.get("claim_type")
        if claim_type is not None and getattr(v, "claim_type", None) != claim_type:
            raise ValueError(
                f"payload type {getattr(v, 'claim_type', None)!r} does not match "
                f"claim_type {claim_type!r}"
            )
        return v


# ---------------------------------------------------------------------------
# Claim context (Milestone 2) — pre-fetched claims injected into chat prompts.
# See docs/ontology/GROUNDING-DESIGN.md.
# ---------------------------------------------------------------------------


class ClaimContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str | None = None
    entity_name: str | None = None
    claims: list[Claim] = Field(default_factory=list)
    coverage_confidence: Literal["high", "medium", "low", "none"] = "none"
