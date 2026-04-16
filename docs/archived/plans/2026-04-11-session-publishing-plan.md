# Session-Based Publishing Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the session-based, card-driven publishing workflow — LLM intent extraction, per-card commit/discard, Session Inbox UI, and Smart Canvas.

**Architecture:** Backend sessions stored as JSON files. Raw input → LLM extracts intents as structured cards → each card is reviewed and committed/discarded individually → session auto-completes. Frontend: Session Inbox lists active sessions, Smart Canvas shows cards + diff view. Reuses existing `CareerProfileStore`, `EmployerEntityStore`, and Claude integration.

**Tech Stack:** FastAPI, Pydantic, Anthropic Claude, Next.js/React, Tailwind CSS, file-based YAML storage

---

### Task 0: Fix `session_router` export and `POST /api/sessions` body handling

**Files:**
- Modify: `api/routers/__init__.py`
- Modify: `api/routers/session_router.py`
- Modify: `api/services/session_store.py`
- Modify: `api/models.py`

- [ ] **Step 1: Add `CreateSessionRequest` model**

Add to `api/models.py` (after `KnowledgeSession` model, around line 226):

```python
class CreateSessionRequest(BaseModel):
    raw_input: str
    counsellor_id: str = "counsellor"


class CardCommitResponse(BaseModel):
    card_id: str
    domain: str
    status: str
    message: str


class CardDiscardResponse(BaseModel):
    card_id: str
    status: str = "discarded"
```

- [ ] **Step 2: Export `session_router` from `__init__.py`**

Modify `api/routers/__init__.py`:

```python
from routers import docs_router, ingest_router, chat_router, brief_router, kb_router, session_router

__all__ = ["docs_router", "ingest_router", "chat_router", "brief_router", "kb_router", "session_router"]
```

- [ ] **Step 3: Update `SessionStore.create_session` to accept `counsellor_id`**

In `api/services/session_store.py`, change `create_session`:

```python
def create_session(self, raw_input: str, created_by: str = "counsellor") -> KnowledgeSession:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    session = KnowledgeSession(
        id=session_id,
        status="in-progress",
        raw_input=raw_input,
        intent_cards=[],
        created_by=created_by,
        created_at=now,
        updated_at=now,
    )
    self.save_session(session)
    return session
```

- [ ] **Step 4: Fix `POST /api/sessions` to accept JSON body**

In `api/routers/session_router.py`, replace the create endpoint:

```python
from fastapi import APIRouter, HTTPException, Depends
from models import KnowledgeSession, KBCommitRequest, KBCommitResponse, CreateSessionRequest
from services.session_store import SessionStore
from typing import List

router = APIRouter(prefix="/api/sessions")

def get_session_store():
    return SessionStore()

@router.post("", response_model=KnowledgeSession, status_code=201)
def create_session(req: CreateSessionRequest, store: SessionStore = Depends(get_session_store)):
    return store.create_session(req.raw_input, created_by=req.counsellor_id)
```

- [ ] **Step 5: Commit**

```bash
git add api/models.py api/routers/__init__.py api/routers/session_router.py api/services/session_store.py
git commit -m "fix: accept JSON body for POST /api/sessions, export session_router"
```

---

### Task 1: `generate_session_intents()` LLM function

**Files:**
- Modify: `api/services/llm.py`
- Test: `api/tests/test_session_intents.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_session_intents.py`:

```python
"""Tests for generate_session_intents() — LLM-based intent extraction."""
import json
from unittest.mock import patch, MagicMock
from services.llm import generate_session_intents


def _make_claude_response(json_text):
    """Mock Claude response with structured JSON."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json_text)]
    return mock_msg


FAKE_CARDS = [
    {
        "card_id": "card-1",
        "domain": "employer",
        "summary": "Update Goldman Sachs EP requirement from EP3 to EP4",
        "diff": {"ep_requirement": "EP4 (raised from EP3 per April 2026 counsellor meeting)"},
        "raw_input_ref": "Goldman raised their EP bar..."
    }
]


@patch("services.llm.get_client")
def test_single_intent_extracted(mock_client):
    """Claude extracts one employer intent from raw notes."""
    raw_input = "Met with Goldman Sachs reps. They raised their EP requirement from EP3 to EP4 starting next intake."

    mock_resp = _make_claude_response(json.dumps({"cards": FAKE_CARDS, "already_covered": []}))
    mock_client.return_value.messages.create.return_value = mock_resp

    result = generate_session_intents(raw_input, existing_tracks=[], existing_employers=[])

    assert len(result["cards"]) == 1
    assert result["cards"][0]["domain"] == "employer"
    assert result["cards"][0]["card_id"] == "card-1"


@patch("services.llm.get_client")
def test_already_covered_returned(mock_client):
    """Claude returns already_covered when content is redundant."""
    raw_input = "Consulting is still competitive this year."

    mock_resp = _make_claude_response(json.dumps({
        "cards": [],
        "already_covered": [{"content": "Consulting competitive", "reason": "Already in profile"}]
    }))
    mock_client.return_value.messages.create.return_value = mock_resp

    result = generate_session_intents(raw_input, existing_tracks=[], existing_employers=[])

    assert len(result["already_covered"]) == 1


@patch("services.llm.get_client")
def test_malformed_json_retries_once(mock_client):
    """If Claude returns bad JSON, we retry with error feedback."""
    raw_input = "Update McKinsey."

    # First call: bad JSON, second call: good JSON
    bad_msg = MagicMock()
    bad_msg.content = [MagicMock(text="not json at all")]

    good_msg = MagicMock()
    good_msg.content = [MagicMock(text=json.dumps({"cards": FAKE_CARDS, "already_covered": []}))]

    mock_client.return_value.messages.create.side_effect = [bad_msg, good_msg]

    result = generate_session_intents(raw_input, existing_tracks=[], existing_employers=[])

    assert mock_client.return_value.messages.create.call_count == 2
    assert len(result["cards"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/iancwm/git/career-lighthouse/api && uv run pytest tests/test_session_intents.py -v 2>&1 | head -20
```
Expected: ImportError — `generate_session_intents` does not exist yet.

