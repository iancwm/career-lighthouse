"""Ontology extraction pipeline — Milestone 1, Phase 3.

Stages 1-4 of the extraction pipeline described in
`docs/ontology/ONTOLOGY-DESIGN.md` §5:

  Stage 1 — mention extraction (one LLM call): candidate entity mentions and
            candidate claim-worthy fact spans, each as a character offset pair
            into the exact source text given to the model. The server, not the
            LLM, slices the excerpt from those offsets.
  Stage 2 — entity resolution (no LLM call): each mention is looked up against
            `EntityStore.find_candidates()` and classified as matched /
            proposed_new / ambiguous. Ambiguous mentions are excluded from
            Stage 3 entirely.
  Stage 3 — claim extraction (one LLM call): given only the resolved entities
            and evidence spans from Stages 1-2 (not the full source text),
            produces typed `ClaimPayload` proposals. Scope fields left blank
            by the LLM are defaulted server-side from `SourceMetadata`.
  Stage 4 — verification: deterministic checks first (subject resolved,
            evidence is a literal substring of the source text, claim_id
            collision against existing active claims), then one small LLM
            call for the softer "does the evidence plausibly support this"
            check.

Every LLM call has an explicit timeout and a defined non-fatal fallback:
Stage 1/3 timeout aborts extraction and returns no proposals; Stage 4's LLM
call timing out leaves the claim proposal in a distinct
`verification_status="unverified_timeout"` state rather than defaulting to
verified. See docs/ontology/MILESTONE-1.md §6 for why this is not optional.

This module never writes a `Claim`. It does create idempotent `Evidence`
records for the extracted spans and may create a known-employer organization
entity during resolution. Stage 5 (review + claim commit via `IntentCard`) is
the later write path for claims.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from config import settings
from models_ontology import (
    AssertionStatus,
    ClaimPayload,
    ClaimScope,
    EntityType,
    Evidence,
    EvidenceLocator,
    SourceMetadata,
)
from services.claim_store import ClaimStore, _compute_claim_id
from services.employer_store import EmployerEntityStore
from services.entity_store import (
    EntityStore,
    ensure_organization_entity_for_employer,
    normalize_name,
)
from services.evidence_store import EvidenceStore
from services.llm import SCHOOL_NAME, _resolve_prompt, call_structured_json, get_model_name
from services.shared_yaml import safe_slug
from services.source_ledger import SourceLedgerStore
from utils.sanitization import sanitize_for_prompt

logger = logging.getLogger(__name__)

# Milestone 1 supports exactly these two claim types — kept as a local literal
# rather than reusing the full `models_ontology.ClaimType` (which lists all
# eight eventual types) so a malformed/out-of-scope claim_type fails Pydantic
# validation immediately and triggers the JSON-repair-vs-discriminator path
# in `call_structured_json`, rather than silently accepting a claim type this
# pipeline has no payload for.
ClaimTypeM1 = Literal["application_window", "recruitment_stage"]

_STAGE1_FLOW = "ontology_mention_extraction"
_STAGE3_FLOW = "ontology_claim_extraction"
_STAGE4_FLOW = "ontology_claim_verification"


# ---------------------------------------------------------------------------
# Stage 1 — mention extraction: pipeline-internal wrapper models
# ---------------------------------------------------------------------------


class MentionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    entity_type: EntityType
    character_start: int = Field(ge=0)
    character_end: int = Field(ge=0)


class ClaimSpanCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character_start: int = Field(ge=0)
    character_end: int = Field(ge=0)


class MentionExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mentions: list[MentionCandidate] = Field(default_factory=list)
    claim_spans: list[ClaimSpanCandidate] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 2 — entity resolution: pipeline-internal result shape
# ---------------------------------------------------------------------------

ResolutionStatus = Literal["matched", "proposed_new", "ambiguous"]


class EntityResolutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mention_text: str
    entity_type: EntityType
    character_start: int
    character_end: int
    excerpt: str
    evidence_id: str | None = None
    resolution_status: ResolutionStatus
    entity_id: str | None = None
    candidate_entity_ids: list[str] = Field(default_factory=list)
    draft_entity: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Stage 3 — claim extraction: pipeline-internal wrapper models
# ---------------------------------------------------------------------------


class ClaimProposal(BaseModel):
    """One claim as proposed by the Stage 3 LLM call, referencing Stage 1/2
    output by index rather than repeating text (cheaper, and removes the
    ambiguity of matching on mention text when two mentions share a name).
    """

    model_config = ConfigDict(extra="forbid")

    claim_type: ClaimTypeM1
    subject_mention_ref: int = Field(ge=0)
    object_mention_ref: int | None = Field(default=None, ge=0)
    payload: ClaimPayload
    scope: ClaimScope = Field(default_factory=ClaimScope)
    assertion_status: AssertionStatus = "inferred"
    extraction_confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    evidence_span_refs: list[int] = Field(default_factory=list)

    @field_validator("payload")
    @classmethod
    def _payload_matches_claim_type(cls, v: ClaimPayload, info: Any) -> ClaimPayload:
        claim_type = info.data.get("claim_type")
        if claim_type is not None and getattr(v, "claim_type", None) != claim_type:
            raise ValueError(
                f"payload type {getattr(v, 'claim_type', None)!r} does not match "
                f"claim_type {claim_type!r}"
            )
        return v


class ClaimExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[ClaimProposal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stage 4 — verification: pipeline-internal wrapper + result shapes
# ---------------------------------------------------------------------------

VerificationStatus = Literal["verified", "rejected", "unverified_timeout"]


class VerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verified: bool
    note: str | None = None


class ClaimProposalResult(BaseModel):
    """Fully resolved, post-Stage-4 claim proposal — the unit returned to callers."""

    model_config = ConfigDict(extra="forbid")

    claim_type: ClaimTypeM1
    subject_entity_id: str | None
    subject_mention_text: str
    subject_resolution_status: ResolutionStatus
    object_entity_id: str | None = None
    object_mention_text: str | None = None
    payload: ClaimPayload
    scope: ClaimScope
    assertion_status: AssertionStatus
    extraction_confidence: float
    evidence_ids: list[str]
    evidence_excerpts: list[str]
    verification_status: VerificationStatus
    verification_note: str | None = None
    would_be_claim_id: str | None = None


class OntologyExtractionResult(BaseModel):
    """Top-level pipeline output. Nothing here is persisted as a `Claim` —
    these are proposals for a later review/commit phase.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str
    entity_resolutions: list[EntityResolutionResult] = Field(default_factory=list)
    claim_proposals: list[ClaimProposalResult] = Field(default_factory=list)
    stage1_timed_out: bool = False
    stage3_timed_out: bool = False


