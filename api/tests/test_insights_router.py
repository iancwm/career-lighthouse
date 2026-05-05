from unittest.mock import MagicMock

import numpy as np
from fastapi.testclient import TestClient

import dependencies
from config import settings
from services.student_chat_insights import StudentChatInsightStore


def _make_client(in_memory_qdrant, mock_embedder):
    from main import app

    store = StudentChatInsightStore(client=in_memory_qdrant)
    store.ensure_collection(dim=384)
    app.dependency_overrides[dependencies.get_student_insight_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    return TestClient(app), store


def _seed_insight(
    store: StudentChatInsightStore,
    *,
    message_id: str,
    text: str,
    timestamp: str,
    vector: np.ndarray,
    active_career_type: str | None = None,
    background: str | None = None,
    region: str | None = None,
) -> None:
    assert store._store is not None
    payload = {
        "message_id": message_id,
        "timestamp": timestamp,
        "role": "user",
        "text": text,
        "has_resume": False,
        "source_channel": "student_chat",
        "schema_version": 1,
    }
    if active_career_type is not None:
        payload["active_career_type"] = active_career_type
    if background is not None:
        payload["background"] = background
    if region is not None:
        payload["region"] = region
    store._store.upsert([{"id": message_id, "vector": vector, "payload": payload}])


def test_requires_admin_key_when_configured(
    in_memory_qdrant, mock_embedder, monkeypatch
):
    monkeypatch.setattr(settings, "admin_key", "super-secret")
    monkeypatch.setattr(settings, "student_chat_insights_enabled", True)

    client, _ = _make_client(in_memory_qdrant, mock_embedder)
    response = client.post(
        "/api/insights/student-questions/search",
        json={"query": "interview prep"},
    )

    assert response.status_code == 401


def test_search_returns_empty_results_on_empty_collection(
    in_memory_qdrant, mock_embedder, monkeypatch
):
    monkeypatch.setattr(settings, "admin_key", "")
    monkeypatch.setattr(settings, "student_chat_insights_enabled", True)
    monkeypatch.setattr(settings, "student_chat_store_background", False)
    monkeypatch.setattr(settings, "student_chat_store_region", False)

    client, _ = _make_client(in_memory_qdrant, mock_embedder)
    response = client.post(
        "/api/insights/student-questions/search",
        json={"query": "international hiring"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []
    assert data["total_returned"] == 0
    assert data["insights_enabled"] is True
    assert data["supports_background_filter"] is False
    assert data["supports_region_filter"] is False


def test_search_applies_career_type_filter(
    in_memory_qdrant, mock_embedder, monkeypatch
):
    monkeypatch.setattr(settings, "admin_key", "")
    monkeypatch.setattr(settings, "student_chat_insights_enabled", True)
    monkeypatch.setattr(settings, "student_chat_store_background", True)
    monkeypatch.setattr(settings, "student_chat_store_region", False)

    query_vec = np.ones(384, dtype=np.float32)
    mock_embedder.encode.return_value = query_vec
    client, store = _make_client(in_memory_qdrant, mock_embedder)

    _seed_insight(
        store,
        message_id="career-1",
        text="How do I prep for product interviews?",
        timestamp="2026-03-01T00:00:00+00:00",
        active_career_type="product_management",
        vector=query_vec,
    )
    _seed_insight(
        store,
        message_id="career-2",
        text="How do I break into consulting?",
        timestamp="2026-03-02T00:00:00+00:00",
        active_career_type="consulting",
        vector=query_vec,
    )

    response = client.post(
        "/api/insights/student-questions/search",
        json={
            "query": "interview prep",
            "career_type": "consulting",
            "top_k": 10,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_returned"] == 1
    assert data["results"][0]["message_id"] == "career-2"
    assert data["results"][0]["active_career_type"] == "consulting"
    assert data["insights_enabled"] is True
    assert data["supports_background_filter"] is True
    assert data["supports_region_filter"] is False


def test_search_applies_date_range_filter(in_memory_qdrant, mock_embedder, monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "")
    monkeypatch.setattr(settings, "student_chat_insights_enabled", True)
    monkeypatch.setattr(settings, "student_chat_store_background", False)
    monkeypatch.setattr(settings, "student_chat_store_region", True)

    query_vec = np.ones(384, dtype=np.float32)
    mock_embedder.encode.return_value = query_vec
    client, store = _make_client(in_memory_qdrant, mock_embedder)

    _seed_insight(
        store,
        message_id="date-1",
        text="Old question",
        timestamp="2026-01-01T00:00:00+00:00",
        active_career_type="consulting",
        vector=query_vec,
    )
    _seed_insight(
        store,
        message_id="date-2",
        text="Recent question",
        timestamp="2026-03-15T00:00:00+00:00",
        active_career_type="consulting",
        vector=query_vec,
    )

    response = client.post(
        "/api/insights/student-questions/search",
        json={
            "query": "recent student concerns",
            "date_from": "2026-03-01T00:00:00+00:00",
            "date_to": "2026-03-31T23:59:59+00:00",
            "top_k": 10,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_returned"] == 1
    assert data["results"][0]["message_id"] == "date-2"
    assert data["insights_enabled"] is True
    assert data["supports_background_filter"] is False
    assert data["supports_region_filter"] is True


def test_search_returns_disabled_response_when_feature_flag_off(
    mock_embedder, monkeypatch
):
    from main import app

    monkeypatch.setattr(settings, "admin_key", "")
    monkeypatch.setattr(settings, "student_chat_insights_enabled", False)
    monkeypatch.setattr(settings, "student_chat_store_background", True)
    monkeypatch.setattr(settings, "student_chat_store_region", False)

    mock_store = MagicMock()
    app.dependency_overrides[dependencies.get_student_insight_store] = lambda: (
        mock_store
    )
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

    client = TestClient(app)
    response = client.post(
        "/api/insights/student-questions/search",
        json={"query": "anything"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["results"] == []
    assert data["total_returned"] == 0
    assert data["insights_enabled"] is False
    assert data["supports_background_filter"] is True
    assert data["supports_region_filter"] is False
    mock_embedder.encode.assert_not_called()
    mock_store.search.assert_not_called()


def test_search_handles_missing_optional_fields_as_null(
    in_memory_qdrant, mock_embedder, monkeypatch
):
    monkeypatch.setattr(settings, "admin_key", "")
    monkeypatch.setattr(settings, "student_chat_insights_enabled", True)
    monkeypatch.setattr(settings, "student_chat_store_background", False)
    monkeypatch.setattr(settings, "student_chat_store_region", False)

    query_vec = np.ones(384, dtype=np.float32)
    mock_embedder.encode.return_value = query_vec
    client, store = _make_client(in_memory_qdrant, mock_embedder)

    _seed_insight(
        store,
        message_id="missing-optional-1",
        text="Question without optional metadata",
        timestamp="2026-04-01T00:00:00+00:00",
        vector=query_vec,
    )

    response = client.post(
        "/api/insights/student-questions/search",
        json={"query": "metadata gaps"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_returned"] == 1
    result = data["results"][0]
    assert result["message_id"] == "missing-optional-1"
    assert result["active_career_type"] is None
    assert result["background"] is None
    assert result["region"] is None
    assert result["source_label"] == "Student chat"
    assert data["insights_enabled"] is True
    assert data["supports_background_filter"] is False
    assert data["supports_region_filter"] is False
