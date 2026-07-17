"""Claim context service — Milestone 2 grounded-answers claim injection.

Resolves an entity from a chat query (fast path: explicit employer slug;
fallback: keyword-normalization match against `EntityStore`), fetches its
approved/active `Claim`s, scope-filters and scores them into a coverage
confidence tier, and packages the result as a `ClaimContext` for injection
into the chat LLM prompt.

Called from `chat_router.py` (never from `llm.py` — that would couple
service layers). See docs/ontology/GROUNDING-DESIGN.md ("Recommended
Approach", Steps 1-3) and docs/ontology/SPRINT-M2-TASKS.md (tasks 3, 5, 6,
10, 13, 14) for the governing spec.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from cfg import kb_cfg
from models_ontology import (
    ApplicationWindowPayload,
    Claim,
    ClaimContext,
    RecruitmentStagePayload,
)
from services.claim_store import ClaimStore, get_claim_store
from services.entity_store import Entity, EntityStore, get_entity_store
from services.employer_store import EmployerEntityStore, get_employer_store
from services.evidence_store import EvidenceStore

logger = logging.getLogger(__name__)


def _normalized_terms(text: str) -> set[str]:
    """Return lowercase alphanumeric tokens for lightweight name matching.

    Private re-implementation of `services.employer_store._normalized_terms`
    — deliberately not imported cross-module since that helper is
    underscore-prefixed (private to its module).
    """
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


class ClaimContextService:
    """Orchestrates entity resolution + claim retrieval + confidence scoring
    for Milestone 2 grounded-answer prompt injection."""

    def __init__(
        self,
        *,
        claim_store: ClaimStore | None = None,
        entity_store: EntityStore | None = None,
        employer_store: EmployerEntityStore | None = None,
    ) -> None:
        self._claim_store = claim_store if claim_store is not None else get_claim_store()
        self._entity_store = entity_store if entity_store is not None else get_entity_store()
        self._employer_store = (
            employer_store if employer_store is not None else get_employer_store()
        )

    # -- entity resolution ---------------------------------------------------

    def resolve_entity(self, employer_slug: str | None, query: str) -> str | None:
        """Resolve a query (+ optional fast-path employer slug) to an `entity_id`.

        Fast path: `employer_slug` truthy → derive `organization-{employer_slug}`
        directly, no store lookup (per GROUNDING-DESIGN.md, "No EntityStore
        lookup needed").

        Fallback: keyword-normalization match against
        `EntityStore.list_entities(entity_type="organization")`. Exactly one
        match → that entity's id. Zero or multiple matches → None (ambiguous
        or no match; caller falls through to ungrounded behavior).
        """
        if employer_slug:
            return f"organization-{employer_slug}"

        query_terms = _normalized_terms(query)
        if not query_terms:
            return None

        matched: list[Entity] = []
        for entity in self._entity_store.list_entities(entity_type="organization"):
            terms: set[str] = set()
            terms |= _normalized_terms(entity.canonical_name)
            for alias in entity.aliases:
                terms |= _normalized_terms(alias)
            if not terms:
                continue
            if len(terms) == 1:
                if next(iter(terms)) in query_terms:
                    matched.append(entity)
            else:
                if terms.issubset(query_terms):
                    matched.append(entity)

        if len(matched) == 1:
            return matched[0].entity_id
        return None

    # -- claim retrieval ------------------------------------------------------

    def get_claims(self, entity_id: str, scope_geography: str | None = None) -> list[Claim]:
        """Fetch approved/active claims for `entity_id`, scope- and
        assertion-status-filtered. Stale claims (`valid_time.valid_until <
        today`) pass through here unfiltered — they affect the
        coverage_confidence tier instead of being silently dropped.
        """
        if scope_geography is None:
            scope_geography = kb_cfg["ontology"]["grounding_default_geography"]

        claims = self._claim_store.list_claims_for_entity(
            entity_id, review_status="approved", lifecycle="active"
        )
        return [
            c
            for c in claims
            if c.scope.geography in (scope_geography, None)
            and c.assertion_status not in ("contradicted", "superseded")
        ]

    # -- orchestration --------------------------------------------------------

    def get_claim_context(
        self,
        query: str,
        active_career_type: str | None = None,
        *,
        employer_slug: str | None = None,
    ) -> ClaimContext:
        """Resolve entity, fetch claims, score coverage confidence, and
        package the result as a `ClaimContext`. Never raises — any failure
        falls through to `ClaimContext(coverage_confidence="none")`, which
        is the "no injection, existing chat behavior unchanged" state.
        """
        try:
            entity_id = self.resolve_entity(employer_slug, query)
            if entity_id is None:
                return ClaimContext(coverage_confidence="none")

            claims = self.get_claims(entity_id)

            max_claims = kb_cfg["ontology"].get("max_injected_claims", 10)
            claims = claims[:max_claims]

            if not claims:
                return ClaimContext(entity_id=entity_id, coverage_confidence="none")

            today = date.today()

            def is_stale(c: Claim) -> bool:
                return (
                    c.valid_time.valid_until is not None and c.valid_time.valid_until < today
                )

            stale = [c for c in claims if is_stale(c)]
            non_stale = [c for c in claims if not is_stale(c)]
            mean_confidence = sum(c.confidence.extraction for c in claims) / len(claims)

            if stale and not non_stale:
                tier = "low"
            elif len(claims) >= 3 and not stale and mean_confidence >= 0.7:
                tier = "high"
            else:
                tier = "medium"

            entity_name: str | None = None
            if employer_slug:
                employer = self._employer_store.get_employer(employer_slug)
                if employer:
                    entity_name = employer.get("employer_name")
            if entity_name is None:
                entity = self._entity_store.get_entity("organization", entity_id)
                if entity is not None:
                    entity_name = entity.canonical_name

            return ClaimContext(
                entity_id=entity_id,
                entity_name=entity_name,
                claims=claims,
                coverage_confidence=tier,
            )
        except Exception:
            logger.warning("ClaimContext failed, falling through", exc_info=True)
            return ClaimContext(coverage_confidence="none")


# ---------------------------------------------------------------------------
# Module-level pure formatting helpers (no store access, no exceptions
# expected — these format already-fetched data). The caller (`llm.py`) runs
# the returned text through `sanitize_for_prompt()` before use; do not
# sanitize here.
# ---------------------------------------------------------------------------


def claim_display_text(claim: Claim, evidence_store: EvidenceStore | None = None) -> str:
    """Return one unsanitized display line for `claim`.

    Format: `[{claim_type}] {payload_summary}`, optionally followed by
    `. Evidence: "{excerpt}"` when `evidence_store` is supplied and the
    claim's first evidence_id resolves.
    """
    payload = claim.payload
    if isinstance(payload, ApplicationWindowPayload):
        summary = f"Application window opens {payload.opens_on or 'unknown'}, closes {payload.closes_on or 'unknown'}"
    elif isinstance(payload, RecruitmentStagePayload):
        sequence = payload.sequence if payload.sequence is not None else "?"
        summary = (
            f"{payload.stage_name} (stage {sequence}, type: {payload.stage_type}, "
            f"modality: {payload.modality})"
        )
    else:
        summary = str(payload)

    text = f"[{claim.claim_type}] {summary}"

    if evidence_store is not None and claim.evidence_ids:
        try:
            evidence = evidence_store.get_evidence(claim.evidence_ids[0])
        except Exception:
            evidence = None
        if evidence is not None:
            text += f'. Evidence: "{evidence.excerpt}"'

    return text


def stale_caveat_year(claims: list[Claim]) -> str:
    """Return the max `valid_time.valid_until` year across `claims` as a
    string, or `"outdated"` if every claim has `valid_time.valid_until=None`.
    """
    years = [c.valid_time.valid_until.year for c in claims if c.valid_time.valid_until is not None]
    if not years:
        return "outdated"
    return str(max(years))
