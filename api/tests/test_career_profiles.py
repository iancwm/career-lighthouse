# api/tests/test_career_profiles.py
"""Tests for the CareerProfileStore and related helpers."""
import logging
import os
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers — write minimal valid YAML files into a temp profiles dir
# ---------------------------------------------------------------------------

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
    profile = {**MINIMAL_PROFILE, **(overrides or {})}
    with open(directory / f"{slug}.yaml", "w") as f:
        yaml.dump(profile, f)


# ---------------------------------------------------------------------------
# Fixtures — reset singleton between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset CareerProfileStore singleton state before each test."""
    from services.career_profiles import CareerProfileStore
    CareerProfileStore._instance = None
    yield
    CareerProfileStore._instance = None


@pytest.fixture
def profiles_dir(tmp_path):
    return tmp_path / "career_profiles"


# ---------------------------------------------------------------------------
# resolve_career_type_from_intake
# ---------------------------------------------------------------------------

class TestResolveCareerTypeFromIntake:
    def test_finance_maps_to_investment_banking(self):
        from services.career_profiles import resolve_career_type_from_intake
        assert resolve_career_type_from_intake("finance") == "investment_banking"

    def test_consulting_maps_correctly(self):
        from services.career_profiles import resolve_career_type_from_intake
        assert resolve_career_type_from_intake("consulting") == "consulting"

    def test_tech_maps_to_tech_product(self):
        from services.career_profiles import resolve_career_type_from_intake
        assert resolve_career_type_from_intake("tech") == "tech_product"

    def test_public_sector_maps_correctly(self):
        from services.career_profiles import resolve_career_type_from_intake
        assert resolve_career_type_from_intake("public_sector") == "public_sector"

    def test_not_sure_maps_to_general_singapore(self):
        from services.career_profiles import resolve_career_type_from_intake
        assert resolve_career_type_from_intake("not_sure") == "general_singapore"

    def test_none_returns_default(self):
        from services.career_profiles import resolve_career_type_from_intake
        assert resolve_career_type_from_intake(None) == "general_singapore"

    def test_empty_string_returns_default(self):
        from services.career_profiles import resolve_career_type_from_intake
        assert resolve_career_type_from_intake("") == "general_singapore"

    def test_unknown_value_returns_default(self):
        from services.career_profiles import resolve_career_type_from_intake
        assert resolve_career_type_from_intake("underwater basket weaving") == "general_singapore"

    def test_case_insensitive(self):
        from services.career_profiles import resolve_career_type_from_intake
        assert resolve_career_type_from_intake("Finance") == "investment_banking"
        assert resolve_career_type_from_intake("CONSULTING") == "consulting"


# ---------------------------------------------------------------------------
# profile_to_context_block
# ---------------------------------------------------------------------------

class TestProfileToContextBlock:
    def test_includes_career_type_header(self):
        from services.career_profiles import profile_to_context_block
        block = profile_to_context_block(MINIMAL_PROFILE)
        assert "Career Track: Test Track" in block

    def test_includes_ep_sponsorship(self):
        from services.career_profiles import profile_to_context_block
        block = profile_to_context_block(MINIMAL_PROFILE)
        assert "EP Sponsorship:" in block
        assert "High" in block

    def test_includes_top_employers(self):
        from services.career_profiles import profile_to_context_block
        block = profile_to_context_block(MINIMAL_PROFILE)
        assert "Acme Corp" in block

    def test_includes_section_delimiters(self):
        from services.career_profiles import profile_to_context_block
        block = profile_to_context_block(MINIMAL_PROFILE)
        assert block.startswith("=== CAREER CONTEXT")
        assert "=== END CAREER CONTEXT ===" in block

    def test_missing_optional_fields_render_as_na(self):
        from services.career_profiles import profile_to_context_block
        # notes is optional
        profile = {**MINIMAL_PROFILE}
        del profile["notes"]
        block = profile_to_context_block(profile)
        assert "Notes:\nN/A" in block


# ---------------------------------------------------------------------------
# CareerProfileStore — loading
# ---------------------------------------------------------------------------

