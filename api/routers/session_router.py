from fastapi import APIRouter, File, HTTPException, Depends, UploadFile
from dependencies import require_admin_key
from models import (
    AlreadyCovered,
    CardCommitRequest,
    CreateSessionRequest,
    IntentCard,
    KnowledgeSession,
    SessionAnalysisResponse,
)
from services.session_store import SessionStore
from services.track_guidance import build_track_guidance
from typing import List
from pathlib import Path
from starlette.requests import Request
import yaml
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", dependencies=[Depends(require_admin_key)])

# Imported from sibling modules
from config import settings
from routers.ingest_router import _sanitize_filename
from services.ingestion import parse_file

def get_session_store():
    return SessionStore()


def _get_embedder():
    from dependencies import get_embedder

    return get_embedder()

# Allowlists — mirror the ones in kb_router.py
# Inspected 2026-04-12 (knowledge-capture-hardening): these guards prevent
# arbitrary YAML key injection from card commit payloads. Fields not in the
# allowlist are skipped with a warning — same posture as kb_router.py.
ALLOWED_CARD_PROFILE_FIELDS = {
    "ep_sponsorship", "compass_score_typical", "top_employers_smu",
    "recruiting_timeline", "international_realistic", "entry_paths",
    "salary_range_2024", "typical_background", "counselor_contact",
    "notes", "match_description", "match_keywords",
}

ALLOWED_CARD_EMPLOYER_FIELDS = {
    "employer_name", "tracks", "ep_requirement",
    "intake_seasons", "application_process", "headcount_estimate",
    "counselor_contact", "notes",
}


def _slug_is_safe(slug: str) -> bool:
    """Reject path traversal and injection in slug values."""
    if not slug or "/" in slug or ".." in slug or " " in slug:
        return False
    return all(c.isalnum() or c in "-_" for c in slug)


