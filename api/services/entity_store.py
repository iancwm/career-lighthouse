"""Entity store — ontology & metadata layer, Milestone 1.

Singleton, file-backed YAML store for `Entity` records, one subdirectory per
`entity_type` under `knowledge/entities/`:

    knowledge/entities/{entity_type}/{entity_id}.yaml

See docs/ontology/ONTOLOGY-DESIGN.md §1.1 (Entity model), §2 (storage
layout), §3 (identifier strategy) and docs/ontology/MILESTONE-1.md §3 for the
governing spec. Nothing here is wired into any router yet (Milestone 1
Phase 2 — store only, no runtime callers).
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from models_ontology import Entity, EntityType
from services.runtime_paths import default_ontology_entities_dir
from services.shared_yaml import Singleton, atomic_yaml_write, read_yaml, safe_slug

logger = logging.getLogger(__name__)


def _entities_dir() -> Path:
    """Resolve the entities root directory live from the env var.

    Deliberately not cached on the singleton instance (unlike
    `EmployerEntityStore._employers`) so tests can monkeypatch
    `ONTOLOGY_ENTITIES_DIR` between cases and immediately see the new
    directory, exactly like `services.source_ledger._ledger_dir()`.
    """
    return Path(
        os.environ.get("ONTOLOGY_ENTITIES_DIR", str(default_ontology_entities_dir()))
    )


def _entity_type_dir(entity_type: str) -> Path:
    return _entities_dir() / entity_type


def _entity_path(entity_type: str, entity_id: str) -> Path:
    return _entity_type_dir(entity_type) / f"{entity_id}.yaml"


def normalize_name(name: str) -> str:
    """Normalize a name for exact-match candidate lookup.

    Milestone 1 keeps this deliberately simple per ONTOLOGY-DESIGN.md/the
    task spec: lowercase, strip, collapse internal whitespace. No corporate
    suffix stripping, no fuzzy matching — that is explicitly out of scope
    here and left to Stage 2 of the extraction pipeline in a later
    milestone.
    """
    return " ".join(str(name or "").strip().lower().split())


class EntityStore(Singleton):
    """Singleton file-backed store for ontology `Entity` records.

    Every read and write goes straight to disk on each call (no in-memory
    cache of loaded entities) — unlike `EmployerEntityStore`'s
    load-once-and-invalidate model. This keeps `create_entity`'s collision
    checks always correct against the current on-disk state and means
    tests never need to call an `invalidate()` between a write and a
    subsequent read.
    """

    _instance = None

    def _init_singleton(self) -> None:
        """No state to initialize — this store is intentionally stateless."""

    # -- internal helpers ---------------------------------------------------

    def _load_entity_file(self, path: Path) -> Entity | None:
        """Read and validate a single entity YAML file.

        Any parse or validation failure is logged and skipped rather than
        raised, matching `services.source_ledger._load_yaml`'s defensive
        pattern — a single corrupt record must never take down a directory
        scan.
        """
        try:
            payload = read_yaml(path)
        except Exception:
            logger.warning("Skipping unreadable entity file: %s", path, exc_info=True)
            return None
        if not isinstance(payload, dict):
            if payload is not None:
                logger.warning("Skipping non-mapping entity file: %s", path)
            return None
        try:
            return Entity.model_validate(payload)
        except ValidationError:
            logger.warning("Skipping invalid entity file: %s", path, exc_info=True)
            return None

    def _iter_entity_type_dirs(self, entity_type: str | None) -> list[Path]:
        base = _entities_dir()
        if entity_type is not None:
            type_dir = base / entity_type
            return [type_dir] if type_dir.exists() else []
        if not base.exists():
            return []
        return [child for child in sorted(base.iterdir()) if child.is_dir()]

    def _resolve_entity_id(
        self, entity_type: str, base_slug: str, canonical_name: str, geography: str | None
    ) -> str:
        """Escalate `{entity_type}-{base_slug}` to a free, non-colliding entity_id.

        Mirrors alumni_store._preferred_profile_slug's collision-suffix
        pattern (api/services/alumni_store.py:547): try the naive slug
        first; if it is taken by a record with a *different* canonical
        name, escalate — first by appending a `geography` disambiguator if
        one was supplied, then by appending a short sha1 hash of the
        canonical name. If even the hashed id somehow collides with a
        different canonical name (astronomically unlikely at this scale,
        but handled rather than assumed away), a numeric counter is
        appended until a free id is found.
        """
        candidate_id = f"{entity_type}-{base_slug}"
        existing = self.get_entity(entity_type, candidate_id)
        if existing is None or existing.canonical_name == canonical_name:
            return candidate_id

        if geography:
            geo_slug = safe_slug(geography)
            if geo_slug:
                geo_id = f"{entity_type}-{base_slug}_{geo_slug}"
                geo_existing = self.get_entity(entity_type, geo_id)
                if geo_existing is None or geo_existing.canonical_name == canonical_name:
                    return geo_id

        digest = hashlib.sha1(canonical_name.encode("utf-8")).hexdigest()[:8]
        hash_id = f"{entity_type}-{base_slug}_{digest}"
        hash_existing = self.get_entity(entity_type, hash_id)
        if hash_existing is None or hash_existing.canonical_name == canonical_name:
            return hash_id

        counter = 2
        while True:
            candidate = f"{hash_id}_{counter}"
            candidate_existing = self.get_entity(entity_type, candidate)
            if candidate_existing is None or candidate_existing.canonical_name == canonical_name:
                return candidate
            counter += 1

    # -- public API -----------------------------------------------------

    def get_entity(self, entity_type: str, entity_id: str) -> Entity | None:
        """Return the entity for `entity_type`/`entity_id`, or None if absent/invalid."""
        path = _entity_path(entity_type, entity_id)
        if not path.exists():
            return None
        return self._load_entity_file(path)

    def list_entities(
        self, entity_type: str | None = None, status: str | None = None
    ) -> list[Entity]:
        """List entities, optionally filtered by entity_type and/or status.

        Scans a single entity_type subdirectory when entity_type is given,
        or all subdirectories under the entities root otherwise. Corrupt
        files are skipped (logged, not raised) per `_load_entity_file`.
        """
        results: list[Entity] = []
        for type_dir in self._iter_entity_type_dirs(entity_type):
            for yaml_path in sorted(type_dir.glob("*.yaml")):
                entity = self._load_entity_file(yaml_path)
                if entity is None:
                    continue
                if status is not None and entity.status != status:
                    continue
                results.append(entity)
        return results

    def find_candidates(self, entity_type: str, name: str) -> list[Entity]:
        """Return entities of `entity_type` whose canonical_name or an alias
        exact-matches `name` after normalization (see `normalize_name`).

        This is the resolution-candidate lookup Stage 2 of the extraction
        pipeline (ONTOLOGY-DESIGN.md §5) will call later. Milestone 1 keeps
        it to exact normalized-string matching only — no fuzzy matching.
        """
        target = normalize_name(name)
        if not target:
            return []
        matches: list[Entity] = []
        for entity in self.list_entities(entity_type=entity_type):
            if normalize_name(entity.canonical_name) == target:
                matches.append(entity)
                continue
            if any(normalize_name(alias) == target for alias in entity.aliases):
                matches.append(entity)
        return matches

    def create_entity(
        self,
        entity_type: EntityType,
        canonical_name: str,
        *,
        aliases: list[str] | None = None,
        parent_entity_id: str | None = None,
        geography: str | None = None,
        external_ids: dict[str, str] | None = None,
        entity_id: str | None = None,
    ) -> Entity:
        """Create (or idempotently return) an Entity for `entity_type`/`canonical_name`.

        entity_id is `{entity_type}-{safe_slug(canonical_name)}`, escalated
        on collision per `_resolve_entity_id`. Calling this again with the
        exact same entity_type + canonical_name returns the existing
        record rather than creating a duplicate file (checked by
        recomputing the naive slug and comparing canonical_name on the
        file already there, before any escalation logic runs).

        The record is validated through the `Entity` Pydantic model before
        being written, so a malformed record never reaches disk.

        `entity_id`, when passed, is used verbatim instead of the derived
        `{entity_type}-{safe_slug(canonical_name)}` id — no collision
        escalation applies. This is the explicit-id path required by
        docs/ontology/GROUNDING-DESIGN.md §D2/D3 (organization entities must
        resolve to `organization-{employer_slug}`, which does not always
        equal `safe_slug(canonical_name)`; see SPRINT-M2-TASKS.md P0/Task 0).
        If a record already exists at that exact id: idempotently return it
        when `canonical_name` matches, otherwise raise `ValueError` — an
        explicit id is a caller contract, not a hint to be escalated around.
        """
        if entity_id is not None:
            existing_explicit = self.get_entity(entity_type, entity_id)
            if existing_explicit is not None:
                if existing_explicit.canonical_name == canonical_name:
                    return existing_explicit
                raise ValueError(
                    f"entity_id {entity_id!r} already exists with canonical_name "
                    f"{existing_explicit.canonical_name!r}, not {canonical_name!r}"
                )
            now = datetime.now(timezone.utc)
            entity = Entity(
                entity_id=entity_id,
                entity_type=entity_type,
                canonical_name=canonical_name,
                aliases=list(aliases or []),
                parent_entity_id=parent_entity_id,
                geography=geography,
                external_ids=dict(external_ids or {}),
                created_at=now,
                updated_at=now,
            )
            atomic_yaml_write(_entity_path(entity_type, entity_id), entity.model_dump())
            return entity

        base_slug = safe_slug(canonical_name) or "entity"
        naive_id = f"{entity_type}-{base_slug}"
        existing = self.get_entity(entity_type, naive_id)
        if existing is not None and existing.canonical_name == canonical_name:
            return existing

        resolved_entity_id = self._resolve_entity_id(
            entity_type, base_slug, canonical_name, geography
        )

        now = datetime.now(timezone.utc)
        entity = Entity(
            entity_id=resolved_entity_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            aliases=list(aliases or []),
            parent_entity_id=parent_entity_id,
            geography=geography,
            external_ids=dict(external_ids or {}),
            created_at=now,
            updated_at=now,
        )
        atomic_yaml_write(_entity_path(entity_type, resolved_entity_id), entity.model_dump())
        return entity


def get_entity_store() -> "EntityStore":
    """FastAPI dependency accessor — returns the EntityStore singleton."""
    return EntityStore()


def ensure_organization_entity_for_employer(
    employer_slug: str,
    employer_name: str,
    *,
    entity_store: "EntityStore | None" = None,
) -> Entity:
    """Idempotently ensure the organization Entity for a `knowledge/employers/`
    record exists with `entity_id = f"organization-{employer_slug}"`.

    This locks in the GROUNDING-DESIGN.md §D2/D3 convention that Milestone 2's
    claim-injection fast path depends on: it derives `entity_id` directly from
    the employer YAML's filename slug rather than from
    `safe_slug(canonical_name)`, which can diverge (e.g. `ao_shearman.yaml`'s
    `employer_name: "A&O Shearman Singapore"` slugs to `a_o_shearman_singapore`,
    not `ao_shearman`). Call this before Stage 2 entity resolution
    (`ontology_extraction.resolve_mention`) runs for an organization mention
    that matches a known employer, so the mention resolves to this
    correctly-keyed entity instead of drafting a divergent one.
    """
    store = entity_store or EntityStore()
    entity_id = f"organization-{employer_slug}"
    return store.create_entity(
        "organization",
        employer_name,
        entity_id=entity_id,
    )