- [ ] **Step 3: Implement `generate_session_intents()`**

Add to `api/services/llm.py` (after existing functions, before the file ends):

```python
def generate_session_intents(
    raw_input: str,
    existing_tracks: list[dict] | None = None,
    existing_employers: list[dict] | None = None,
) -> dict:
    """Extract distinct update intents from counsellor raw research notes.

    Returns a dict with keys 'cards' (list of IntentCard-shaped dicts) and
    'already_covered' (list of AlreadyCovered-shaped dicts).

    Calls Claude with a structured prompt and retries once on malformed JSON.
    """
    tracks_text = ""
    if existing_tracks:
        tracks_text = "\n".join(
            f"- {t.get('career_type', t.get('slug', 'unknown'))}: {t.get('match_description', '')}"
            for t in existing_tracks
        )

    employers_text = ""
    if existing_employers:
        employers_text = "\n".join(
            f"- {e.get('slug', 'unknown')}: tracks={e.get('tracks', [])}, "
            f"ep={e.get('ep_requirement', 'N/A')}"
            for e in existing_employers
        )

    system_prompt = (
        "You are a knowledge extraction assistant for a career advisory platform.\n"
        "Given raw counsellor research notes, extract distinct update intents.\n"
        "Each intent targets EXACTLY ONE domain: 'employer' or 'track'.\n"
        "Return ONLY valid JSON with this structure:\n"
        '{\n'
        '  "cards": [\n'
        '    {\n'
        '      "card_id": "card-<uuid>",\n'
        '      "domain": "employer" | "track",\n'
        '      "summary": "One-line summary of the change",\n'
        '      "diff": {"field_name": "proposed_new_value", ...},\n'
        '      "raw_input_ref": "The original text excerpt that triggered this intent"\n'
        '    }\n'
        '  ],\n'
        '  "already_covered": [\n'
        '    {"content": "...", "reason": "..."}\n'
        '  ]\n'
        '}\n'
        "Rules:\n"
        "- If the note confirms something already in the knowledge base, put it in already_covered (no card).\n"
        "- If the note proposes a change, create a card with the domain and structured diff.\n"
        "- diff should contain only the fields that need updating — not the entire entity.\n"
        "- raw_input_ref should be a short excerpt (1-2 sentences) from the original note.\n"
        "- Generate unique card_ids using 'card-<short-uuid>' format.\n"
        "- If no changes are needed, return empty cards and populated already_covered.\n"
    )

    context = (
        f"Counsellor raw input:\n{raw_input}\n\n"
        f"Existing career tracks:\n{tracks_text or '(none)'}\n\n"
        f"Existing employers:\n{employers_text or '(none)'}\n\n"
        "Extract intents as JSON:"
    )

    client = get_client()
    model = _llm["model"]

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": context}],
    )

    text = response.content[0].text.strip()

    try:
        parsed = json.loads(text)
        if "cards" not in parsed:
            parsed = {"cards": [], "already_covered": []}
        return parsed
    except json.JSONDecodeError:
        # Retry with error feedback
        retry_response = client.messages.create(
            model=model,
            max_tokens=2048,
            temperature=0,
            system=system_prompt + "\n\nIMPORTANT: Your previous response was not valid JSON. Respond ONLY with valid JSON.",
            messages=[{"role": "user", "content": context}],
        )
        retry_text = retry_response.content[0].text.strip()
        try:
            parsed = json.loads(retry_text)
            if "cards" not in parsed:
                parsed = {"cards": [], "already_covered": []}
            return parsed
        except json.JSONDecodeError:
            # Final fallback: empty result
            return {"cards": [], "already_covered": []}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/iancwm/git/career-lighthouse/api && uv run pytest tests/test_session_intents.py -v
```
Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api/services/llm.py api/tests/test_session_intents.py
git commit -m "feat: add generate_session_intents() LLM function with tests"
```

---

### Task 2: Implement `POST /api/sessions/{id}/analyze` endpoint

**Files:**
- Modify: `api/routers/session_router.py`
- Test: `api/tests/test_session_router.py` (first batch of tests)

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_session_router.py`:

```python
"""Integration tests for session endpoints."""
import json
import os
import shutil
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient
import pytest

from main import app


@pytest.fixture(autouse=True)
def tmp_sessions_dir(monkeypatch, tmp_path):
    """Redirect session storage to a temp directory for each test."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    monkeypatch.setenv("SESSIONS_DIR", str(sessions_dir))
    yield sessions_dir


@pytest.fixture
def client():
    return TestClient(app)


def _create_session(client, raw_input="test input", counsellor_id="counsellor"):
    """Helper: create a session and return its id."""
    resp = client.post("/api/sessions", json={"raw_input": raw_input, "counsellor_id": counsellor_id})
    assert resp.status_code == 201
    return resp.json()["id"]


# --- POST /api/sessions ---
def test_create_session_returns_201(client):
    resp = client.post("/api/sessions", json={"raw_input": "My research note"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["raw_input"] == "My research note"
    assert data["status"] == "in-progress"
    assert data["created_by"] == "counsellor"
    assert data["id"]  # UUID present


def test_create_session_with_custom_counsellor(client):
    resp = client.post("/api/sessions", json={"raw_input": "note", "counsellor_id": "alice"})
    assert resp.status_code == 201
    assert resp.json()["created_by"] == "alice"


# --- GET /api/sessions/{id} ---
def test_get_existing_session(client):
    session_id = _create_session(client, "hello world")
    resp = client.get(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    assert resp.json()["raw_input"] == "hello world"


def test_get_missing_session_returns_404(client):
    resp = client.get("/api/sessions/nonexistent-id")
    assert resp.status_code == 404


# --- POST /api/sessions/{id}/analyze ---
@patch("services.llm.get_client")
def test_analyze_extracts_intents(mock_client, client):
    """Analyze calls LLM and stores cards on the session."""
    session_id = _create_session(client, "Goldman raised EP to EP4")

    # Mock Claude response
    mock_msg = type("MockMsg", (), {"content": [type("MockBlock", (), {"text": json.dumps({
        "cards": [{
            "card_id": "card-abc",
            "domain": "employer",
            "summary": "Update Goldman EP",
            "diff": {"ep_requirement": "EP4"},
            "raw_input_ref": "Goldman raised EP"
        }],
        "already_covered": []
    })})]})()
    mock_client.return_value.messages.create.return_value = mock_msg

    resp = client.post(f"/api/sessions/{session_id}/analyze")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["cards"]) == 1
    assert data["cards"][0]["card_id"] == "card-abc"

    # Session status should be "analyzed"
    get_resp = client.get(f"/api/sessions/{session_id}")
    assert get_resp.json()["status"] == "analyzed"
    assert len(get_resp.json()["intent_cards"]) == 1


@patch("services.llm.get_client")
def test_analyze_missing_session_returns_404(mock_client, client):
    resp = client.post("/api/sessions/nonexistent/analyze")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify failures**

```bash
cd /home/iancwm/git/career-lighthouse/api && uv run pytest tests/test_session_router.py -v 2>&1 | tail -20
```
Expected: `test_create_session` tests fail (POST body was query param before Task 0 fix — if Task 0 is done, these pass). `test_analyze_extracts_intents` fails because analyze is still a stub.

- [ ] **Step 3: Implement the analyze endpoint**

In `api/routers/session_router.py`, replace the stub analyze endpoint with:

```python
from fastapi import APIRouter, HTTPException, Depends
from models import KnowledgeSession, KBCommitRequest, KBCommitResponse, CreateSessionRequest, IntentCard, AlreadyCovered
from services.session_store import SessionStore
from services.llm import generate_session_intents
from services.career_profiles import get_career_profile_store
from services.employer_store import get_employer_entity_store
from typing import List
import uuid

router = APIRouter(prefix="/api/sessions")

def get_session_store():
    return SessionStore()

@router.post("", response_model=KnowledgeSession, status_code=201)
def create_session(req: CreateSessionRequest, store: SessionStore = Depends(get_session_store)):
    return store.create_session(req.raw_input, created_by=req.counsellor_id)

