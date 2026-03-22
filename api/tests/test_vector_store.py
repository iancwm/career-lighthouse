# api/tests/test_vector_store.py
import numpy as np
import pytest
from services.vector_store import VectorStore

COLLECTION = "knowledge"


@pytest.fixture
def store(in_memory_qdrant):
    vs = VectorStore(client=in_memory_qdrant, collection=COLLECTION)
    vs.ensure_collection(dim=384)
    return vs


def test_upsert_and_search(store):
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{
        "id": "test-1",
        "vector": vec,
        "payload": {"source_filename": "test.txt", "chunk_index": 0,
                    "upload_timestamp": "2026-01-01T00:00:00", "text": "career advice"}
    }])
    results = store.search(vec, top_k=1)
    assert len(results) == 1
    assert results[0]["payload"]["source_filename"] == "test.txt"
    assert results[0]["payload"]["text"] == "career advice"


def test_delete_by_filename(store):
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{
        "id": "del-1",
        "vector": vec,
        "payload": {"source_filename": "remove.txt", "chunk_index": 0,
                    "upload_timestamp": "2026-01-01T00:00:00", "text": "to delete"}
    }])
    store.delete_by_filename("remove.txt")
    results = store.search(vec, top_k=10)
    filenames = [r["payload"]["source_filename"] for r in results]
    assert "remove.txt" not in filenames


def test_list_docs(store):
    vec = np.ones(384, dtype=np.float32)
    store.upsert([
        {"id": "a-0", "vector": vec, "payload": {"source_filename": "a.txt", "chunk_index": 0,
          "upload_timestamp": "2026-01-01T00:00:00", "text": "chunk a"}},
        {"id": "a-1", "vector": vec, "payload": {"source_filename": "a.txt", "chunk_index": 1,
          "upload_timestamp": "2026-01-01T00:00:00", "text": "chunk a2"}},
        {"id": "b-0", "vector": vec, "payload": {"source_filename": "b.txt", "chunk_index": 0,
          "upload_timestamp": "2026-01-02T00:00:00", "text": "chunk b"}},
    ])
    docs = store.list_docs()
    assert len(docs) == 2
    doc_a = next(d for d in docs if d["filename"] == "a.txt")
    assert doc_a["chunk_count"] == 2
