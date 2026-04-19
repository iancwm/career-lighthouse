"""Track guidance helpers for counselor note analysis.

This module keeps the trust signal boring:
  - the append-only log is the source of truth
  - a tiny in-memory index is rebuilt when the file changes
  - guidance is derived from nearest track candidates, not prompt magic
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import numpy as np

from cfg import track_guidance_cfg
from models import TrackCandidate, TrackGuidance
from services.career_profiles import CareerProfileStore

logger = logging.getLogger(__name__)

# Load guidance thresholds at module init
_conf = track_guidance_cfg["confidence"]
_routing = track_guidance_cfg["routing"]


def _default_signals_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "logs" / "emerging_track_signals.jsonl"


def _signals_path() -> Path:
    return Path(os.environ.get("EMERGING_TRACK_SIGNALS_PATH", str(_default_signals_path())))


def _cluster_key(candidates: list[dict]) -> str:
    """Form a cluster key from top candidates for recurrence tracking.

    Takes the top N candidates (N from config) and combines their slugs.
    """
    limit = _routing["cluster_key_candidates"]
    slugs = [str(item.get("slug", "")).strip() for item in candidates[:limit]]
    slugs = [slug for slug in slugs if slug]
    if not slugs:
        return ""
    return "|".join(sorted(slugs))


class EmergingTrackSignalStore:
    """Append-only recurrence log with a tiny derived index."""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _ensure_loaded(self) -> None:
        """Reload the signal log if the file has changed."""
        path = _signals_path()
        current_mtime = path.stat().st_mtime if path.exists() else None
        if self._loaded and getattr(self, "_signals_mtime", None) == current_mtime:
            return

        counts: dict[str, int] = {}
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("EmergingTrackSignalStore: skipping malformed log line")
                    continue
                key = str(entry.get("cluster_key", "")).strip()
                if not key:
                    continue
                counts[key] = counts.get(key, 0) + 1

        self._counts = counts
        self._signals_mtime = current_mtime
        self._loaded = True

    def invalidate(self) -> None:
        """Mark the store as stale so it reloads on next access."""
        self._loaded = False

    def record_signal(self, payload: dict) -> None:
        """Append a new signal entry to the log and invalidate the cache."""
        path = _signals_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
                f.flush()
                os.fsync(f.fileno())
            self.invalidate()

    def recurrence_count(self, cluster_key: str) -> int:
        """Return the number of times this cluster key has been recorded."""
        if not cluster_key:
            return 0
        self._ensure_loaded()
        return int(self._counts.get(cluster_key, 0))


def get_emerging_track_signal_store() -> EmergingTrackSignalStore:
    return EmergingTrackSignalStore()


def build_track_guidance(
    raw_input: str,
    query_embedding: np.ndarray,
    profile_store: CareerProfileStore,
    session_id: str | None = None,
) -> TrackGuidance | None:
    """Build the counselor-facing nearest-track guidance for a session note.

    Uses cosine similarity thresholds to classify notes as:
    - safe_update: high confidence (score >= safe_update_min_score AND gap >= safe_update_min_gap)
    - emerging_taxonomy_signal: pattern recurring >= emerging_signal_min_recurrence times
    - clustered_uncertainty: ambiguous between multiple tracks

    Thresholds are configured in track_guidance.yaml.
    """
    candidates = profile_store.top_candidates(query_embedding, limit=_routing["top_candidates_limit"])
    if not candidates:
        return None

    nearest_tracks = [
        TrackCandidate(
            slug=str(item.get("slug", "")),
            label=str(item.get("label", item.get("slug", ""))),
            score=float(item.get("score", 0.0)),
        )
        for item in candidates
        if str(item.get("slug", "")).strip()
    ]
    if not nearest_tracks:
        return None

    best = nearest_tracks[0]
    second = nearest_tracks[1] if len(nearest_tracks) > 1 else None
    cluster_key = _cluster_key(candidates)
    store = get_emerging_track_signal_store()

    # We only count uncertain notes. Clean, high-confidence updates do not need
    # recurrence tracking because they are already safe to map.
    score_gap = best.score - (second.score if second else 0.0)
    best_is_confident = (
        best.score >= _conf["safe_update_min_score"]
        and score_gap >= _conf["safe_update_min_gap"]
    )

    if best_is_confident:
        return TrackGuidance(
            status="safe_update",
            recommendation=f"This looks closest to {best.label}. Treat it as an existing-track update unless the note says otherwise.",
            nearest_tracks=nearest_tracks,
            recurrence_count=0,
            cluster_key=cluster_key or None,
        )

    recurrence_count = 0
    if cluster_key:
        store.record_signal({
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "raw_input": raw_input,
            "cluster_key": cluster_key,
            "nearest_tracks": [candidate.model_dump() for candidate in nearest_tracks],
        })
        recurrence_count = store.recurrence_count(cluster_key)

    if recurrence_count >= _conf["emerging_signal_min_recurrence"]:
        status = "emerging_taxonomy_signal"
        recommendation = (
            "This pattern keeps recurring across sessions. Henry review is the right next step "
            "before anyone creates a new track."
        )
    else:
        status = "clustered_uncertainty"
        labels = ", ".join(candidate.label for candidate in nearest_tracks[:3])
        recommendation = (
            f"Closest tracks: {labels}. Check the definitions and do your own research before "
            "deciding whether this is a new path."
        )

    return TrackGuidance(
        status=status,
        recommendation=recommendation,
        nearest_tracks=nearest_tracks,
        recurrence_count=recurrence_count,
        cluster_key=cluster_key or None,
    )
