# api/tests/test_ingest_dedup.py
"""Tests for deduplication check in POST /api/ingest."""
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import MagicMock


def make_ingest_client(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    return TestClient(app), store


class TestIngestDedup:
    def test_unique_doc_no_warning(self, in_memory_qdrant, mock_embedder):
        """Uploading into an empty KB should produce no similarity_warning."""
        # Make embedder return distinct vectors so no overlap
        mock_embedder.encode_batch.return_value = np.random.rand(1, 384).astype(np.float32)
        client, _ = make_ingest_client(in_memory_qdrant, mock_embedder)

        r = client.post("/api/ingest", files={"file": ("unique.txt", b"brand new content about GIC", "text/plain")})

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["similarity_warning"] is None
        assert data["overlap_pct"] == 0.0

    def test_duplicate_doc_produces_warning(self, in_memory_qdrant, mock_embedder):
        """Uploading content with high similarity to existing docs triggers a warning."""
        client, store = make_ingest_client(in_memory_qdrant, mock_embedder)

        # Seed an existing document with all-ones vectors
        identical_vec = np.ones(384, dtype=np.float32)
        store.upsert([{
            "id": "existing-0",
            "vector": identical_vec,
            "payload": {
                "source_filename": "existing.txt",
                "chunk_index": 0,
                "upload_timestamp": "2026-01-01",
                "text": "existing content",
            },
        }])

        # Upload new file — embedder returns identical vectors (100% overlap)
        mock_embedder.encode_batch.return_value = np.ones((1, 384), dtype=np.float32)

        r = client.post("/api/ingest", files={"file": ("new.txt", b"same content", "text/plain")})

        assert r.status_code == 200
        data = r.json()
        assert data["similarity_warning"] is not None
        assert "existing.txt" in data["similarity_warning"]
        assert data["overlap_pct"] > 0.0
        assert "existing.txt" in data["overlapping_docs"]

    def test_empty_kb_no_warning(self, in_memory_qdrant, mock_embedder):
        """Dedup check against empty KB must not error and must return no warning."""
        mock_embedder.encode_batch.return_value = np.ones((3, 384), dtype=np.float32)
        client, _ = make_ingest_client(in_memory_qdrant, mock_embedder)

        r = client.post("/api/ingest", files={"file": ("doc.txt", b"word " * 200, "text/plain")})

        assert r.status_code == 200
        assert r.json()["similarity_warning"] is None

    def test_ingest_response_backward_compatible(self, in_memory_qdrant, mock_embedder):
        """Existing fields (doc_id, chunk_count, status) must always be present."""
        mock_embedder.encode_batch.return_value = np.ones((1, 384), dtype=np.float32)
        client, _ = make_ingest_client(in_memory_qdrant, mock_embedder)

        r = client.post("/api/ingest", files={"file": ("t.txt", b"hello world", "text/plain")})

        data = r.json()
        assert "doc_id" in data
        assert "chunk_count" in data
        assert "status" in data
