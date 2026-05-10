# api/tests/test_ingest_router.py
import numpy as np
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from services import health_cache


def _make_client(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    mock_embedder.encode_batch.return_value = np.ones((1, 384), dtype=np.float32)
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    return TestClient(app)


def test_ingest_txt_file(in_memory_qdrant, mock_embedder):
    client = _make_client(in_memory_qdrant, mock_embedder)
    r = client.post(
        "/api/ingest", files={"file": ("test.txt", b"hello world career", "text/plain")}
    )
    assert r.status_code == 200
    data = r.json()
    assert data["doc_id"] == "test.txt"
    assert data["chunk_count"] >= 1
    assert data["status"] == "ok"

    from services.source_ledger import get_source_ledger_store

    record = get_source_ledger_store().get_record("test.txt")
    assert record is not None
    assert record["lifecycle"] == "active"


def test_ingest_invalidates_career_profile_store(in_memory_qdrant, mock_embedder):
    """Uploading a document resets CareerProfileStore so updated YAMLs are picked up."""
    client = _make_client(in_memory_qdrant, mock_embedder)
    with patch("routers.ingest_router.get_career_profile_store") as mock_get_store:
        mock_store = mock_get_store.return_value
        client.post(
            "/api/ingest",
            files={"file": ("test.txt", b"hello world career", "text/plain")},
        )
    mock_store.invalidate.assert_called_once()


def test_reupload_same_filename_replaces_doc_and_invalidates_overlap_cache(
    in_memory_qdrant, mock_embedder
):
    client = _make_client(in_memory_qdrant, mock_embedder)
    health_cache.set_overlap_pairs(
        [{"doc_a": "old.txt", "doc_b": "other.txt", "overlap_pct": 0.9}]
    )
    assert health_cache.get_overlap_pairs() is not None

    first = client.post(
        "/api/ingest", files={"file": ("repeat.txt", b"old content", "text/plain")}
    )
    assert first.status_code == 200
    assert first.json()["status"] == "ok"
    assert health_cache.get_overlap_pairs() is None

    health_cache.set_overlap_pairs(
        [{"doc_a": "repeat.txt", "doc_b": "other.txt", "overlap_pct": 0.9}]
    )
    second = client.post(
        "/api/ingest", files={"file": ("repeat.txt", b"new content", "text/plain")}
    )

    assert second.status_code == 200
    assert second.json()["status"] == "ok"
    assert health_cache.get_overlap_pairs() is None

    docs = client.get("/api/docs").json()
    repeat = [doc for doc in docs if doc["filename"] == "repeat.txt"]
    assert len(repeat) == 1
    assert repeat[0]["chunk_count"] >= 1


class TestFilenameValidation:
    @pytest.mark.parametrize(
        "filename",
        [
            "../etc/passwd",
            "../../secret",
            "/etc/passwd",
            "foo/bar.txt",
            "file\x00name.txt",
            "file\x01name.txt",
            "a" * 256,
            "file;rm -rf *.txt",
            "file$(whoami).txt",
        ],
    )
    def test_rejects_dangerous_filenames(
        self, in_memory_qdrant, mock_embedder, filename
    ):
        client = _make_client(in_memory_qdrant, mock_embedder)
        r = client.post(
            "/api/ingest", files={"file": (filename, b"content", "text/plain")}
        )
        assert r.status_code == 400

    @pytest.mark.parametrize(
        "filename",
        [
            "report.txt",
            "my-resume_2024.txt",
            "Career Guide v2.txt",
            "a" * 255,
            "Career_Services_Meeting_Memo (1).txt",
            "report [final].txt",
        ],
    )
    def test_accepts_valid_filenames(self, in_memory_qdrant, mock_embedder, filename):
        client = _make_client(in_memory_qdrant, mock_embedder)
        r = client.post(
            "/api/ingest",
            files={"file": (filename, b"hello world career", "text/plain")},
        )
        assert r.status_code == 200


class TestUploadSizeLimit:
    def test_rejects_oversized_upload_via_ingest(self, in_memory_qdrant, mock_embedder):

        client = _make_client(in_memory_qdrant, mock_embedder)

        # Simulate Content-Length header > 10MB
        oversized_content = b"x" * (11 * 1024 * 1024)
        r = client.post(
            "/api/ingest",
            files={"file": ("large.txt", oversized_content, "text/plain")},
            headers={"Content-Length": str(len(oversized_content))},
        )
        assert r.status_code == 413
        assert "exceeds maximum upload size" in r.json()["detail"]
