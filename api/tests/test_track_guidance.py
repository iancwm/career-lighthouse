"""Tests for track guidance and recurrence logging."""
from unittest.mock import MagicMock

import numpy as np
import pytest


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


def write_profile(directory, slug, overrides=None):
    import yaml

    profile = {**MINIMAL_PROFILE, **(overrides or {})}
    with open(directory / f"{slug}.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(profile, f, allow_unicode=True, sort_keys=False)


def _load_with_mock_embedder(store, profiles_dir, mock_emb):
    import yaml as _yaml
    from services.career_profiles import _REQUIRED_FIELDS

    yaml_files = sorted(profiles_dir.glob("*.yaml"))
    store._profiles = {}
    store._type_embeddings = {}
    store._keyword_index = {}

    for yaml_path in yaml_files:
        slug = yaml_path.stem
        with open(yaml_path, encoding="utf-8") as f:
            profile = _yaml.safe_load(f) or {}
        missing = _REQUIRED_FIELDS - set(profile.keys())
        if missing:
            continue
        store._profiles[slug] = profile
        store._keyword_index[slug] = [str(profile.get("career_type", slug)).strip().lower()]
        store._type_embeddings[slug] = mock_emb.encode(profile["career_type"])


@pytest.fixture(autouse=True)
def reset_singletons():
    from services.career_profiles import CareerProfileStore
    from services.track_guidance import EmergingTrackSignalStore

    CareerProfileStore._instance = None
    EmergingTrackSignalStore._instance = None
    yield
    CareerProfileStore._instance = None
    EmergingTrackSignalStore._instance = None


def test_build_track_guidance_records_recurrence(tmp_path, monkeypatch):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    write_profile(profiles_dir, "quant_finance", {"career_type": "Quant Finance"})
    write_profile(profiles_dir, "software_engineering", {"career_type": "Software Engineering"})

    monkeypatch.setenv("CAREER_PROFILES_DIR", str(profiles_dir))
    monkeypatch.setenv("EMERGING_TRACK_SIGNALS_PATH", str(tmp_path / "signals.jsonl"))

    quant_vec = np.zeros(384, dtype=np.float32)
    quant_vec[0] = 1.0
    tech_vec = np.zeros(384, dtype=np.float32)
    tech_vec[1] = 1.0

    mock_emb = MagicMock()

    def _encode(text):
        text = str(text).lower()
        if "quant" in text:
            return quant_vec
        if "software" in text:
            return tech_vec
        return quant_vec

    mock_emb.encode.side_effect = _encode

    from services.career_profiles import CareerProfileStore
    from services.track_guidance import build_track_guidance

    monkeypatch.setattr(
        "services.career_profiles.CareerProfileStore._load_profiles",
        lambda self: _load_with_mock_embedder(self, profiles_dir, mock_emb),
    )
    store = CareerProfileStore()
    query_vec = np.zeros(384, dtype=np.float32)
    query_vec[0] = 0.62
    query_vec[1] = 0.38

    first = build_track_guidance("DRW quantitative research", query_vec, store, session_id="s-1")
    second = build_track_guidance("DRW quantitative research", query_vec, store, session_id="s-2")

    assert first is not None
    assert first.status == "clustered_uncertainty"
    assert first.recurrence_count == 1
    assert [track.slug for track in first.nearest_tracks] == ["quant_finance", "software_engineering"]
    assert second is not None
    assert second.status == "emerging_taxonomy_signal"
    assert second.recurrence_count == 2
    assert second.cluster_key == first.cluster_key
