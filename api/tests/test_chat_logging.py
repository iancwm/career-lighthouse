# api/tests/test_chat_logging.py
"""Tests for query logging side-effect in POST /api/chat."""
import json
import numpy as np
import os
from fastapi.testclient import TestClient
from unittest.mock import patch


def make_chat_client(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{
        "id": "c1",
        "vector": vec,
        "payload": {
            "source_filename": "guide.txt",
            "chunk_index": 0,
            "upload_timestamp": "2026-01-01",
            "text": "SMU career advice content",
        },
    }])
    mock_embedder.encode.return_value = vec
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    return TestClient(app), store


class TestChatLogging:
    def test_chat_writes_jsonl_log_entry(self, in_memory_qdrant, mock_embedder, tmp_path):
        client, _ = make_chat_client(in_memory_qdrant, mock_embedder)
        log_path = str(tmp_path / "logs" / "query_log.jsonl")

        import services.llm as llm_module
        with patch.object(llm_module, "chat_with_context", return_value="advice here"), \
             patch("routers.chat_router.settings") as mock_settings:
            mock_settings.query_log_path = log_path
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            r = client.post("/api/chat", json={
                "message": "how do I get into banking?",
                "resume_text": None,
                "history": [],
            })

        assert r.status_code == 200
        assert os.path.exists(log_path)
        with open(log_path) as f:
            entry = json.loads(f.readline())
        assert entry["query_text"] == "how do I get into banking?"
        assert isinstance(entry["scores"], list)
        assert len(entry["scores"]) >= 1
        assert "ts" in entry
        assert "top_docs" in entry

    def test_chat_succeeds_even_if_log_write_fails(self, in_memory_qdrant, mock_embedder, tmp_path):
        """Log failure must never propagate as a 500 to the student."""
        client, _ = make_chat_client(in_memory_qdrant, mock_embedder)

        import services.llm as llm_module
        with patch.object(llm_module, "chat_with_context", return_value="good advice"), \
             patch("routers.chat_router.settings") as mock_settings:
            # Point to an unwritable path to force IOError
            mock_settings.query_log_path = "/root/no_permission/log.jsonl"
            r = client.post("/api/chat", json={
                "message": "career question",
                "resume_text": None,
                "history": [],
            })

        assert r.status_code == 200
        assert r.json()["response"] == "good advice"
