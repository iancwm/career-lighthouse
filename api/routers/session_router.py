from typing import Any, List
from typing import Any, List
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from fastapi import APIRouter, File, HTTPException, Depends, UploadFile
from pydantic import ValidationError
from dependencies import get_embedder, require_admin_key
from models_session import CardCommitRequest, CreateSessionRequest, KnowledgeSession
from models_kb import (
    AlreadyCovered,
    IntentCard,
    SessionAnalysisResponse,
    validate_intent_card_diff,
)
from services.session_store import SessionStore
from services.track_guidance import build_track_guidance
from services.kb_writer import (
    apply_alumni_diff,
    apply_employer_diff,
    apply_profile_diff,
)
from services.career_profiles import get_career_profile_store
from services.employer_store import get_employer_store
from services.alumni_store import get_alumni_store
from services.llm import (
    generate_session_intents,
    generate_alumni_extraction,
)
from services.shared_yaml import safe_slug
from starlette.requests import Request
import logging
from datetime import datetime, timezone
from time import perf_counter
import re
from uuid import uuid4

_SESSION_INTENTS_EXECUTOR = ThreadPoolExecutor(
    max_workers=4, thread_name_prefix="session_intents"
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", dependencies=[Depends(require_admin_key)])
_ALUMNI_KEYWORD_RE = re.compile(
    r"\b("
    r"graduated|worked at|joined|promoted|company|role|current|alumni|mentor|"
    r"analyst|associate|manager|director|vice president|vp|md"
    r")\b",
    re.IGNORECASE,
)
_ALUMNI_NAME_RE = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")


# ---------------------------------------------------------------------------
# Ownership helpers
# ---------------------------------------------------------------------------


def _get_counsellor_id(request: Request) -> str | None:
    """Return the X-Counsellor-ID header value, or None if absent.

    NOTE: This header is currently untrusted — callers must treat it as
    an advisory identifier only. In production, replace with JWT-based auth
    so the counsellor identity is cryptographically verified.
    """
    return request.headers.get("X-Counsellor-ID")


def _check_session_ownership(
    session: KnowledgeSession, counsellor_id: str | None
) -> None:
    """Raise HTTP 403 if *counsellor_id* is provided and does not match the session owner.

    If *counsellor_id* is None (header absent), the check is skipped so that
    admin callers without a scoped header retain full access.
    All 403 attempts are logged for security monitoring.
    """
    if counsellor_id is None:
        return
    if session.created_by != counsellor_id:
        logger.warning(
            "Session access denied: session=%s owner=%r requester=%r",
            session.id,
            session.created_by,
            counsellor_id,
        )
        raise HTTPException(status_code=403, detail="Session access denied")


# Imported from sibling modules
from config import settings
from routers.ingest_router import _sanitize_filename
from services.ingestion import parse_file


def get_session_store():
    return SessionStore()


def _get_embedder():
    return get_embedder()


def _slug_is_safe(slug: str) -> bool:
    """Reject path traversal and injection in slug values."""
    if not slug or "/" in slug or ".." in slug or " " in slug:
        return False
    return all(c.isalnum() or c in "-_" for c in slug)


def _is_alumni_heavy(text: str) -> bool:
    if not text or not text.strip():
        return False
    keyword_hits = _ALUMNI_KEYWORD_RE.findall(text)
    return len(keyword_hits) >= 3 and bool(_ALUMNI_NAME_RE.search(text))


def _default_alumni_confidence(source_type: str | None) -> int:
    normalized = (source_type or "").strip().lower()
    if normalized == "direct_from_alumni":
        return 95
    if normalized == "counselor":
        return 85
    return 75


def _proposal_value(proposal: Any) -> Any:
    if isinstance(proposal, dict):
        return proposal.get("value")
    return proposal


def _proposal_confidence(proposal: Any, source_type: str | None) -> int:
    if isinstance(proposal, dict):
        raw = proposal.get("confidence")
        try:
            if raw is not None:
                return int(raw)
        except (TypeError, ValueError):
            pass
    return _default_alumni_confidence(source_type)


def _iter_alumni_extractions(extraction: Any) -> list[dict[str, Any]]:
    if isinstance(extraction, dict):
        alumni_items = extraction.get("alumni")
        if isinstance(alumni_items, list):
            return [item for item in alumni_items if isinstance(item, dict)]
        if (
            extraction.get("profile_proposals")
            or extraction.get("company_link_proposals")
            or extraction.get("summary_bullets")
        ):
            return [extraction]
    if isinstance(extraction, list):
        return [item for item in extraction if isinstance(item, dict)]
    return []


def _build_alumni_cards(
    extraction: dict[str, Any],
    session_id: str,
    existing_alumni: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing_slug_map: dict[str, str] = {}
    for item in existing_alumni:
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        existing_slug_map[slug] = slug
        canonical_slug = safe_slug(slug)
        if canonical_slug:
            existing_slug_map.setdefault(canonical_slug, slug)

    cards: list[dict[str, Any]] = []
    date_suffix = datetime.now(timezone.utc).strftime("%Y%m%d")

    for alumnus in _iter_alumni_extractions(extraction):
        proposals_payload = alumnus.get("profile_proposals") or {}
        if not isinstance(proposals_payload, dict):
            proposals_payload = {}
        company_links = alumnus.get("company_link_proposals")
        if not isinstance(company_links, list):
            company_links = (
                alumnus.get("company_links")
                if isinstance(alumnus.get("company_links"), list)
                else []
            )

        source_type = (
            alumnus.get("source")
            or alumnus.get("source_type")
            or extraction.get("source")
            or extraction.get("source_type")
        )
        diff: dict[str, Any] = {}
        proposals: dict[str, dict[str, Any]] = {}
        for field, proposal in proposals_payload.items():
            value = _proposal_value(proposal)
            if value is None or value == "":
                continue
            diff[field] = value
            if isinstance(proposal, dict):
                proposals[field] = {
                    "confidence": _proposal_confidence(proposal, source_type),
                    "evidence": proposal.get("evidence") or [],
                    "rationale": proposal.get("rationale"),
                }
            else:
                proposals[field] = {
                    "confidence": _default_alumni_confidence(source_type),
                    "evidence": [],
                    "rationale": None,
                }

        full_name = str(
            diff.get("full_name") or diff.get("name") or alumnus.get("full_name") or ""
        ).strip()
        matched_slug = str(alumnus.get("matched_slug") or "").strip() or None
        resolved_matched_slug = None
        if matched_slug:
            resolved_matched_slug = existing_slug_map.get(
                matched_slug
            ) or existing_slug_map.get(safe_slug(matched_slug))
        is_update = bool(alumnus.get("is_update")) and bool(resolved_matched_slug)
        if is_update and not resolved_matched_slug:
            is_update = False
        matched_slug = resolved_matched_slug

        slug = matched_slug or str(alumnus.get("slug") or "").strip()
        if not slug:
            slug = safe_slug(full_name) or f"alumni-{uuid4().hex[:8]}"
        canonical_slug = safe_slug(slug) or slug
        if not is_update and (
            slug in existing_slug_map or canonical_slug in existing_slug_map
        ):
            slug = f"{canonical_slug}-{date_suffix}"

        diff["slug"] = slug
        if company_links:
            diff["company_links"] = company_links

        summary_bullets = alumnus.get("summary_bullets")
        if not isinstance(summary_bullets, list):
            summary_bullets = (
                extraction.get("summary_bullets")
                if isinstance(extraction.get("summary_bullets"), list)
                else []
            )
        source_excerpt = str(alumnus.get("source_excerpt") or "").strip()
        if not source_excerpt:
            source_excerpt = str(
                next(
                    (
                        bullet
                        for bullet in summary_bullets
                        if isinstance(bullet, str) and bullet.strip()
                    ),
                    "",
                )
            ).strip()

        display_name = full_name or slug.replace("-", " ").title()
        summary = (
            f"Update alumni profile for {display_name}"
            if is_update
            else f"Create alumni profile for {display_name}"
        )
        cards.append(
            {
                "card_id": f"alumni-{slug}-{uuid4().hex[:8]}",
                "domain": "alumni",
                "summary": summary,
                "diff": diff,
                "raw_input_ref": source_excerpt or display_name,
                "proposals": proposals,
                "is_update": is_update,
                "matched_slug": matched_slug,
            }
        )
    return cards


def _apply_field_updates_to_profile(slug: str, diff: dict) -> tuple[list[str], bool]:
    result = apply_profile_diff(slug, diff, create_missing=True, source="Card commit")
    return result.changed_fields, result.is_new


def _apply_field_updates_to_employer(slug: str, diff: dict) -> tuple[list[str], bool]:
    result = apply_employer_diff(
        slug, diff, create_missing=True, snapshot=False, source="Card commit"
    )
    return result.changed_fields, result.is_new


def _apply_field_updates_to_alumni(
    slug: str, diff: dict[str, Any]
) -> tuple[list[str], bool, int | None, int | None]:
    result = apply_alumni_diff(slug, diff, source="Card commit")
    return (
        result.changed_fields,
        result.is_new,
        result.company_links_attempted,
        result.company_links_written,
    )


def _check_session_completion(session: KnowledgeSession) -> None:
    """Transition to 'completed' if all cards are committed/discarded."""
    if session.status != "analyzed":
        return
    all_done = all(
        c.get("status") in ("committed", "discarded") for c in session.intent_cards
    )
    if all_done and len(session.intent_cards) > 0:
        session.status = "completed"


def _touch_session(session: KnowledgeSession) -> None:
    """Update session timestamp and persist the current state."""
    session.updated_at = datetime.now(timezone.utc).isoformat()
    store = SessionStore()
    store.save_session(session)


def _workflow_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workflow_step(
    label: str, status: str, detail: str | None = None, **metadata: Any
) -> dict[str, Any]:
    return {
        "step_id": f"step-{uuid4().hex[:8]}",
        "label": label,
        "status": status,
        "started_at": _workflow_timestamp(),
        "ended_at": _workflow_timestamp(),
        "detail": detail,
        "metadata": {
            key: value for key, value in metadata.items() if value is not None
        },
    }


def _ensure_analysis_workflow(session: KnowledgeSession) -> dict[str, Any]:
    if not isinstance(session.analysis_workflow, dict):
        session.analysis_workflow = {}
    return session.analysis_workflow


@router.get("", response_model=List[KnowledgeSession])
def list_sessions(request: Request, store: SessionStore = Depends(get_session_store)):
    """List sessions, most recently updated first.

    If X-Counsellor-ID header is present, only that counsellor's sessions
    are returned. Otherwise all sessions are returned (admin mode).
    """
    counsellor_id = _get_counsellor_id(request)
    return store.list_sessions(counsellor_id=counsellor_id)


@router.post("/parse-file")
async def parse_session_file(
    request: Request,
    file: UploadFile = File(...),
):
    """Parse an uploaded file (PDF, DOCX, TXT) and return extracted text."""
    # 1. Check Content-Length against max_upload_bytes
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail="File exceeds maximum upload size (10MB).",
        )

    # 2. Validate filename
    try:
        sanitized_filename = _sanitize_filename(file.filename)
    except HTTPException:
        raise

    # 3. Read file content
    raw_content = await file.read()

    # 4. Check for empty content
    if not raw_content or len(raw_content) == 0:
        raise HTTPException(
            status_code=422,
            detail="File is empty or could not be read.",
        )

    # 5. Parse the file
    try:
        extracted_text = parse_file(raw_content, sanitized_filename)
    except Exception:
        logger.warning(
            "parse_session_file: failed to parse %r", sanitized_filename, exc_info=True
        )
        raise HTTPException(
            status_code=422,
            detail="Could not extract text from this file. Try pasting the content manually.",
        )

    # 6. Check that extracted text is non-empty
    if not extracted_text or not extracted_text.strip():
        raise HTTPException(
            status_code=422,
            detail="File is empty or could not be read.",
        )

    return {"text": extracted_text, "filename": sanitized_filename}


@router.post("", response_model=KnowledgeSession, status_code=201)
def create_session(
    req: CreateSessionRequest,
    request: Request,
    store: SessionStore = Depends(get_session_store),
):
    # Prefer X-Counsellor-ID header; fall back to request body field.
    counsellor_id = _get_counsellor_id(request) or req.counsellor_id
    return store.create_session(req.raw_input, created_by=counsellor_id)


@router.get("/{session_id}", response_model=KnowledgeSession)
def get_session(
    session_id: str, request: Request, store: SessionStore = Depends(get_session_store)
):
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_ownership(session, _get_counsellor_id(request))
    return session


@router.post("/{session_id}/analyze", response_model=SessionAnalysisResponse)
def analyze_session(
    session_id: str,
    request: Request,
    store: SessionStore = Depends(get_session_store),
    embedder=Depends(_get_embedder),
):
    """Extract intents from session raw_input using LLM."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_ownership(session, _get_counsellor_id(request))

    if session.status == "completed":
        raise HTTPException(
            status_code=409, detail="Completed sessions cannot be re-analyzed"
        )

    workflow_id = uuid4().hex
    session.analysis_workflow = {
        "workflow_id": workflow_id,
        "workflow_name": "session_card_analysis",
        "status": "started",
        "started_at": _workflow_timestamp(),
        "ended_at": None,
        "drop_point": "analysis_started",
        "partial_result": False,
        "failure_summary": None,
        "steps": [],
        "context_pack": {},
        "repair": {"applied": False, "attempts": 0},
        "raw_output": {},
        "parsed_payload": {},
        "validation": {},
        "append": {},
        "card_counts": {
            "raw": 0,
            "repaired": 0,
            "committed": 0,
            "already_covered": 0,
            "alumni_built": 0,
        },
        "alumni": {
            "heavy": False,
            "invoked": False,
            "result": "not_evaluated",
            "cards_built": 0,
        },
    }
    workflow = _ensure_analysis_workflow(session)

    # Mark the run before starting the LLM call so the UI can stop auto-retrying
    # and operators can see that work is in flight.
    session.status = "analyzing"
    session.analysis_error = None
    _touch_session(session)

    # Gather existing knowledge for context
    profile_store = get_career_profile_store()
    employer_store = get_employer_store()

    existing_tracks = []
    try:
        profiles = profile_store.list_profiles()
        # list_profiles returns model objects — convert to dicts
        existing_tracks = [
            p if isinstance(p, dict) else p.model_dump() for p in profiles
        ]
    except Exception:
        pass  # Non-fatal — LLM works without track context

    existing_employers = []
    try:
        employers = employer_store.list_employers()
        # list_employers returns dicts already
        existing_employers = [
            e if isinstance(e, dict) else e.model_dump() for e in employers
        ]
    except Exception:
        pass  # Non-fatal

    workflow["context_pack"] = {
        "existing_track_count": len(existing_tracks),
        "existing_employer_count": len(existing_employers),
        "raw_input_chars": len(session.raw_input or ""),
    }

    # Call LLM — run in a sub-thread so we can enforce an overall deadline even
    # on multi-pass notes where each chunk has its own per-call timeout but the
    # total can still exceed the ALB/nginx gateway timeout.

    _deadline = float(getattr(settings, "llm_session_timeout_seconds", 180))
    logger.info(
        "analyze: passing %d tracks and %d employers to LLM (deadline %.0fs)",
        len(existing_tracks),
        len(existing_employers),
        _deadline,
    )
    try:
        _future = _SESSION_INTENTS_EXECUTOR.submit(
            generate_session_intents,
            raw_input=session.raw_input,
            existing_tracks=existing_tracks,
            existing_employers=existing_employers,
            session_id=session.id,
            trace_metadata={
                "workflow_id": workflow_id,
                "workflow_name": "session_card_analysis",
            },
        )
        result = _future.result(timeout=_deadline)
    except FuturesTimeoutError:
        current = store.get_session(session_id)
        if current and current.status == "cancelled":
            raise HTTPException(status_code=409, detail="Session was cancelled.")
        session.status = "failed"
        session.analysis_error = f"Analysis timed out after {_deadline:.0f}s"
        workflow["status"] = "error"
        workflow["ended_at"] = _workflow_timestamp()
        workflow["drop_point"] = "session_intent_generation"
        workflow["failure_summary"] = session.analysis_error
        workflow["steps"].append(
            _workflow_step("Intent extraction", "error", session.analysis_error)
        )
        _touch_session(session)
        raise HTTPException(
            status_code=504,
            detail=(
                f"Analysis timed out after {_deadline:.0f}s. "
                "Notes may be too long — try splitting them into smaller sessions."
            ),
        )
    except HTTPException as exc:
        current = store.get_session(session_id)
        if current and current.status == "cancelled":
            raise HTTPException(status_code=409, detail="Session was cancelled.")
        session.status = "failed"
        session.analysis_error = str(exc.detail)
        workflow["status"] = "error"
        workflow["ended_at"] = _workflow_timestamp()
        workflow["drop_point"] = "session_intent_generation"
        workflow["failure_summary"] = session.analysis_error
        workflow["steps"].append(
            _workflow_step("Intent extraction", "error", session.analysis_error)
        )
        _touch_session(session)
        raise
    except Exception as exc:
        current = store.get_session(session_id)
        if current and current.status == "cancelled":
            raise HTTPException(status_code=409, detail="Session was cancelled.")
        session.status = "failed"
        session.analysis_error = str(exc)
        workflow["status"] = "error"
        workflow["ended_at"] = _workflow_timestamp()
        err_lower = str(exc).lower()
        if "repair" in err_lower or "json" in err_lower or "parse" in err_lower:
            workflow["drop_point"] = "json_parse_or_repair"
            workflow["repair"]["applied"] = True
            workflow["repair"]["failure"] = str(exc)
        else:
            workflow["drop_point"] = "session_intent_generation"
        workflow["failure_summary"] = session.analysis_error
        workflow["steps"].append(
            _workflow_step("Intent extraction", "error", session.analysis_error)
        )
        _touch_session(session)
        raise HTTPException(status_code=503, detail="Analysis service unavailable")

    workflow["steps"].append(
        _workflow_step(
            "Intent extraction",
            "ok",
            cards=len(result.get("cards", [])),
            already_covered=len(result.get("already_covered", [])),
        )
    )
    workflow["card_counts"]["raw"] = len(result.get("cards", []))
    workflow["card_counts"]["repaired"] = len(result.get("cards", []))
    workflow["card_counts"]["already_covered"] = len(result.get("already_covered", []))
    workflow["parsed_payload"] = {
        "cards_raw": len(result.get("cards", [])),
        "cards_repaired": len(result.get("cards", [])),
        "already_covered": len(result.get("already_covered", [])),
    }

    track_guidance = None
    try:
        query_embedding = embedder.encode(session.raw_input)
        track_guidance = build_track_guidance(
            raw_input=session.raw_input,
            query_embedding=query_embedding,
            profile_store=profile_store,
            session_id=session.id,
        )
    except Exception:
        logger.warning("analyze: failed to build track guidance", exc_info=True)

    # Build IntentCard objects
    cards = []
    try:
        for card_data in result.get("cards", []):
            card = IntentCard(**card_data)
            cards.append(card)
    except (ValidationError, ValueError, TypeError) as exc:
        session.status = "failed"
        session.analysis_error = f"Invalid intent card payload: {exc}"
        workflow["status"] = "error"
        workflow["ended_at"] = _workflow_timestamp()
        workflow["drop_point"] = "card_validation"
        workflow["failure_summary"] = session.analysis_error
        workflow["validation"] = {
            "result": "rejected",
            "reason": str(exc),
        }
        workflow["steps"].append(_workflow_step("Card validation", "error", str(exc)))
        _touch_session(session)
        raise HTTPException(
            status_code=422, detail="Invalid intent card payload from analysis service"
        )

    alumni_heavy = _is_alumni_heavy(session.raw_input)
    workflow["alumni"]["heavy"] = alumni_heavy

    if alumni_heavy:
        try:
            alumni_store = get_alumni_store()
            existing_alumni = [
                {
                    "slug": item.get("slug"),
                    "full_name": item.get("full_name"),
                    "current_company": item.get("current_company"),
                }
                for item in alumni_store.list_alumni()
            ]
            started = perf_counter()
            alumni_extraction = generate_alumni_extraction(
                text=session.raw_input,
                existing_alumni=existing_alumni,
                session_id=session.id,
                trace_metadata={
                    "workflow_id": workflow_id,
                    "workflow_name": "session_card_analysis",
                },
            )
            workflow["alumni"]["invoked"] = True
            built_alumni_cards = _build_alumni_cards(
                alumni_extraction, session.id, existing_alumni
            )
            for alumni_card in built_alumni_cards:
                cards.append(IntentCard(**alumni_card))
            workflow["alumni"]["result"] = "invoked"
            workflow["alumni"]["cards_built"] = len(built_alumni_cards)
            workflow["card_counts"]["alumni_built"] = len(built_alumni_cards)
            workflow["steps"].append(
                _workflow_step("Alumni extraction", "ok", cards=len(built_alumni_cards))
            )
            logger.info(
                "analyze: alumni extraction took %dms",
                round((perf_counter() - started) * 1000),
            )
        except HTTPException:
            workflow["alumni"]["invoked"] = True
            workflow["alumni"]["result"] = "http_error"
            workflow["steps"].append(
                _workflow_step("Alumni extraction", "error", "Upstream HTTP error")
            )
            logger.warning(
                "analyze: alumni extraction skipped after upstream HTTP error",
                exc_info=True,
            )
        except Exception:
            workflow["alumni"]["invoked"] = True
            workflow["alumni"]["result"] = "parse_error"
            workflow["steps"].append(
                _workflow_step(
                    "Alumni extraction", "error", "Parse or validation error"
                )
            )
            logger.warning(
                "analyze: alumni extraction skipped after parse/validation error",
                exc_info=True,
            )
    else:
        workflow["alumni"]["result"] = "skipped_not_alumni_heavy"
        workflow["steps"].append(
            _workflow_step(
                "Alumni heavy detection", "ok", "Alumni path skipped", heavy=False
            )
        )

    # Build AlreadyCovered objects
    already_covered = []
    for ac_data in result.get("already_covered", []):
        ac = AlreadyCovered(**ac_data)
        already_covered.append(ac)

    # Store on session
    current = store.get_session(session_id)
    if current and current.status == "cancelled":
        raise HTTPException(status_code=409, detail="Session was cancelled.")

    session.intent_cards = [c.model_dump() for c in cards]
    session.already_covered = [a.model_dump() for a in already_covered]
    session.track_guidance = track_guidance
    session.analysis_error = None
    session.status = "analyzed"
    workflow["status"] = "ok"
    workflow["ended_at"] = _workflow_timestamp()
    workflow["card_counts"]["committed"] = len(session.intent_cards)
    workflow["append"] = {
        "target": "session.intent_cards",
        "result": "written",
        "card_count": len(session.intent_cards),
    }
    workflow["validation"] = {
        "result": "accepted",
        "validated_cards": len(session.intent_cards),
    }
    workflow["drop_point"] = (
        "alumni_card_build"
        if alumni_heavy
        and workflow["alumni"]["invoked"]
        and workflow["alumni"]["cards_built"] == 0
        and workflow["card_counts"]["raw"] == 0
        else "session.intent_cards"
    )
    _touch_session(session)

    return SessionAnalysisResponse(
        session_id=session.id,
        cards=[c.model_dump() for c in cards],
        already_covered=[a.model_dump() for a in already_covered],
        track_guidance=track_guidance,
    )


@router.post("/{session_id}/cancel")
def cancel_session(
    session_id: str,
    request: Request,
    store: SessionStore = Depends(get_session_store),
):
    """Cancel a session so the UI stops auto-running it."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_ownership(session, _get_counsellor_id(request))
    if session.status == "completed":
        raise HTTPException(
            status_code=409, detail="Completed sessions cannot be cancelled"
        )
    session.status = "cancelled"
    session.analysis_error = "Cancelled by user"
    if isinstance(session.analysis_workflow, dict):
        session.analysis_workflow["status"] = "cancelled"
        session.analysis_workflow["ended_at"] = _workflow_timestamp()
        session.analysis_workflow["drop_point"] = "cancelled"
        session.analysis_workflow["failure_summary"] = "Cancelled by user"
    _touch_session(session)
    return {"session_id": session_id, "status": "cancelled"}


@router.post("/{session_id}/cards/{card_id}/commit")
def commit_card(
    session_id: str,
    card_id: str,
    request: Request,
    req: CardCommitRequest | None = None,
    store: SessionStore = Depends(get_session_store),
):
    """Commit a single card's diff to the appropriate YAML file."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_ownership(session, _get_counsellor_id(request))

    card = next((c for c in session.intent_cards if c.get("card_id") == card_id), None)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if card.get("status") != "pending":
        raise HTTPException(
            status_code=409, detail=f"Card already {card.get('status')}"
        )

    domain = card.get("domain", "")
    if domain not in ("track", "employer", "alumni"):
        raise HTTPException(status_code=400, detail=f"Unknown domain: {domain}")

    # Use edited diff if provided, otherwise use card's stored diff
    effective_diff = req.diff if req and req.diff else card.get("diff", {})

    # Require slug in diff to identify the target entity
    try:
        effective_diff = validate_intent_card_diff(domain, effective_diff)
    except (ValidationError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422, detail=f"Invalid {domain} card diff: {exc}"
        )

    # Strip empty values to avoid writing blank fields
    effective_diff = {
        k: v
        for k, v in effective_diff.items()
        if v is not None and v != "" and v != [] and v != {}
    }

    target_slug = effective_diff.get("slug")
    if not target_slug:
        raise HTTPException(
            status_code=400,
            detail="Card diff is missing 'slug' field — cannot determine target entity",
        )

    if not _slug_is_safe(target_slug):
        raise HTTPException(status_code=422, detail="Invalid slug format")

    changed_fields: list[str] = []
    is_new = False
    links_attempted: int | None = None
    links_written: int | None = None
    if domain == "track":
        changed_fields, is_new = _apply_field_updates_to_profile(
            target_slug, effective_diff
        )
    elif domain == "employer":
        changed_fields, is_new = _apply_field_updates_to_employer(
            target_slug, effective_diff
        )
    else:
        changed_fields, is_new, links_attempted, links_written = (
            _apply_field_updates_to_alumni(target_slug, effective_diff)
        )

    card["status"] = "committed"
    _check_session_completion(session)
    store.save_session(session)

    response: dict[str, Any] = {
        "card_id": card_id,
        "domain": domain,
        "status": "committed",
        "message": f"Updated {len(changed_fields)} field(s) on {domain} '{target_slug}'",
    }
    if links_attempted is not None:
        response["company_links_attempted"] = links_attempted
        response["company_links_written"] = links_written
        if links_written is not None and links_attempted > links_written:
            response["company_links_warning"] = (
                f"{links_attempted - links_written} of {links_attempted} company link(s) "
                "were dropped due to missing required fields."
            )
    return response


@router.post("/{session_id}/cards/{card_id}/discard")
def discard_card(
    session_id: str,
    card_id: str,
    request: Request,
    store: SessionStore = Depends(get_session_store),
):
    """Discard a single card without writing anything."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _check_session_ownership(session, _get_counsellor_id(request))

    card = next((c for c in session.intent_cards if c.get("card_id") == card_id), None)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if card.get("status") != "pending":
        raise HTTPException(
            status_code=409, detail=f"Card already {card.get('status')}"
        )

    card["status"] = "discarded"
    _check_session_completion(session)
    store.save_session(session)

    return {
        "card_id": card_id,
        "status": "discarded",
    }
