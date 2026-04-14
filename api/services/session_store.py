import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from models import KnowledgeSession

# Storage directory within the API root
_SESSIONS_DIR = Path(os.environ.get("SESSIONS_DIR", "/app/data/sessions"))

# Allow word chars, hyphens, and @-signs; reject everything else
_SAFE_ID_RE = re.compile(r"[^\w\-@]")


def _safe_counsellor_dir(counsellor_id: str) -> str:
    """Sanitize counsellor_id for use as a directory component.

    Prevents path traversal and injection. Empty / blank ids become "unknown".
    """
    if not counsellor_id or not counsellor_id.strip():
        return "unknown"
    safe = _SAFE_ID_RE.sub("_", counsellor_id.strip())
    # Extra guard: reject traversal artifacts that may survive the regex
    if not safe or safe in (".", "..") or "/" in safe or "\\" in safe:
        return "unknown"
    return safe


class SessionStore:
    """Singleton for persisting counsellor knowledge publishing sessions.

    Sessions are stored in counsellor-scoped sub-directories:
        <SESSIONS_DIR>/<counsellor_id>/<session_id>.json

    Legacy flat-file sessions (created before scoping was introduced) are
    migrated on first access and their `created_by` field is backfilled with
    "unknown" if it still holds the old default value "counsellor".
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
            return cls._instance

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _get_path(self, session_id: str, counsellor_id: str) -> Path:
        """Scoped path: <SESSIONS_DIR>/<counsellor_id>/<session_id>.json"""
        return _SESSIONS_DIR / _safe_counsellor_dir(counsellor_id) / f"{session_id}.json"

    def _legacy_path(self, session_id: str) -> Path:
        """Flat path used before counsellor-scoped directories were introduced."""
        return _SESSIONS_DIR / f"{session_id}.json"

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def create_session(self, raw_input: str, created_by: str = "counsellor") -> KnowledgeSession:
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        session = KnowledgeSession(
            id=session_id,
            status="in-progress",
            raw_input=raw_input,
            created_by=_safe_counsellor_dir(created_by),
            created_at=now,
            updated_at=now,
        )
        self.save_session(session)
        return session

    def save_session(self, session: KnowledgeSession) -> None:
        path = self._get_path(session.id, session.created_by)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")

        with self._lock:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(session.model_dump_json(indent=2))
            tmp_path.replace(path)

    def get_session(self, session_id: str) -> Optional[KnowledgeSession]:
        """Look up a session by ID.

        Search order:
        1. All counsellor-scoped sub-directories (new layout).
        2. Legacy flat file at <SESSIONS_DIR>/<session_id>.json.

        Legacy sessions are migrated on first access:
        - `created_by` is backfilled to "unknown" if it still holds the
          old default value "counsellor".
        - The file is moved to the scoped directory and the legacy file
          is removed.
        """
        # 1. Scan scoped sub-directories
        try:
            for subdir in _SESSIONS_DIR.iterdir():
                if not subdir.is_dir():
                    continue
                p = subdir / f"{session_id}.json"
                if p.exists():
                    with open(p, encoding="utf-8") as f:
                        return KnowledgeSession.model_validate_json(f.read())
        except OSError:
            pass

        # 2. Fall back to legacy flat path and migrate if found
        legacy = self._legacy_path(session_id)
        if legacy.exists():
            with open(legacy, encoding="utf-8") as f:
                session = KnowledgeSession.model_validate_json(f.read())

            # Backfill sessions with the old default created_by
            if session.created_by in ("counsellor", ""):
                session.created_by = "unknown"

            # Migrate to scoped directory and remove legacy file
            try:
                self.save_session(session)
                legacy.unlink(missing_ok=True)
            except OSError:
                pass  # Non-fatal — session still readable from legacy path

            return session

        return None

    def list_sessions(self, counsellor_id: Optional[str] = None) -> list[KnowledgeSession]:
        """Return sessions sorted by updated_at descending.

        If *counsellor_id* is given, only sessions owned by that counsellor
        are returned. Otherwise all sessions are returned (admin/legacy mode).
        """
        sessions: list[KnowledgeSession] = []

        if counsellor_id:
            # Scoped listing: only the matching sub-directory
            cdir = _SESSIONS_DIR / _safe_counsellor_dir(counsellor_id)
            if cdir.exists():
                for path in cdir.glob("*.json"):
                    try:
                        with open(path, encoding="utf-8") as f:
                            sessions.append(KnowledgeSession.model_validate_json(f.read()))
                    except (OSError, ValueError):
                        pass
        else:
            # Admin listing: all scoped sub-directories + legacy flat files
            try:
                for entry in _SESSIONS_DIR.iterdir():
                    if entry.is_dir():
                        for path in entry.glob("*.json"):
                            try:
                                with open(path, encoding="utf-8") as f:
                                    sessions.append(KnowledgeSession.model_validate_json(f.read()))
                            except (OSError, ValueError):
                                pass
            except OSError:
                pass
            # Legacy flat files
            for path in _SESSIONS_DIR.glob("*.json"):
                try:
                    with open(path, encoding="utf-8") as f:
                        sessions.append(KnowledgeSession.model_validate_json(f.read()))
                except (OSError, ValueError):
                    pass

        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions
