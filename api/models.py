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
    excerpt: str
    source_doc: str


class KBAnalysisResult(BaseModel):
    interpretation_bullets: list[str]
    profile_updates: dict[str, dict[str, ProfileFieldChange]] = {}
    new_chunks: list[NewChunk] = []
    already_covered: list[AlreadyCovered] = []


class KBCommitRequest(BaseModel):
    profile_updates: dict[str, dict[str, ProfileFieldChange]] = {}
    new_chunks: list[NewChunk] = []


class KBCommitResponse(BaseModel):
    status: str
    chunks_added: int
    profiles_updated: list[str] = []
