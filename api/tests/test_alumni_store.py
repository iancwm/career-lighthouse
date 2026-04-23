"""Tests for the alumni YAML store."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


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
    monkeypatch.setenv("ALUMNI_BACKFILL_MANIFEST_PATH", str(alumni_dir / "_backfill_manifest.yaml"))
    monkeypatch.setenv("EMPLOYERS_DIR", str(tmp_path / "employers"))
    return alumni_dir


def test_create_update_and_append_only_link_history(alumni_env):
    from services.alumni_store import get_alumni_store

    store = get_alumni_store()
    created = store.create_alumni(
        {
            "slug": "aditya_mehta",
            "name": "Aditya Mehta",
            "degree": "LLM",
            "school": "NUS",
            "graduation_year": 2018,
            "current_company": "Stripe Singapore",
            "current_title": "Head of Compliance",
            "available_for_mentoring": True,
            "notes": "Trusted for compliance and referrals.",
        }
    )

    assert created["full_name"] == "Aditya Mehta"
    assert created["graduation_program"] == "LLM"
    assert created["consent_for_referrals"] is True

    updated = store.update_alumni(
        "aditya_mehta",
        {
            "notes": "Trusted for compliance and referrals.",
            "current_title": "Head of Compliance Program APAC",
        },
    )
    assert updated["current_title"] == "Head of Compliance Program APAC"
    assert store.list_history("aditya_mehta")

    first_link = store.append_link(
        "aditya_mehta",
        {
            "company_name": "Stripe Singapore",
            "relationship": "Mentor contact",
            "notes": "Can speak to compliance and risk roles",
        },
    )
    second_link = store.append_link(
        "aditya_mehta",
        {
            "company_name": "Stripe Singapore",
            "relationship": "Mentor contact",
            "notes": "Updated note",
        },
    )

    assert first_link["link_id"] == second_link["link_id"]
    assert len(store.list_link_events("aditya_mehta")) == 2
    assert len(store.list_links("aditya_mehta")) == 1
    assert store.get_alumni("aditya_mehta")["completeness"] == "green"


def test_backfill_legacy_alumni_migrates_employer_facts(alumni_env, tmp_path, monkeypatch):
    employers_dir = Path(tmp_path / "employers")
    employers_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))

    (employers_dir / "stripe_singapore.yaml").write_text(
        textwrap.dedent(
            """\
            employer_name: Stripe Singapore
            slug: stripe_singapore
            structured:
              facts:
                - type: alumni
                  slug: stripe-aditya-mehta
                  timestamp: "2026-04-22T00:00:00Z"
                  data:
                    full_name: Aditya Mehta
                    current_company: Stripe Singapore
                    current_title: Head of Compliance
                    graduation_school: NUS
                    graduation_program: LLM
                    graduation_year: 2018
                    rationale: Trusted for compliance referrals
            """
        ),
        encoding="utf-8",
    )

    from services.alumni_store import get_alumni_store

    store = get_alumni_store()
    stats = store.backfill_legacy_alumni()

    assert stats["facts_migrated"] == 1
    migrated = store.get_alumni("aditya_mehta")
    assert migrated is not None
    assert migrated["full_name"] == "Aditya Mehta"
    assert len(store.list_links("aditya_mehta")) == 1
