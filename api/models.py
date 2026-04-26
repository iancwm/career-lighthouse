# api/models.py — Compatibility barrel for domain-specific model modules
# Re-exports all models for backward compatibility while allowing new imports from domain modules

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
    from .models_session import (
        CardCommitRequest,
        CardCommitResponse,
        CardDiscardResponse,
        CreateSessionRequest,
        KnowledgeSession,
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
    from models_session import (
        CardCommitRequest,
        CardCommitResponse,
        CardDiscardResponse,
        CreateSessionRequest,
        KnowledgeSession,
    )


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
