# api/tests/conftest.py
import os
import pytest
from unittest.mock import MagicMock
import numpy as np

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
