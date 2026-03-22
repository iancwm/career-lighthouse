# api/tests/test_ingestion.py
import numpy as np
import pytest
from unittest.mock import MagicMock
from services.ingestion import chunk_text, parse_file, ingest_document


def test_chunk_text_splits_on_token_boundary():
    text = " ".join([f"word{i}" for i in range(200)])
    chunks = chunk_text(text, max_tokens=50, overlap=10)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.split()) <= 60  # allow slight overage for overlap


def test_chunk_text_single_chunk_if_short():
    text = "short text here"
    chunks = chunk_text(text, max_tokens=512, overlap=64)
    assert chunks == ["short text here"]


def test_parse_file_txt():
    content = b"hello career world"
    text = parse_file(content, "test.txt")
    assert "hello career world" in text


def test_ingest_document_calls_upsert(in_memory_qdrant, mock_embedder):
    from services.vector_store import VectorStore
    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(dim=384)

    mock_embedder.encode_batch.return_value = np.ones((2, 384), dtype=np.float32)

    count = ingest_document(
        file_content=b"chunk one content. " * 60 + b"chunk two content. " * 60,
        filename="test.txt",
        embedder=mock_embedder,
        store=store,
    )
    assert count >= 1
    mock_embedder.encode_batch.assert_called_once()
    docs = store.list_docs()
    assert any(d["filename"] == "test.txt" for d in docs)
