"""Student chat insight storage (counsellor-only, non-canonical).

This collection stores demand-side student question signals for counsellor search.
It is intentionally separate from YAML canonical knowledge and must never be used
for student-facing grounding retrieval.
"""

from datetime import datetime, timezone
from uuid import uuid4

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Filter

from config import settings
from models_chat import IntakeContext
from models_insights import StudentChatInsightPayload
from services.embedder import Embedder
from services.vector_store import VectorStore


class StudentChatInsightStore:
    """Store for counsellor-only semantic indexing of student chat messages."""

    def __init__(self, client: QdrantClient | None):
        self._client = client
        self._collection = settings.student_chat_collection_name
        self._store: VectorStore | None = None
        if client is not None:
            self._store = VectorStore(client=client, collection=self._collection)

    def ensure_collection(self, dim: int) -> None:
        """Idempotently ensure the student insight collection exists."""
        if self._store is None:
            return
        self._store.ensure_collection(dim=dim)

    def build_payload(
        self,
        text: str,
        active_career_type: str | None,
        intake_context: IntakeContext | None,
        has_resume: bool,
    ) -> StudentChatInsightPayload:
        """Build payload with privacy gates for optional intake fields.

        Resume text is never stored. Only a boolean has_resume signal is persisted.
        """
        return StudentChatInsightPayload(
            message_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            text=text,
            active_career_type=active_career_type,
            background=(
                intake_context.background
                if settings.student_chat_store_background and intake_context is not None
                else None
            ),
            region=(
                intake_context.region
                if settings.student_chat_store_region and intake_context is not None
                else None
            ),
            interest=(
                intake_context.interest
                if settings.student_chat_store_interest and intake_context is not None
                else None
            ),
            has_resume=has_resume,
        )

    def index_message(
        self,
        text: str,
        embedder: Embedder,
        active_career_type: str | None,
        intake_context: IntakeContext | None,
        has_resume: bool,
    ) -> str:
        """Embed + upsert one student message into the insight collection."""
        if self._store is None:
            raise RuntimeError("Student chat insight store is disabled")

        payload = self.build_payload(
            text=text,
            active_career_type=active_career_type,
            intake_context=intake_context,
            has_resume=has_resume,
        )
        payload_data = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        vector = embedder.encode(text)
        self._store.upsert(
            [{
                "id": payload.message_id,
                "vector": vector,
                "payload": payload_data,
            }]
        )
        return payload.message_id

    def search(self, vector: np.ndarray, top_k: int, filters: Filter | None = None) -> list[dict]:
        """Search student insight collection with optional metadata filters.

        This uses a client compatibility shim because embedded/local clients may
        expose ``query_points`` while server-backed clients expose ``search``.
        """
        if self._client is None:
            return []

        if hasattr(self._client, "search"):
            results = self._client.search(
                collection_name=self._collection,
                query_vector=vector.tolist(),
                query_filter=filters,
                limit=top_k,
                with_payload=True,
            )
        else:
            results = self._client.query_points(
                collection_name=self._collection,
                query=vector.tolist(),
                query_filter=filters,
                limit=top_k,
                with_payload=True,
            ).points
        return [{"score": r.score, "payload": r.payload} for r in results]
