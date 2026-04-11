"""Tests for the session router — Task 0 scaffolding."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
from datetime import datetime, timezone


@pytest.fixture(autouse=True)
def reset_session_store():
    """Reset SessionStore singleton between tests."""
    from services.session_store import SessionStore
    SessionStore._instance = None
    yield
    SessionStore._instance = None


@pytest.fixture
def mock_session_store():
    """Return a mocked SessionStore."""
    mock = MagicMock()
    return mock


@pytest.fixture
def app(mock_session_store):
    """Build a minimal FastAPI app with only the session router, with mocked store."""
    # Patch SessionStore before loading the module
    with patch("services.session_store.SessionStore") as MockStore:
        MockStore.return_value = mock_session_store
        MockStore._instance = mock_session_store

        import importlib.util
        spec = importlib.util.spec_from_file_location("session_router", "routers/session_router.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["session_router"] = module
        spec.loader.exec_module(module)

        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(module.router)
        yield app


def _make_session(**overrides):
    """Helper to create a KnowledgeSession with sensible defaults."""
    defaults = {
        "id": "test-session-id",
        "status": "in-progress",
        "raw_input": "notes",
        "created_by": "counsellor",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    defaults.update(overrides)
    from models import KnowledgeSession
    return KnowledgeSession(**defaults)


class TestCreateSessionJsonBody:
    """POST /api/sessions must accept a JSON body, not a query param."""

    def test_create_session_with_json_body(self, app, mock_session_store):
        """Sending a JSON body with raw_input and counsellor_id should return 201."""
        mock_session_store.create_session.return_value = _make_session(
            id="test-session-id", raw_input="Some research notes", created_by="alice"
        )

        client = TestClient(app)
        resp = client.post("/api/sessions", json={
            "raw_input": "Some research notes",
            "counsellor_id": "alice",
        })

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "test-session-id"
        assert body["status"] == "in-progress"
        mock_session_store.create_session.assert_called_once_with("Some research notes", created_by="alice")

    def test_create_session_uses_default_counsellor_id(self, app, mock_session_store):
        """Omitting counsellor_id should default to 'counsellor'."""
        mock_session_store.create_session.return_value = _make_session(raw_input="Notes here")

        client = TestClient(app)
        resp = client.post("/api/sessions", json={"raw_input": "Notes here"})

        assert resp.status_code == 201
        mock_session_store.create_session.assert_called_once_with("Notes here", created_by="counsellor")

    def test_create_session_rejects_missing_body(self, app):
        """POST without a body should return 422."""
        client = TestClient(app)
        resp = client.post("/api/sessions", content=b"")
        assert resp.status_code in (422, 400)

    def test_create_session_rejects_missing_raw_input(self, app):
        """POST with an empty JSON object should return 422."""
        client = TestClient(app)
        resp = client.post("/api/sessions", json={})
        assert resp.status_code == 422


class TestGetSession:
    def test_get_existing_session(self, app, mock_session_store):
        mock_session_store.get_session.return_value = _make_session(id="abc-123")

        client = TestClient(app)
        resp = client.get("/api/sessions/abc-123")

        assert resp.status_code == 200
        assert resp.json()["id"] == "abc-123"

    def test_get_missing_session_returns_404(self, app, mock_session_store):
        mock_session_store.get_session.return_value = None

        client = TestClient(app)
        resp = client.get("/api/sessions/nonexistent")

        assert resp.status_code == 404


class TestAnalyzeSession:
    def test_analyze_existing_session(self, app, mock_session_store):
        mock_session_store.get_session.return_value = _make_session(id="abc-123", status="analyzed")

        client = TestClient(app)
        resp = client.post("/api/sessions/abc-123/analyze")

        assert resp.status_code == 200
        body = resp.json()
        assert body["session_id"] == "abc-123"

    def test_analyze_missing_session_returns_404(self, app, mock_session_store):
        mock_session_store.get_session.return_value = None

        client = TestClient(app)
        resp = client.post("/api/sessions/nonexistent/analyze")

        assert resp.status_code == 404


class TestModelsExist:
    """Verify the new request/response models can be imported and instantiated."""

    def test_create_session_request_model(self):
        from models import CreateSessionRequest
        req = CreateSessionRequest(raw_input="test notes")
        assert req.raw_input == "test notes"
        assert req.counsellor_id == "counsellor"  # default

    def test_create_session_request_custom_counsellor(self):
        from models import CreateSessionRequest
        req = CreateSessionRequest(raw_input="notes", counsellor_id="bob")
        assert req.counsellor_id == "bob"

    def test_card_commit_response_model(self):
        from models import CardCommitResponse
        resp = CardCommitResponse(card_id="c1", domain="employer", status="committed", message="done")
        assert resp.card_id == "c1"
        assert resp.domain == "employer"

    def test_card_discard_response_model(self):
        from models import CardDiscardResponse
        resp = CardDiscardResponse(card_id="c1")
        assert resp.card_id == "c1"
        assert resp.status == "discarded"


class TestSessionRouterExported:
    """session_router must be importable from the routers package."""

    def test_session_router_module_exists(self):
        """Direct import of session_router module works."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("session_router", "routers/session_router.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.router is not None
        assert hasattr(module.router, "routes")

    def test_session_router_in_all_source(self):
        """__init__.py source code includes session_router in __all__."""
        init_path = "routers/__init__.py"
        with open(init_path) as f:
            content = f.read()
        assert "session_router" in content
