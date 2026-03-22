# api/dependencies.py
from functools import lru_cache
from qdrant_client import QdrantClient
from services.embedder import Embedder
from services.vector_store import VectorStore
from config import settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    client = QdrantClient(path=settings.data_path)
    return client


@lru_cache
def get_embedder() -> Embedder:
    return Embedder()


@lru_cache
def get_vector_store() -> VectorStore:
    client = get_qdrant_client()
    store = VectorStore(client=client, collection="knowledge")
    store.ensure_collection(dim=384)
    return store
