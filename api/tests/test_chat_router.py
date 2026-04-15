# api/tests/test_chat_router.py
import numpy as np
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Shared setup helpers
# ---------------------------------------------------------------------------

def _make_store(in_memory_qdrant):
    from services.vector_store import VectorStore
    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{
        "id": "c1", "vector": vec,
        "payload": {"source_filename": "guide.txt", "chunk_index": 0,
                    "upload_timestamp": "2026-01-01", "text": "GIC recruits from SMU"},
    }])
    return store, vec


def _mock_profile_store(get_profile_return=None, match_return=None):
    """Return a mock CareerProfileStore with controllable get_profile / match_career_type."""
    mock = MagicMock()
    mock.get_profile.return_value = get_profile_return
    mock.match_career_type.return_value = match_return
    mock.match_career_type_keywords.return_value = None
    return mock


# ---------------------------------------------------------------------------
# Existing behaviour — unchanged
# ---------------------------------------------------------------------------

def test_chat_returns_response_and_citations(in_memory_qdrant, mock_embedder):
    from main import app
    import dependencies
    import services.llm as llm_module
    from services.career_profiles import get_career_profile_store

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_career_profile_store] = lambda: _mock_profile_store()

    with patch.object(llm_module, "chat_with_context", return_value="Here is career advice"):
        client = TestClient(app)
        r = client.post("/api/chat", json={
            "message": "how do I get into GIC?", "resume_text": None, "history": [],
        })

    assert r.status_code == 200
    data = r.json()
    assert data["response"] == "Here is career advice"
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["filename"] == "guide.txt"


# ---------------------------------------------------------------------------
# Sprint 2 — intake_context resolution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("interest,expected_slug", [
    ("finance", "investment_banking"),
    ("consulting", "consulting"),
    ("tech", "tech_product"),
    ("public_sector", "public_sector"),
    ("not_sure", "general_singapore"),
])
def test_intake_context_resolves_career_type(in_memory_qdrant, mock_embedder, interest, expected_slug):
    from main import app
    import dependencies
    import services.llm as llm_module
    from services.career_profiles import get_career_profile_store

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec

    # Profile store: get_profile returns a minimal profile; cosine returns None (low score)
    fake_profile = {
        "career_type": "Test Track", "ep_sponsorship": "High",
        "compass_score_typical": "40-50", "top_employers_smu": ["Firm A"],
        "recruiting_timeline": "Oct–Jan", "international_realistic": True,
        "entry_paths": ["Internship"], "salary_range_2024": "S$60K",
        "typical_background": "Any", "notes": "",
    }
    mock_ps = _mock_profile_store(get_profile_return=fake_profile, match_return=None)

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_career_profile_store] = lambda: mock_ps

    with patch.object(llm_module, "chat_with_context", return_value="advice") as mock_llm:
        client = TestClient(app)
        r = client.post("/api/chat", json={
            "message": "help me",
            "resume_text": None,
            "history": [],
            "intake_context": {"interest": interest},
        })

    assert r.status_code == 200
    data = r.json()
    assert data["active_career_type"] == expected_slug
    # career_context must be non-None when a profile is active
    _, kwargs = mock_llm.call_args
    assert kwargs.get("career_context") is not None


def test_no_intake_no_active_type_returns_none(in_memory_qdrant, mock_embedder):
    from main import app
    import dependencies
    import services.llm as llm_module
    from services.career_profiles import get_career_profile_store

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec
    mock_ps = _mock_profile_store(get_profile_return=None, match_return=None)

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_career_profile_store] = lambda: mock_ps

    with patch.object(llm_module, "chat_with_context", return_value="advice") as mock_llm:
        client = TestClient(app)
        r = client.post("/api/chat", json={
            "message": "I want a job", "resume_text": None, "history": [],
        })

    assert r.status_code == 200
    data = r.json()
    assert data["active_career_type"] is None
    # career_context should be None → disambiguation instruction used in LLM
    _, kwargs = mock_llm.call_args
    career_context = kwargs.get("career_context")
    assert career_context is None


