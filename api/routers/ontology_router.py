"""Ontology & metadata layer endpoints — Milestone 1, Phase 4.

Read endpoints over the new `entities/` / `claims/` / `evidence/` stores,
plus the two write-adjacent endpoints that drive Stage 5 (review) of the
extraction pipeline described in docs/ontology/ONTOLOGY-DESIGN.md §5 and §7:

  - `POST /api/kb/employers/{slug}/extract-claims` runs Stages 1-4
    (`services.ontology_extraction.extract_claims_for_source`) and returns
    `IntentCard(domain="claim")` proposals. It persists nothing — no card is
    written to a session, no `Claim` is written to `ClaimStore` — matching
    ONTOLOGY-DESIGN.md §7 ("does not persist"). Gated behind
    `kb_cfg["ontology"]["extraction_enabled"]`.
  - `POST /api/kb/session/{session_id}/claims/{card_id}/commit` is the
    approve path for a claim card: it re-validates the card's diff and calls
    `ClaimStore.create_claim(..., review_status="approved")`. Rejecting a
    claim card needs no new code — `session_router.discard_card` is already
    fully domain-agnostic (see that router's docstring-equivalent comment at
    its definition) and handles claim cards unmodified.

This module only imports from `entity_store.py` / `evidence_store.py` /
`claim_store.py` / `models_ontology.py` / `ontology_extraction.py` /
`models_kb.py` — it does not modify any of them, and it does not modify
`session_router.py` (it duplicates the small amount of session/card lookup
logic it needs, reusing `_check_session_ownership`/`_get_counsellor_id`
from `session_router` since both are importable module-level functions).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import TypeAdapter, ValidationError

from cfg import kb_cfg
from dependencies import require_admin_key
from models_kb import IntentCard, validate_intent_card_diff
from models_ontology import (
    ClaimConfidence,
    ClaimObservationTime,
    ClaimPayload,
    ClaimScope,
    ClaimValidTime,
)
from routers.session_router import (
    _check_session_completion,
    _check_session_ownership,
    _get_counsellor_id,
    _touch_session,
)
from services import ontology_extraction
from services.claim_store import ClaimStore
from services.employer_store import EmployerEntityStore, get_employer_store
from services.entity_store import EntityStore
from services.evidence_store import EvidenceStore
from services.session_store import SessionStore
from services.shared_yaml import safe_slug_is_valid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kb", dependencies=[Depends(require_admin_key)])

_claim_payload_adapter: TypeAdapter[Any] = TypeAdapter(ClaimPayload)


def get_session_store() -> SessionStore:
    return SessionStore()


# ---------------------------------------------------------------------------
# GET /api/kb/entities[/{entity_id}]
# ---------------------------------------------------------------------------


@router.get("/entities")
def list_entities_endpoint(
    entity_type: str | None = None,
    status: str | None = None,
):
    entities = EntityStore().list_entities(entity_type=entity_type, status=status)
    return [e.model_dump(mode="json") for e in entities]


@router.get("/entities/{entity_id}")
def get_entity_endpoint(entity_id: str):
    # entity_id is always "{entity_type}-{slug}" (ONTOLOGY-DESIGN.md §3);
    # entity_type itself never contains a hyphen, only underscores, so
    # splitting on the first "-" recovers it. An entity_id with no "-" at
    # all, or a prefix that isn't a real entity_type subdirectory, simply
    # fails the subsequent lookup and 404s rather than crashing.
    if "-" not in entity_id:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found.")
    entity_type = entity_id.split("-", 1)[0]
    entity = EntityStore().get_entity(entity_type, entity_id)
    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found.")
    return entity.model_dump(mode="json")


# ---------------------------------------------------------------------------
# GET /api/kb/claims[/{claim_id}]
# ---------------------------------------------------------------------------


@router.get("/claims")
def list_claims_endpoint(
    claim_type: str | None = None,
    subject_entity_id: str | None = None,
    review_status: str | None = None,
    lifecycle: str | None = None,
):
    claims = ClaimStore().list_claims(
        claim_type=claim_type,
        subject_entity_id=subject_entity_id,
        review_status=review_status,
        lifecycle=lifecycle,
    )
    return [c.model_dump(mode="json") for c in claims]


@router.get("/claims/{claim_id}")
def get_claim_endpoint(claim_id: str):
    claim = ClaimStore().get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found.")

    evidence_store = EvidenceStore()
    evidence = []
    for evidence_id in claim.evidence_ids:
        record = evidence_store.get_evidence(evidence_id)
        if record is not None:
            evidence.append(record.model_dump(mode="json"))

    result = claim.model_dump(mode="json")
    result["evidence"] = evidence
    return result


# ---------------------------------------------------------------------------
# GET /api/kb/evidence/{evidence_id}
# ---------------------------------------------------------------------------


@router.get("/evidence/{evidence_id}")
def get_evidence_endpoint(evidence_id: str):
    evidence = EvidenceStore().get_evidence(evidence_id)
    if evidence is None:
        raise HTTPException(
            status_code=404, detail=f"Evidence '{evidence_id}' not found."
        )
    return evidence.model_dump(mode="json")


# ---------------------------------------------------------------------------
# POST /api/kb/employers/{slug}/extract-claims
# ---------------------------------------------------------------------------


def _claim_card_diff_for_proposal(
    proposal: "ontology_extraction.ClaimProposalResult", source_id: str
) -> dict[str, Any]:
    """Build a `ClaimCardDiff`-shaped dict from a Stage-4-verified proposal.

    Two fields aren't produced anywhere upstream of this endpoint and need a
    Milestone-1 default, both flagged in the design doc as open decisions:

    - `observation_time.recorded_at`: stamped "now" (when the card was
      proposed for review), since the pipeline itself has no notion of a
      separate observation timestamp. `observed_at` is left unset.
    - `confidence.evidence_strength` / `confidence.source_reliability`:
      `ClaimProposalResult` only carries a single `extraction_confidence`
      float — there is no separate evidence-strength or source-reliability
      signal computed by Stages 1-4. `evidence_strength` mirrors
      `extraction_confidence` (the closest available signal);
      `source_reliability` defaults to a neutral 0.5 pending a later
      milestone that maps `SourceMetadata.authority_tier` to a numeric
      score. Both are editable by a counsellor before commit in a future
      SmartCanvas claim-card renderer (out of scope here, per
      ONTOLOGY-DESIGN.md §8).
    """
    return {
        "claim_type": proposal.claim_type,
        "subject_entity_id": proposal.subject_entity_id,
        "subject_mention_text": proposal.subject_mention_text,
        "object_entity_id": proposal.object_entity_id,
        "object_mention_text": proposal.object_mention_text,
        "payload": proposal.payload.model_dump(mode="json"),
        "scope": proposal.scope.model_dump(mode="json"),
        "valid_time": {},
        "observation_time": {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
        "assertion_status": proposal.assertion_status,
        "confidence": {
            "extraction": proposal.extraction_confidence,
            "evidence_strength": proposal.extraction_confidence,
            "source_reliability": 0.5,
        },
        "evidence_ids": proposal.evidence_ids,
        "evidence_excerpts": proposal.evidence_excerpts,
        "source_id": source_id,
    }


@router.post("/employers/{slug}/extract-claims")
def extract_claims_from_employer_notes(
    slug: str,
    employer_store: EmployerEntityStore = Depends(get_employer_store),
):
    """Run the Stage 1-4 ontology extraction pipeline over an employer's
    notes + source documents. Mirrors `employers_router.extract_facts_from_employer_notes`
    exactly, but calls `ontology_extraction.extract_claims_for_source` instead
    of `extract_facts_from_prose`, and returns `IntentCard(domain="claim")`
    proposals instead of raw fact dicts. Nothing is persisted by this call.
    """
    if not kb_cfg.get("ontology", {}).get("extraction_enabled", False):
        raise HTTPException(
            status_code=403,
            detail=(
                "Ontology claim extraction is not enabled "
                "(kb.yaml: ontology.extraction_enabled=false)."
            ),
        )

    if not safe_slug_is_valid(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format.")

    emp = employer_store.get_employer(slug)
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employer '{slug}' not found.")

    notes = emp.get("notes") or ""
    source_docs = emp.get("source_documents") or []
    doc_texts = "\n\n".join(d["raw_text"] for d in source_docs if d.get("raw_text"))
    combined = "\n\n".join(filter(None, [notes.strip(), doc_texts.strip()]))

    if not combined:
        raise HTTPException(
            status_code=400,
            detail="Employer has no notes or source documents to extract from.",
        )

    source_label = "employer_notes+documents" if doc_texts else "employer_notes"
    source_id = f"employer:{slug}:notes"

    try:
        result = ontology_extraction.extract_claims_for_source(
            combined, source_id, employer_slug=slug
        )
    except Exception as exc:
        logger.error(
            "extract_claims_from_employer_notes: failed for %r: %s", slug, exc
        )
        raise HTTPException(status_code=500, detail=f"Extraction failed: {exc}")

    cards: list[dict[str, Any]] = []
    for proposal in result.claim_proposals:
        # Hard deterministic-check failures aren't worth surfacing for
        # review; soft-check timeouts still get a human's judgment.
        if proposal.verification_status == "rejected":
            continue

        diff = _claim_card_diff_for_proposal(proposal, source_id)
        card_id = f"claim-{uuid4().hex[:8]}"
        summary = f"{proposal.claim_type} claim for {proposal.subject_mention_text}"

        try:
            card = IntentCard(
                card_id=card_id,
                domain="claim",
                summary=summary,
                diff=diff,
                raw_input_ref=source_id,
                status="pending",
            )
        except ValidationError:
            logger.warning(
                "Dropping claim proposal that failed IntentCard validation",
                exc_info=True,
            )
            continue

        cards.append(card.model_dump())

    return {
        "cards": cards,
        "total": len(cards),
        "source": source_label,
    }


# ---------------------------------------------------------------------------
# POST /api/kb/session/{session_id}/claims/{card_id}/commit
# ---------------------------------------------------------------------------


@router.post("/session/{session_id}/claims/{card_id}/commit")
def commit_claim_card(
    session_id: str,
    card_id: str,
    request: Request,
    store: SessionStore = Depends(get_session_store),
):
    """Approve path for a claim card: writes a real `Claim` via `ClaimStore`.

    Rejecting a claim card needs no code here — the existing, fully
    domain-agnostic `POST /{session_id}/cards/{card_id}/discard` route in
    `session_router.py` already handles it unmodified.
    """
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_ownership(session, _get_counsellor_id(request))

    card = next((c for c in session.intent_cards if c.get("card_id") == card_id), None)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if card.get("domain") != "claim":
        raise HTTPException(
            status_code=400, detail=f"Card is not a claim card (domain={card.get('domain')!r})"
        )

    if card.get("status") != "pending":
        raise HTTPException(
            status_code=409, detail=f"Card already {card.get('status')}"
        )

    # Defense-in-depth re-validation, matching commit_card's own
    # re-validation of effective_diff — the diff was already validated once
    # when the IntentCard was constructed, but this repo re-validates at
    # commit time too.
    try:
        validated_diff = validate_intent_card_diff("claim", card.get("diff", {}))
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid claim card diff: {exc}")

    subject_entity_id = validated_diff.get("subject_entity_id")
    if not subject_entity_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Claim card has no resolved subject entity (Stage 2 "
                "resolution_status was 'proposed_new') — cannot commit a "
                "claim until the entity is created. Entity-merge/creation "
                "UI is out of scope for Milestone 1."
            ),
        )

    try:
        payload_obj = _claim_payload_adapter.validate_python(validated_diff["payload"])
        scope_obj = ClaimScope(**validated_diff.get("scope", {}) or {})
        valid_time_obj = ClaimValidTime(**validated_diff.get("valid_time", {}) or {})
        observation_time_obj = ClaimObservationTime(
            **validated_diff["observation_time"]
        )
        confidence_obj = ClaimConfidence(**validated_diff["confidence"])
    except (ValidationError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid claim card diff: {exc}")

    try:
        claim = ClaimStore().create_claim(
            claim_type=validated_diff["claim_type"],
            subject_entity_id=subject_entity_id,
            payload=payload_obj,
            observation_time=observation_time_obj,
            confidence=confidence_obj,
            evidence_ids=validated_diff.get("evidence_ids") or [],
            object_entity_id=validated_diff.get("object_entity_id"),
            scope=scope_obj,
            valid_time=valid_time_obj,
            assertion_status=validated_diff.get("assertion_status", "inferred"),
            review_status="approved",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    card["status"] = "committed"
    _check_session_completion(session)
    _touch_session(session)

    return {
        "card_id": card_id,
        "domain": "claim",
        "status": "committed",
        "claim_id": claim.claim_id,
        "message": f"Created claim '{claim.claim_id}'",
    }
