# api/models.py — Compatibility barrel for domain-specific model modules
# Re-exports all models for backward compatibility while allowing new imports from domain modules

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# Try relative imports first (when imported as api.models), fall back to absolute (when api is in path)
try:
    from .models_chat import (
        BriefRequest,
        BriefResponse,
        ChatMessage,
        ChatRequest,
        ChatResponse,
        Citation,
        IntakeContext,
    )
    from .models_kb import (
        AlreadyCovered,
        DeleteResponse,
        DocCoverageItem,
        DocInfo,
        EmployerCardDiff,
        IntentCard,
        KBAnalysisResult,
        KBCommitRequest,
        KBCommitResponse,
        KBHealthResponse,
        LLMTraceEntry,
        LowConfidenceQuery,
        NewChunk,
        OverlapPair,
        ProfileFieldChange,
        SessionAnalysisResponse,
        SourceStateEvidence,
        SourceStateSummary,
        TestQueryResult,
        TrackCandidate,
        TrackCardDiff,
        TrackGuidance,
        _model_validate,
        validate_intent_card_diff,
        MultiIntentAnalysisResult,
        IngestResponse,
    )
    from .models_employers import (
        AlumniCompanyLink,
        AlumniCompanyLinkInput,
        AlumniDetail,
        AlumniExtractionPreview,
        AlumniExtractionRequest,
        AlumniFieldProposal,
        AlumniHistoryVersion,
        AlumniLinkVersion,
        EmployerDetail,
        EmployerHistoryVersion,
    )
    from .models_tracks import (
        DraftTrackDetail,
        SalaryLevel,
        SourceRef,
        TrackPublishResponse,
        TrackReferenceDetail,
        TrackRegistryEntry,
        TrackVersionInfo,
    )
    from .models_facts import (
        Fact,
        ExtractFactsRequest,
        FactGroupResponse,
        FactQueryResponse,
    )
except ImportError:
    # Fallback: absolute imports when api is in path
    from models_chat import (
        BriefRequest,
        BriefResponse,
        ChatMessage,
        ChatRequest,
        ChatResponse,
        Citation,
        IntakeContext,
    )
    from models_kb import (
        AlreadyCovered,
        DeleteResponse,
        DocCoverageItem,
        DocInfo,
        EmployerCardDiff,
        IntentCard,
        KBAnalysisResult,
        KBCommitRequest,
        KBCommitResponse,
        KBHealthResponse,
        LLMTraceEntry,
        LowConfidenceQuery,
        NewChunk,
        OverlapPair,
        ProfileFieldChange,
        SessionAnalysisResponse,
        SourceStateEvidence,
        SourceStateSummary,
        TestQueryResult,
        TrackCandidate,
        TrackCardDiff,
        TrackGuidance,
        _model_validate,
        validate_intent_card_diff,
        MultiIntentAnalysisResult,
        IngestResponse,
    )
    from models_employers import (
        AlumniCompanyLink,
        AlumniCompanyLinkInput,
        AlumniDetail,
        AlumniExtractionPreview,
        AlumniExtractionRequest,
        AlumniFieldProposal,
        AlumniHistoryVersion,
        AlumniLinkVersion,
        EmployerDetail,
        EmployerHistoryVersion,
    )
    from models_tracks import (
        DraftTrackDetail,
        SalaryLevel,
        SourceRef,
        TrackPublishResponse,
        TrackReferenceDetail,
        TrackRegistryEntry,
        TrackVersionInfo,
    )
    from models_facts import (
        Fact,
        ExtractFactsRequest,
        FactGroupResponse,
        FactQueryResponse,
    )

# Session and shared models (kept in barrel)

class KnowledgeSession(BaseModel):
    id: str
    status: str  # "in-progress" | "analyzing" | "analyzed" | "completed" | "failed" | "cancelled"
    raw_input: str
    intent_cards: list[dict] = []
    track_guidance: TrackGuidance | None = None
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


# For backward compatibility, re-export the utility
__all__ = [
    # Chat
    "ChatMessage",
    "IntakeContext",
    "ChatRequest",
    "Citation",
    "ChatResponse",
    "BriefRequest",
    "BriefResponse",
    # KB observability
    "DocInfo",
    "IngestResponse",
    "DeleteResponse",
    "TestQueryResult",
    "DocCoverageItem",
    "LowConfidenceQuery",
    "LLMTraceEntry",
    "OverlapPair",
    "SourceStateEvidence",
    "SourceStateSummary",
    "KBHealthResponse",
    # KB analysis
    "ProfileFieldChange",
    "NewChunk",
    "AlreadyCovered",
    "TrackCandidate",
    "TrackGuidance",
    "EmployerCardDiff",
    "TrackCardDiff",
    "IntentCard",
    "KBAnalysisResult",
    "SessionAnalysisResponse",
    "MultiIntentAnalysisResult",
    "KBCommitRequest",
    "KBCommitResponse",
    "validate_intent_card_diff",
    # Employers
    "EmployerDetail",
    "EmployerHistoryVersion",
    "AlumniFieldProposal",
    "AlumniCompanyLinkInput",
    "AlumniCompanyLink",
    "AlumniDetail",
    "AlumniHistoryVersion",
    "AlumniLinkVersion",
    "AlumniExtractionRequest",
    "AlumniExtractionPreview",
    # Tracks
    "SourceRef",
    "SalaryLevel",
    "DraftTrackDetail",
    "TrackRegistryEntry",
    "TrackReferenceDetail",
    "TrackVersionInfo",
    "TrackPublishResponse",
    # Facts
    "Fact",
    "ExtractFactsRequest",
    "FactQueryResponse",
    "FactGroupResponse",
    # Session
    "KnowledgeSession",
    "CreateSessionRequest",
    "CardCommitRequest",
    "CardCommitResponse",
    "CardDiscardResponse",
    # Utilities
    "_model_validate",
]
