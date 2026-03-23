# api/tests/test_kb_router.py
import json
import os
import tempfile
import numpy as np
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


def make_client(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    return TestClient(app), store


def seed_chunk(store, filename, chunk_text, chunk_index=0):
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{
        "id": f"{filename}-{chunk_index}",
        "vector": vec,
        "payload": {
            "source_filename": filename,
            "chunk_index": chunk_index,
            "upload_timestamp": "2026-01-01T00:00:00+00:00",
            "text": chunk_text,
        },
    }])


# ---------------------------------------------------------------------------
# POST /api/kb/test-query
# ---------------------------------------------------------------------------

class TestTestQuery:
    def test_returns_chunks_with_scores(self, in_memory_qdrant, mock_embedder):
        client, store = make_client(in_memory_qdrant, mock_embedder)
        seed_chunk(store, "guide.txt", "SMU career guide content")

        r = client.post("/api/kb/test-query", json={"query": "career advice"})

        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert data[0]["source_filename"] == "guide.txt"
        assert "excerpt" in data[0]
        assert isinstance(data[0]["score"], float)
        assert len(data[0]["excerpt"]) <= 300

    def test_empty_kb_returns_empty_list(self, in_memory_qdrant, mock_embedder):
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        r = client.post("/api/kb/test-query", json={"query": "anything"})

        assert r.status_code == 200
        assert r.json() == []

    def test_503_when_qdrant_unavailable(self, mock_embedder):
        from main import app
        import dependencies

        broken_store = object()  # not a VectorStore — will raise on .search()
        app.dependency_overrides[dependencies.get_vector_store] = lambda: broken_store
        app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/kb/test-query", json={"query": "anything"})

        assert r.status_code == 503
        assert "unavailable" in r.json()["detail"].lower()

        app.dependency_overrides.pop(dependencies.get_vector_store)
        app.dependency_overrides.pop(dependencies.get_embedder)


# ---------------------------------------------------------------------------
# GET /api/kb/health — doc coverage
# ---------------------------------------------------------------------------

class TestKBHealthDocCoverage:
    def test_empty_kb_returns_zeroes_and_nulls(self, in_memory_qdrant, mock_embedder):
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        r = client.get("/api/kb/health")

        assert r.status_code == 200
        data = r.json()
        assert data["total_docs"] == 0
        assert data["total_chunks"] == 0
        assert data["avg_match_score"] is None
        assert data["retrieval_diversity_score"] is None
        assert data["low_confidence_queries"] == []
        assert data["doc_coverage"] == []

    def test_doc_with_20_plus_chunks_is_good(self, in_memory_qdrant, mock_embedder):
        client, store = make_client(in_memory_qdrant, mock_embedder)
        for i in range(20):
            seed_chunk(store, "big-doc.txt", f"chunk {i}", chunk_index=i)

        r = client.get("/api/kb/health")

        assert r.status_code == 200
        coverage = {d["filename"]: d for d in r.json()["doc_coverage"]}
        assert coverage["big-doc.txt"]["coverage_status"] == "good"
        assert coverage["big-doc.txt"]["chunk_count"] == 20

    def test_doc_with_fewer_than_20_chunks_is_thin(self, in_memory_qdrant, mock_embedder):
        client, store = make_client(in_memory_qdrant, mock_embedder)
        for i in range(5):
            seed_chunk(store, "small-doc.txt", f"chunk {i}", chunk_index=i)

        r = client.get("/api/kb/health")

        coverage = {d["filename"]: d for d in r.json()["doc_coverage"]}
        assert coverage["small-doc.txt"]["coverage_status"] == "thin"

    def test_503_when_qdrant_unavailable(self, mock_embedder):
        from main import app
        import dependencies

        broken_store = object()
        app.dependency_overrides[dependencies.get_vector_store] = lambda: broken_store
        app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/kb/health")

        assert r.status_code == 503

        app.dependency_overrides.pop(dependencies.get_vector_store)
        app.dependency_overrides.pop(dependencies.get_embedder)


# ---------------------------------------------------------------------------
# GET /api/kb/health — query log metrics
# ---------------------------------------------------------------------------

class TestKBHealthQueryLog:
    def _write_log(self, path, entries):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_absent_log_returns_null_metrics(self, in_memory_qdrant, mock_embedder, tmp_path):
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        log_path = str(tmp_path / "no_log.jsonl")

        with patch("routers.kb_router.settings") as mock_settings:
            mock_settings.query_log_path = log_path
            r = client.get("/api/kb/health")

        data = r.json()
        assert data["avg_match_score"] is None
        assert data["low_confidence_queries"] == []

    def test_avg_match_score_computed_from_log(self, in_memory_qdrant, mock_embedder, tmp_path):
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        log_path = str(tmp_path / "query_log.jsonl")
        self._write_log(log_path, [
            {"ts": "2026-03-22T10:00:00+00:00", "query_text": "q1", "scores": [0.8, 0.5], "doc_matched": "a.txt", "top_docs": ["a.txt", "b.txt"]},
            {"ts": "2026-03-22T11:00:00+00:00", "query_text": "q2", "scores": [0.6, 0.4], "doc_matched": "b.txt", "top_docs": ["b.txt", "a.txt"]},
        ])

        with patch("routers.kb_router.settings") as mock_settings:
            mock_settings.query_log_path = log_path
            r = client.get("/api/kb/health")

        data = r.json()
        assert data["avg_match_score"] == pytest.approx(0.7, abs=0.001)

    def test_low_confidence_query_appears_in_list(self, in_memory_qdrant, mock_embedder, tmp_path):
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        log_path = str(tmp_path / "query_log.jsonl")
        self._write_log(log_path, [
            {"ts": "2026-03-22T10:00:00+00:00", "query_text": "weak question", "scores": [0.20], "doc_matched": None, "top_docs": []},
            {"ts": "2026-03-22T11:00:00+00:00", "query_text": "strong question", "scores": [0.90], "doc_matched": "a.txt", "top_docs": ["a.txt"]},
        ])

        with patch("routers.kb_router.settings") as mock_settings:
            mock_settings.query_log_path = log_path
            r = client.get("/api/kb/health")

        data = r.json()
        lc = data["low_confidence_queries"]
        assert len(lc) == 1
        assert lc[0]["query_text"] == "weak question"
        assert lc[0]["max_score"] == pytest.approx(0.20, abs=0.001)

    def test_malformed_log_line_skipped(self, in_memory_qdrant, mock_embedder, tmp_path):
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        log_path = str(tmp_path / "query_log.jsonl")
        with open(log_path, "w") as f:
            f.write("this is not json\n")
            f.write(json.dumps({"ts": "2026-03-22T10:00:00+00:00", "query_text": "q", "scores": [0.7], "doc_matched": "a.txt", "top_docs": ["a.txt"]}) + "\n")

        with patch("routers.kb_router.settings") as mock_settings:
            mock_settings.query_log_path = log_path
            r = client.get("/api/kb/health")

        # Should still succeed, the good line is processed
        assert r.status_code == 200
        data = r.json()
        assert data["avg_match_score"] is not None

    def test_entries_outside_7day_window_excluded(self, in_memory_qdrant, mock_embedder, tmp_path):
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        log_path = str(tmp_path / "query_log.jsonl")
        self._write_log(log_path, [
            # Old entry — outside 7 day window (year 2020)
            {"ts": "2020-01-01T00:00:00+00:00", "query_text": "old q", "scores": [0.1], "doc_matched": None, "top_docs": []},
            # Recent entry
            {"ts": "2026-03-22T10:00:00+00:00", "query_text": "recent q", "scores": [0.9], "doc_matched": "a.txt", "top_docs": ["a.txt"]},
        ])

        with patch("routers.kb_router.settings") as mock_settings:
            mock_settings.query_log_path = log_path
            r = client.get("/api/kb/health")

        data = r.json()
        # avg_match_score should only reflect the recent entry (0.9), not 0.1
        assert data["avg_match_score"] == pytest.approx(0.9, abs=0.001)
