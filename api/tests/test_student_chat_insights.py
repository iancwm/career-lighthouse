from datetime import datetime
from uuid import UUID

from config import settings
from models_chat import IntakeContext
from services.student_chat_insights import StudentChatInsightStore


def test_build_payload_contains_required_fields(monkeypatch):
    monkeypatch.setattr(settings, "student_chat_store_background", False)
    monkeypatch.setattr(settings, "student_chat_store_region", False)
    monkeypatch.setattr(settings, "student_chat_store_interest", False)

    store = StudentChatInsightStore(client=None)
    payload = store.build_payload(
        text="What internships are realistic for me?",
        active_career_type="consulting",
        intake_context=IntakeContext(
            background="undergrad", region="sea", interest="consulting"
        ),
        has_resume=True,
    )

    UUID(payload.message_id)
    datetime.fromisoformat(payload.timestamp)
    assert payload.text == "What internships are realistic for me?"
    assert payload.source_channel == "student_chat"
    assert payload.role == "user"
    assert payload.has_resume is True
    assert payload.background is None
    assert payload.region is None
    assert payload.interest is None

    payload_data = (
        payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    )
    assert "resume_text" not in payload_data


def test_build_payload_includes_optional_intake_fields_when_enabled(monkeypatch):
    monkeypatch.setattr(settings, "student_chat_store_background", True)
    monkeypatch.setattr(settings, "student_chat_store_region", True)
    monkeypatch.setattr(settings, "student_chat_store_interest", True)

    store = StudentChatInsightStore(client=None)
    payload = store.build_payload(
        text="How hard is hiring in SG now?",
        active_career_type="tech_product",
        intake_context=IntakeContext(
            background="masters", region="sea", interest="tech"
        ),
        has_resume=False,
    )

    assert payload.background == "masters"
    assert payload.region == "sea"
    assert payload.interest == "tech"


def test_build_payload_handles_none_intake_with_flags_enabled(monkeypatch):
    monkeypatch.setattr(settings, "student_chat_store_background", True)
    monkeypatch.setattr(settings, "student_chat_store_region", True)
    monkeypatch.setattr(settings, "student_chat_store_interest", True)

    store = StudentChatInsightStore(client=None)
    payload = store.build_payload(
        text="What is hiring like this year?",
        active_career_type=None,
        intake_context=None,
        has_resume=False,
    )

    assert payload.background is None
    assert payload.region is None
    assert payload.interest is None


def test_ensure_collection_is_idempotent(in_memory_qdrant):
    store = StudentChatInsightStore(client=in_memory_qdrant)
    store.ensure_collection(dim=384)
    store.ensure_collection(dim=384)
    collection = in_memory_qdrant.get_collection(settings.student_chat_collection_name)
    assert collection is not None


def test_index_message_writes_payload_without_resume_text(
    in_memory_qdrant, mock_embedder, monkeypatch
):
    monkeypatch.setattr(settings, "student_chat_store_background", True)
    monkeypatch.setattr(settings, "student_chat_store_region", True)
    monkeypatch.setattr(settings, "student_chat_store_interest", True)

    store = StudentChatInsightStore(client=in_memory_qdrant)
    store.ensure_collection(dim=384)

    message_id = store.index_message(
        text="What worries should I prepare for in IB recruiting?",
        embedder=mock_embedder,
        active_career_type="investment_banking",
        intake_context=IntakeContext(
            background="undergrad", region="sea", interest="finance"
        ),
        has_resume=True,
    )

    points, _ = in_memory_qdrant.scroll(
        collection_name=settings.student_chat_collection_name,
        limit=10,
        with_payload=True,
        with_vectors=False,
    )
    assert len(points) == 1
    payload = points[0].payload
    assert payload["message_id"] == message_id
    assert payload["text"] == "What worries should I prepare for in IB recruiting?"
    assert payload["has_resume"] is True
    assert payload["background"] == "undergrad"
    assert payload["region"] == "sea"
    assert payload["interest"] == "finance"
    assert "resume_text" not in payload


def test_feature_toggle_disabled_skips_collection_bootstrap(monkeypatch):
    import dependencies

    monkeypatch.setattr(settings, "student_chat_insights_enabled", False)
    dependencies.get_student_insight_store.cache_clear()

    def should_not_be_called():
        raise AssertionError(
            "get_qdrant_client should not be called when insights are disabled"
        )

    monkeypatch.setattr(dependencies, "get_qdrant_client", should_not_be_called)

    store = dependencies.get_student_insight_store()
    assert isinstance(store, StudentChatInsightStore)
    dependencies.get_student_insight_store.cache_clear()