def test_career_context_injected_into_llm_when_profile_active(in_memory_qdrant, mock_embedder):
    """Assert the career context block is passed to chat_with_context when intake resolves."""
    from main import app
    import dependencies
    import services.llm as llm_module
    from services.career_profiles import get_career_profile_store, profile_to_context_block

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec

    fake_profile = {
        "career_type": "Investment Banking", "ep_sponsorship": "High at BBs",
        "compass_score_typical": "45-55", "top_employers_smu": ["Goldman Sachs"],
        "recruiting_timeline": "Oct–Jan", "international_realistic": True,
        "entry_paths": ["Summer internship → return offer"],
        "salary_range_2024": "S$85K–95K", "typical_background": "Finance/Econ", "notes": "",
    }
    mock_ps = _mock_profile_store(get_profile_return=fake_profile, match_return=None)

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_career_profile_store] = lambda: mock_ps

    expected_context = profile_to_context_block(fake_profile)

    with patch.object(llm_module, "chat_with_context", return_value="ib advice") as mock_llm:
        client = TestClient(app)
        r = client.post("/api/chat", json={
            "message": "how do I break into IBD?",
            "resume_text": None,
            "history": [],
            "intake_context": {"interest": "finance"},
        })

    assert r.status_code == 200
    _, kwargs = mock_llm.call_args
    assert kwargs.get("career_context") == expected_context


def test_active_career_type_echoed_back_in_response(in_memory_qdrant, mock_embedder):
    from main import app
    import dependencies
    import services.llm as llm_module
    from services.career_profiles import get_career_profile_store

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec
    fake_profile = {
        "career_type": "Consulting", "ep_sponsorship": "High at MBB",
        "compass_score_typical": "45-55", "top_employers_smu": ["McKinsey"],
        "recruiting_timeline": "Sep–Nov", "international_realistic": True,
        "entry_paths": ["Case interview"], "salary_range_2024": "S$90K",
        "typical_background": "Any", "notes": "",
    }
    mock_ps = _mock_profile_store(get_profile_return=fake_profile, match_return=None)

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_career_profile_store] = lambda: mock_ps

    with patch.object(llm_module, "chat_with_context", return_value="consulting advice"):
        client = TestClient(app)
        r = client.post("/api/chat", json={
            "message": "tell me about MBB",
            "resume_text": None,
            "history": [],
            "intake_context": {"interest": "consulting"},
        })

    assert r.status_code == 200
    assert r.json()["active_career_type"] == "consulting"


def test_cosine_match_overrides_active_career_type(in_memory_qdrant, mock_embedder):
    """If cosine score >= threshold for a new type, it overrides the client's active_career_type."""
    from main import app
    import dependencies
    import services.llm as llm_module
    from services.career_profiles import get_career_profile_store

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec
    fake_profile = {
        "career_type": "Consulting", "ep_sponsorship": "High",
        "compass_score_typical": "45", "top_employers_smu": ["BCG"],
        "recruiting_timeline": "Sep–Nov", "international_realistic": True,
        "entry_paths": ["Case"], "salary_range_2024": "S$90K",
        "typical_background": "Any", "notes": "",
    }
    # Cosine matches "consulting" even though client sent "investment_banking" as active
    mock_ps = _mock_profile_store(get_profile_return=fake_profile, match_return="consulting")

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_career_profile_store] = lambda: mock_ps

    with patch.object(llm_module, "chat_with_context", return_value="switched advice"):
        client = TestClient(app)
        r = client.post("/api/chat", json={
            "message": "what about BCG?",
            "resume_text": None,
            "history": [],
            "active_career_type": "investment_banking",
        })

    assert r.status_code == 200
    assert r.json()["active_career_type"] == "consulting"


def test_stale_active_career_type_from_client_falls_through(in_memory_qdrant, mock_embedder):
    """Unknown slug from client (stale/typo) → treated as None, no profile injected."""
    from main import app
    import dependencies
    import services.llm as llm_module
    from services.career_profiles import get_career_profile_store

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec
    # get_profile returns None for the unknown slug (and logs a warning)
    mock_ps = _mock_profile_store(get_profile_return=None, match_return=None)

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_career_profile_store] = lambda: mock_ps

    with patch.object(llm_module, "chat_with_context", return_value="no profile advice") as mock_llm:
        client = TestClient(app)
        r = client.post("/api/chat", json={
            "message": "what should I do?",
            "resume_text": None,
            "history": [],
            "active_career_type": "renamed_old_track",
        })

    assert r.status_code == 200
    assert r.json()["active_career_type"] is None
    _, kwargs = mock_llm.call_args
    assert kwargs.get("career_context") is None


