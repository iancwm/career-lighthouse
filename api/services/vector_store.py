"""Vector store service — interface to Qdrant for embedding-based semantic search.

Wraps the Qdrant client with a simple API for upserting document chunks and searching
by embedding vector. Collection name and vector dimensionality are configurable.

Usage:
    store = VectorStore(qdrant_client, collection="knowledge")
    store.ensure_collection(dim=384)
    store.upsert([{"id": "doc-1", "vector": embedding_vector, "payload": {...}}])
    results = store.search(query_vector, top_k=5)  # returns [{"score": 0.95, "payload": {...}}, ...]
"""
import uuid
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue
)

from cfg import model_cfg, kb_cfg


def _to_uuid(id_str: str) -> str:
    """Convert any string ID to a deterministic UUID.

    Qdrant requires UUIDs or unsigned integers. This uses uuid5 with a fixed
    namespace for deterministic conversion of string IDs.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, id_str))


class VectorStore:
    def __init__(self, client: QdrantClient, collection: str = None):
        """Initialize the vector store with a Qdrant client and collection name.

        Args:
            client: QdrantClient instance
            collection: collection name (defaults to kb.yaml storage.collection)
        """
        self._client = client
        self._collection = collection or kb_cfg["storage"]["collection"]

    def ensure_collection(self, dim: int = None):
        """Create the collection if it does not already exist.

        Args:
            dim: vector dimensionality (defaults to model.yaml embedding.dim)
        """
        if dim is None:
            dim = model_cfg["embedding"]["dim"]
        try:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise

    def upsert(self, points: list[dict]):
        """Insert or update a batch of points (chunks) in the collection.

        Each point must have 'id', 'vector' (np.ndarray), and 'payload' (dict).
        """
        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(id=_to_uuid(p["id"]), vector=p["vector"].tolist(), payload=p["payload"])
                for p in points
            ],
        )

    def search(self, vector: np.ndarray, top_k: int = None) -> list[dict]:
        """Search for the nearest vectors to the query vector.

        Args:
            vector: query embedding (1-d np.ndarray)
            top_k: number of results (defaults to kb.yaml vector_store.default_top_k)

        Returns:
            List of dicts with 'score' (cosine similarity) and 'payload' (chunk metadata).
        """
        if top_k is None:
            top_k = kb_cfg["vector_store"]["default_top_k"]
        if hasattr(self._client, "search"):
            results = self._client.search(
                collection_name=self._collection,
                query_vector=vector.tolist(),
                limit=top_k,
                with_payload=True,
            )
        else:
            results = self._client.query_points(
                collection_name=self._collection,
                query=vector.tolist(),
                limit=top_k,
                with_payload=True,
            ).points
        return [{"score": r.score, "payload": r.payload} for r in results]

    def delete_by_filename(self, filename: str):
        """Delete all points (chunks) with the given source_filename."""
        self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[FieldCondition(key="source_filename", match=MatchValue(value=filename))]
            ),
        )

    def list_docs(self) -> list[dict]:
        """List all unique documents in the collection, aggregated by filename.

        Returns:
            List of dicts with 'doc_id', 'filename', 'chunk_count', 'uploaded_at'.
        """
        all_points, _ = self._client.scroll(
            collection_name=self._collection,
            limit=kb_cfg["vector_store"]["scroll_limit"],
            with_payload=True,
            with_vectors=False,
        )
        docs: dict[str, dict] = {}
        for pt in all_points:
            fname = pt.payload["source_filename"]
            ts = pt.payload.get("upload_timestamp", "")
            if fname not in docs:
                docs[fname] = {"doc_id": fname, "filename": fname, "chunk_count": 0, "uploaded_at": ts}
            docs[fname]["chunk_count"] += 1
        return list(docs.values())