# ---------------------------------------------------------------------------
# Stage 1 — mention extraction
# ---------------------------------------------------------------------------


def run_stage1_mention_extraction(
    source_text: str,
    *,
    timeout_seconds: float,
    trace_metadata: dict[str, Any] | None = None,
) -> tuple[MentionExtractionResult | None, bool]:
    """Run the Stage 1 LLM call. Returns (result, timed_out).

    On any failure (timeout or otherwise) returns (None, True) — per
    ONTOLOGY-DESIGN.md §5, a Stage 1 failure aborts extraction and returns no
    proposals rather than propagating the exception.
    """
    resolved_prompt = _resolve_prompt(
        _STAGE1_FLOW, prompt_kwargs={"school_name": SCHOOL_NAME}
    )
    system = resolved_prompt["text"]
    user = f"SOURCE TEXT (offsets must be into this exact text):\n{source_text}"
    schema_hint = (
        "JSON object with 'mentions' (array of {text, entity_type, "
        "character_start, character_end}) and 'claim_spans' (array of "
        "{character_start, character_end}), offsets into the exact source "
        "text provided."
    )
    try:
        result = call_structured_json(
            operation=_STAGE1_FLOW,
            model=get_model_name(),
            system=system,
            user=user,
            schema_name="MentionExtractionResult",
            schema_hint=schema_hint,
            max_tokens=2000,
            timeout_seconds=timeout_seconds,
            trace_metadata={
                "feature": _STAGE1_FLOW,
                "input_chars_pre_trim": len(source_text),
                **(trace_metadata or {}),
            },
            validator=MentionExtractionResult,
        )
    except Exception:
        logger.warning(
            "Stage 1 (mention extraction) failed or timed out; returning no proposals",
            exc_info=True,
        )
        return None, True

    if isinstance(result, MentionExtractionResult):
        return result, False
    try:
        return MentionExtractionResult.model_validate(result), False
    except Exception:
        logger.warning("Stage 1 result failed post-validation", exc_info=True)
        return None, True


