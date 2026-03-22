# api/tests/test_brief_router.py
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch


def test_brief_returns_brief_text(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies
    import services.llm as llm_module

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    vec = np.ones(384, dtype=np.float32)
    mock_embedder.encode.return_value = vec
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

    with patch.object(llm_module, "generate_brief", return_value="# Student Brief\nGoals: finance"):
        client = TestClient(app)
        r = client.post("/api/brief", json={"resume_text": "SMU Business Year 3, interested in GIC"})

    assert r.status_code == 200
    assert "brief" in r.json()
