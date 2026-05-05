from typing import Optional

from pydantic import BaseModel


# Sprint 4 — Track publishing workflow models


class SourceRef(BaseModel):
    type: str
    label: str


class SalaryLevel(BaseModel):
    """Per-stage salary breakdown extracted from counsellor research."""

    stage: str  # e.g. "Junior Analyst"
    range_sgd: str  # e.g. "80–110K"
    notes: str = ""  # e.g. "Base + 15-20% bonus"


class DraftTrackDetail(BaseModel):
    slug: str
    track_name: str
    status: str = "draft"
    match_description: str = ""
    match_keywords: list[str] = []
    ep_sponsorship: str = ""
    compass_score_typical: str = ""
    top_employers_smu: list[str] = []
    recruiting_timeline: str = ""
    international_realistic: bool = True
    entry_paths: list[str] = []
    salary_range_2024: str = ""
    typical_background: str = ""
    counselor_contact: str | None = None
    notes: str = ""
    source_refs: list[SourceRef] = []
    structured: dict = {}
    last_updated: str | None = None
    archived_at: str | None = None

    # Optional: per-stage salary breakdown extracted from counsellor research.
    salary_levels: list[SalaryLevel] | None = None

    # Optional: visa and international pathway notes beyond the ep_sponsorship headline.
    visa_pathway_notes: str | None = None


class TrackRegistryEntry(BaseModel):
    slug: str
    label: str
    status: str = "active"
    last_published: str | None = None


class TrackReferenceDetail(BaseModel):
    slug: str
    label: str
    status: str = "active"
    last_published: str | None = None
    track_name: str = ""
    match_description: str = ""
    match_keywords: list[str] = []
    ep_sponsorship: str = ""
    compass_score_typical: str = ""
    top_employers_smu: list[str] = []
    recruiting_timeline: str = ""
    international_realistic: bool = True
    entry_paths: list[str] = []
    salary_range_2024: str = ""
    typical_background: str = ""
    counselor_contact: str | None = None
    notes: str = ""

    # Optional: per-stage salary breakdown (published).
    salary_levels: list[SalaryLevel] | None = None

    # Optional: visa/international pathway notes (published).
    visa_pathway_notes: str | None = None


class TrackVersionInfo(BaseModel):
    version: str
    published_at: str
    filename: str


class TrackPublishResponse(BaseModel):
    status: str
    slug: str
    version: str
    registry_updated: bool = True