# ---------------------------------------------------------------------------
# Stage 2 — entity resolution (pure code, no LLM call)
# ---------------------------------------------------------------------------


def _draft_entity(entity_type: str, canonical_name: str) -> dict[str, Any]:
    """Build a draft, unpersisted Entity-shaped dict for a `proposed_new` mention.

    Deliberately NOT written via `EntityStore.create_entity` — Milestone 1's
    rule is that ambiguous/unresolved mentions never silently create entities.
    `proposed_entity_id` mirrors what `EntityStore.create_entity` would choose
    if this draft is later approved, for display purposes only.
    """
    base_slug = safe_slug(canonical_name) or "entity"
    return {
        "entity_type": entity_type,
        "canonical_name": canonical_name,
        "aliases": [],
        "status": "active",
        "parent_entity_id": None,
        "geography": None,
        "external_ids": {},
        "proposed_entity_id": f"{entity_type}-{base_slug}",
    }


def _find_employer_slug_for_mention(
    text: str, employer_store: EmployerEntityStore
) -> tuple[str, str] | None:
    """Return `(slug, employer_name)` if `text` exactly names a known employer.

    Deliberately strict (normalized full-name or slug equality only, no
    substring/token matching) — this gates whether a mention resolves to the
    correctly-keyed `organization-{slug}` entity (see
    `ensure_organization_entity_for_employer`) instead of being drafted with
    a `safe_slug(canonical_name)`-derived id, per SPRINT-M2-TASKS.md P0/Task 0.
    A loose match here would silently reassign unrelated organization
    mentions to an existing employer record.
    """
    target = normalize_name(text)
    if not target:
        return None
    for employer in employer_store.list_employers():
        name = str(employer.get("employer_name") or "")
        slug = str(employer.get("slug") or "")
        if normalize_name(name) == target or normalize_name(slug.replace("_", " ")) == target:
            return slug, name
    return None


def resolve_mention(
    mention: MentionCandidate,
    *,
    entity_store: EntityStore | None = None,
    employer_store: EmployerEntityStore | None = None,
) -> tuple[ResolutionStatus, str | None, list[str], dict[str, Any] | None]:
    """Classify a single mention. Returns (status, entity_id, candidate_ids, draft)."""
    store = entity_store or EntityStore()
    candidates = store.find_candidates(mention.entity_type, mention.text)
    if len(candidates) == 1:
        return "matched", candidates[0].entity_id, [], None
    if len(candidates) == 0:
        if mention.entity_type == "organization":
            emp_store = employer_store or EmployerEntityStore()
            match = _find_employer_slug_for_mention(mention.text, emp_store)
            if match is not None:
                slug, employer_name = match
                entity = ensure_organization_entity_for_employer(
                    slug, employer_name, entity_store=store
                )
                return "matched", entity.entity_id, [], None
        return (
            "proposed_new",
            None,
            [],
            _draft_entity(mention.entity_type, mention.text),
        )
    return "ambiguous", None, [c.entity_id for c in candidates], None


# ---------------------------------------------------------------------------
# Stage 3 — claim extraction
# ---------------------------------------------------------------------------


