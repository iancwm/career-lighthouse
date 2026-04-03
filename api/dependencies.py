# api/dependencies.py
from functools import lru_cache
from qdrant_client import QdrantClient
from services.embedder import Embedder
from services.vector_store import VectorStore
from config import settings
from cfg import kb_cfg, model_cfg


@lru_cache
def get_qdrant_client() -> QdrantClient:
    if settings.qdrant_url:
        # Server mode: Docker Compose sets QDRANT_URL=http://qdrant:6333.
        # Avoids the file-lock conflict that occurs when the embedded client
        # is used with multiple workers or on container restart.
        return QdrantClient(url=settings.qdrant_url)
    # Embedded mode: single-process local dev only (no QDRANT_URL set).
    return QdrantClient(path=settings.data_path)


@lru_cache
def get_embedder() -> Embedder:
    return Embedder()


@lru_cache
def get_vector_store() -> VectorStore:
    client = get_qdrant_client()
    store = VectorStore(client=client, collection=kb_cfg["storage"]["collection"])
    store.ensure_collection(dim=model_cfg["embedding"]["dim"])
    return store
