"""Smoke tests for the domain model split and compatibility barrel."""

from models import (
    ChatRequest as BarrelChatRequest,
    EmployerDetail as BarrelEmployerDetail,
    Fact as BarrelFact,
    KnowledgeSession as BarrelKnowledgeSession,
    TrackRegistryEntry as BarrelTrackRegistryEntry,
)
from models_employers import EmployerDetail
from models_facts import Fact
from models_chat import ChatRequest
from models_kb import KBAnalysisResult
from models_session import KnowledgeSession
from models_tracks import TrackRegistryEntry


def test_split_modules_are_importable():
    assert ChatRequest is BarrelChatRequest
    assert EmployerDetail is BarrelEmployerDetail
    assert Fact is BarrelFact
    assert KnowledgeSession is BarrelKnowledgeSession
    assert TrackRegistryEntry is BarrelTrackRegistryEntry
    assert BarrelKnowledgeSession.__name__ == "KnowledgeSession"
    assert KBAnalysisResult.__name__ == "KBAnalysisResult"
