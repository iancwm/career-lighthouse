# api/tests/test_chat_router.py
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch


def test_chat_returns_response_and_citations(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies
    import services.llm as llm_module

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{"id": "c1", "vector": vec,
                   "payload": {"source_filename": "guide.txt", "chunk_index": 0,
                               "upload_timestamp": "2026-01-01", "text": "GIC recruits from SMU"}}])
    mock_embedder.encode.return_value = vec
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

    with patch.object(llm_module, "chat_with_context", return_value="Here is career advice"):
        client = TestClient(app)
        r = client.post("/api/chat", json={"message": "how do I get into GIC?", "resume_text": None, "history": []})

    assert r.status_code == 200
    data = r.json()
    assert data["response"] == "Here is career advice"
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["filename"] == "guide.txt"
