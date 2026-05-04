from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DocInfo(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    uploaded_at: str
    lifecycle: Literal["active", "superseded", "archived"] = "active"
    uploaded_by: Optional[str] = None
    superseded_by: Optional[str] = None
    linked_knowledge_object: Optional[str] = None
    archived_at: Optional[str] = None
    source_record_id: Optional[str] = None


class IngestResponse(BaseModel):
    doc_id: str
    chunk_count: int
    status: str
    similarity_warning: Optional[str] = None
    overlap_pct: float = 0.0
    overlapping_docs: list[str] = []


class DeleteResponse(BaseModel):
    status: str  # "deleted" | "not_found"


# KB Observability models

class TestQueryResult(BaseModel):
    source_filename: str
    excerpt: str
    score: float


class DocCoverageItem(BaseModel):
    filename: str
    chunk_count: int
    coverage_status: str  # "good" | "thin"
    has_overlap_warning: bool = False


class LowConfidenceQuery(BaseModel):
    ts: str
    query_text: str
    max_score: float
    doc_matched: Optional[str] = None


class LLMTraceEntry(BaseModel):
    trace_id: str
    ts: str
    operation: str
    status: str
    model: str
    feature: str | None = None
    session_id: str | None = None
    workflow_id: str | None = None
    workflow_name: str | None = None
    phase: str | None = None
    chunk_index: int | None = None
    chunk_count: int | None = None
    multi_pass_threshold_chars: int | None = None
    multi_pass_chunk_tokens: int | None = None
    multi_pass_overlap_tokens: int | None = None
    input_chars_pre_trim: int | None = None
    input_chars_sent: int | None = None
    kb_chunks_retrieved: int | None = None
    kb_chunks_sent: int | None = None
    parse_attempt: int | None = None
    repair_attempt: int | None = None
    partial_result: bool | None = None
    prompt_name: str | None = None
    prompt_source: str | None = None
    prompt_label: str | None = None
    prompt_version: int | None = None
    schema_name: str | None = None
    error_class: str | None = None
    domain_mix: str | None = None
    repair_applied: bool | None = None
    card_count_raw: int | None = None
    card_count_repaired: int | None = None
    card_count_committed: int | None = None
    timeout_seconds: float | None = None
    max_tokens: int
    latency_ms: float
    input_chars: int
    output_chars: int = 0
    input_preview: str = ""
    output_preview: str = ""
    error: str | None = None


class LLMPromptProvenance(BaseModel):
    prompt_name: str | None = None
    prompt_source: str | None = None
    prompt_label: str | None = None
    prompt_version: int | None = None


class LLMWorkflowCardCounts(BaseModel):
    raw: int | None = None
    repaired: int | None = None
    committed: int | None = None
    already_covered: int | None = None
    alumni_built: int | None = None


class LLMWorkflowScore(BaseModel):
    key: str
    value: float | int | str | bool | None = None
    label: str
    rationale: str | None = None


class LLMWorkflowStep(BaseModel):
    step_id: str
    label: str
    status: str
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: float | None = None
    detail: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMWorkflowSummary(BaseModel):
    workflow_id: str
    workflow_name: str
    status: str
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: float | None = None
    session_id: str | None = None
    model: str | None = None
    prompt: LLMPromptProvenance = Field(default_factory=LLMPromptProvenance)
    drop_point: str | None = None
    failure_summary: str | None = None
    repair_applied: bool = False
    card_counts: LLMWorkflowCardCounts = Field(default_factory=LLMWorkflowCardCounts)
    alumni_path: str | None = None
    is_partial: bool = False


class LLMWorkflowDetail(BaseModel):
    workflow_id: str
    workflow_name: str
    status: str
    session_id: str | None = None
    trace_ids: list[str] = Field(default_factory=list)
    started_at: str | None = None
    ended_at: str | None = None
    duration_ms: float | None = None
    prompt: LLMPromptProvenance = Field(default_factory=LLMPromptProvenance)
    model: str | None = None
    summary: str | None = None
    likely_cause: str | None = None
    recommended_action: str | None = None
    drop_point: str | None = None
    alumni_path: str | None = None
    prompt_provenance_unavailable: bool = False
    context_pack_summary: dict[str, Any] = Field(default_factory=dict)
    raw_output_summary: dict[str, Any] = Field(default_factory=dict)
    repair_summary: dict[str, Any] = Field(default_factory=dict)
    parsed_payload_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    append_summary: dict[str, Any] = Field(default_factory=dict)
    card_counts: LLMWorkflowCardCounts = Field(default_factory=LLMWorkflowCardCounts)
    scores: list[LLMWorkflowScore] = Field(default_factory=list)
    steps: list[LLMWorkflowStep] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class OverlapPair(BaseModel):
    doc_a: str
    doc_b: str
    overlap_pct: float
    recommendation: str = "merge or remove one"


class SourceStateEvidence(BaseModel):
    filename: str
    reason: str
    chunk_count: int = 0
    last_seen_at: Optional[str] = None


class SourceStateSummary(BaseModel):
    active_source_count: int = 0
    superseded_source_count: int = 0
    stale_source_count: int = 0
    active_hit_count: int = 0
    superseded_hit_count: int = 0
    last_refreshed_at: Optional[str] = None
    stale_source_evidence: list[SourceStateEvidence] = []


class KBHealthResponse(BaseModel):
    total_docs: int
    total_chunks: int
    avg_match_score: Optional[float] = None
    retrieval_diversity_score: Optional[float] = None
    low_confidence_queries: list[LowConfidenceQuery] = []
    doc_coverage: list[DocCoverageItem] = []
    high_overlap_pairs: list[OverlapPair] = []
    source_state: Optional[SourceStateSummary] = None
    active_sources: Optional[int] = None
    active_source_count: Optional[int] = None
    superseded_sources: Optional[int] = None
    superseded_source_count: Optional[int] = None
    stale_sources: Optional[int] = None
    stale_source_count: Optional[int] = None
    active_hits: Optional[int] = None
    active_hit_count: Optional[int] = None
    superseded_hits: Optional[int] = None
    superseded_hit_count: Optional[int] = None
    last_refreshed_at: Optional[str] = None
    updated_at: Optional[str] = None
    stale_source_evidence: list[SourceStateEvidence] = []


# Sprint 3 — diff-first KB ingestion models

class ProfileFieldChange(BaseModel):
    old: Optional[str] = None   # current value in YAML (None if field is new)
    new: str                    # proposed replacement value (counsellor-editable)
    source_type: str | None = None
    source_label: str | None = None
    source_timestamp: str | None = None


class NewChunk(BaseModel):
    text: str
    source_type: str            # "note" | "file"
    source_label: str           # "counsellor_note" for notes; filename for uploads
    source_timestamp: str | None = None
    career_type: Optional[str] = None
    chunk_id: str = ""          # filled by server after Claude returns


class AlreadyCovered(BaseModel):
    content: str | None = None  # session-intent wording
    reason: str = ""  # why no action is needed
    excerpt: str | None = None  # KB-analysis wording
    source_doc: str | None = None  # KB-analysis wording


class TrackCandidate(BaseModel):
    slug: str
    label: str
    score: float


class TrackGuidance(BaseModel):
    status: str  # "safe_update" | "clustered_uncertainty" | "emerging_taxonomy_signal"
    recommendation: str
    nearest_tracks: list[TrackCandidate] = []
    recurrence_count: int = 0
    cluster_key: str | None = None


class EmployerCardDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    employer_name: str | None = None
    tracks: list[str] | None = None
    ep_requirement: str | None = None
    intake_seasons: list[str] | None = None
    application_process: str | None = None
    singapore_headcount_estimate: str | int | None = None
    counselor_contact: str | None = None
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_headcount_field(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "singapore_headcount_estimate" in data or "headcount_estimate" not in data:
            return data
        normalized = dict(data)
        normalized["singapore_headcount_estimate"] = normalized.pop("headcount_estimate")
        return normalized


class TrackCardDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    track_name: str | None = None
    match_description: str | None = None
    match_keywords: list[str] | None = None
    ep_sponsorship: str | None = None
    compass_score_typical: str | None = None
    top_employers_smu: list[str] | None = None
    recruiting_timeline: str | None = None
    international_realistic: bool | str | None = None
    entry_paths: list[str] | None = None
    salary_range_2024: str | None = None
    typical_background: str | None = None
    counselor_contact: str | None = None
    notes: str | None = None


class AlumniCardDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str
    full_name: str | None = None
    name: str | None = None
    degree: str | None = None
    graduation_school: str | None = None
    school: str | None = None
    current_title: str | None = None
    current_company: str | None = None
    graduation_year: str | int | None = None
    graduation_program: str | None = None
    home_country: str | None = None
    career_trajectory_summary: str | None = None
    available_for_mentoring: bool | str | None = None
    notes: str | None = None
    career_goals_domains: list[str] | str | None = None
    help_capacity: str | None = None
    can_refer: Literal["yes", "maybe", "no"] | None = None
    can_refer_confidence: int | str | None = None
    can_refer_evidence: list[str] | str | None = None
    can_refer_rationale: str | None = None
    network_strength: Literal["low", "medium", "high"] | None = None
    mentoring_modes: list[str] | str | None = None
    communication_style: str | None = None
    preferred_student_traits: list[str] | str | None = None
    common_interests: list[str] | str | None = None
    consent_for_referrals: bool | str | None = None
    consent_scope_notes: str | None = None
    source_type: str | None = None
    source_label: str | None = None
    source_timestamp: str | None = None
    trace_id: str | None = None
    lifecycle: Literal["active", "superseded", "archived"] | None = None
    deleted: bool | str | None = None
    superseded_by: str | None = None
    archived_at: str | None = None
    last_confirmed_at: str | None = None
    last_updated: str | None = None
    company_links: list[dict[str, Any]] | None = None


def _model_validate(model_cls: type[BaseModel], data: Any) -> BaseModel:
    validator = getattr(model_cls, "model_validate", None)
    if callable(validator):
        return validator(data)
    return model_cls.parse_obj(data)


def validate_intent_card_diff(domain: str, diff: Any) -> dict[str, Any]:
    """Validate a session-intent diff against the domain-specific schema."""
    if domain == "employer":
        validated = _model_validate(EmployerCardDiff, diff)
    elif domain == "track":
        validated = _model_validate(TrackCardDiff, diff)
    elif domain == "alumni":
        validated = _model_validate(AlumniCardDiff, diff)
    else:
        raise ValueError(f"Unknown intent card domain: {domain!r}")
    return validated.model_dump(exclude_none=True)


class IntentCard(BaseModel):
    card_id: str
    domain: Literal["employer", "track", "alumni"]
    summary: str
    diff: dict[str, Any]  # structured representation of the proposed change
    raw_input_ref: str  # reference back to the originating text chunk
    status: Literal["pending", "committed", "discarded"] = "pending"
    proposals: dict[str, dict[str, Any]] = Field(default_factory=dict)
    is_update: bool = False
    matched_slug: str | None = None

    @field_validator("diff", mode="before")
    @classmethod
    def _validate_diff(cls, value: Any, info):
        domain = info.data.get("domain")
        return validate_intent_card_diff(domain, value)


class KBAnalysisResult(BaseModel):
    """Result from LLM analysis of counsellor input (diff-first review)."""
    interpretation_bullets: list[str] = []
    new_chunks: list[NewChunk] = []
    profile_updates: dict[str, dict[str, ProfileFieldChange]] = {}
    employer_updates: dict[str, dict[str, ProfileFieldChange]] = {}
    already_covered: list[AlreadyCovered] = []


class SessionAnalysisResponse(BaseModel):
    session_id: str
    cards: list[IntentCard]
    already_covered: list[AlreadyCovered] = []
    track_guidance: TrackGuidance | None = None


class MultiIntentAnalysisResult(BaseModel):
    session_id: str
    cards: list[IntentCard]
    already_covered: list[AlreadyCovered] = []


class KBCommitRequest(BaseModel):
    profile_updates: dict[str, dict[str, ProfileFieldChange]] = {}
    employer_updates: dict[str, dict[str, ProfileFieldChange]] = {}
    new_chunks: list[NewChunk] = []


class KBCommitResponse(BaseModel):
    status: str
    chunks_added: int
    profiles_updated: list[str] = []
    employers_updated: list[str] = []