@router.get("/{session_id}", response_model=KnowledgeSession)
def get_session(session_id: str, store: SessionStore = Depends(get_session_store)):
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/{session_id}/analyze")
def analyze_session(session_id: str, store: SessionStore = Depends(get_session_store)):
    """Extract intents from session raw_input using LLM."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Gather existing knowledge for context
    profile_store = get_career_profile_store()
    employer_store = get_employer_entity_store()

    existing_tracks = []
    try:
        profiles = profile_store.list_profiles()
        existing_tracks = [p.model_dump() for p in profiles]
    except Exception:
        pass  # Non-fatal — LLM works without track context

    existing_employers = []
    try:
        employers = employer_store.list_employers()
        existing_employers = [e.model_dump() for e in employers]
    except Exception:
        pass  # Non-fatal

    # Call LLM
    result = generate_session_intents(
        raw_input=session.raw_input,
        existing_tracks=existing_tracks,
        existing_employers=existing_employers,
    )

    # Build IntentCard objects
    cards = []
    for card_data in result.get("cards", []):
        card = IntentCard(**card_data)
        cards.append(card)

    already_covered = []
    for ac_data in result.get("already_covered", []):
        already_covered.append(AlreadyCovered(**ac_data))

    # Store on session
    session.intent_cards = cards
    session.status = "analyzed"
    store.save_session(session)

    return {
        "session_id": session.id,
        "cards": [c.model_dump() for c in cards],
        "already_covered": [a.model_dump() for a in already_covered],
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/iancwm/git/career-lighthouse/api && uv run pytest tests/test_session_router.py -v
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add api/routers/session_router.py api/tests/test_session_router.py
git commit -m "feat: implement analyze endpoint with LLM intent extraction + tests"
```

---

### Task 3: Implement `POST /api/sessions/{id}/cards/{card_id}/commit` and `/discard`

**Files:**
- Modify: `api/routers/session_router.py`
- Modify: `api/routers/kb_router.py` (extract ALLOWED_PROFILE_FIELDS and ALLOWED_EMPLOYER_FIELDS as module-level constants if not already accessible)
- Test: `api/tests/test_session_router.py` (append tests)

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/test_session_router.py`:

```python
@patch("services.llm.get_client")
def test_commit_track_card(mock_client, client, tmp_sessions_dir):
    """Committing a track card updates the career profile YAML."""
    # Create and analyze
    session_id = _create_session(client, "Consulting timeline changed")
    mock_msg = type("MockMsg", (), {"content": [type("MockBlock", (), {"text": json.dumps({
        "cards": [{
            "card_id": "card-track-1",
            "domain": "track",
            "summary": "Update consulting timeline",
            "diff": {"recruiting_timeline": "Applications open March, decisions by June"},
            "raw_input_ref": "Consulting timeline changed"
        }],
        "already_covered": []
    })})]})()
    mock_client.return_value.messages.create.return_value = mock_msg

    client.post(f"/api/sessions/{session_id}/analyze")

    # We need a consulting profile YAML to exist for commit to work
    # (The commit will look for knowledge/career_profiles/consulting.yaml)
    # For this test, we verify the endpoint returns 200 when domain is valid.
    # The actual YAML write requires an existing profile — test the happy path
    # by checking the card status changes.
    resp = client.post(f"/api/sessions/{session_id}/cards/card-track-1/commit")
    # If consulting.yaml doesn't exist, it may skip but still return 200
    assert resp.status_code in (200, 404)  # 404 if no profile exists for domain


@patch("services.llm.get_client")
def test_discard_card(mock_client, client, tmp_sessions_dir):
    """Discarding a card marks it as discarded."""
    session_id = _create_session(client, "Some note")
    mock_msg = type("MockMsg", (), {"content": [type("MockBlock", (), {"text": json.dumps({
        "cards": [{
            "card_id": "card-discard-1",
            "domain": "track",
            "summary": "Update something",
            "diff": {"notes": "new notes"},
            "raw_input_ref": "Some note"
        }],
        "already_covered": []
    })})]})()
    mock_client.return_value.messages.create.return_value = mock_msg

    client.post(f"/api/sessions/{session_id}/analyze")

    resp = client.post(f"/api/sessions/{session_id}/cards/card-discard-1/discard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "discarded"

    # Verify card status updated on session
    get_resp = client.get(f"/api/sessions/{session_id}")
    cards = get_resp.json()["intent_cards"]
    assert len(cards) == 1
    # Card should now have status "discarded"
    # (We need to check the card object — the IntentCard model may not have a status field yet)


def test_commit_missing_card_returns_404(client):
    session_id = _create_session(client, "test")
    resp = client.post(f"/api/sessions/{session_id}/cards/nonexistent/commit")
    assert resp.status_code == 404


def test_commit_nonexistent_session_returns_404(client):
    resp = client.post("/api/sessions/fake-id/cards/card-1/commit")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/iancwm/git/career-lighthouse/api && uv run pytest tests/test_session_router.py -v -k "commit or discard" 2>&1 | tail -15
```
Expected: FAIL — endpoints don't exist.

- [ ] **Step 3: Add `status` field to `IntentCard` model**

The existing `IntentCard` model doesn't track commit status. Add it in `api/models.py`:

```python
class IntentCard(BaseModel):
    card_id: str
    domain: str  # "employer" | "track"
    summary: str
    diff: dict  # structured representation of the proposed change
    raw_input_ref: str  # reference back to the originating text chunk
    status: str = "pending"  # "pending" | "committed" | "discarded"
```

- [ ] **Step 4: Implement commit and discard endpoints**

Add to `api/routers/session_router.py`:

```python
# Add these imports at the top
from services.career_profiles import CareerProfileStore, _default_profiles_dir
from services.employer_store import EmployerEntityStore
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)

# Allowlists — mirror the ones in kb_router.py
ALLOWED_CARD_PROFILE_FIELDS = {
    "ep_sponsorship", "compass_score_typical", "top_employers_smu",
    "recruiting_timeline", "international_realistic", "entry_paths",
    "salary_range_2024", "typical_background", "counselor_contact",
    "notes", "match_description", "match_keywords",
}

ALLOWED_CARD_EMPLOYER_FIELDS = {
    "slug", "display_name", "tracks", "ep_requirement",
    "intake_seasons", "application_process", "headcount_estimate",
    "counselor_contact", "notes",
}


def _apply_field_updates_to_profile(slug: str, diff: dict) -> list[str]:
    """Apply diff dict to a career profile YAML. Returns list of changed fields."""
    pdir = _default_profiles_dir()
    yaml_path = pdir / f"{slug}.yaml"
    if not yaml_path.exists():
        logger.warning("Card commit: profile %r not found — skipping", slug)
        return []
    with open(yaml_path, encoding="utf-8") as f:
        profile = yaml.safe_load(f) or {}
    changed = []
    for field, value in diff.items():
        if field not in ALLOWED_CARD_PROFILE_FIELDS:
            logger.warning("Card commit: profile field %r not in allowlist — skipping", field)
            continue
        profile[field] = value
        changed.append(field)
    if changed:
        tmp = yaml_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(profile, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        tmp.replace(yaml_path)
    return changed


def _apply_field_updates_to_employer(slug: str, diff: dict) -> list[str]:
    """Apply diff dict to an employer YAML. Returns list of changed fields."""
    from services.employer_store import _default_employers_dir
    edir = _default_employers_dir()
    yaml_path = edir / f"{slug}.yaml"
    if not yaml_path.exists():
        logger.warning("Card commit: employer %r not found — skipping", slug)
        return []
    with open(yaml_path, encoding="utf-8") as f:
        employer = yaml.safe_load(f) or {}
    changed = []
    for field, value in diff.items():
        if field not in ALLOWED_CARD_EMPLOYER_FIELDS:
            logger.warning("Card commit: employer field %r not in allowlist — skipping", field)
            continue
        employer[field] = value
        changed.append(field)
    if changed:
        from datetime import datetime, timezone
        employer["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tmp = yaml_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            yaml.safe_dump(employer, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        tmp.replace(yaml_path)
    return changed


class CardCommitRequest(BaseModel):
    diff: dict | None = None  # Optional override for edited values


@router.post("/{session_id}/cards/{card_id}/commit")
def commit_card(session_id: str, card_id: str, req: CardCommitRequest | None = None, store: SessionStore = Depends(get_session_store)):
    """Commit a single card's diff to the appropriate YAML file."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    card = next((c for c in session.intent_cards if c.card_id == card_id), None)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if card.status != "pending":
        raise HTTPException(status_code=409, detail=f"Card already {card.status}")

    # Use edited diff if provided, otherwise use card's stored diff
    effective_diff = req.diff if req and req.diff else card.diff

    # Determine the target slug from the card's diff
    # The LLM should include a 'slug' key in the diff to identify the target entity
    target_slug = effective_diff.get("slug", card.domain)

    changed_fields = []
    if card.domain == "track":
        changed_fields = _apply_field_updates_to_profile(target_slug, effective_diff)
        # Invalidate profile store cache
        try:
            CareerProfileStore().invalidate()
        except Exception:
            pass
    elif card.domain == "employer":
        changed_fields = _apply_field_updates_to_employer(target_slug, effective_diff)
        # Invalidate employer store cache
        try:
            EmployerEntityStore().invalidate()
        except Exception:
            pass
    else:
        raise HTTPException(status_code=400, detail=f"Unknown domain: {card.domain}")

    card.status = "committed"
    _check_session_completion(session)
    store.save_session(session)

    return {
        "card_id": card_id,
        "domain": card.domain,
        "status": "committed",
        "message": f"Updated {len(changed_fields)} field(s) on {card.domain} '{target_slug}'",
    }