def _format_resolved_entities_for_prompt(
    eligible: list[dict[str, Any]],
) -> str:
    lines = []
    for index, entry in enumerate(eligible):
        resolution: EntityResolutionResult = entry["resolution"]
        lines.append(
            f"[{index}] entity_type={resolution.entity_type} "
            f"mention_text={resolution.mention_text!r} "
            f"resolution_status={resolution.resolution_status} "
            f"entity_id={resolution.entity_id or 'null'}"
        )
    return "\n".join(lines) if lines else "(none)"


def _format_claim_spans_for_prompt(span_records: list[dict[str, Any]]) -> str:
    lines = []
    for index, record in enumerate(span_records):
        lines.append(f"[{index}] {record['excerpt']!r}")
    return "\n".join(lines) if lines else "(none)"


def run_stage3_claim_extraction(
    eligible: list[dict[str, Any]],
    span_records: list[dict[str, Any]],
    *,
    source_metadata: SourceMetadata | None,
    timeout_seconds: float,
    trace_metadata: dict[str, Any] | None = None,
) -> tuple[ClaimExtractionResult | None, bool]:
    """Run the Stage 3 LLM call over resolved entities + evidence spans only
    (never the full source text). Returns (result, timed_out) with the same
    "abort and return no proposals" fallback contract as Stage 1.
    """
    resolved_prompt = _resolve_prompt(
        _STAGE3_FLOW,
        prompt_kwargs={
            "school_name": SCHOOL_NAME,
            "allowed_claim_types": "application_window, recruitment_stage",
        },
    )
    system = resolved_prompt["text"]

    source_kind = source_metadata.source_kind if source_metadata else "unknown"
    authority_tier = source_metadata.authority_tier if source_metadata else "unknown"
    authority_line = (
        f"SOURCE AUTHORITY: {source_kind}, tier={authority_tier} "
        "(weight anecdotal/internal_counsellor sources conservatively)"
    )

    user = (
        f"{authority_line}\n\n"
        f"RESOLVED ENTITIES:\n{_format_resolved_entities_for_prompt(eligible)}\n\n"
        f"EVIDENCE SPANS:\n{_format_claim_spans_for_prompt(span_records)}\n"
    )
    schema_hint = (
        "JSON object with a 'claims' array; each item has claim_type, "
        "subject_mention_ref (index into RESOLVED ENTITIES), "
        "object_mention_ref, payload (typed per claim_type), scope, "
        "assertion_status, extraction_confidence, and evidence_span_refs "
        "(indices into EVIDENCE SPANS)."
    )

    try:
        result = call_structured_json(
            operation=_STAGE3_FLOW,
            model=get_model_name(),
            system=system,
            user=user,
            schema_name="ClaimExtractionResult",
            schema_hint=schema_hint,
            max_tokens=2000,
            timeout_seconds=timeout_seconds,
            trace_metadata={
                "feature": _STAGE3_FLOW,
                "resolved_entity_count": len(eligible),
                "evidence_span_count": len(span_records),
                **(trace_metadata or {}),
            },
            validator=ClaimExtractionResult,
        )
    except Exception:
        logger.warning(
            "Stage 3 (claim extraction) failed or timed out; returning no proposals",
            exc_info=True,
        )
        return None, True

    if isinstance(result, ClaimExtractionResult):
        return result, False
    try:
        return ClaimExtractionResult.model_validate(result), False
    except Exception:
        logger.warning("Stage 3 result failed post-validation", exc_info=True)
        return None, True


def _apply_scope_defaults(
    scope: ClaimScope, source_metadata: SourceMetadata | None
) -> ClaimScope:
    """Server-side scope narrowing (ONTOLOGY-DESIGN.md §5): fill scope.geography
    from the source's coverage_geographies when the LLM left it blank and the
    source unambiguously covers exactly one geography. This is what keeps a
    single alumni interview from silently becoming an employer-wide claim.
    """
    if scope.geography is not None or source_metadata is None:
        return scope
    geographies = source_metadata.coverage_geographies
    if len(geographies) == 1:
        return scope.model_copy(update={"geography": geographies[0]})
    return scope