class TestCareerProfileStoreLoading:
    def test_loads_valid_profile(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        write_profile(profiles_dir, "test_track")

        monkeypatch.setenv("CAREER_PROFILES_DIR", str(profiles_dir))
        mock_emb = MagicMock()
        mock_emb.encode.return_value = np.ones(384, dtype=np.float32)
        monkeypatch.setattr("services.career_profiles.CareerProfileStore._load_profiles",
                            lambda self: _load_with_mock_embedder(self, profiles_dir, mock_emb))

        from services.career_profiles import CareerProfileStore
        store = CareerProfileStore()
        profile = store.get_profile("test_track")
        assert profile is not None
        assert profile["career_type"] == "Test Track"

    def test_load_profiles_real_code_path(self, tmp_path, monkeypatch):
        """Integration: real _load_profiles() runs — only Embedder is mocked.

        Exercises the actual code inside _load_profiles (not the monkeypatched stub used
        by other tests). Any bug in the real code path (e.g., undefined variable in a
        logger.info call) is caught here rather than at production startup.
        """
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        write_profile(profiles_dir, "test_track")

        monkeypatch.setenv("CAREER_PROFILES_DIR", str(profiles_dir))

        mock_emb = MagicMock()
        mock_emb.encode.return_value = np.ones(384, dtype=np.float32)
        import services.embedder
        monkeypatch.setattr(services.embedder, "Embedder", lambda: mock_emb)

        from services.career_profiles import CareerProfileStore
        store = CareerProfileStore()
        store._ensure_loaded()

        assert store.get_profile("test_track") is not None
        assert len(store.list_profiles()) == 1

    def test_missing_directory_does_not_crash(self, tmp_path, monkeypatch):
        nonexistent = tmp_path / "does_not_exist"
        monkeypatch.setenv("CAREER_PROFILES_DIR", str(nonexistent))

        from services.career_profiles import CareerProfileStore
        store = CareerProfileStore()
        store._ensure_loaded()  # must not raise
        assert store.list_profiles() == []

    def test_malformed_yaml_is_skipped(self, tmp_path, monkeypatch, caplog):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        (profiles_dir / "bad.yaml").write_text(":\nnot valid yaml: {unclosed")
        write_profile(profiles_dir, "good_track")

        monkeypatch.setenv("CAREER_PROFILES_DIR", str(profiles_dir))
        mock_emb = MagicMock()
        mock_emb.encode.return_value = np.ones(384, dtype=np.float32)
        monkeypatch.setattr("services.career_profiles.CareerProfileStore._load_profiles",
                            lambda self: _load_with_mock_embedder(self, profiles_dir, mock_emb))

        from services.career_profiles import CareerProfileStore
        with caplog.at_level(logging.WARNING, logger="services.career_profiles"):
            store = CareerProfileStore()
        assert store.get_profile("good_track") is not None
        assert store.get_profile("bad") is None

    def test_profile_missing_required_fields_is_skipped(self, tmp_path, monkeypatch, caplog):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        # Missing most required fields
        (profiles_dir / "incomplete.yaml").write_text("career_type: Incomplete\n")

        monkeypatch.setenv("CAREER_PROFILES_DIR", str(profiles_dir))
        mock_emb = MagicMock()
        mock_emb.encode.return_value = np.ones(384, dtype=np.float32)
        monkeypatch.setattr("services.career_profiles.CareerProfileStore._load_profiles",
                            lambda self: _load_with_mock_embedder(self, profiles_dir, mock_emb))

        from services.career_profiles import CareerProfileStore
        with caplog.at_level(logging.WARNING, logger="services.career_profiles"):
            store = CareerProfileStore()
        assert store.get_profile("incomplete") is None
        assert any("missing required fields" in r.message for r in caplog.records)

    def test_get_profile_unknown_slug_returns_none_with_warning(self, tmp_path, monkeypatch, caplog):
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        monkeypatch.setenv("CAREER_PROFILES_DIR", str(profiles_dir))

        from services.career_profiles import CareerProfileStore
        store = CareerProfileStore()
        store._ensure_loaded()

        with caplog.at_level(logging.WARNING, logger="services.career_profiles"):
            result = store.get_profile("stale_slug_from_client")
        assert result is None
        assert any("unknown career type slug" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# CareerProfileStore — cosine matching
# ---------------------------------------------------------------------------

class TestCareerProfileStoreMatching:
    def test_match_returns_none_when_no_profiles_loaded(self, tmp_path, monkeypatch):
        profiles_dir = tmp_path / "empty"
        profiles_dir.mkdir()
        monkeypatch.setenv("CAREER_PROFILES_DIR", str(profiles_dir))

        from services.career_profiles import CareerProfileStore
        store = CareerProfileStore()
        store._ensure_loaded()
        result = store.match_career_type(np.ones(384, dtype=np.float32))
        assert result is None

    def test_match_returns_slug_when_score_above_threshold(self, tmp_path, monkeypatch):
        """If the query vector is identical to a career type vector, score=1.0 → match
        (when threshold is set low enough for testing)."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        write_profile(profiles_dir, "finance_track", {"career_type": "Finance"})

        finance_vec = np.ones(384, dtype=np.float32)
        finance_vec /= np.linalg.norm(finance_vec)

        monkeypatch.setenv("CAREER_PROFILES_DIR", str(profiles_dir))
        mock_emb = MagicMock()
        mock_emb.encode.return_value = finance_vec
        monkeypatch.setattr("services.career_profiles.CareerProfileStore._load_profiles",
                            lambda self: _load_with_mock_embedder(self, profiles_dir, mock_emb))
        # Temporarily lower threshold so score=1.0 triggers a match
        monkeypatch.setattr("services.career_profiles._CAREER_TYPE_MATCH_THRESHOLD", 0.70)

        from services.career_profiles import CareerProfileStore
        store = CareerProfileStore()
        # Query with the same vector → cosine = 1.0 > threshold
        result = store.match_career_type(finance_vec)
        assert result == "finance_track"

    def test_match_returns_none_when_score_below_threshold(self, tmp_path, monkeypatch):
        """Orthogonal query vector → cosine ≈ 0 < 0.70 → no match."""
        profiles_dir = tmp_path / "profiles"
        profiles_dir.mkdir()
        write_profile(profiles_dir, "finance_track", {"career_type": "Finance"})

        type_vec = np.zeros(384, dtype=np.float32)
        type_vec[0] = 1.0  # unit vector in dimension 0

        monkeypatch.setenv("CAREER_PROFILES_DIR", str(profiles_dir))
        mock_emb = MagicMock()
        mock_emb.encode.return_value = type_vec
        monkeypatch.setattr("services.career_profiles.CareerProfileStore._load_profiles",
                            lambda self: _load_with_mock_embedder(self, profiles_dir, mock_emb))

        from services.career_profiles import CareerProfileStore
        store = CareerProfileStore()

        # Orthogonal query: unit vector in dimension 1 → dot product = 0
        query_vec = np.zeros(384, dtype=np.float32)
        query_vec[1] = 1.0
        result = store.match_career_type(query_vec)
        assert result is None


# ---------------------------------------------------------------------------
# Internal helper (test-only) — bypasses Embedder import in _load_profiles
# ---------------------------------------------------------------------------

def _load_with_mock_embedder(store, profiles_dir, mock_emb):
    """Replaces CareerProfileStore._load_profiles for tests.
    Loads profiles from profiles_dir using a mock embedder instead of the real one.
    """
    import yaml as _yaml
    from services.career_profiles import _REQUIRED_FIELDS
    import logging as _logging
    _log = _logging.getLogger("services.career_profiles")

    yaml_files = sorted(profiles_dir.glob("*.yaml"))
    store._profiles = {}
    store._type_embeddings = {}

    for yaml_path in yaml_files:
        slug = yaml_path.stem
        try:
            with open(yaml_path) as f:
                profile = _yaml.safe_load(f)
            if not isinstance(profile, dict):
                _log.warning("Career profile %s: not a valid YAML mapping — skipping", yaml_path.name)
                continue
            missing = _REQUIRED_FIELDS - set(profile.keys())
            if missing:
                _log.warning("Career profile %s: missing required fields %s — skipping",
                             yaml_path.name, sorted(missing))
                continue
            store._profiles[slug] = profile
            # Respect match_cosine: false — mirrors production _load_profiles behaviour
            if profile.get("match_cosine", True):
                store._type_embeddings[slug] = mock_emb.encode(profile["career_type"])
        except _yaml.YAMLError as exc:
            _log.warning("Career profile %s: YAML parse error — skipping: %s", yaml_path.name, exc)
        except Exception as exc:
            _log.warning("Career profile %s: failed to load — skipping: %s", yaml_path.name, exc)
    store._loaded = True