def test_keyword_match_activates_track_when_no_active_type(in_memory_qdrant, mock_embedder):
    from main import app
    import dependencies
    import services.llm as llm_module
    from services.career_profiles import get_career_profile_store

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec
    fake_profile = {
        "career_type": "Data Science", "ep_sponsorship": "High",
        "compass_score_typical": "45-60", "top_employers_smu": ["Grab"],
        "recruiting_timeline": "Sep-Nov", "international_realistic": True,
        "entry_paths": ["Internship"], "salary_range_2024": "S$80K",
        "typical_background": "Stats/CS", "notes": "",
    }
    mock_ps = _mock_profile_store(get_profile_return=fake_profile, match_return=None)
    mock_ps.match_career_type_keywords.return_value = "data_science"

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_career_profile_store] = lambda: mock_ps

    with patch.object(llm_module, "chat_with_context", return_value="ds advice"):
        client = TestClient(app)
        r = client.post("/api/chat", json={
            "message": "I want to move into data science roles",
            "resume_text": None,
            "history": [],
        })

    assert r.status_code == 200
    assert r.json()["active_career_type"] == "data_science"


def test_active_career_type_blocks_keyword_track_flapping(in_memory_qdrant, mock_embedder):
    from main import app
    import dependencies
    import services.llm as llm_module
    from services.career_profiles import get_career_profile_store

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec
    fake_profile = {
        "career_type": "Consulting", "ep_sponsorship": "High",
        "compass_score_typical": "45", "top_employers_smu": ["BCG"],
        "recruiting_timeline": "Sep-Nov", "international_realistic": True,
        "entry_paths": ["Case"], "salary_range_2024": "S$90K",
        "typical_background": "Any", "notes": "",
    }
    mock_ps = _mock_profile_store(get_profile_return=fake_profile, match_return=None)
    mock_ps.match_career_type_keywords.return_value = "data_science"

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_career_profile_store] = lambda: mock_ps

    with patch.object(llm_module, "chat_with_context", return_value="keep track"):
        client = TestClient(app)
        r = client.post("/api/chat", json={
            "message": "data science sounds interesting too",
            "resume_text": None,
            "history": [],
            "active_career_type": "consulting",
        })

    assert r.status_code == 200
    assert r.json()["active_career_type"] == "consulting"


def test_employer_context_not_injected_without_active_career_type(in_memory_qdrant, mock_embedder):
    from main import app
    import dependencies
    import services.llm as llm_module
    from services.career_profiles import get_career_profile_store
    from services.employer_store import get_employer_store

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec
    mock_ps = _mock_profile_store(get_profile_return=None, match_return=None)

    mock_employer_store = MagicMock()
    mock_employer_store.to_context_block.return_value = ""

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_career_profile_store] = lambda: mock_ps
    app.dependency_overrides[get_employer_store] = lambda: mock_employer_store

    with patch.object(llm_module, "chat_with_context", return_value="general advice") as mock_llm:
        client = TestClient(app)
        r = client.post("/api/chat", json={
            "message": "What should I explore?",
            "resume_text": None,
            "history": [],
        })

    assert r.status_code == 200
    mock_employer_store.to_context_block.assert_called_once_with(
        active_career_type=None,
        query_text="What should I explore?",
        profile_top_employers=None,
    )
    _, kwargs = mock_llm.call_args
    assert kwargs.get("employer_context") is None


def test_chat_passes_message_to_employer_matching_layer(in_memory_qdrant, mock_embedder):
    from main import app
    import dependencies
    import services.llm as llm_module
    from services.career_profiles import get_career_profile_store
    from services.employer_store import get_employer_store

    store, vec = _make_store(in_memory_qdrant)
    mock_embedder.encode.return_value = vec
    mock_ps = _mock_profile_store(get_profile_return=None, match_return=None)

    mock_employer_store = MagicMock()
    mock_employer_store.to_context_block.return_value = "=== EMPLOYER FACTS ===\n  DBS:\n=== END EMPLOYER FACTS ==="

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    app.dependency_overrides[get_career_profile_store] = lambda: mock_ps
    app.dependency_overrides[get_employer_store] = lambda: mock_employer_store

    with patch.object(llm_module, "chat_with_context", return_value="dbs advice") as mock_llm:
        client = TestClient(app)
        r = client.post("/api/chat", json={
            "message": "What are DBS hiring requirements?",
            "resume_text": None,
            "history": [],
        })

    assert r.status_code == 200
    mock_employer_store.to_context_block.assert_called_once_with(
        active_career_type=None,
        query_text="What are DBS hiring requirements?",
        profile_top_employers=None,
    )
    _, kwargs = mock_llm.call_args
    assert kwargs.get("employer_context") is not None
