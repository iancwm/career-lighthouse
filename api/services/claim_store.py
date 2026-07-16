"""Claim store — ontology & metadata layer, Milestone 1.

Singleton, file-backed YAML store for `Claim` records, one flat file per
claim under `knowledge/claims/`:

    knowledge/claims/{claim_id}.yaml

Claims are append-only by construction: superseding a claim never rewrites
its meaning in place, it writes a *new* claim file and field-updates the old
claim's `superseded_by`/`lifecycle`. See docs/ontology/ONTOLOGY-DESIGN.md §2
(storage layout), §3 (identifier strategy) and docs/ontology/MILESTONE-1.md
§3/§4 (acceptance criterion 3: "claims cannot be created without evidence")
for the governing spec. Nothing here is wired into any router yet
(Milestone 1 Phase 2 — store only, no runtime callers).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from models_ontology import (
    Claim,
    ClaimConfidence,
    ClaimObservationTime,
    ClaimPayload,
    ClaimScope,
    ClaimValidTime,
    ReviewStatus,
)
from services.runtime_paths import default_ontology_claims_dir
from services.shared_yaml import Singleton, atomic_yaml_write, read_yaml

logger = logging.getLogger(__name__)

_REVIEW_STATUSES = {"proposed", "approved", "rejected"}


def _claims_dir() -> Path:
    """Resolve the claims root directory live from the env var.

    Deliberately not cached on the singleton instance (unlike
    `EmployerEntityStore._employers`) so tests can monkeypatch
    `ONTOLOGY_CLAIMS_DIR` between cases and immediately see the new
    directory, exactly like `services.source_ledger._ledger_dir()` and
    `services.entity_store._entities_dir()`.
    """
    return Path(os.environ.get("ONTOLOGY_CLAIMS_DIR", str(default_ontology_claims_dir())))


def _claim_path(claim_id: str) -> Path:
    return _claims_dir() / f"{claim_id}.yaml"


def _canonical_json(value: Any) -> str:
    """Deterministic JSON serialization used as hash-input material.

    `sort_keys=True` makes the digest independent of field insertion order
    (Pydantic's `model_dump` order follows declaration order today, but that
    is an implementation detail we should not depend on for a stable id).
    """
    return json.dumps(value, sort_keys=True, default=str)


def _compute_claim_id(
    claim_type: str,
    subject_entity_id: str,
    object_entity_id: str | None,
    payload: ClaimPayload,
    scope: ClaimScope,
) -> str:
    """Deterministic id over the claim's *meaning*, not its metadata.

    Per ONTOLOGY-DESIGN.md §3: `claim_id = claim-{claim_type}-{sha1(subject|
    object|claim_type|payload_json|scope_json)[:16]}`. Confidence,
    evidence_ids, and timestamps are deliberately excluded so that
    re-extracting the same claim from the same (or different) evidence is
    idempotent — Stage 4 verification can cheaply recompute this hash to
    detect duplicates without a semantic comparison.
    """
    hash_input = "|".join(
        [
            subject_entity_id,
            object_entity_id or "",
            claim_type,
            _canonical_json(payload.model_dump(mode="json")),
            _canonical_json(scope.model_dump(mode="json")),
        ]
    )
    digest = hashlib.sha1(hash_input.encode("utf-8")).hexdigest()[:16]
    return f"claim-{claim_type}-{digest}"


class ClaimStore(Singleton):
    """Singleton file-backed store for ontology `Claim` records.

    Every read and write goes straight to disk on each call (no in-memory
    cache of loaded claims), matching `EntityStore`'s stateless model — this
    keeps `create_claim`'s idempotency check always correct against the
    current on-disk state.
    """

    _instance = None

    def _init_singleton(self) -> None:
        """No state to initialize — this store is intentionally stateless."""

    # -- internal helpers ---------------------------------------------------

    def _load_claim_file(self, path: Path) -> Claim | None:
        """Read and validate a single claim YAML file.

        Any parse or validation failure is logged and skipped rather than
        raised, matching `EntityStore._load_entity_file`'s defensive
        pattern — a single corrupt record must never take down a directory
        scan.
        """
        try:
            payload = read_yaml(path)
        except Exception:
            logger.warning("Skipping unreadable claim file: %s", path, exc_info=True)
            return None
        if not isinstance(payload, dict):
            if payload is not None:
                logger.warning("Skipping non-mapping claim file: %s", path)
            return None
        try:
            return Claim.model_validate(payload)
        except ValidationError:
            logger.warning("Skipping invalid claim file: %s", path, exc_info=True)
            return None

    def _write_claim(self, claim: Claim) -> None:
        atomic_yaml_write(_claim_path(claim.claim_id), claim.model_dump())

    # -- public API -----------------------------------------------------

    def get_claim(self, claim_id: str) -> Claim | None:
        """Return the claim for `claim_id`, or None if absent/invalid."""
        path = _claim_path(claim_id)
        if not path.exists():
            return None
        return self._load_claim_file(path)

    def list_claims(
        self,
        claim_type: str | None = None,
        subject_entity_id: str | None = None,
        review_status: str | None = None,
        lifecycle: str | None = None,
    ) -> list[Claim]:
        """List claims, optionally filtered by claim_type/subject_entity_id/
        review_status/lifecycle. Directory scan, corrupt files skipped (logged,
        not raised) per `_load_claim_file`.
        """
        base = _claims_dir()
        if not base.exists():
            return []
        results: list[Claim] = []
        for yaml_path in sorted(base.glob("*.yaml")):
            claim = self._load_claim_file(yaml_path)
            if claim is None:
                continue
            if claim_type is not None and claim.claim_type != claim_type:
                continue
            if subject_entity_id is not None and claim.subject_entity_id != subject_entity_id:
                continue
            if review_status is not None and claim.review_status != review_status:
                continue
            if lifecycle is not None and claim.lifecycle != lifecycle:
                continue
            results.append(claim)
        return results

    def list_claims_for_entity(
        self,
        entity_id: str,
        review_status: str | None = None,
        lifecycle: str | None = None,
    ) -> list[Claim]:
        """Convenience wrapper: claims where `entity_id` is the subject OR
        the object, with the same optional review_status/lifecycle filters
        as `list_claims`. Name/parameter names are locked by
        docs/ontology/SPRINT-M2-TASKS.md for a later milestone's consumer —
        do not rename.
        """
        matches: list[Claim] = []
        for claim in self.list_claims(review_status=review_status, lifecycle=lifecycle):
            if claim.subject_entity_id == entity_id or claim.object_entity_id == entity_id:
                matches.append(claim)
        return matches

    def create_claim(
        self,
        claim_type: str,
        subject_entity_id: str,
        payload: ClaimPayload,
        observation_time: ClaimObservationTime,
        confidence: ClaimConfidence,
        evidence_ids: list[str],
        *,
        object_entity_id: str | None = None,
        scope: ClaimScope | None = None,
        valid_time: ClaimValidTime | None = None,
        assertion_status: str = "inferred",
        review_status: str = "proposed",
        trace_id: str | None = None,
    ) -> Claim:
        """Create (or idempotently return) a Claim.

        `evidence_ids` is re-checked non-empty here BEFORE the Pydantic
        model is constructed — defense-in-depth beyond `Claim`'s own
        `Field(min_length=1)` + `field_validator`, per
        docs/ontology/MILESTONE-1.md acceptance criterion 3. This guarantees
        the store never even attempts to build a Claim, let alone write one,
        for an unevidenced call — the ValueError is raised on this exact
        code path, not surfaced indirectly via a caught ValidationError.

        `claim_id` is computed deterministically from
        `subject_entity_id`/`object_entity_id`/`claim_type`/`payload`/`scope`
        only (see `_compute_claim_id`). If an *active* claim with the same
        computed id already exists, that existing claim is returned as-is
        rather than overwritten — this is what makes re-extracting the same
        claim from the same evidence idempotent (ONTOLOGY-DESIGN.md §3).
        """
        if not evidence_ids:
            raise ValueError("a claim must cite at least one evidence_id")

        scope = scope or ClaimScope()
        valid_time = valid_time or ClaimValidTime()

        claim_id = _compute_claim_id(
            claim_type, subject_entity_id, object_entity_id, payload, scope
        )

        existing = self.get_claim(claim_id)
        if existing is not None and existing.lifecycle == "active":
            return existing

        claim = Claim(
            claim_id=claim_id,
            claim_type=claim_type,
            subject_entity_id=subject_entity_id,
            object_entity_id=object_entity_id,
            payload=payload,
            scope=scope,
            valid_time=valid_time,
            observation_time=observation_time,
            assertion_status=assertion_status,
            confidence=confidence,
            evidence_ids=list(evidence_ids),
            review_status=review_status,
            trace_id=trace_id,
        )
        self._write_claim(claim)
        return claim

    def supersede_claim(self, old_claim_id: str, new_claim_data: dict[str, Any]) -> Claim:
        """Supersede `old_claim_id` with a newly-created claim.

        Writes a NEW claim file via `create_claim(**new_claim_data)`, then
        field-updates the OLD claim file to set `superseded_by` to the new
        claim's id and `lifecycle="superseded"` — a targeted re-write of
        just that one file, not a full directory rewrite, per
        ONTOLOGY-DESIGN.md §2's append-only-by-construction design. Returns
        the NEW claim.
        """
        old_claim = self.get_claim(old_claim_id)
        if old_claim is None:
            raise ValueError(f"unknown claim_id: {old_claim_id!r}")

        new_claim = self.create_claim(**new_claim_data)

        updated_old = old_claim.model_copy(
            update={"superseded_by": new_claim.claim_id, "lifecycle": "superseded"}
        )
        self._write_claim(updated_old)

        return new_claim

    def update_review_status(self, claim_id: str, review_status: ReviewStatus) -> Claim:
        """Set `review_status` on an existing claim and persist it."""
        if review_status not in _REVIEW_STATUSES:
            raise ValueError(f"unknown review_status: {review_status!r}")

        claim = self.get_claim(claim_id)
        if claim is None:
            raise ValueError(f"unknown claim_id: {claim_id!r}")

        updated = claim.model_copy(update={"review_status": review_status})
        self._write_claim(updated)
        return updated


def get_claim_store() -> "ClaimStore":
    """FastAPI dependency accessor — returns the ClaimStore singleton."""
    return ClaimStore()
