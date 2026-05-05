from unittest.mock import MagicMock, patch

import numpy as np
from fastapi.testclient import TestClient

from config import settings
from services.student_chat_insights import StudentChatInsightStore


def _make_store(in_memory_qdrant):
    from services.vector_store import VectorStore

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    vec = np.ones(384, dtype=np.float32)
    store.upsert(
        [
            {
                "id": "chat-source-1",
                "vector": vec,
                "payload": {
                    "source_filename": "guide.txt",
                    "chunk_index": 0,
                    "upload_timestamp": "2026-01-01",
                    "text": "Consulting recruiting is front-loaded in September and October.",
                },
            }
        ]
    )
    return store, vec


def _mock_profile_store():
    mock = MagicMock()
    mock.get_profile.return_value = None
    mock.match_career_type.return_value = None
    mock.match_career_type_keywords.return_value = None
    return mock


def _make_client(in_memory_qdrant, mock_embedder, insight_store):
    from main import app
    import dependencies
    from services.career_profiles import get_career_profile_store
    from services.employer_store import get_employer_store

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec

    mock_employer_store = MagicMock()
    mock_employer_store.to_context_block.return_value = None

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[dependencies.get_student_insight_store] = lambda: (
        insight_store
    )
    app.dependency_overrides[get_career_profile_store] = lambda: _mock_profile_store()
    app.dependency_overrides[get_employer_store] = lambda: mock_employer_store
    return TestClient(app)


def test_chat_indexes_student_message_when_feature_enabled(
    in_memory_qdrant, mock_embedder, monkeypatch
):
    import services.llm as llm_module

    monkeypatch.setattr(settings, "student_chat_insights_enabled", True)
    monkeypatch.setattr(settings, "student_chat_embedding_min_chars", 1)

    mock_insight_store = MagicMock()
    mock_insight_store.index_message.return_value = "message-1"
    client = _make_client(in_memory_qdrant, mock_embedder, mock_insight_store)

    with patch.object(llm_module, "chat_with_context", return_value="Here is advice"):
        response = client.post(
            "/api/chat",
            json={
                "message": "How should I prepare for consulting interviews?",
                "resume_text": "secret resume text",
                "history": [],
            },
        )

    assert response.status_code == 200
    mock_insight_store.index_message.assert_called_once()
    kwargs = mock_insight_store.index_message.call_args.kwargs
    assert kwargs["text"] == "How should I prepare for consulting interviews?"
    assert kwargs["has_resume"] is True
    assert kwargs["active_career_type"] == response.json()["active_career_type"]


def test_chat_skips_index_when_feature_disabled(
    in_memory_qdrant, mock_embedder, monkeypatch
):
    import services.llm as llm_module

    monkeypatch.setattr(settings, "student_chat_insights_enabled", False)
    monkeypatch.setattr(settings, "student_chat_embedding_min_chars", 1)

    mock_insight_store = MagicMock()
    client = _make_client(in_memory_qdrant, mock_embedder, mock_insight_store)

    with patch.object(llm_module, "chat_with_context", return_value="Advice"):
        response = client.post(
            "/api/chat",
            json={
                "message": "Tell me about internship timing",
                "resume_text": None,
                "history": [],
            },
        )

    assert response.status_code == 200
    mock_insight_store.index_message.assert_not_called()


def test_chat_skips_index_for_short_messages(
    in_memory_qdrant, mock_embedder, monkeypatch
):
    import services.llm as llm_module

    monkeypatch.setattr(settings, "student_chat_insights_enabled", True)
    monkeypatch.setattr(settings, "student_chat_embedding_min_chars", 20)

    mock_insight_store = MagicMock()
    client = _make_client(in_memory_qdrant, mock_embedder, mock_insight_store)

    with patch.object(llm_module, "chat_with_context", return_value="Advice"):
        response = client.post(
            "/api/chat",
            json={
                "message": "hi",
                "resume_text": None,
                "history": [],
            },
        )

    assert response.status_code == 200
    mock_insight_store.index_message.assert_not_called()


def test_chat_continues_when_insight_indexing_fails(
    in_memory_qdrant, mock_embedder, monkeypatch
):
    import services.llm as llm_module

    monkeypatch.setattr(settings, "student_chat_insights_enabled", True)
    monkeypatch.setattr(settings, "student_chat_embedding_min_chars", 1)

    mock_insight_store = MagicMock()
    mock_insight_store.index_message.side_effect = RuntimeError("qdrant unavailable")
    client = _make_client(in_memory_qdrant, mock_embedder, mock_insight_store)

    with patch.object(
        llm_module, "chat_with_context", return_value="Still returns response"
    ):
        response = client.post(
            "/api/chat",
            json={
                "message": "What should I do next?",
                "resume_text": None,
                "history": [],
            },
        )

    assert response.status_code == 200
    assert response.json()["response"] == "Still returns response"
    mock_insight_store.index_message.assert_called_once()


def test_chat_with_no_intake_context_is_safe_when_context_flags_enabled(
    in_memory_qdrant, mock_embedder, monkeypatch
):
    import services.llm as llm_module

    monkeypatch.setattr(settings, "student_chat_insights_enabled", True)
    monkeypatch.setattr(settings, "student_chat_embedding_min_chars", 1)
    monkeypatch.setattr(settings, "student_chat_store_background", True)
    monkeypatch.setattr(settings, "student_chat_store_region", True)
    monkeypatch.setattr(settings, "student_chat_store_interest", True)

    real_store = StudentChatInsightStore(client=in_memory_qdrant)
    real_store.ensure_collection(dim=384)
    client = _make_client(in_memory_qdrant, mock_embedder, real_store)

    with patch.object(llm_module, "chat_with_context", return_value="Advice"):
        response = client.post(
            "/api/chat",
            json={
                "message": "What concerns should I prioritize first?",
                "resume_text": None,
                "history": [],
            },
        )

    assert response.status_code == 200

    points, _ = in_memory_qdrant.scroll(
        collection_name=settings.student_chat_collection_name,
        limit=10,
        with_payload=True,
        with_vectors=False,
    )
    assert len(points) == 1
    payload = points[0].payload
    assert payload["background"] is None
    assert payload["region"] is None
    assert payload["interest"] is None


def test_chat_indexes_message_text_only_when_resume_is_present(
    in_memory_qdrant, mock_embedder, monkeypatch
):
    import services.llm as llm_module

    monkeypatch.setattr(settings, "student_chat_insights_enabled", True)
    monkeypatch.setattr(settings, "student_chat_embedding_min_chars", 1)
    monkeypatch.setattr(settings, "student_chat_store_background", False)
    monkeypatch.setattr(settings, "student_chat_store_region", False)
    monkeypatch.setattr(settings, "student_chat_store_interest", False)

    real_store = StudentChatInsightStore(client=in_memory_qdrant)
    real_store.ensure_collection(dim=384)
    client = _make_client(in_memory_qdrant, mock_embedder, real_store)

    message = "How do I position my internship experience for consulting?"
    resume_text = "Private resume content that must never be indexed."
    with patch.object(llm_module, "chat_with_context", return_value="Advice"):
        response = client.post(
            "/api/chat",
            json={
                "message": message,
                "resume_text": resume_text,
                "history": [],
            },
        )

    assert response.status_code == 200

    points, _ = in_memory_qdrant.scroll(
        collection_name=settings.student_chat_collection_name,
        limit=10,
        with_payload=True,
        with_vectors=False,
    )
    assert len(points) == 1
    payload = points[0].payload
    assert payload["text"] == message
    assert payload["has_resume"] is True
    assert resume_text not in payload["text"]
    assert "resume_text" not in payload
