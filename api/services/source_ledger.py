"""Source ledger service for uploaded document lifecycle state.

The ledger is file-backed YAML, one current record per source filename, plus a
history directory with immutable snapshots for prior versions. It is the truth
layer for source lifecycle state, while Qdrant keeps the semantic chunks.
"""

from __future__ import annotations

import logging
import hashlib
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import yaml

from models_kb import SourceStateEvidence, SourceStateSummary
from services.runtime_paths import (
    default_source_ledger_dir,
    default_source_ledger_history_dir,
)
from services.shared_yaml import Singleton, atomic_yaml_write, version_stamp

logger = logging.getLogger(__name__)

_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9._\-()\[\] ]+")


def _ledger_dir() -> Path:
    return Path(os.environ.get("SOURCE_LEDGER_DIR", str(default_source_ledger_dir())))


def _history_dir() -> Path:
    return Path(
        os.environ.get(
            "SOURCE_LEDGER_HISTORY_DIR", str(default_source_ledger_history_dir())
        )
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(filename: str) -> str:
    clean = _SAFE_KEY_RE.sub("_", str(filename).strip()).strip("._")
    if not clean:
        return "source"
    max_len = 120
    if len(clean) <= max_len:
        return clean
    digest = hashlib.sha1(clean.encode("utf-8")).hexdigest()[:12]
    prefix = clean[: max_len - 13].rstrip("._- ")
    if not prefix:
        return digest
    return f"{prefix}-{digest}"


def _load_yaml(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if isinstance(payload, dict):
            return payload
    except FileNotFoundError:
        return None
    except Exception:
        logger.warning(
            "Skipping unreadable source ledger file: %s", path, exc_info=True
        )
    return None


def _normalize_record(
    payload: dict[str, Any], filename: str | None = None
) -> dict[str, Any]:
    """Coerce a raw YAML ledger payload into a canonical record dict with all required keys present."""
    resolved_filename = str(payload.get("filename") or filename or "").strip()
    if not resolved_filename:
        resolved_filename = str(
            payload.get("doc_id") or payload.get("source_record_id") or ""
        ).strip()
    resolved_filename = resolved_filename or "unknown"
    record = dict(payload)
    record["filename"] = resolved_filename
    record["doc_id"] = str(
        record.get("doc_id") or record.get("source_record_id") or resolved_filename
    )
    record["source_record_id"] = str(record.get("source_record_id") or record["doc_id"])
    record["lifecycle"] = str(record.get("lifecycle") or "active")
    record["uploaded_at"] = str(record.get("uploaded_at") or _now())
    record["uploaded_by"] = record.get("uploaded_by")
    record["superseded_by"] = record.get("superseded_by")
    record["linked_knowledge_object"] = record.get("linked_knowledge_object")
    record["chunk_count"] = int(record.get("chunk_count") or 0)
    record["archived_at"] = record.get("archived_at")
    record["record_version"] = str(record.get("record_version") or version_stamp())
    return record


def _latest_query_hits(
    query_entries: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Build a filename→latest_ts map from query log entries, keeping only the most recent hit per source."""
    latest: dict[str, str] = {}
    if not query_entries:
        return latest
    for entry in query_entries:
        ts = str(entry.get("ts") or "")
        for doc_name in entry.get("top_docs") or []:
            filename = str(doc_name).strip()
            if not filename:
                continue
            current = latest.get(filename)
            if current is None or ts > current:
                latest[filename] = ts
    return latest


class SourceLedgerStore(Singleton):
    """Singleton file-backed ledger for source lifecycle metadata."""

    _instance = None
    _lock = Lock()

    def _init_singleton(self) -> None:
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._records: dict[str, dict[str, Any]] = {}
        self._load_records()
        self._loaded = True

    def _load_records(self) -> None:
        ledger_dir = _ledger_dir()
        if not ledger_dir.exists():
            return
        for yaml_path in sorted(ledger_dir.glob("*.yaml")):
            payload = _load_yaml(yaml_path)
            if not payload:
                continue
            record = _normalize_record(payload, filename=yaml_path.stem)
            self._records[record["filename"]] = record

    def invalidate(self) -> None:
        with self._lock:
            self._loaded = False

    def _current_path(self, filename: str) -> Path:
        return _ledger_dir() / f"{_safe_filename(filename)}.yaml"

    def _history_path(self, filename: str, record_version: str) -> Path:
        return _history_dir() / _safe_filename(filename) / f"{record_version}.yaml"

    def _snapshot_history(
        self,
        record: dict[str, Any],
        *,
        lifecycle: str | None = None,
        superseded_by: str | None = None,
    ) -> None:
        """Write an immutable history snapshot of the given record under the history directory."""
        snapshot = dict(record)
        snapshot["lifecycle"] = lifecycle or snapshot.get("lifecycle") or "superseded"
        snapshot["superseded_by"] = superseded_by or snapshot.get("superseded_by")
        snapshot["record_version"] = str(
            snapshot.get("record_version") or version_stamp()
        )
        atomic_yaml_write(
            self._history_path(snapshot["filename"], snapshot["record_version"]),
            snapshot,
        )

    def list_records(self) -> list[dict[str, Any]]:
        self._ensure_loaded()
        return sorted(
            (dict(record) for record in self._records.values()),
            key=lambda item: item["filename"].lower(),
        )

    def list_history_records(self) -> list[dict[str, Any]]:
        """Return all historical ledger snapshots sorted by filename then record_version."""
        history_dir = _history_dir()
        if not history_dir.exists():
            return []
        records: list[dict[str, Any]] = []
        for filename_dir in sorted(history_dir.iterdir()):
            if not filename_dir.is_dir():
                continue
            for yaml_path in sorted(filename_dir.glob("*.yaml")):
                payload = _load_yaml(yaml_path)
                if not payload:
                    continue
                records.append(
                    _normalize_record(
                        payload, filename=payload.get("filename") or filename_dir.name
                    )
                )
        return sorted(
            records, key=lambda item: (item["filename"].lower(), item["record_version"])
        )

    def get_record(self, filename: str | None) -> dict[str, Any] | None:
        if not filename:
            return None
        self._ensure_loaded()
        record = self._records.get(filename)
        return dict(record) if record else None

    def is_active(self, filename: str | None) -> bool:
        record = self.get_record(filename)
        if record is None:
            return True
        return record.get("lifecycle") == "active"

    def active_filenames(self) -> set[str]:
        return {
            record["filename"]
            for record in self.list_records()
            if record.get("lifecycle") == "active"
        }

    def upsert_record(
        self,
        *,
        filename: str,
        chunk_count: int,
        uploaded_by: str | None = None,
        linked_knowledge_object: str | None = None,
        lifecycle: str = "active",
        superseded_by: str | None = None,
        archived_at: str | None = None,
        uploaded_at: str | None = None,
    ) -> dict[str, Any]:
        """Create or replace the current ledger record for a source file, snapshotting the previous version to history."""
        self._ensure_loaded()
        current = self._records.get(filename)
        now = uploaded_at or _now()
        record_version = version_stamp()
        record = {
            "doc_id": filename,
            "source_record_id": filename,
            "filename": filename,
            "lifecycle": lifecycle,
            "uploaded_at": now,
            "uploaded_by": uploaded_by,
            "linked_knowledge_object": linked_knowledge_object,
            "superseded_by": superseded_by,
            "archived_at": archived_at,
            "chunk_count": int(chunk_count),
            "record_version": record_version,
        }

        if current:
            # Preserve the previous record as immutable history before replacing it.
            if current.get("record_version") != record_version:
                self._snapshot_history(
                    current, lifecycle="superseded", superseded_by=record_version
                )

        atomic_yaml_write(self._current_path(filename), record)
        self._records[filename] = dict(record)
        return dict(record)

    def archive_record(
        self,
        *,
        filename: str,
        chunk_count: int | None = None,
        archived_at: str | None = None,
    ) -> dict[str, Any]:
        """Set a source record's lifecycle to 'archived', snapshotting the prior state. Creates the record if absent."""
        current = self.get_record(filename)
        if current is None:
            return self.upsert_record(
                filename=filename,
                chunk_count=int(chunk_count or 0),
                lifecycle="archived",
                archived_at=archived_at or _now(),
            )

        if chunk_count is not None:
            current["chunk_count"] = int(chunk_count)
        current["lifecycle"] = "archived"
        current["archived_at"] = archived_at or _now()
        current["record_version"] = version_stamp()
        atomic_yaml_write(self._current_path(filename), current)
        self._records[filename] = dict(current)
        self._snapshot_history(current, lifecycle="archived")
        return dict(current)

    def backfill_from_docs(self, docs: list[dict[str, Any]]) -> int:
        """Seed current ledger records for legacy docs that do not yet exist."""
        added = 0
        for doc in docs:
            filename = str(doc.get("filename") or "").strip()
            if not filename or self.get_record(filename) is not None:
                continue
            self.upsert_record(
                filename=filename,
                chunk_count=int(doc.get("chunk_count") or 0),
                uploaded_at=str(doc.get("uploaded_at") or _now()),
                uploaded_by=doc.get("uploaded_by"),
                linked_knowledge_object=doc.get("linked_knowledge_object"),
                lifecycle=str(doc.get("lifecycle") or "active"),
            )
            added += 1
        return added

    def summarize_source_state(
        self,
        docs: list[dict[str, Any]],
        query_entries: list[dict[str, Any]] | None = None,
    ) -> SourceStateSummary:
        """Compute aggregate KB health metrics: active/superseded counts, stale-source evidence, and recent query hit attribution."""
        current_by_filename = {doc["filename"]: doc for doc in docs}
        history_records = self.list_history_records()

        active_current = [doc for doc in docs if doc.get("lifecycle") == "active"]
        superseded_candidates = [
            doc for doc in docs if doc.get("lifecycle") == "superseded"
        ] + [doc for doc in history_records if doc.get("lifecycle") == "superseded"]
        archived_candidates = [
            doc for doc in docs if doc.get("lifecycle") == "archived"
        ] + [doc for doc in history_records if doc.get("lifecycle") == "archived"]

        def _dedupe(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
            unique: dict[str, dict[str, Any]] = {}
            for record in records:
                filename = str(record.get("filename") or "").strip()
                if not filename or filename in unique:
                    continue
                unique[filename] = record
            return list(unique.values())

        superseded_records = _dedupe(superseded_candidates)
        archived_records = _dedupe(archived_candidates)

        stale_evidence: list[SourceStateEvidence] = []
        stale_filenames: set[str] = set()

        for record in [*superseded_records, *archived_records]:
            filename = str(record.get("filename") or "").strip()
            if not filename:
                continue
            if int(record.get("chunk_count") or 0) <= 0:
                continue
            stale_filenames.add(filename)
            stale_evidence.append(
                SourceStateEvidence(
                    filename=filename,
                    reason=f"{record.get('lifecycle', 'archived')} record still has indexed chunks",
                    chunk_count=int(record.get("chunk_count") or 0),
                    last_seen_at=str(
                        record.get("archived_at") or record.get("uploaded_at") or ""
                    ),
                )
            )

        active_hit_count = 0
        superseded_hit_count = 0
        latest_hits = _latest_query_hits(query_entries)
        for entry in query_entries or []:
            for doc_name in entry.get("top_docs") or []:
                filename = str(doc_name).strip()
                if not filename:
                    continue
                lifecycle = str(
                    current_by_filename.get(filename, {}).get("lifecycle") or "active"
                )
                if lifecycle == "active":
                    active_hit_count += 1
                else:
                    superseded_hit_count += 1
                if lifecycle != "active" and filename not in stale_filenames:
                    stale_filenames.add(filename)
                    record = current_by_filename.get(filename)
                    stale_evidence.append(
                        SourceStateEvidence(
                            filename=filename,
                            reason=f"{lifecycle} source still appears in recent retrieval results",
                            chunk_count=int(record.get("chunk_count") or 0)
                            if record
                            else 0,
                            last_seen_at=latest_hits.get(filename),
                        )
                    )

        summary = SourceStateSummary(
            active_source_count=len(active_current),
            superseded_source_count=len(superseded_records),
            stale_source_count=len(stale_evidence),
            active_hit_count=active_hit_count,
            superseded_hit_count=superseded_hit_count,
            last_refreshed_at=_now(),
            stale_source_evidence=stale_evidence,
        )
        return summary


def get_source_ledger_store() -> SourceLedgerStore:
    return SourceLedgerStore()


def chunk_is_current(
    payload: dict[str, Any], ledger: SourceLedgerStore | None = None
) -> bool:
    lifecycle = (
        str(payload.get("lifecycle") or payload.get("status") or "").strip().lower()
    )
    if lifecycle in {"superseded", "archived", "deleted"}:
        return False
    filename = str(
        payload.get("source_filename") or payload.get("filename") or ""
    ).strip()
    if not filename:
        return True
    ledger = ledger or get_source_ledger_store()
    return ledger.is_active(filename)


def filter_active_chunks(
    chunks: list[dict[str, Any]], ledger: SourceLedgerStore | None = None
) -> list[dict[str, Any]]:
    ledger = ledger or get_source_ledger_store()
    return [
        chunk
        for chunk in chunks
        if chunk_is_current(chunk.get("payload", {}), ledger=ledger)
    ]


def ensure_backfilled_from_store(store: Any) -> int:
    """Backfill the ledger from a vector store-like object that exposes list_docs()."""
    docs = store.list_docs()
    return get_source_ledger_store().backfill_from_docs(docs)
