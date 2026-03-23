# api/services/vector_store.py
import uuid
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue
)


def _to_uuid(id_str: str) -> str:
    """Convert any string ID to a deterministic UUID (Qdrant requires UUID or uint)."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, id_str))


class VectorStore:
    def __init__(self, client: QdrantClient, collection: str = "knowledge"):
        self._client = client
        self._collection = collection

    def ensure_collection(self, dim: int = 384):
        try:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise

    def upsert(self, points: list[dict]):
        self._client.upsert(
            collection_name=self._collection,
            points=[
                PointStruct(id=_to_uuid(p["id"]), vector=p["vector"].tolist(), payload=p["payload"])
                for p in points
            ],
        )

    def search(self, vector: np.ndarray, top_k: int = 5) -> list[dict]:
        results = self._client.search(
            collection_name=self._collection,
            query_vector=vector.tolist(),
            limit=top_k,
            with_payload=True,
        )
        return [{"score": r.score, "payload": r.payload} for r in results]

    def delete_by_filename(self, filename: str):
        self._client.delete(
            collection_name=self._collection,
            points_selector=Filter(
                must=[FieldCondition(key="source_filename", match=MatchValue(value=filename))]
            ),
        )

    def list_docs(self) -> list[dict]:
        """Returns [{doc_id, filename, chunk_count, uploaded_at}] aggregated by filename."""
        all_points, _ = self._client.scroll(
            collection_name=self._collection,
            limit=10000,
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
