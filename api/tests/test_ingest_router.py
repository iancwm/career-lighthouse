# api/tests/test_ingest_router.py
import numpy as np
from fastapi.testclient import TestClient


def test_ingest_txt_file(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    mock_embedder.encode_batch.return_value = np.ones((1, 384), dtype=np.float32)

    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

    client = TestClient(app)
    r = client.post("/api/ingest", files={"file": ("test.txt", b"hello world career", "text/plain")})
    assert r.status_code == 200
    data = r.json()
    assert data["doc_id"] == "test.txt"
    assert data["chunk_count"] >= 1
    assert data["status"] == "ok"