def _apply_field_updates_to_profile(slug: str, diff: dict) -> tuple[list[str], bool]:
    """Apply diff dict to a career profile YAML. Creates new file if missing.
    Returns (changed_fields, is_new)."""
    from services.career_profiles import _default_profiles_dir
    if not _slug_is_safe(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format")
    pdir = _default_profiles_dir()
    yaml_path = pdir / f"{slug}.yaml"

    # Create new profile if it doesn't exist
    is_new = not yaml_path.exists()
    profile = {}
    if not is_new:
        with open(yaml_path, encoding="utf-8") as f:
            profile = yaml.safe_load(f) or {}

    changed = []
    for field, value in diff.items():
        if field == "slug":
            continue  # skip slug, it's the identifier
        if field not in ALLOWED_CARD_PROFILE_FIELDS:
            logger.warning("Card commit: profile field %r not in allowlist — skipping", field)
            continue
        profile[field] = value
        changed.append(field)
    if changed:
        tmp = yaml_path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                yaml.safe_dump(profile, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            tmp.replace(yaml_path)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            logger.error("_apply_field_updates_to_profile: failed to write %r: %s", yaml_path, exc)
            raise HTTPException(status_code=500, detail=f"Failed to write profile '{slug}'")
        # Invalidate profile store cache
        try:
            from services.career_profiles import CareerProfileStore
            CareerProfileStore().invalidate()
        except Exception:
            pass
    return changed, is_new


def _apply_field_updates_to_employer(slug: str, diff: dict) -> tuple[list[str], bool]:
    """Apply diff dict to an employer YAML. Creates new file if missing.
    Returns (changed_fields, is_new)."""
    from services.employer_store import _default_employers_dir
    if not _slug_is_safe(slug):
        raise HTTPException(status_code=422, detail="Invalid slug format")
    edir = _default_employers_dir()
    yaml_path = edir / f"{slug}.yaml"

    # Create new employer if it doesn't exist
    is_new = not yaml_path.exists()
    employer = {"slug": slug}
    if not is_new:
        with open(yaml_path, encoding="utf-8") as f:
            employer = yaml.safe_load(f) or {}
    changed = []
    for field, value in diff.items():
        if field == "slug":
            continue
        if field not in ALLOWED_CARD_EMPLOYER_FIELDS:
            logger.warning("Card commit: employer field %r not in allowlist — skipping", field)
            continue
        employer[field] = value
        changed.append(field)
    if changed:
        from datetime import datetime, timezone
        employer["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tmp = yaml_path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                yaml.safe_dump(employer, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            tmp.replace(yaml_path)
        except Exception as exc:
            tmp.unlink(missing_ok=True)
            logger.error("_apply_field_updates_to_employer: failed to write %r: %s", yaml_path, exc)
            raise HTTPException(status_code=500, detail=f"Failed to write employer '{slug}'")
        # Invalidate employer store cache
        try:
            from services.employer_store import EmployerEntityStore
            EmployerEntityStore().invalidate()
        except Exception:
            pass
    return changed, is_new


def _check_session_completion(session: KnowledgeSession) -> None:
    """Transition to 'completed' if all cards are committed/discarded."""
    if session.status != "analyzed":
        return
    all_done = all(c.get("status") in ("committed", "discarded") for c in session.intent_cards)
    if all_done and len(session.intent_cards) > 0:
        session.status = "completed"

@router.get("", response_model=List[KnowledgeSession])
def list_sessions(store: SessionStore = Depends(get_session_store)):
    """List all sessions, most recently updated first."""
    return store.list_sessions()


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
        logger.warning("parse_session_file: failed to parse %r", sanitized_filename, exc_info=True)
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
def create_session(req: CreateSessionRequest, store: SessionStore = Depends(get_session_store)):
    return store.create_session(req.raw_input, created_by=req.counsellor_id)

@router.get("/{session_id}", response_model=KnowledgeSession)
def get_session(session_id: str, store: SessionStore = Depends(get_session_store)):
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/{session_id}/analyze", response_model=SessionAnalysisResponse)
def analyze_session(
    session_id: str,
    store: SessionStore = Depends(get_session_store),
    embedder=Depends(_get_embedder),
):
    """Extract intents from session raw_input using LLM."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Gather existing knowledge for context
    from services.career_profiles import get_career_profile_store
    from services.employer_store import get_employer_store

    profile_store = get_career_profile_store()
    employer_store = get_employer_store()

    existing_tracks = []
    try:
        profiles = profile_store.list_profiles()
        # list_profiles returns model objects — convert to dicts
        existing_tracks = [p if isinstance(p, dict) else p.model_dump() for p in profiles]
    except Exception:
        pass  # Non-fatal — LLM works without track context

    existing_employers = []
    try:
        employers = employer_store.list_employers()
        # list_employers returns dicts already
        existing_employers = [e if isinstance(e, dict) else e.model_dump() for e in employers]
    except Exception:
        pass  # Non-fatal

    # Call LLM
    from services.llm import generate_session_intents
    logger.info("analyze: passing %d tracks and %d employers to LLM",
        len(existing_tracks), len(existing_employers))
    result = generate_session_intents(
        raw_input=session.raw_input,
        existing_tracks=existing_tracks,
        existing_employers=existing_employers,
    )

    thought = result.get("thought")

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
    for card_data in result.get("cards", []):
        card = IntentCard(**card_data)
        cards.append(card)

    # Build AlreadyCovered objects
    already_covered = []
    for ac_data in result.get("already_covered", []):
        ac = AlreadyCovered(**ac_data)
        already_covered.append(ac)

    # Store on session
    session.intent_cards = [c.model_dump() for c in cards]
    session.track_guidance = track_guidance
    session.thought = thought
    session.status = "analyzed"
    store.save_session(session)

    return SessionAnalysisResponse(
        session_id=session.id,
        cards=[c.model_dump() for c in cards],
        already_covered=[a.model_dump() for a in already_covered],
        track_guidance=track_guidance,
        thought=thought,
    )


@router.post("/{session_id}/cards/{card_id}/commit")
def commit_card(
    session_id: str,
    card_id: str,
    req: CardCommitRequest | None = None,
    store: SessionStore = Depends(get_session_store),
):
    """Commit a single card's diff to the appropriate YAML file."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    card = next((c for c in session.intent_cards if c.get("card_id") == card_id), None)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if card.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"Card already {card.get('status')}")

    # Use edited diff if provided, otherwise use card's stored diff
    effective_diff = req.diff if req and req.diff else card.get("diff", {})

    # Strip empty values to avoid writing blank fields
    effective_diff = {k: v for k, v in effective_diff.items() if v}

    # Require slug in diff to identify the target entity
    target_slug = effective_diff.get("slug")
    if not target_slug:
        raise HTTPException(status_code=400, detail="Card diff is missing 'slug' field — cannot determine target entity")

    if not _slug_is_safe(target_slug):
        raise HTTPException(status_code=422, detail="Invalid slug format")

    changed_fields: list[str] = []
    is_new = False
    domain = card.get("domain", "")
    if domain == "track":
        changed_fields, is_new = _apply_field_updates_to_profile(target_slug, effective_diff)
    elif domain == "employer":
        changed_fields, is_new = _apply_field_updates_to_employer(target_slug, effective_diff)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown domain: {domain}")

    # Build message — differentiate create vs update
    action = "Created new" if is_new else "Updated"
    msg = f"{action} {domain} '{target_slug}' ({len(changed_fields)} field(s))"

    card["status"] = "committed"
    _check_session_completion(session)
    store.save_session(session)

    return {
        "card_id": card_id,
        "domain": domain,
        "status": "committed",
        "message": f"Updated {len(changed_fields)} field(s) on {domain} '{target_slug}'",
    }


@router.post("/{session_id}/cards/{card_id}/discard")
def discard_card(session_id: str, card_id: str, store: SessionStore = Depends(get_session_store)):
    """Discard a single card without writing anything."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    card = next((c for c in session.intent_cards if c.get("card_id") == card_id), None)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if card.get("status") != "pending":
        raise HTTPException(status_code=409, detail=f"Card already {card.get('status')}")

    card["status"] = "discarded"
    _check_session_completion(session)
    store.save_session(session)

    return {
        "card_id": card_id,
        "status": "discarded",
    }