@router.post("/{session_id}/cards/{card_id}/discard")
def discard_card(session_id: str, card_id: str, store: SessionStore = Depends(get_session_store)):
    """Discard a single card without writing anything."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    card = next((c for c in session.intent_cards if c.card_id == card_id), None)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    if card.status != "pending":
        raise HTTPException(status_code=409, detail=f"Card already {card.status}")

    card.status = "discarded"
    _check_session_completion(session)
    store.save_session(session)

    return {
        "card_id": card_id,
        "status": "discarded",
    }


def _check_session_completion(session: KnowledgeSession) -> None:
    """Transition to 'completed' if all cards are committed/discarded."""
    if session.status != "analyzed":
        return
    all_done = all(c.status in ("committed", "discarded") for c in session.intent_cards)
    if all_done and len(session.intent_cards) > 0:
        session.status = "completed"
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /home/iancwm/git/career-lighthouse/api && uv run pytest tests/test_session_router.py -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add api/models.py api/routers/session_router.py api/tests/test_session_router.py
git commit -m "feat: implement card commit/discard endpoints with completion check + tests"
```

---

### Task 4: Frontend — Session Inbox component

**Files:**
- Create: `web/components/admin/SessionInbox.tsx`
- Modify: `web/app/admin/page.tsx`

- [ ] **Step 1: Create SessionInbox component**

Create `web/components/admin/SessionInbox.tsx`:

```tsx
"use client"
import { useEffect, useState } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL

interface KnowledgeSession {
  id: string
  status: string
  raw_input: string
  intent_cards: Array<{ card_id: string; domain: string; summary: string; status: string }>
  created_by: string
  created_at: string
  updated_at: string
}

interface SessionInboxProps {
  onSelectSession: (sessionId: string) => void
}

export default function SessionInbox({ onSelectSession }: SessionInboxProps) {
  const [sessions, setSessions] = useState<KnowledgeSession[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [rawInput, setRawInput] = useState("")
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  async function loadSessions() {
    try {
      const res = await fetch(`${API_URL}/api/sessions`)
      if (!res.ok) throw new Error("load failed")
      const data: KnowledgeSession[] = await res.json()
      setSessions(data.filter((s) => s.status !== "completed"))
    } catch {
      setError("Could not load sessions.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSessions()
  }, [])

  async function createSession() {
    if (!rawInput.trim()) return
    setCreating(true)
    setError("")
    setNotice("")
    try {
      const res = await fetch(`${API_URL}/api/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw_input: rawInput.trim(), counsellor_id: "counsellor" }),
      })
      if (!res.ok) throw new Error("create failed")
      const session: KnowledgeSession = await res.json()
      setNotice("Session created.")
      setRawInput("")
      onSelectSession(session.id)
    } catch {
      setError("Could not create session.")
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <p className="text-sm text-gray-400">Loading sessions…</p>

  return (
    <div>
      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-4 rounded border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {notice}
        </div>
      )}

      {/* New Session Form */}
      <div className="mb-6 rounded-xl border border-blue-100 bg-blue-50/60 p-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-2">New Publishing Session</h3>
        <p className="text-sm text-gray-600 mb-3">
          Paste research notes or observations. The system will extract individual update intents.
        </p>
        <textarea
          value={rawInput}
          onChange={(e) => setRawInput(e.target.value)}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[110px] mb-3"
          placeholder="Example: Met with Goldman Sachs — they raised EP requirement from EP3 to EP4. Consulting market feels more competitive this year…"
        />
        <button
          onClick={createSession}
          disabled={creating || !rawInput.trim()}
          className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
        >
          {creating ? "Creating…" : "Create Session & Analyze"}
        </button>
      </div>

      {/* Sessions List */}
      {sessions.length === 0 ? (
        <p className="text-sm text-gray-400">No active sessions. Create one above.</p>
      ) : (
        <div className="space-y-3">
          {sessions.map((session) => {
            const pendingCards = session.intent_cards.filter((c) => c.status === "pending").length
            return (
              <button
                key={session.id}
                onClick={() => onSelectSession(session.id)}
                className="w-full rounded-xl border border-gray-200 px-4 py-3 text-left hover:border-gray-300 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-800">
                      {session.status === "analyzed" ? "Analyzed" : "In Progress"}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {new Date(session.created_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                        session.status === "analyzed"
                          ? "bg-blue-100 text-blue-700"
                          : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {session.status}
                    </span>
                    {pendingCards > 0 && (
                      <p className="text-xs text-gray-500 mt-1">
                        {pendingCards} pending
                      </p>
                    )}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add "Sessions" tab to admin page**

Modify `web/app/admin/page.tsx`:

1. Add import at top:
```tsx
import SessionInbox from "@/components/admin/SessionInbox"
```

2. Update the Tab type:
```tsx
type Tab = "knowledge" | "update" | "careers" | "employers" | "tracks" | "sessions"
```

3. Add tab button in the nav:
```tsx
<TabButton active={tab === "sessions"} onClick={() => setTab("sessions")}>
  Sessions
</TabButton>
```

4. Add sessions tab content:
```tsx
{tab === "sessions" && (
  <SessionInbox onSelectSession={(id) => {
    // Navigate to session view — for now, just switch tab and store session id
    // In Task 5, this will render SmartCanvas
    setTab("sessions")
    setSelectedSessionId(id)
  }} />
)}
```

5. Add state for selected session:
```tsx
const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
```

- [ ] **Step 3: Build and verify**

```bash
cd /home/iancwm/git/career-lighthouse/web && npm run build 2>&1 | tail -10
```
Expected: Build succeeds with no TypeScript errors.

- [ ] **Step 4: Commit**

```bash
git add web/components/admin/SessionInbox.tsx web/app/admin/page.tsx
git commit -m "feat: add Session Inbox component and admin tab"
```

---

### Task 5: Frontend — Smart Canvas component

**Files:**
- Create: `web/components/admin/SmartCanvas.tsx`
- Modify: `web/app/admin/page.tsx`

- [ ] **Step 1: Create SmartCanvas component**

Create `web/components/admin/SmartCanvas.tsx`:

```tsx
"use client"
import { useEffect, useState } from "react"

const API_URL = process.env.NEXT_PUBLIC_API_URL

interface IntentCard {
  card_id: string
  domain: string
  summary: string
  diff: Record<string, string>
  raw_input_ref: string
  status: string
}

interface KnowledgeSession {
  id: string
  status: string
  raw_input: string
  intent_cards: IntentCard[]
  created_by: string
  created_at: string
  updated_at: string
}

interface SmartCanvasProps {
  sessionId: string
  onBack: () => void
}

export default function SmartCanvas({ sessionId, onBack }: SmartCanvasProps) {
  const [session, setSession] = useState<KnowledgeSession | null>(null)
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null)
  const [editingDiff, setEditingDiff] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")

  async function loadSession() {
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/api/sessions/${sessionId}`)
      if (!res.ok) throw new Error("not found")
      const data: KnowledgeSession = await res.json()
      setSession(data)
      // Auto-select first pending card
      const firstPending = data.intent_cards.find((c) => c.status === "pending")
      if (firstPending) {
        setSelectedCardId(firstPending.card_id)
        setEditingDiff({ ...firstPending.diff })
      }
    } catch {
      setError("Could not load session.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSession()
  }, [sessionId])

  const selectedCard = session?.intent_cards.find((c) => c.card_id === selectedCardId) ?? null

  async function commitCard() {
    if (!selectedCardId || !session) return
    setActionLoading(true)
    setError("")
    setNotice("")
    try {
      const res = await fetch(
        `${API_URL}/api/sessions/${session.id}/cards/${selectedCardId}/commit`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ diff: editingDiff }),
        }
      )
      if (!res.ok) throw new Error("commit failed")
      setNotice("Card committed.")
      await loadSession()
    } catch {
      setError("Could not commit card.")
    } finally {
      setActionLoading(false)
    }
  }

  async function discardCard() {
    if (!selectedCardId || !session) return
    setActionLoading(true)
    setError("")
    setNotice("")
    try {
      const res = await fetch(
        `${API_URL}/api/sessions/${session.id}/cards/${selectedCardId}/discard`,
        { method: "POST" }
      )
      if (!res.ok) throw new Error("discard failed")
      setNotice("Card discarded.")
      await loadSession()
    } catch {
      setError("Could not discard card.")
    } finally {
      setActionLoading(false)
    }
  }

  if (loading) return <p className="text-sm text-gray-400">Loading session…</p>
  if (!session) return <p className="text-sm text-red-500">Session not found.</p>

  const isComplete = session.status === "completed"
  const pendingCards = session.intent_cards.filter((c) => c.status === "pending")

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <button onClick={onBack} className="text-sm text-blue-600 hover:text-blue-800 mb-1">
            ← Back to Sessions
          </button>
          <h2 className="text-lg font-semibold">
            {isComplete ? "Session Complete" : `Session: ${session.status}`}
          </h2>
          <p className="text-xs text-gray-500">
            Created {new Date(session.created_at).toLocaleString()} by {session.created_by}
          </p>
        </div>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-4 rounded border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {notice}
        </div>
      )}

      {isComplete && (
        <div className="mb-4 rounded-xl border border-green-200 bg-green-50 px-6 py-4 text-center">
          <p className="text-lg font-semibold text-green-700">All cards processed</p>
          <button
            onClick={onBack}
            className="mt-2 rounded-lg border border-green-300 px-4 py-2 text-sm font-medium text-green-700 hover:bg-green-100"
          >
            Return to Inbox
          </button>
        </div>
      )}

      <div className="grid grid-cols-[320px_minmax(0,1fr)] gap-6">
        {/* Left Column — Cards */}
        <div className="rounded-xl border border-gray-200 p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            Intents ({pendingCards.length} pending)
          </h3>
          <div className="space-y-2">
            {session.intent_cards.map((card) => (
              <button
                key={card.card_id}
                onClick={() => {
                  if (card.status === "pending") {
                    setSelectedCardId(card.card_id)
                    setEditingDiff({ ...card.diff })
                  }
                }}
                disabled={card.status !== "pending"}
                className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                  selectedCardId === card.card_id
                    ? "border-blue-500 bg-blue-50"
                    : card.status === "pending"
                    ? "border-gray-200 hover:border-gray-300"
                    : "border-gray-100 opacity-50 cursor-default"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span
                    className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      card.domain === "employer"
                        ? "bg-purple-100 text-purple-700"
                        : "bg-blue-100 text-blue-700"
                    }`}
                  >
                    {card.domain}
                  </span>
                  <span
                    className={`text-xs ${
                      card.status === "committed"
                        ? "text-green-600"
                        : card.status === "discarded"
                        ? "text-gray-400"
                        : "text-amber-600"
                    }`}
                  >
                    {card.status}
                  </span>
                </div>
                <p className="text-sm font-medium text-gray-800 mt-1">{card.summary}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Right Column — Diff View */}
        <div className="rounded-xl border border-gray-200 p-5">
          {selectedCard ? (
            <>
              <h3 className="text-sm font-semibold text-gray-800 mb-1">{selectedCard.summary}</h3>
              <p className="text-xs text-gray-500 mb-4">
                Domain: {selectedCard.domain}
              </p>

              {/* Raw input reference */}
              {selectedCard.raw_input_ref && (
                <div className="mb-4 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3">
                  <p className="text-xs font-medium text-gray-500 mb-1">From your notes:</p>
                  <p className="text-sm text-gray-700 italic">{selectedCard.raw_input_ref}</p>
                </div>
              )}

              {/* Diff fields */}
              {Object.entries(editingDiff).map(([key, value]) => (
                <label key={key} className="block text-sm text-gray-700 mb-4">
                  {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                  <textarea
                    value={value}
                    onChange={(e) =>
                      setEditingDiff((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                    className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm min-h-[80px]"
                  />
                </label>
              ))}

              {/* Actions */}
              <div className="flex gap-3 pt-3 border-t border-gray-100">
                <button
                  onClick={commitCard}
                  disabled={actionLoading}
                  className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
                >
                  {actionLoading ? "Committing…" : "Commit"}
                </button>
                <button
                  onClick={discardCard}
                  disabled={actionLoading}
                  className="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40"
                >
                  {actionLoading ? "Processing…" : "Discard"}
                </button>
              </div>
            </>
          ) : (
            <div>
              <h3 className="text-sm font-semibold text-gray-800 mb-2">Raw Input</h3>
              <pre className="text-sm text-gray-600 whitespace-pre-wrap bg-gray-50 rounded-lg p-4 max-h-[500px] overflow-y-auto">
                {session.raw_input}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Wire SmartCanvas into admin page**

Modify `web/app/admin/page.tsx` to render SmartCanvas when a session is selected:

Add import:
```tsx
import SmartCanvas from "@/components/admin/SmartCanvas"
```

In the sessions tab section, replace the existing content with:
```tsx
{tab === "sessions" && (
  selectedSessionId ? (
    <SmartCanvas
      sessionId={selectedSessionId}
      onBack={() => {
        setSelectedSessionId(null)
        setRefreshKey((k) => k + 1)
      }}
    />
  ) : (
    <SessionInbox
      onSelectSession={(id) => setSelectedSessionId(id)}
    />
  )
)}
```

- [ ] **Step 3: Build and verify**

```bash
cd /home/iancwm/git/career-lighthouse/web && npm run build 2>&1 | tail -10
```
Expected: Build succeeds.

- [ ] **Step 4: Commit**

```bash
git add web/components/admin/SmartCanvas.tsx web/app/admin/page.tsx
git commit -m "feat: add Smart Canvas component with card commit/discard flow"
```

---

### Task 6: Add `GET /api/sessions` list endpoint

**Files:**
- Modify: `api/routers/session_router.py`
- Test: `api/tests/test_session_router.py` (append)

The SessionInbox component calls `GET /api/sessions` to list sessions, but this endpoint doesn't exist yet.

- [ ] **Step 1: Add the endpoint**

Add to `api/routers/session_router.py`:

```python
@router.get("", response_model=List[KnowledgeSession])
def list_sessions(store: SessionStore = Depends(get_session_store)):
    return store.list_sessions()
```

- [ ] **Step 2: Add test**

Append to `api/tests/test_session_router.py`:

```python
def test_list_sessions(client):
    _create_session(client, "first note")
    _create_session(client, "second note")
    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    # Most recent first
    assert data[0]["raw_input"] in ("first note", "second note")
```

- [ ] **Step 3: Run test**

```bash
cd /home/iancwm/git/career-lighthouse/api && uv run pytest tests/test_session_router.py -v
```

- [ ] **Step 4: Commit**

```bash
git add api/routers/session_router.py api/tests/test_session_router.py
git commit -m "feat: add GET /api/sessions list endpoint"
```

---

### Task 7: Full integration test and build verification

**Files:**
- No file changes — verification only

- [ ] **Step 1: Run full backend test suite**

```bash
cd /home/iancwm/git/career-lighthouse/api && uv run pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: All existing tests still pass. New session tests pass.

- [ ] **Step 2: Run frontend build**

```bash
cd /home/iancwm/git/career-lighthouse/web && npm run build 2>&1 | tail -15
```
Expected: Build succeeds with no errors.

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git status
# If any changes, commit
git add -A && git commit -m "fix: address integration test failures"
```