# ---------------------------------------------------------------------------
# Stage 4 — verification
# ---------------------------------------------------------------------------


def _deterministic_verify(
    *,
    subject_resolution_status: ResolutionStatus,
    evidence_excerpts: list[str],
    source_text: str,
) -> tuple[bool, str | None]:
    """The non-LLM half of Stage 4. Returns (passed, rejection_reason)."""
    if subject_resolution_status == "ambiguous":
        return False, "claim's subject entity resolution is ambiguous"
    if not any(excerpt and excerpt in source_text for excerpt in evidence_excerpts):
        return (
            False,
            "no evidence excerpt is a literal substring of the source text",
        )
    return True, None


def _check_claim_id_collision(
    *,
    claim_type: str,
    subject_entity_id: str | None,
    object_entity_id: str | None,
    payload: ClaimPayload,
    scope: ClaimScope,
    claim_store: ClaimStore | None = None,
) -> tuple[str | None, bool]:
    """Recompute the would-be claim_id and check for a conflicting active claim.

    Returns (would_be_claim_id, is_contradicted). "Contradicted" means an
    *active* claim already exists for the same subject_entity_id + claim_type
    whose computed claim_id differs from this proposal's (i.e. its payload or
    scope differs) — not merely that a claim with the identical id exists
    (that's an exact duplicate / idempotent re-extraction, not a conflict).

    Design note (not fully pinned down by the brief): "collide" in
    ONTOLOGY-DESIGN.md §5 is read here as "conflicts with", since claim_id is
    a hash over claim_type/subject/object/payload/scope — two different
    payloads for the same subject+type never literally hash-collide, they
    just produce two different existing active claims to compare against.
    """
    if not subject_entity_id:
        return None, False

    would_be_id = _compute_claim_id(
        claim_type, subject_entity_id, object_entity_id, payload, scope
    )
    store = claim_store or ClaimStore()
    same_subject_type = store.list_claims(
        claim_type=claim_type,
        subject_entity_id=subject_entity_id,
        lifecycle="active",
    )
    conflicting = [c for c in same_subject_type if c.claim_id != would_be_id]
    return would_be_id, bool(conflicting)


