"""Integration tests for session track guidance persistence."""
import json
import os
import sys
import tempfile
import types
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


MINIMAL_PROFILE = {
    "career_type": "Test Track",
    "ep_sponsorship": "High",
    "compass_score_typical": "40-50",
    "top_employers_smu": ["Acme Corp"],
    "recruiting_timeline": "October–January",
    "international_realistic": True,
    "entry_paths": ["Internship → offer"],
    "salary_range_2024": "S$60,000–80,000",
    "typical_background": "Any",
    "notes": "Test notes",
}


def write_profile(directory: Path, slug: str, overrides: dict | None = None) -> None:
    import yaml

    profile = {**MINIMAL_PROFILE, **(overrides or {})}
    with open(directory / f"{slug}.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(profile, f, allow_unicode=True, sort_keys=False)


def _load_profiles_with_mock_embedder(self, profiles_dir: Path, mock_emb) -> None:
    import yaml
    from services.career_profiles import _REQUIRED_FIELDS

    self._profiles = {}
    self._type_embeddings = {}
    self._keyword_index = {}

    for yaml_path in sorted(profiles_dir.glob("*.yaml")):
        slug = yaml_path.stem
        with open(yaml_path, encoding="utf-8") as f:
            profile = yaml.safe_load(f) or {}
        missing = _REQUIRED_FIELDS - set(profile.keys())
        if missing:
            continue
        self._profiles[slug] = profile
        self._keyword_index[slug] = [str(profile.get("career_type", slug)).strip().lower()]
        self._type_embeddings[slug] = mock_emb.encode(profile["career_type"])


@pytest.fixture
def app_with_guidance_router():
    """FastAPI app with a temp KB and deterministic guidance embeddings."""
    import services.session_store as ss_module
    from services.session_store import SessionStore

    original_sessions_dir = ss_module._SESSIONS_DIR
    original_profiles_dir = os.environ.get("CAREER_PROFILES_DIR")
    original_tracks_version = os.environ.get("TRACKS_VERSION_PATH")
    original_guidance_path = os.environ.get("EMERGING_TRACK_SIGNALS_PATH")
    SessionStore._instance = None

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        sessions_dir = tmp_path / "sessions"
        profiles_dir = tmp_path / "profiles"
        sessions_dir.mkdir()
        profiles_dir.mkdir()
        signals_path = tmp_path / "signals.jsonl"
        tracks_version_path = tmp_path / ".tracks-version"

        write_profile(profiles_dir, "quant_finance", {"career_type": "Quant Finance"})
        write_profile(profiles_dir, "software_engineering", {"career_type": "Software Engineering"})

        ss_module._SESSIONS_DIR = sessions_dir
        os.environ["CAREER_PROFILES_DIR"] = str(profiles_dir)
        os.environ["TRACKS_VERSION_PATH"] = str(tracks_version_path)
        os.environ["EMERGING_TRACK_SIGNALS_PATH"] = str(signals_path)

        quant_vec = np.zeros(384, dtype=np.float32)
        quant_vec[0] = 1.0
        tech_vec = np.zeros(384, dtype=np.float32)
        tech_vec[1] = 1.0
        query_vec = np.zeros(384, dtype=np.float32)
        query_vec[0] = 0.62
        query_vec[1] = 0.38

        mock_embedder = MagicMock()

        def _encode(text):
            text = str(text).lower()
            if "quant" in text:
                return query_vec
            if "software" in text:
                return tech_vec
            return quant_vec

        mock_embedder.encode.side_effect = _encode

        fake_dependencies = types.ModuleType("dependencies")
        fake_dependencies.get_embedder = lambda: mock_embedder

        with patch(
            "services.career_profiles.CareerProfileStore._load_profiles",
            lambda self: _load_profiles_with_mock_embedder(self, profiles_dir, mock_embedder),
        ):
            original_dependencies = sys.modules.get("dependencies")
            sys.modules["dependencies"] = fake_dependencies

            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "session_router_guidance_test", "routers/session_router.py"
            )
            session_router_mod = importlib.util.module_from_spec(spec)
            sys.modules["session_router_guidance_test"] = session_router_mod
            spec.loader.exec_module(session_router_mod)

            app = FastAPI()
            app.include_router(session_router_mod.router)
            yield app

        if original_dependencies is None:
            sys.modules.pop("dependencies", None)
        else:
            sys.modules["dependencies"] = original_dependencies

    SessionStore._instance = None
    ss_module._SESSIONS_DIR = original_sessions_dir
    sys.modules.pop("session_router_guidance_test", None)
    if original_profiles_dir is None:
        os.environ.pop("CAREER_PROFILES_DIR", None)
    else:
        os.environ["CAREER_PROFILES_DIR"] = original_profiles_dir
    if original_tracks_version is None:
        os.environ.pop("TRACKS_VERSION_PATH", None)
    else:
        os.environ["TRACKS_VERSION_PATH"] = original_tracks_version
    if original_guidance_path is None:
        os.environ.pop("EMERGING_TRACK_SIGNALS_PATH", None)
    else:
        os.environ["EMERGING_TRACK_SIGNALS_PATH"] = original_guidance_path


@patch("services.llm.get_client")
def test_analyze_persists_track_guidance(mock_client, app_with_guidance_router):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps({"cards": [], "already_covered": []}))]
    mock_client.return_value.messages.create.return_value = mock_msg

    client = TestClient(app_with_guidance_router)
    create_resp = client.post("/api/sessions", json={"raw_input": "DRW quantitative research"})
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    analyze_resp = client.post(f"/api/sessions/{session_id}/analyze")
    assert analyze_resp.status_code == 200
    analyze_body = analyze_resp.json()
    assert analyze_body["track_guidance"]["status"] == "clustered_uncertainty"
    assert [item["slug"] for item in analyze_body["track_guidance"]["nearest_tracks"]] == [
        "quant_finance",
        "software_engineering",
    ]

    get_resp = client.get(f"/api/sessions/{session_id}")
    assert get_resp.status_code == 200
    session_body = get_resp.json()
    assert session_body["track_guidance"]["status"] == "clustered_uncertainty"
    assert session_body["track_guidance"]["recurrence_count"] == 1
