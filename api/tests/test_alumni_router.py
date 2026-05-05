"""Integration tests for the alumni admin router."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def reset_store():
    from services.alumni_store import AlumniEntityStore

    AlumniEntityStore._instance = None
    yield
    AlumniEntityStore._instance = None


@pytest.fixture
def alumni_env(tmp_path, monkeypatch):
    alumni_dir = tmp_path / "alumni"
    history_dir = tmp_path / "alumni_history"
    links_dir = tmp_path / "alumni_company_links"
    alumni_dir.mkdir()
    history_dir.mkdir()
    links_dir.mkdir()

    monkeypatch.setenv("ALUMNI_DIR", str(alumni_dir))
    monkeypatch.setenv("ALUMNI_HISTORY_DIR", str(history_dir))
    monkeypatch.setenv("ALUMNI_COMPANY_LINKS_DIR", str(links_dir))
    monkeypatch.setenv(
        "ALUMNI_BACKFILL_MANIFEST_PATH", str(alumni_dir / "_backfill_manifest.yaml")
    )

    from config import settings

    monkeypatch.setattr(settings, "admin_key", "", raising=False)
    return alumni_dir


def _client():
    from main import app

    return TestClient(app)


def test_create_update_and_list_round_trip(alumni_env):
    client = _client()

    create_resp = client.post(
        "/api/kb/alumni",
        json={
            "name": "Maya Lim",
            "degree": "BSc Economics",
            "school": "SMU",
            "graduation_year": 2021,
            "current_company": "Grab",
            "current_title": "Product Lead",
            "available_for_mentoring": True,
            "notes": "Known for product mentoring and referrals.",
            "company_links": [
                {
                    "company_name": "Grab",
                    "company_slug": "grab",
                    "relationship": "Mentor contact",
                    "notes": "Can refer product students",
                }
            ],
        },
    )

    assert create_resp.status_code == 200
    created = create_resp.json()
    assert created["name"] == "Maya Lim"
    assert created["degree"] == "BSc Economics"
    assert created["available_for_mentoring"] is True
    assert created["company_link_count"] == 1
    assert created["company_links"][0]["relationship"] == "Mentor contact"
    assert created["company_links"][0]["notes"] == "Can refer product students"

    list_resp = client.get("/api/kb/alumni")
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["slug"] == "maya_lim"

    update_resp = client.put(
        "/api/kb/alumni/maya_lim",
        json={
            "name": "Maya Lim",
            "degree": "BSc Economics",
            "school": "SMU",
            "graduation_year": 2021,
            "current_company": "Grab",
            "current_title": "Senior Product Lead",
            "available_for_mentoring": True,
            "notes": "Known for product mentoring and referrals.",
            "company_links": [
                {
                    "company_name": "Grab",
                    "company_slug": "grab",
                    "relationship": "Mentor contact",
                    "notes": "Updated note",
                }
            ],
        },
    )

    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["current_title"] == "Senior Product Lead"
    assert updated["company_links"][0]["notes"] == "Updated note"


def test_extract_preview_returns_ui_friendly_shape(alumni_env):
    client = _client()

    create_resp = client.post(
        "/api/kb/alumni",
        json={
            "name": "Maya Lim",
            "degree": "BSc Economics",
            "school": "SMU",
            "graduation_year": 2021,
            "current_company": "Grab",
            "current_title": "Product Lead",
            "available_for_mentoring": True,
            "company_links": [
                {
                    "company_name": "Grab",
                    "company_slug": "grab",
                    "relationship": "Mentor contact",
                    "notes": "Current mentor link",
                }
            ],
        },
    )
    assert create_resp.status_code == 200

    mock_preview = {
        "summary_bullets": [
            "The alumnus can mentor product students.",
            "Grab was mentioned as a helpful link.",
        ],
        "profile_proposals": {
            "current_title": {
                "value": "Senior Product Lead",
                "confidence": 91,
                "evidence": ["product lead at Grab"],
                "rationale": "Role is clearly described in the note.",
            }
        },
        "company_link_proposals": [
            {
                "company_name": "Grab",
                "company_slug": "grab",
                "relationship": "Mentor contact",
                "notes": "Can refer product students",
            }
        ],
        "fit_triad": {
            "student_goal_fit": {
                "value": "Strong fit for product coaching",
                "confidence": 84,
                "evidence": ["student wants product guidance"],
                "rationale": "Career goals align with the alumnus background.",
            },
            "technical_depth": {
                "value": "Enough depth for product questions",
                "confidence": 78,
                "evidence": ["product lead"],
                "rationale": "The role suggests practical depth.",
            },
            "character_compatibility": {
                "value": "Shared interest in product work",
                "confidence": 69,
                "evidence": ["product mentoring"],
                "rationale": "Common interest is explicitly mentioned.",
            },
        },
    }

    with patch(
        "services.alumni_store.llm_service.generate_alumni_extraction",
        return_value=mock_preview,
    ) as mock_generate:
        resp = client.post(
            "/api/kb/alumni/extract-preview",
            json={
                "text": "Maya can mentor product students at Grab.",
                "alumni_slug": "maya_lim",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["interpretation_bullets"][0].startswith("The alumnus")
    assert body["profile_updates"]["current_title"]["new"] == "Senior Product Lead"
    assert body["company_links"][0]["relationship"] == "Mentor contact"
    assert {fact["type"] for fact in body["facts"]} == {
        "student_goal_fit",
        "technical_depth",
        "character_compatibility",
    }
    mock_generate.assert_called_once()
    args, kwargs = mock_generate.call_args
    assert args[0] == "Maya can mentor product students at Grab."
    assert any(candidate.get("slug") == "maya_lim" for candidate in args[1])
    assert kwargs["alumni_slug"] == "maya_lim"
    assert kwargs["current_profile"]["full_name"] == "Maya Lim"
    assert kwargs["current_links"][0]["company_slug"] == "grab"


def test_sync_company_links_wrapper_delegates_to_store():
    from routers.alumni_router import _sync_company_links

    store = Mock()
    payload = [{"company_name": "Grab"}]

    _sync_company_links(store, "maya_lim", payload)

    store.sync_company_links.assert_called_once_with("maya_lim", payload)