def run_stage4_verification(
    record: ClaimProposalResult,
    source_text: str,
    *,
    timeout_seconds: float,
    trace_metadata: dict[str, Any] | None = None,
    claim_store: ClaimStore | None = None,
) -> ClaimProposalResult:
    """Verify one claim proposal. Deterministic checks run first and can
    short-circuit (reject) before any LLM call is made. The soft LLM check
    only runs if the deterministic checks pass; on its timeout the claim is
    left explicitly `unverified_timeout`, never silently promoted to verified.
    """
    passed, reason = _deterministic_verify(
        subject_resolution_status=record.subject_resolution_status,
        evidence_excerpts=record.evidence_excerpts,
        source_text=source_text,
    )
    if not passed:
        return record.model_copy(
            update={"verification_status": "rejected", "verification_note": reason}
        )

    would_be_id, contradicted = _check_claim_id_collision(
        claim_type=record.claim_type,
        subject_entity_id=record.subject_entity_id,
        object_entity_id=record.object_entity_id,
        payload=record.payload,
        scope=record.scope,
        claim_store=claim_store,
    )
    assertion_status = record.assertion_status
    if contradicted:
        assertion_status = "contradicted"

    resolved_prompt = _resolve_prompt(
        _STAGE4_FLOW, prompt_kwargs={"school_name": SCHOOL_NAME}
    )
    system = resolved_prompt["text"]
    user = (
        f"PROPOSED CLAIM:\n"
        f"claim_type={record.claim_type}\n"
        f"payload={record.payload.model_dump_json()}\n\n"
        f"EVIDENCE EXCERPT(S):\n"
        + "\n".join(f"- {excerpt!r}" for excerpt in record.evidence_excerpts)
    )
    schema_hint = "JSON object with 'verified' (bool) and 'note' (string or null)."

    try:
        result = call_structured_json(
            operation=_STAGE4_FLOW,
            model=get_model_name(),
            system=system,
            user=user,
            schema_name="VerificationResult",
            schema_hint=schema_hint,
            max_tokens=300,
            timeout_seconds=timeout_seconds,
            trace_metadata={"feature": _STAGE4_FLOW, **(trace_metadata or {})},
            validator=VerificationResult,
        )
    except Exception:
        logger.warning(
            "Stage 4 (verification) LLM call failed or timed out; leaving claim "
            "unverified rather than promoting it",
            exc_info=True,
        )
        return record.model_copy(
            update={
                "verification_status": "unverified_timeout",
                "assertion_status": assertion_status,
                "would_be_claim_id": would_be_id,
            }
        )

    if not isinstance(result, VerificationResult):
        try:
            result = VerificationResult.model_validate(result)
        except Exception:
            logger.warning("Stage 4 result failed post-validation", exc_info=True)
            return record.model_copy(
                update={
                    "verification_status": "unverified_timeout",
                    "assertion_status": assertion_status,
                    "would_be_claim_id": would_be_id,
                }
            )

    verification_status: VerificationStatus = "verified" if result.verified else "rejected"
    return record.model_copy(
        update={
            "verification_status": verification_status,
            "verification_note": result.note,
            "assertion_status": assertion_status,
            "would_be_claim_id": would_be_id,
        }
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def extract_claims_for_source(
    source_text: str,
    source_id: str,
    *,
    employer_slug: str | None = None,
    trace_metadata: dict[str, Any] | None = None,
    timeout_seconds: float | None = None,
) -> OntologyExtractionResult:
    """Run Stages 1-4 over `source_text` and return claim proposals.

    Extraction does not persist a ``Claim``. It does persist idempotent,
    content-addressed ``Evidence`` records for mention/claim spans and may
    persist a known-employer organization ``Entity`` during resolution, so
    re-running extraction is safe.
    """
    trace_metadata = dict(trace_metadata or {})
    if employer_slug:
        trace_metadata.setdefault("employer_slug", employer_slug)
    timeout = (
        timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds
    )

    working_text = sanitize_for_prompt(str(source_text or ""))
    if not working_text.strip():
        return OntologyExtractionResult(source_id=source_id)

    source_metadata = SourceLedgerStore().to_source_metadata(source_id)

    # -- Stage 1 -----------------------------------------------------------
    stage1_result, stage1_timed_out = run_stage1_mention_extraction(
        working_text, timeout_seconds=timeout, trace_metadata=trace_metadata
    )
    if stage1_timed_out or stage1_result is None:
        return OntologyExtractionResult(source_id=source_id, stage1_timed_out=True)

    evidence_store = EvidenceStore()

    mention_records: list[dict[str, Any]] = []
    for mention in stage1_result.mentions:
        excerpt = working_text[mention.character_start : mention.character_end]
        if not excerpt.strip():
            logger.debug("Skipping mention with degenerate offsets: %r", mention)
            continue
        evidence: Evidence = evidence_store.create_evidence(
            source_id,
            excerpt,
            "context_only",
            0.5,
            locator=EvidenceLocator(
                character_start=mention.character_start,
                character_end=mention.character_end,
            ),
            trace_id=str(trace_metadata.get("trace_id") or "") or None,
        )
        mention_records.append(
            {"mention": mention, "excerpt": excerpt, "evidence_id": evidence.evidence_id}
        )

    span_records: list[dict[str, Any]] = []
    for span in stage1_result.claim_spans:
        excerpt = working_text[span.character_start : span.character_end]
        if not excerpt.strip():
            logger.debug("Skipping claim span with degenerate offsets: %r", span)
            continue
        evidence = evidence_store.create_evidence(
            source_id,
            excerpt,
            "directly_supports",
            0.5,
            locator=EvidenceLocator(
                character_start=span.character_start,
                character_end=span.character_end,
            ),
            trace_id=str(trace_metadata.get("trace_id") or "") or None,
        )
        span_records.append({"excerpt": excerpt, "evidence_id": evidence.evidence_id})

    # -- Stage 2 -------------------------------------------------------------
    entity_store = EntityStore()
    resolutions: list[EntityResolutionResult] = []
    eligible: list[dict[str, Any]] = []
    for rec in mention_records:
        mention: MentionCandidate = rec["mention"]
        status, entity_id, candidate_ids, draft = resolve_mention(
            mention, entity_store=entity_store
        )
        resolution = EntityResolutionResult(
            mention_text=mention.text,
            entity_type=mention.entity_type,
            character_start=mention.character_start,
            character_end=mention.character_end,
            excerpt=rec["excerpt"],
            evidence_id=rec["evidence_id"],
            resolution_status=status,
            entity_id=entity_id,
            candidate_entity_ids=candidate_ids,
            draft_entity=draft,
        )
        resolutions.append(resolution)
        if status != "ambiguous":
            eligible.append({"resolution": resolution, "mention": mention})

    if not eligible or not span_records:
        return OntologyExtractionResult(source_id=source_id, entity_resolutions=resolutions)

    # -- Stage 3 -------------------------------------------------------------
    stage3_result, stage3_timed_out = run_stage3_claim_extraction(
        eligible,
        span_records,
        source_metadata=source_metadata,
        timeout_seconds=timeout,
        trace_metadata=trace_metadata,
    )
    if stage3_timed_out or stage3_result is None:
        return OntologyExtractionResult(
            source_id=source_id, entity_resolutions=resolutions, stage3_timed_out=True
        )

    # -- Stage 4 (+ assembling ClaimProposalResult) --------------------------
    claim_store = ClaimStore()
    claim_proposals: list[ClaimProposalResult] = []
    for proposal in stage3_result.claims:
        if not (0 <= proposal.subject_mention_ref < len(eligible)):
            logger.warning(
                "Dropping claim proposal with out-of-range subject_mention_ref=%s",
                proposal.subject_mention_ref,
            )
            continue
        subject_entry = eligible[proposal.subject_mention_ref]
        subject_resolution: EntityResolutionResult = subject_entry["resolution"]

        object_entry = None
        if proposal.object_mention_ref is not None and (
            0 <= proposal.object_mention_ref < len(eligible)
        ):
            object_entry = eligible[proposal.object_mention_ref]

        valid_span_indices = [
            i for i in proposal.evidence_span_refs if 0 <= i < len(span_records)
        ]
        evidence_excerpts = [span_records[i]["excerpt"] for i in valid_span_indices]
        evidence_ids = [span_records[i]["evidence_id"] for i in valid_span_indices]

        scope = _apply_scope_defaults(proposal.scope, source_metadata)

        record = ClaimProposalResult(
            claim_type=proposal.claim_type,
            subject_entity_id=subject_resolution.entity_id,
            subject_mention_text=subject_resolution.mention_text,
            subject_resolution_status=subject_resolution.resolution_status,
            object_entity_id=(
                object_entry["resolution"].entity_id if object_entry else None
            ),
            object_mention_text=(
                object_entry["resolution"].mention_text if object_entry else None
            ),
            payload=proposal.payload,
            scope=scope,
            assertion_status=proposal.assertion_status,
            extraction_confidence=proposal.extraction_confidence,
            evidence_ids=evidence_ids,
            evidence_excerpts=evidence_excerpts,
            verification_status="rejected",
        )
        verified_record = run_stage4_verification(
            record,
            working_text,
            timeout_seconds=timeout,
            trace_metadata=trace_metadata,
            claim_store=claim_store,
        )
        claim_proposals.append(verified_record)

    return OntologyExtractionResult(
        source_id=source_id,
        entity_resolutions=resolutions,
        claim_proposals=claim_proposals,
    )
