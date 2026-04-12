import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from models import KnowledgeSession
from services.career_profiles import canonicalize_career_type_slug

# Storage directory within the API root
_SESSIONS_DIR = Path(os.environ.get("SESSIONS_DIR", "/app/data/sessions"))


class SessionStore:
    """Singleton for persisting counsellor knowledge publishing sessions."""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            return cls._instance

    def _get_path(self, session_id: str) -> Path:
        return _SESSIONS_DIR / f"{session_id}.json"

    def _normalize_payload(self, payload: dict) -> tuple[dict, bool]:
        """Canonicalize legacy track slugs in persisted session payloads."""
        changed = False

        for card in payload.get("intent_cards", []) or []:
            if not isinstance(card, dict) or card.get("domain") != "track":
                continue
            diff = card.get("diff")
            if not isinstance(diff, dict):
                continue
            legacy_slug = diff.get("slug")
            canonical_slug = canonicalize_career_type_slug(legacy_slug)
            if canonical_slug and canonical_slug != legacy_slug:
                diff["slug"] = canonical_slug
                changed = True

        track_guidance = payload.get("track_guidance")
        if isinstance(track_guidance, dict):
            for candidate in track_guidance.get("nearest_tracks", []) or []:
                if not isinstance(candidate, dict):
                    continue
                legacy_slug = candidate.get("slug")
                canonical_slug = canonicalize_career_type_slug(legacy_slug)
                if canonical_slug and canonical_slug != legacy_slug:
                    candidate["slug"] = canonical_slug
                    changed = True

        return payload, changed

    def create_session(self, raw_input: str, created_by: str = "counsellor") -> KnowledgeSession:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        session = KnowledgeSession(
            id=session_id,
            status="in-progress",
            raw_input=raw_input,
            created_by=created_by,
            created_at=now,
            updated_at=now
        )
        self.save_session(session)
        return session

    def save_session(self, session: KnowledgeSession) -> None:
        path = self._get_path(session.id)
        tmp_path = path.with_suffix(".tmp")

        with self._lock:
            payload, _ = self._normalize_payload(session.model_dump())
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(payload, indent=2))
            tmp_path.replace(path)

    def get_session(self, session_id: str) -> Optional[KnowledgeSession]:
        path = self._get_path(session_id)
        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            payload = json.loads(f.read())
        payload, changed = self._normalize_payload(payload)
        session = KnowledgeSession.model_validate(payload)
        if changed:
            self.save_session(session)
        return session

    def list_sessions(self) -> list[KnowledgeSession]:
        sessions = []
        for path in _SESSIONS_DIR.glob("*.json"):
            with open(path, encoding="utf-8") as f:
                payload = json.loads(f.read())
            payload, changed = self._normalize_payload(payload)
            session = KnowledgeSession.model_validate(payload)
            sessions.append(session)
            if changed:
                self.save_session(session)
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions
