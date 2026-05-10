# api/tests/conftest.py
import pytest
from unittest.mock import MagicMock
import numpy as np
from limiter import limiter


@pytest.fixture
def mock_embedder():
    """Returns a fixed 384-dim vector for any input."""
    mock = MagicMock()
    mock.encode.return_value = np.ones(384, dtype=np.float32)
    return mock


@pytest.fixture
def in_memory_qdrant():
    """Qdrant client using in-memory storage for tests."""
    from qdrant_client import QdrantClient

    client = QdrantClient(":memory:")
    return client


@pytest.fixture(autouse=True)
def clear_env_secrets(monkeypatch, tmp_path):
    """Ensure sensitive environment variables don't leak from dev .env into tests.
    ADMIN_KEY='' forces development mode (auth bypass).
    """
    monkeypatch.setenv("ADMIN_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    monkeypatch.setenv("SENTENCE_TRANSFORMERS_HOME", str(tmp_path / "cache"))


@pytest.fixture(autouse=True)
def reset_docs_cache():
    """Invalidate the list_docs() TTL cache before and after each test."""
    try:
        from services.kb_health import invalidate_docs_cache

        invalidate_docs_cache()
    except Exception:
        pass
    yield
    try:
        from services.kb_health import invalidate_docs_cache

        invalidate_docs_cache()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Ensure per-test rate limiting state does not leak across the suite."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def reset_app_overrides():
    """Keep FastAPI dependency overrides scoped to each test."""
    try:
        from main import app
    except Exception:
        app = None
    if app is not None:
        app.dependency_overrides.clear()
    yield
    if app is not None:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_source_ledger(monkeypatch, tmp_path):
    """Keep the source ledger isolated to each test case."""
    monkeypatch.setenv("SOURCE_LEDGER_DIR", str(tmp_path / "source_ledger"))
    monkeypatch.setenv(
        "SOURCE_LEDGER_HISTORY_DIR", str(tmp_path / "source_ledger_history")
    )
    try:
        from services.source_ledger import SourceLedgerStore

        SourceLedgerStore._instance = None
    except Exception:
        pass
    yield
    try:
        from services.source_ledger import SourceLedgerStore

        SourceLedgerStore._instance = None
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Real-service fixtures (for integration/eval tests)
# These are clearly named with 'real_' prefix to prevent accidental use
# in unit tests that expect mocks.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_embedder():
    """Real SentenceTransformer embedder — use ONLY in integration tests."""
    from services.embedder import Embedder

    return Embedder()
