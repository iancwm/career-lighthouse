# api/dependencies.py
from functools import lru_cache
from fastapi import Header, HTTPException, status
from qdrant_client import QdrantClient
from services.embedder import Embedder
from services.vector_store import VectorStore
from config import settings
from cfg import kb_cfg, model_cfg


async def require_admin_key(x_admin_key: str = Header(default="")) -> None:
    """FastAPI dependency that enforces admin key auth on sensitive endpoints.

    The key is set via the ADMIN_KEY env var. If ADMIN_KEY is empty (development
    mode), the check is bypassed. Always set ADMIN_KEY in production deployments.

    Usage:
        router = APIRouter(dependencies=[Depends(require_admin_key)])
    """
    if not settings.admin_key:
        return  # Development mode — no key configured, allow all
    if x_admin_key != settings.admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )


@lru_cache
def get_qdrant_client() -> QdrantClient:
    if settings.qdrant_url:
        # Server mode: Docker Compose sets QDRANT_URL=http://qdrant:6333.
        # Avoids the file-lock conflict that occurs when the embedded client
        # is used with multiple workers or on container restart.
        # api_key=None is equivalent to no auth; Qdrant ignores it when the
        # server is not configured with an API key.
        return QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
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
