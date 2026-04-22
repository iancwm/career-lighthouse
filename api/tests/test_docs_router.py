# api/tests/test_docs_router.py
import numpy as np
from fastapi.testclient import TestClient
from services import health_cache


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


def test_delete_doc_invalidates_overlap_cache(in_memory_qdrant):
    client, store = make_client(in_memory_qdrant)
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{
        "id": "remove-0",
        "vector": vec,
        "payload": {
            "source_filename": "remove.txt",
            "chunk_index": 0,
            "upload_timestamp": "2026-01-01T00:00:00",
            "text": "to delete",
        },
    }])

    health_cache.set_overlap_pairs([{"doc_a": "remove.txt", "doc_b": "other.txt", "overlap_pct": 0.9}])
    assert health_cache.get_overlap_pairs() is not None

    r = client.delete("/api/docs/remove.txt")

    assert r.status_code == 200
    assert r.json()["status"] == "deleted"
    assert health_cache.get_overlap_pairs() is None
    docs = store.list_docs()
    assert len(docs) == 1
    assert docs[0]["filename"] == "remove.txt"
    assert docs[0]["lifecycle"] == "archived"
    assert docs[0]["chunk_count"] == 0


def test_backfill_legacy_docs_seeds_active_ledger_entries(in_memory_qdrant):
    client, store = make_client(in_memory_qdrant)
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{
        "id": "legacy-0",
        "vector": vec,
        "payload": {
            "source_filename": "legacy.txt",
            "chunk_index": 0,
            "upload_timestamp": "2025-01-01T00:00:00",
            "text": "legacy content",
        },
    }])

    from services.source_ledger import get_source_ledger_store

    ledger = get_source_ledger_store()
    added = ledger.backfill_from_docs(store.list_docs())
    assert added == 1
    assert ledger.get_record("legacy.txt")["lifecycle"] == "active"

    assert ledger.backfill_from_docs(store.list_docs()) == 0
    docs = client.get("/api/docs").json()
    assert docs[0]["filename"] == "legacy.txt"
    assert docs[0]["lifecycle"] == "active"
