# api/models.py
from pydantic import BaseModel
from typing import Optional

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    resume_text: Optional[str] = None
    history: list[ChatMessage] = []

class Citation(BaseModel):
    filename: str
    excerpt: str

class ChatResponse(BaseModel):
    response: str
    citations: list[Citation]

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
