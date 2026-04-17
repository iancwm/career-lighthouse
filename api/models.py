# api/models.py
from pydantic import BaseModel
from typing import Optional


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


class ChatResponse(BaseModel):
    response: str
    citations: list[Citation]
    active_career_type: Optional[str] = None  # resolved career type slug; client stores and echoes on next request

class BriefRequest(BaseModel):
    resume_text: str

class BriefResponse(BaseModel):
    brief: str

class DocInfo(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    uploaded_at: str

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
    session_id: str | None = None
    phase: str | None = None
    chunk_index: int | None = None
    chunk_count: int | None = None
    multi_pass_threshold_chars: int | None = None
    multi_pass_chunk_tokens: int | None = None
    multi_pass_overlap_tokens: int | None = None
    timeout_seconds: float | None = None
    max_tokens: int
    latency_ms: float
    input_chars: int
    output_chars: int = 0
    input_preview: str = ""
    output_preview: str = ""
    error: str | None = None


class OverlapPair(BaseModel):
    doc_a: str
    doc_b: str
    overlap_pct: float
    recommendation: str = "merge or remove one"


class KBHealthResponse(BaseModel):
    total_docs: int
    total_chunks: int
    avg_match_score: Optional[float] = None
    retrieval_diversity_score: Optional[float] = None
    low_confidence_queries: list[LowConfidenceQuery] = []
    doc_coverage: list[DocCoverageItem] = []
    high_overlap_pairs: list[OverlapPair] = []


# Sprint 3 — diff-first KB ingestion models

class ProfileFieldChange(BaseModel):
    old: Optional[str] = None   # current value in YAML (None if field is new)
    new: str                    # proposed replacement value (counsellor-editable)


class NewChunk(BaseModel):
    text: str
    source_type: str            # "note" | "file"
    source_label: str           # "counsellor_note" for notes; filename for uploads
    career_type: Optional[str] = None
    chunk_id: str = ""          # filled by server after Claude returns


class AlreadyCovered(BaseModel):
    content: str  # the text that is already covered
    reason: str = ""  # why no action is needed


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


class IntentCard(BaseModel):
    card_id: str
    domain: str  # "employer" | "track"
    summary: str
    diff: dict  # structured representation of the proposed change
    raw_input_ref: str # reference back to the originating text chunk
    status: str = "pending"  # "pending" | "committed" | "discarded"


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
    thought: Optional[str] = None


class MultiIntentAnalysisResult(BaseModel):
    session_id: str
    cards: list[IntentCard]
    already_covered: list[AlreadyCovered] = []
    thought: Optional[str] = None


class KBCommitRequest(BaseModel):
    profile_updates: dict[str, dict[str, ProfileFieldChange]] = {}
    employer_updates: dict[str, dict[str, ProfileFieldChange]] = {}
    new_chunks: list[NewChunk] = []


class KBCommitResponse(BaseModel):
    status: str
    chunks_added: int
    profiles_updated: list[str] = []
    employers_updated: list[str] = []


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
    last_updated: str | None = None
    completeness: str = "amber"  # computed by server: "green" | "amber"


# Sprint 4 — Track publishing workflow models

class SourceRef(BaseModel):
    type: str
    label: str


class SalaryLevel(BaseModel):
    """Per-stage salary breakdown extracted from counsellor research."""
    stage: str        # e.g. "Junior Analyst"
    range_sgd: str    # e.g. "80–110K"
    notes: str = ""   # e.g. "Base + 15-20% bonus"


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


class KnowledgeSession(BaseModel):
    id: str
    status: str  # "in-progress" | "analyzing" | "analyzed" | "completed" | "failed" | "cancelled"
    raw_input: str
    intent_cards: list[dict] = []
    track_guidance: TrackGuidance | None = None
    thought: Optional[str] = None
    analysis_error: Optional[str] = None
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
