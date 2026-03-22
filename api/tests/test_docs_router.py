# api/tests/test_docs_router.py
import numpy as np
from fastapi.testclient import TestClient


def make_client(in_memory_qdrant):
    from main import app
    from services.vector_store import VectorStore
    import dependencies

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    return TestClient(app), store


def test_list_docs_empty(in_memory_qdrant):
    client, _ = make_client(in_memory_qdrant)
    r = client.get("/api/docs")
    assert r.status_code == 200
    assert r.json() == []


def test_delete_doc_not_found(in_memory_qdrant):
    client, _ = make_client(in_memory_qdrant)
    r = client.delete("/api/docs/nonexistent.txt")
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"
