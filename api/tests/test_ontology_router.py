# api/tests/test_ontology_router.py
"""Tests for api/routers/ontology_router.py — ontology/metadata layer
Milestone 1, Phase 4: GET read endpoints, the extract-claims proposal
endpoint, and the claim-card commit endpoint.
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

from models_ontology import (
    ApplicationWindowPayload,
    ClaimConfidence,
    ClaimObservationTime,
    ClaimScope,
    Evidence,
    EvidenceLocator,
    RecruitmentStagePayload,
)
from services.claim_store import ClaimStore
from services.entity_store import EntityStore
from services.evidence_store import EvidenceStore
from services.ontology_extraction import ClaimProposalResult, OntologyExtractionResult


# ---------------------------------------------------------------------------
# Client helpers
# ---------------------------------------------------------------------------


def make_client(bypass_admin: bool = True) -> TestClient:
    from main import app
    import dependencies

    if bypass_admin:
        app.dependency_overrides[dependencies.require_admin_key] = lambda: None

    client = TestClient(app)
    client.headers["X-Admin-Key"] = "test-key"
    return client


def make_employer(tmp_path, monkeypatch, slug="acme", notes="Applications open in August."):
    import os
    from services.employer_store import EmployerEntityStore

    employers_dir = tmp_path / "employers"
    employers_dir.mkdir(parents=True, exist_ok=True)
    (employers_dir / f"{slug}.yaml").write_text(
        textwrap.dedent(f"""\
            employer_name: Acme Corp
            slug: {slug}
            tracks: []
            notes: "{notes}"
        """),
        encoding="utf-8",
    )
    monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
    os.environ["EMPLOYERS_DIR"] = str(employers_dir)
    EmployerEntityStore._instance = None
    return employers_dir


def enable_extraction(monkeypatch):
    from cfg import kb_cfg

    monkeypatch.setitem(kb_cfg["ontology"], "extraction_enabled", True)


# ---------------------------------------------------------------------------
# GET /api/kb/entities
# ---------------------------------------------------------------------------


class TestListEntitiesEndpoint:
    def test_lists_entities_with_filters(self):
        client = make_client()
        EntityStore().create_entity("organization", "Acme Corp", geography="SG")
        EntityStore().create_entity("organization", "Beta LLC", geography="US")
        EntityStore().create_entity("person", "Jane Teoh")

        r = client.get("/api/kb/entities")
        assert r.status_code == 200
        assert len(r.json()) == 3

        r = client.get("/api/kb/entities", params={"entity_type": "organization"})
        assert r.status_code == 200
        names = {e["canonical_name"] for e in r.json()}
        assert names == {"Acme Corp", "Beta LLC"}

    def test_filters_by_status(self):
        client = make_client()
        entity = EntityStore().create_entity("organization", "Acme Corp")
        # Archive it via a raw model_copy + rewrite so we have a non-active record.
        archived = entity.model_copy(update={"status": "archived"})
        from services.entity_store import _entity_path
        from services.shared_yaml import atomic_yaml_write

        atomic_yaml_write(_entity_path("organization", entity.entity_id), archived.model_dump())

        r = client.get(
            "/api/kb/entities", params={"entity_type": "organization", "status": "archived"}
        )
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["status"] == "archived"


class TestGetEntityEndpoint:
    def test_returns_entity_by_id(self):
        client = make_client()
        entity = EntityStore().create_entity("organization", "Acme Corp")

        r = client.get(f"/api/kb/entities/{entity.entity_id}")
        assert r.status_code == 200
        assert r.json()["canonical_name"] == "Acme Corp"

    def test_404_for_unknown_entity(self):
        client = make_client()
        r = client.get("/api/kb/entities/organization-nonexistent")
        assert r.status_code == 404

    def test_404_for_invalid_entity_type_prefix(self):
        client = make_client()
        r = client.get("/api/kb/entities/not_a_real_type-slug")
        assert r.status_code == 404

    def test_404_for_id_with_no_hyphen(self):
        client = make_client()
        r = client.get("/api/kb/entities/noHyphenHere")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/kb/claims
# ---------------------------------------------------------------------------


def _make_claim(subject_entity_id="organization-acme", claim_type="application_window"):
    evidence = EvidenceStore().create_evidence(
        "src-1", "Applications open in August.", "directly_supports", 0.8
    )
    payload = ApplicationWindowPayload(opens_on="2026-08-01")
    return ClaimStore().create_claim(
        claim_type=claim_type,
        subject_entity_id=subject_entity_id,
        payload=payload,
        observation_time=ClaimObservationTime(recorded_at=datetime.now(timezone.utc)),
        confidence=ClaimConfidence(
            extraction=0.8, evidence_strength=0.8, source_reliability=0.5
        ),
        evidence_ids=[evidence.evidence_id],
    ), evidence


class TestListClaimsEndpoint:
    def test_lists_claims_with_filters(self):
        client = make_client()
        claim, _ = _make_claim(subject_entity_id="organization-acme")
        _make_claim(subject_entity_id="organization-beta")

        r = client.get("/api/kb/claims")
        assert r.status_code == 200
        assert len(r.json()) == 2

        r = client.get(
            "/api/kb/claims", params={"subject_entity_id": "organization-acme"}
        )
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["claim_id"] == claim.claim_id

        r = client.get("/api/kb/claims", params={"review_status": "approved"})
        assert r.status_code == 200
        assert r.json() == []


class TestGetClaimEndpoint:
    def test_returns_claim_with_inlined_evidence(self):
        client = make_client()
        claim, evidence = _make_claim()

        r = client.get(f"/api/kb/claims/{claim.claim_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["claim_id"] == claim.claim_id
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["evidence_id"] == evidence.evidence_id
        assert data["evidence"][0]["excerpt"] == "Applications open in August."

    def test_404_for_unknown_claim(self):
        client = make_client()
        r = client.get("/api/kb/claims/claim-application_window-doesnotexist")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/kb/evidence/{evidence_id}
# ---------------------------------------------------------------------------


class TestGetEvidenceEndpoint:
    def test_returns_evidence_by_id(self):
        client = make_client()
        evidence = EvidenceStore().create_evidence(
            "src-1", "Some excerpt text.", "context_only", 0.5
        )

        r = client.get(f"/api/kb/evidence/{evidence.evidence_id}")
        assert r.status_code == 200
        assert r.json()["excerpt"] == "Some excerpt text."

    def test_404_for_unknown_evidence(self):
        client = make_client()
        r = client.get("/api/kb/evidence/evidence-doesnotexist")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Admin-key enforcement
# ---------------------------------------------------------------------------


def test_requires_admin_key_when_configured(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "admin_key", "super-secret")
    client = make_client(bypass_admin=False)
    client.headers.pop("X-Admin-Key", None)

    r = client.get("/api/kb/entities")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/kb/employers/{slug}/extract-claims
# ---------------------------------------------------------------------------


class TestExtractClaimsEndpoint:
    def test_403_when_extraction_disabled(self, tmp_path, monkeypatch):
        # kb.yaml checked-in default: ontology.extraction_enabled = false
        make_employer(tmp_path, monkeypatch)
        client = make_client()

        r = client.post("/api/kb/employers/acme/extract-claims")
        assert r.status_code == 403

    def test_404_for_unknown_employer(self, tmp_path, monkeypatch):
        make_employer(tmp_path, monkeypatch)
        enable_extraction(monkeypatch)
        client = make_client()

        r = client.post("/api/kb/employers/nonexistent/extract-claims")
        assert r.status_code == 404

    def _canned_result(self, source_id):
        verified_payload = ApplicationWindowPayload(opens_on="2026-08-01")
        rejected_payload = RecruitmentStagePayload(
            stage_name="Online assessment", stage_type="online_assessment"
        )
        return OntologyExtractionResult(
            source_id=source_id,
            claim_proposals=[
                ClaimProposalResult(
                    claim_type="application_window",
                    subject_entity_id="organization-acme",
                    subject_mention_text="Acme Corp",
                    subject_resolution_status="matched",
                    payload=verified_payload,
                    scope=ClaimScope(geography="SG"),
                    assertion_status="asserted",
                    extraction_confidence=0.9,
                    evidence_ids=["evidence-verified"],
                    evidence_excerpts=["Applications open in August."],
                    verification_status="verified",
                    verification_note="Supported by excerpt.",
                ),
                ClaimProposalResult(
                    claim_type="recruitment_stage",
                    subject_entity_id="organization-acme",
                    subject_mention_text="Acme Corp",
                    subject_resolution_status="matched",
                    payload=rejected_payload,
                    scope=ClaimScope(),
                    assertion_status="inferred",
                    extraction_confidence=0.4,
                    evidence_ids=["evidence-rejected"],
                    evidence_excerpts=["some unrelated text"],
                    verification_status="rejected",
                    verification_note="No supporting excerpt found.",
                ),
            ],
        )

    def test_returns_only_verified_cards_excludes_rejected(self, tmp_path, monkeypatch):
        make_employer(tmp_path, monkeypatch)
        enable_extraction(monkeypatch)
        client = make_client()

        canned = self._canned_result("employer:acme:notes")
        with patch(
            "routers.ontology_router.ontology_extraction.extract_claims_for_source",
            return_value=canned,
        ) as mock_extract:
            r = client.post("/api/kb/employers/acme/extract-claims")

        assert r.status_code == 200
        assert mock_extract.call_count == 1
        data = r.json()
        assert data["total"] == 1
        assert len(data["cards"]) == 1
        card = data["cards"][0]
        assert card["domain"] == "claim"
        assert card["status"] == "pending"
        assert card["diff"]["claim_type"] == "application_window"
        assert card["diff"]["subject_entity_id"] == "organization-acme"

    def test_does_not_persist_anything(self, tmp_path, monkeypatch):
        make_employer(tmp_path, monkeypatch)
        enable_extraction(monkeypatch)
        client = make_client()

        canned = self._canned_result("employer:acme:notes")
        with patch(
            "routers.ontology_router.ontology_extraction.extract_claims_for_source",
            return_value=canned,
        ):
            client.post("/api/kb/employers/acme/extract-claims")

        assert ClaimStore().list_claims() == []

    def test_400_when_employer_has_no_notes(self, tmp_path, monkeypatch):
        make_employer(tmp_path, monkeypatch, notes="")
        enable_extraction(monkeypatch)
        client = make_client()

        r = client.post("/api/kb/employers/acme/extract-claims")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Extract -> review -> commit round trip
# ---------------------------------------------------------------------------


def _seed_session_with_claim_card(tmp_path, monkeypatch, *, evidence_id: str):
    import os
    from models_session import KnowledgeSession
    from services.session_store import SessionStore

    monkeypatch.setenv("SESSIONS_DIR", str(tmp_path / "sessions"))
    os.environ["SESSIONS_DIR"] = str(tmp_path / "sessions")
    SessionStore._instance = None

    now = datetime.now(timezone.utc).isoformat()
    card = {
        "card_id": "claim-abc12345",
        "domain": "claim",
        "summary": "application_window claim for Acme Corp",
        "diff": {
            "claim_type": "application_window",
            "subject_entity_id": "organization-acme",
            "subject_mention_text": "Acme Corp",
            "payload": {
                "claim_type": "application_window",
                "opens_on": "2026-08-01",
            },
            "scope": {"geography": "SG"},
            "valid_time": {},
            "observation_time": {"recorded_at": now},
            "assertion_status": "asserted",
            "confidence": {
                "extraction": 0.9,
                "evidence_strength": 0.9,
                "source_reliability": 0.5,
            },
            "evidence_ids": [evidence_id],
            "evidence_excerpts": ["Applications open in August."],
            "source_id": "employer:acme:notes",
        },
        "raw_input_ref": "employer:acme:notes",
        "status": "pending",
        "proposals": {},
        "is_update": False,
        "matched_slug": None,
    }
    session = KnowledgeSession(
        id="sess-1",
        status="analyzed",
        raw_input="Applications open in August.",
        intent_cards=[card],
        created_by="counsellor",
        created_at=now,
        updated_at=now,
    )
    store = SessionStore()
    store.save_session(session)
    return store, session, card


class TestCommitClaimCardEndpoint:
    def test_commit_writes_approved_claim_and_marks_card_committed(
        self, tmp_path, monkeypatch
    ):
        evidence = EvidenceStore().create_evidence(
            "employer:acme:notes", "Applications open in August.", "directly_supports", 0.8
        )
        _seed_session_with_claim_card(tmp_path, monkeypatch, evidence_id=evidence.evidence_id)
        client = make_client()

        r = client.post("/api/kb/session/sess-1/claims/claim-abc12345/commit")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "committed"
        assert data["domain"] == "claim"
        assert "claim_id" in data

        claim = ClaimStore().get_claim(data["claim_id"])
        assert claim is not None
        assert claim.review_status == "approved"
        assert claim.subject_entity_id == "organization-acme"

        from services.session_store import SessionStore

        session = SessionStore().get_session("sess-1")
        committed_card = next(
            c for c in session.intent_cards if c["card_id"] == "claim-abc12345"
        )
        assert committed_card["status"] == "committed"

    def test_double_commit_returns_409(self, tmp_path, monkeypatch):
        evidence = EvidenceStore().create_evidence(
            "employer:acme:notes", "Applications open in August.", "directly_supports", 0.8
        )
        _seed_session_with_claim_card(tmp_path, monkeypatch, evidence_id=evidence.evidence_id)
        client = make_client()

        first = client.post("/api/kb/session/sess-1/claims/claim-abc12345/commit")
        assert first.status_code == 200

        second = client.post("/api/kb/session/sess-1/claims/claim-abc12345/commit")
        assert second.status_code == 409

    def test_404_for_unknown_session(self):
        client = make_client()
        r = client.post("/api/kb/session/nonexistent/claims/claim-abc12345/commit")
        assert r.status_code == 404

    def test_404_for_unknown_card(self, tmp_path, monkeypatch):
        evidence = EvidenceStore().create_evidence(
            "employer:acme:notes", "Applications open in August.", "directly_supports", 0.8
        )
        _seed_session_with_claim_card(tmp_path, monkeypatch, evidence_id=evidence.evidence_id)
        client = make_client()

        r = client.post("/api/kb/session/sess-1/claims/claim-doesnotexist/commit")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Acceptance criterion 4 — scope round-trips unchanged through the IntentCard
# commit path (docs/ontology/MILESTONE-1.md §4).
# ---------------------------------------------------------------------------


def test_claim_scope_round_trips_unchanged_through_intent_card():
    from models_kb import IntentCard

    scope = ClaimScope(
        geography="SG",
        organization_unit_id="ou-tech",
        programme_id="prog-summer",
        role_id="role-swe",
        seniority="intern",
        candidate_segment="undergrad",
        academic_year="2026",
    )
    diff = {
        "claim_type": "application_window",
        "subject_entity_id": "organization-acme",
        "payload": {
            "claim_type": "application_window",
            "opens_on": "2026-08-01",
        },
        "scope": scope.model_dump(mode="json"),
        "observation_time": {
            "recorded_at": datetime.now(timezone.utc).isoformat()
        },
        "confidence": {
            "extraction": 0.8,
            "evidence_strength": 0.8,
            "source_reliability": 0.5,
        },
        "evidence_ids": ["evidence-abc123"],
    }

    card = IntentCard(
        card_id="c1", domain="claim", summary="s", diff=diff, raw_input_ref="ref"
    )

    assert card.diff["scope"] == scope.model_dump(mode="json")
    for field in (
        "geography",
        "organization_unit_id",
        "programme_id",
        "role_id",
        "seniority",
        "candidate_segment",
        "academic_year",
    ):
        assert card.diff["scope"][field] == getattr(scope, field)
