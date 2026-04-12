# api/tests/test_kb_router.py
import json
import os
import tempfile
import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient
from unittest.mock import patch


def make_client(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    return TestClient(app), store


def seed_chunk(store, filename, chunk_text, chunk_index=0):
    vec = np.ones(384, dtype=np.float32)
    store.upsert([{
        "id": f"{filename}-{chunk_index}",
        "vector": vec,
        "payload": {
            "source_filename": filename,
            "chunk_index": chunk_index,
            "upload_timestamp": "2026-01-01T00:00:00+00:00",
            "text": chunk_text,
        },
    }])


def configure_track_paths(monkeypatch, tmp_path):
    profiles_dir = tmp_path / "career_profiles"
    drafts_dir = tmp_path / "draft_tracks"
    logs_dir = tmp_path / "logs"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    drafts_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("CAREER_PROFILES_DIR", str(profiles_dir))
    monkeypatch.setenv("DRAFT_TRACKS_DIR", str(drafts_dir))
    monkeypatch.setenv("CAREER_TRACKS_REGISTRY_PATH", str(tmp_path / "career_tracks.yaml"))
    monkeypatch.setenv("CAREER_PROFILE_HISTORY_DIR", str(tmp_path / "career_profiles_history"))
    monkeypatch.setenv("TRACK_PUBLISH_LOG_PATH", str(logs_dir / "track_publish_log.jsonl"))
    monkeypatch.setenv("TRACK_PUBLISH_JOURNAL_PATH", str(logs_dir / "track_publish_journal.jsonl"))
    monkeypatch.setenv("TRACKS_VERSION_PATH", str(tmp_path / ".tracks-version"))

    from services.career_profiles import get_career_profile_store
    from services.track_drafts import get_track_draft_store
    get_career_profile_store().invalidate()
    get_track_draft_store().invalidate()

    return {
        "profiles_dir": profiles_dir,
        "drafts_dir": drafts_dir,
        "logs_dir": logs_dir,
        "registry_path": tmp_path / "career_tracks.yaml",
        "history_dir": tmp_path / "career_profiles_history",
        "tracks_version_path": tmp_path / ".tracks-version",
    }


def sample_draft_payload(slug="data_science", note_text="Field notes"):
    return {
        "slug": slug,
        "track_name": "Data Science",
        "match_description": "data science machine learning analytics careers",
        "match_keywords": ["data science", "machine learning"],
        "ep_sponsorship": "High at larger tech firms.",
        "compass_score_typical": "45-60",
        "top_employers_smu": ["Grab", "Shopee", "DBS"],
        "recruiting_timeline": "Main internship cycle opens in September.",
        "international_realistic": True,
        "entry_paths": ["Internship to return offer"],
        "salary_range_2024": "S$70K-S$110K",
        "typical_background": "Statistics, CS, IS, and strong portfolio work.",
        "counselor_contact": "Henry",
        "notes": note_text,
        "source_refs": [{"type": "note", "label": "counsellor_note"}],
        "structured": {
            "sponsorship_tier": "High",
            "compass_points_typical": "45-60",
            "salary_min_sgd": 70000,
            "salary_max_sgd": 110000,
            "ep_realistic": True,
        },
    }


# ---------------------------------------------------------------------------
# POST /api/kb/test-query
# ---------------------------------------------------------------------------

class TestTestQuery:
    def test_returns_chunks_with_scores(self, in_memory_qdrant, mock_embedder):
        client, store = make_client(in_memory_qdrant, mock_embedder)
        seed_chunk(store, "guide.txt", "SMU career guide content")

        r = client.post("/api/kb/test-query", json={"query": "career advice"})

        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert data[0]["source_filename"] == "guide.txt"
        assert "excerpt" in data[0]
        assert isinstance(data[0]["score"], float)
        assert len(data[0]["excerpt"]) <= 300

    def test_empty_kb_returns_empty_list(self, in_memory_qdrant, mock_embedder):
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        r = client.post("/api/kb/test-query", json={"query": "anything"})

        assert r.status_code == 200
        assert r.json() == []

    def test_503_when_qdrant_unavailable(self, mock_embedder):
        from main import app
        import dependencies

        broken_store = object()  # not a VectorStore — will raise on .search()
        app.dependency_overrides[dependencies.get_vector_store] = lambda: broken_store
        app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

        client = TestClient(app, raise_server_exceptions=False)
        r = client.post("/api/kb/test-query", json={"query": "anything"})

        assert r.status_code == 503
        assert "unavailable" in r.json()["detail"].lower()

        app.dependency_overrides.pop(dependencies.get_vector_store)
        app.dependency_overrides.pop(dependencies.get_embedder)


# ---------------------------------------------------------------------------
# GET /api/kb/health — doc coverage
# ---------------------------------------------------------------------------

class TestKBHealthDocCoverage:
    def test_empty_kb_returns_zeroes_and_nulls(self, in_memory_qdrant, mock_embedder, tmp_path):
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        with patch("routers.kb_router.settings") as mock_settings:
            mock_settings.query_log_path = str(tmp_path / "empty.jsonl")
            r = client.get("/api/kb/health")

        assert r.status_code == 200
        data = r.json()
        assert data["total_docs"] == 0
        assert data["total_chunks"] == 0
        assert data["avg_match_score"] is None
        assert data["retrieval_diversity_score"] is None
        assert data["low_confidence_queries"] == []
        assert data["doc_coverage"] == []

    def test_doc_with_20_plus_chunks_is_good(self, in_memory_qdrant, mock_embedder):
        client, store = make_client(in_memory_qdrant, mock_embedder)
        for i in range(20):
            seed_chunk(store, "big-doc.txt", f"chunk {i}", chunk_index=i)

        r = client.get("/api/kb/health")

        assert r.status_code == 200
        coverage = {d["filename"]: d for d in r.json()["doc_coverage"]}
        assert coverage["big-doc.txt"]["coverage_status"] == "good"
        assert coverage["big-doc.txt"]["chunk_count"] == 20

    def test_doc_with_fewer_than_20_chunks_is_thin(self, in_memory_qdrant, mock_embedder):
        client, store = make_client(in_memory_qdrant, mock_embedder)
        for i in range(5):
            seed_chunk(store, "small-doc.txt", f"chunk {i}", chunk_index=i)

        r = client.get("/api/kb/health")

        coverage = {d["filename"]: d for d in r.json()["doc_coverage"]}
        assert coverage["small-doc.txt"]["coverage_status"] == "thin"

    def test_503_when_qdrant_unavailable(self, mock_embedder):
        from main import app
        import dependencies

        broken_store = object()
        app.dependency_overrides[dependencies.get_vector_store] = lambda: broken_store
        app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/kb/health")

        assert r.status_code == 503

        app.dependency_overrides.pop(dependencies.get_vector_store)
        app.dependency_overrides.pop(dependencies.get_embedder)


# ---------------------------------------------------------------------------
# GET /api/kb/health — query log metrics
# ---------------------------------------------------------------------------

class TestKBHealthQueryLog:
    def _write_log(self, path, entries):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_absent_log_returns_null_metrics(self, in_memory_qdrant, mock_embedder, tmp_path):
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        log_path = str(tmp_path / "no_log.jsonl")

        with patch("routers.kb_router.settings") as mock_settings:
            mock_settings.query_log_path = log_path
            r = client.get("/api/kb/health")

        data = r.json()
        assert data["avg_match_score"] is None
        assert data["low_confidence_queries"] == []

    def test_avg_match_score_computed_from_log(self, in_memory_qdrant, mock_embedder, tmp_path):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        log_path = str(tmp_path / "query_log.jsonl")
        self._write_log(log_path, [
            {"ts": now, "query_text": "q1", "scores": [0.8, 0.5], "doc_matched": "a.txt", "top_docs": ["a.txt", "b.txt"]},
            {"ts": now, "query_text": "q2", "scores": [0.6, 0.4], "doc_matched": "b.txt", "top_docs": ["b.txt", "a.txt"]},
        ])

        with patch("routers.kb_router.settings") as mock_settings:
            mock_settings.query_log_path = log_path
            r = client.get("/api/kb/health")

        data = r.json()
        assert data["avg_match_score"] == pytest.approx(0.7, abs=0.001)

    def test_low_confidence_query_appears_in_list(self, in_memory_qdrant, mock_embedder, tmp_path):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        log_path = str(tmp_path / "query_log.jsonl")
        self._write_log(log_path, [
            {"ts": now, "query_text": "weak question", "scores": [0.20], "doc_matched": None, "top_docs": []},
            {"ts": now, "query_text": "strong question", "scores": [0.90], "doc_matched": "a.txt", "top_docs": ["a.txt"]},
        ])

        with patch("routers.kb_router.settings") as mock_settings:
            mock_settings.query_log_path = log_path
            r = client.get("/api/kb/health")

        data = r.json()
        lc = data["low_confidence_queries"]
        assert len(lc) == 1
        assert lc[0]["query_text"] == "weak question"
        assert lc[0]["max_score"] == pytest.approx(0.20, abs=0.001)

    def test_malformed_log_line_skipped(self, in_memory_qdrant, mock_embedder, tmp_path):
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        log_path = str(tmp_path / "query_log.jsonl")
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with open(log_path, "w") as f:
            f.write("this is not json\n")
            f.write(json.dumps({"ts": now, "query_text": "q", "scores": [0.7], "doc_matched": "a.txt", "top_docs": ["a.txt"]}) + "\n")

        with patch("routers.kb_router.settings") as mock_settings:
            mock_settings.query_log_path = log_path
            r = client.get("/api/kb/health")

        # Should still succeed, the good line is processed
        assert r.status_code == 200
        data = r.json()
        assert data["avg_match_score"] is not None

    def test_entries_outside_7day_window_excluded(self, in_memory_qdrant, mock_embedder, tmp_path):
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        log_path = str(tmp_path / "query_log.jsonl")
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self._write_log(log_path, [
            # Old entry — outside 7 day window (year 2020)
            {"ts": "2020-01-01T00:00:00+00:00", "query_text": "old q", "scores": [0.1], "doc_matched": None, "top_docs": []},
            # Recent entry
            {"ts": now, "query_text": "recent q", "scores": [0.9], "doc_matched": "a.txt", "top_docs": ["a.txt"]},
        ])

        with patch("routers.kb_router.settings") as mock_settings:
            mock_settings.query_log_path = log_path
            r = client.get("/api/kb/health")

        data = r.json()
        # avg_match_score should only reflect the recent entry (0.9), not 0.1
        assert data["avg_match_score"] == pytest.approx(0.9, abs=0.001)


# ---------------------------------------------------------------------------
# GET /api/kb/career-profiles
# ---------------------------------------------------------------------------

class TestCareerProfilesEndpoint:
    def test_returns_empty_list_when_no_profiles_loaded(self, in_memory_qdrant, mock_embedder):
        from main import app
        from services.career_profiles import get_career_profile_store
        from unittest.mock import MagicMock

        mock_ps = MagicMock()
        mock_ps.list_profiles.return_value = []
        app.dependency_overrides[get_career_profile_store] = lambda: mock_ps

        client, _ = make_client(in_memory_qdrant, mock_embedder)
        r = client.get("/api/kb/career-profiles")

        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# Track Builder endpoints
# ---------------------------------------------------------------------------

class TestTrackBuilderEndpoints:
    def test_list_tracks_bootstraps_registry_from_existing_profiles(self, in_memory_qdrant, mock_embedder, monkeypatch, tmp_path):
        paths = configure_track_paths(monkeypatch, tmp_path)
        with open(paths["profiles_dir"] / "consulting.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump({
                "career_type": "Consulting",
                "ep_sponsorship": "High",
                "top_employers_smu": ["McKinsey"],
                "recruiting_timeline": "Sep-Nov",
                "international_realistic": True,
                "entry_paths": ["Internship"],
                "salary_range_2024": "S$90K",
                "typical_background": "Any",
            }, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        client, _ = make_client(in_memory_qdrant, mock_embedder)
        r = client.get("/api/kb/tracks")

        assert r.status_code == 200
        assert r.json() == [{
            "slug": "consulting",
            "label": "Consulting",
            "status": "active",
            "last_published": None,
        }]
        assert paths["registry_path"].exists()

    def test_get_track_reference_returns_published_detail(self, in_memory_qdrant, mock_embedder, monkeypatch, tmp_path):
        configure_track_paths(monkeypatch, tmp_path)
        with open(tmp_path / "career_profiles" / "data_science.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump({
                "career_type": "Data Science",
                "match_description": "Students interested in analytics, Python, and experimentation.",
                "match_keywords": ["data science", "analytics"],
                "ep_sponsorship": "Common in larger firms.",
                "compass_score_typical": "45-60",
                "top_employers_smu": ["Grab", "DBS"],
                "recruiting_timeline": "Internships open in September.",
                "international_realistic": True,
                "entry_paths": ["Internship to return offer"],
                "salary_range_2024": "S$70K-S$110K",
                "typical_background": "Stats, CS, IS.",
                "counselor_contact": "Henry",
                "notes": "Published reference notes.",
            }, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        client, _ = make_client(in_memory_qdrant, mock_embedder)
        client.get("/api/kb/tracks")

        r = client.get("/api/kb/tracks/data_science")

        assert r.status_code == 200
        data = r.json()
        assert data["slug"] == "data_science"
        assert data["label"] == "Data Science"
        assert data["status"] == "active"
        assert data["last_published"] is None
        assert data["match_description"] == "Students interested in analytics, Python, and experimentation."
        assert data["top_employers_smu"] == ["Grab", "DBS"]
        assert data["entry_paths"] == ["Internship to return offer"]

    def test_create_draft_track_persists_yaml(self, in_memory_qdrant, mock_embedder, monkeypatch, tmp_path):
        paths = configure_track_paths(monkeypatch, tmp_path)
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        r = client.post("/api/kb/draft-tracks", json=sample_draft_payload())

        assert r.status_code == 201
        data = r.json()
        assert data["slug"] == "data_science"
        assert data["status"] == "ready_for_publish"
        with open(paths["drafts_dir"] / "data_science.yaml", encoding="utf-8") as f:
            stored = yaml.safe_load(f)
        assert stored["track_name"] == "Data Science"
        assert stored["match_keywords"] == ["data science", "machine learning"]

    def test_publish_draft_writes_profile_registry_and_tracks_version(self, in_memory_qdrant, mock_embedder, monkeypatch, tmp_path):
        paths = configure_track_paths(monkeypatch, tmp_path)
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        client.post("/api/kb/draft-tracks", json=sample_draft_payload())

        r = client.post("/api/kb/draft-tracks/data_science/publish")

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        with open(paths["profiles_dir"] / "data_science.yaml", encoding="utf-8") as f:
            profile = yaml.safe_load(f)
        assert profile["career_type"] == "Data Science"
        assert profile["match_cosine"] is False
        assert profile["match_keywords"] == ["data science", "machine learning"]
        with open(paths["registry_path"], encoding="utf-8") as f:
            registry = yaml.safe_load(f)
        assert registry["tracks"][0]["slug"] == "data_science"
        assert paths["tracks_version_path"].exists()

    def test_rollback_restores_previous_published_profile(self, in_memory_qdrant, mock_embedder, monkeypatch, tmp_path):
        paths = configure_track_paths(monkeypatch, tmp_path)
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        client.post("/api/kb/draft-tracks", json=sample_draft_payload(note_text="First version"))
        first_publish = client.post("/api/kb/draft-tracks/data_science/publish")
        assert first_publish.status_code == 200

        updated_payload = sample_draft_payload(note_text="Second version")
        updated_payload["salary_range_2024"] = "S$80K-S$120K"
        updated_payload["top_employers_smu"] = ["Grab", "TikTok"]
        client.put("/api/kb/draft-tracks/data_science", json=updated_payload)
        second_publish = client.post("/api/kb/draft-tracks/data_science/publish")
        assert second_publish.status_code == 200

        with open(paths["profiles_dir"] / "data_science.yaml", encoding="utf-8") as f:
            assert yaml.safe_load(f)["notes"] == "Second version"

        rollback = client.post("/api/kb/tracks/data_science/rollback")
        assert rollback.status_code == 200
        with open(paths["profiles_dir"] / "data_science.yaml", encoding="utf-8") as f:
            restored = yaml.safe_load(f)
        assert restored["notes"] == "First version"

    def test_generate_draft_track_from_note(self, in_memory_qdrant, mock_embedder, monkeypatch, tmp_path):
        configure_track_paths(monkeypatch, tmp_path)
        client, store = make_client(in_memory_qdrant, mock_embedder)
        seed_chunk(store, "ds-guide.txt", "Data scientists at Grab need Python and SQL skills.")

        generated = sample_draft_payload()
        generated["status"] = "draft"
        generated["source_refs"] = [{"type": "note", "label": "counsellor_note"}]

        with patch("services.llm.generate_track_draft", return_value=generated):
            r = client.post("/api/kb/draft-tracks/generate", data={
                "slug": "data_science",
                "track_name": "Data Science",
                "text": "Create a data science track from these counsellor notes.",
                "source_type": "note",
            })

        assert r.status_code == 201
        data = r.json()
        assert data["slug"] == "data_science"
        assert data["track_name"] == "Data Science"
        assert data["source_refs"][0]["label"] == "counsellor_note"

    def test_generate_draft_track_rejects_duplicate_slug(self, in_memory_qdrant, mock_embedder, monkeypatch, tmp_path):
        configure_track_paths(monkeypatch, tmp_path)
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        client.post("/api/kb/draft-tracks", json=sample_draft_payload())

        r = client.post("/api/kb/draft-tracks/generate", data={
            "slug": "data_science",
            "track_name": "Data Science",
            "text": "Try to create it again",
            "source_type": "note",
        })

        assert r.status_code == 409

    def test_refresh_existing_draft_from_note_updates_fields_and_merges_sources(self, in_memory_qdrant, mock_embedder, monkeypatch, tmp_path):
        configure_track_paths(monkeypatch, tmp_path)
        client, store = make_client(in_memory_qdrant, mock_embedder)
        client.post("/api/kb/draft-tracks", json=sample_draft_payload(note_text="First draft notes"))
        seed_chunk(store, "alumni-call.txt", "Data scientists at DBS often come from analytics and experimentation roles.")

        refreshed = sample_draft_payload(note_text="Updated from alumni call")
        refreshed["track_name"] = "Data Science"
        refreshed["top_employers_smu"] = ["DBS", "Grab"]
        refreshed["source_refs"] = [{"type": "file", "label": "alumni-call.txt"}]

        with patch("services.llm.generate_track_draft", return_value=refreshed):
            r = client.post(
                "/api/kb/draft-tracks/data_science/generate-update",
                data={
                    "text": "We learned DBS hires analytics candidates with strong SQL and experimentation exposure.",
                    "source_type": "note",
                },
            )

        assert r.status_code == 200
        data = r.json()
        assert data["notes"] == "Updated from alumni call"
        assert data["top_employers_smu"] == ["DBS", "Grab"]
        assert {"type": "file", "label": "alumni-call.txt"} in data["source_refs"]
        assert {"type": "note", "label": "counsellor_note"} in data["source_refs"]

    def test_refresh_existing_draft_requires_existing_slug(self, in_memory_qdrant, mock_embedder, monkeypatch, tmp_path):
        configure_track_paths(monkeypatch, tmp_path)
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        r = client.post(
            "/api/kb/draft-tracks/data_science/generate-update",
            data={
                "text": "Try to update a missing draft",
                "source_type": "note",
            },
        )

        assert r.status_code == 404

    def test_returns_profile_metadata_list(self, in_memory_qdrant, mock_embedder):
        from main import app
        from services.career_profiles import get_career_profile_store
        from unittest.mock import MagicMock

        mock_ps = MagicMock()
        mock_ps.list_profiles.return_value = [
            {
                "slug": "investment_banking",
                "career_type": "Investment Banking",
                "ep_tier": "High",
                "ep_realistic": True,
                "salary_min_sgd": 85000,
                "salary_max_sgd": 95000,
                "compass_points_typical": "45-55",
                "has_counselor_contact": False,
            },
        ]
        app.dependency_overrides[get_career_profile_store] = lambda: mock_ps

        client, _ = make_client(in_memory_qdrant, mock_embedder)
        r = client.get("/api/kb/career-profiles")

        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["slug"] == "investment_banking"
        assert data[0]["career_type"] == "Investment Banking"
        assert data[0]["ep_tier"] == "High"


# ---------------------------------------------------------------------------
# Employer CRUD — helpers
# ---------------------------------------------------------------------------

import textwrap


def make_employer_client(in_memory_qdrant, mock_embedder, employers_dir):
    """Create a TestClient with a real EmployerEntityStore pointed at employers_dir."""
    from main import app
    from services.vector_store import VectorStore
    from services.employer_store import EmployerEntityStore, get_employer_store
    import dependencies

    EmployerEntityStore._instance = None

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder

    # Override EMPLOYERS_DIR via env for the singleton
    os.environ["EMPLOYERS_DIR"] = str(employers_dir)
    emp_store = EmployerEntityStore()
    app.dependency_overrides[get_employer_store] = lambda: emp_store

    return TestClient(app), store, emp_store


def make_employers_dir(tmp_path):
    d = tmp_path / "employers"
    d.mkdir()
    (d / "goldman_sachs.yaml").write_text(textwrap.dedent("""\
        employer_name: Goldman Sachs
        slug: goldman_sachs
        tracks:
          - investment_banking
        ep_requirement: "EP4 (COMPASS 40+)"
        intake_seasons:
          - Jan
          - Jul
        last_updated: "2026-04-05"
    """), encoding="utf-8")
    return d


def make_profiles_dir(tmp_path):
    d = tmp_path / "career_profiles"
    d.mkdir()
    (d / "investment_banking.yaml").write_text(textwrap.dedent("""\
        career_type: Investment Banking
        ep_sponsorship: "High"
        compass_score_typical: "45-55"
        top_employers_smu:
          - Goldman Sachs
        recruiting_timeline: "Oct-Jan"
        international_realistic: true
        entry_paths:
          - Internship
        salary_range_2024: "S$85K-95K"
        typical_background: "Finance"
        counselor_contact: ""
        notes: "Original note"
        structured:
          sponsorship_tier: High
    """), encoding="utf-8")
    return d


# ---------------------------------------------------------------------------
# GET /api/kb/employers
# ---------------------------------------------------------------------------

class TestListEmployersEndpoint:
    def test_returns_employer_list(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)
        r = client.get("/api/kb/employers")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["slug"] == "goldman_sachs"
        assert data[0]["employer_name"] == "Goldman Sachs"

    def test_normalizes_scalar_tracks_in_employer_list(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        (d / "drw.yaml").write_text(textwrap.dedent("""\
            employer_name: DRW
            slug: drw
            tracks: quant_finance
            ep_requirement: EP3
            intake_seasons: Q4 2026
        """), encoding="utf-8")
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)
        r = client.get("/api/kb/employers")
        assert r.status_code == 200
        data = {item["slug"]: item for item in r.json()}
        assert data["drw"]["tracks"] == ["quant_finance"]
        assert data["drw"]["intake_seasons"] == ["Q4 2026"]

    def test_empty_dir_returns_empty_list(self, in_memory_qdrant, mock_embedder, tmp_path):
        empty = tmp_path / "emp"
        empty.mkdir()
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, empty)
        r = client.get("/api/kb/employers")
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# GET /api/kb/employers/{slug}
# ---------------------------------------------------------------------------

class TestGetEmployerEndpoint:
    def test_returns_employer_by_slug(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)
        r = client.get("/api/kb/employers/goldman_sachs")
        assert r.status_code == 200
        assert r.json()["employer_name"] == "Goldman Sachs"

    def test_404_for_unknown_slug(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)
        r = client.get("/api/kb/employers/nonexistent")
        assert r.status_code == 404

    def test_422_for_path_traversal_slug(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)
        r = client.get("/api/kb/employers/..%2Fevil")
        assert r.status_code in (404, 422)


# ---------------------------------------------------------------------------
# POST /api/kb/employers — create
# ---------------------------------------------------------------------------

class TestCreateEmployerEndpoint:
    def test_creates_new_employer(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, emp_store = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "slug": "meta",
            "employer_name": "Meta",
            "tracks": ["tech_product"],
            "ep_requirement": "EP3",
            "intake_seasons": ["Jul"],
            "singapore_headcount_estimate": None,
            "application_process": None,
            "counsellor_contact": None,
            "notes": None,
            "last_updated": None,
            "completeness": "amber",
        }
        r = client.post("/api/kb/employers", json=payload)
        assert r.status_code == 201
        assert r.json()["slug"] == "meta"
        assert (d / "meta.yaml").exists()

    def test_409_on_duplicate_slug(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "slug": "goldman_sachs",
            "employer_name": "Goldman Sachs Duplicate",
            "tracks": [],
            "ep_requirement": None,
            "intake_seasons": [],
            "singapore_headcount_estimate": None,
            "application_process": None,
            "counsellor_contact": None,
            "notes": None,
            "last_updated": None,
            "completeness": "amber",
        }
        r = client.post("/api/kb/employers", json=payload)
        assert r.status_code == 409

    def test_409_if_disabled_file_exists(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        (d / "disabled_corp.yaml.disabled").touch()
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "slug": "disabled_corp",
            "employer_name": "Disabled Corp",
            "tracks": [],
            "ep_requirement": None,
            "intake_seasons": [],
            "singapore_headcount_estimate": None,
            "application_process": None,
            "counsellor_contact": None,
            "notes": None,
            "last_updated": None,
            "completeness": "amber",
        }
        r = client.post("/api/kb/employers", json=payload)
        assert r.status_code == 409

    def test_422_unsafe_slug(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "slug": "../evil",
            "employer_name": "Evil Corp",
            "tracks": [],
            "ep_requirement": None,
            "intake_seasons": [],
            "singapore_headcount_estimate": None,
            "application_process": None,
            "counsellor_contact": None,
            "notes": None,
            "last_updated": None,
            "completeness": "amber",
        }
        r = client.post("/api/kb/employers", json=payload)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# PUT /api/kb/employers/{slug}
# ---------------------------------------------------------------------------

class TestUpdateEmployerEndpoint:
    def test_updates_ep_requirement(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "slug": "goldman_sachs",
            "employer_name": "Goldman Sachs",
            "tracks": ["investment_banking"],
            "ep_requirement": "EP3 (updated)",
            "intake_seasons": ["Jan"],
            "singapore_headcount_estimate": None,
            "application_process": None,
            "counsellor_contact": None,
            "notes": None,
            "last_updated": "2020-01-01",   # server should override this
            "completeness": "amber",         # server should override this
        }
        r = client.put("/api/kb/employers/goldman_sachs", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["ep_requirement"] == "EP3 (updated)"
        # Server must set last_updated to today, not use the body value
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert data["last_updated"] == today

    def test_server_ignores_completeness_in_body(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "slug": "goldman_sachs",
            "employer_name": "Goldman Sachs",
            "tracks": ["investment_banking"],
            "ep_requirement": "EP4",
            "intake_seasons": ["Jan"],
            "singapore_headcount_estimate": None,
            "application_process": None,
            "counsellor_contact": None,
            "notes": None,
            "last_updated": None,
            "completeness": "green",  # will be computed by server
        }
        r = client.put("/api/kb/employers/goldman_sachs", json=payload)
        assert r.status_code == 200
        # completeness is computed from actual fields, not echoed from body

    def test_404_for_unknown_slug(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "slug": "nonexistent",
            "employer_name": "No One",
            "tracks": [],
            "ep_requirement": None,
            "intake_seasons": [],
            "singapore_headcount_estimate": None,
            "application_process": None,
            "counsellor_contact": None,
            "notes": None,
            "last_updated": None,
            "completeness": "amber",
        }
        r = client.put("/api/kb/employers/nonexistent", json=payload)
        assert r.status_code == 404

    def test_422_unsafe_slug(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "slug": "../evil",
            "employer_name": "Evil",
            "tracks": [],
            "ep_requirement": None,
            "intake_seasons": [],
            "singapore_headcount_estimate": None,
            "application_process": None,
            "counsellor_contact": None,
            "notes": None,
            "last_updated": None,
            "completeness": "amber",
        }
        r = client.put("/api/kb/employers/../evil", json=payload)
        assert r.status_code in (422, 404)


# ---------------------------------------------------------------------------
# DELETE /api/kb/employers/{slug}
# ---------------------------------------------------------------------------

class TestDeleteEmployerEndpoint:
    def test_delete_renames_to_disabled(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        r = client.delete("/api/kb/employers/goldman_sachs")
        assert r.status_code == 204
        assert not (d / "goldman_sachs.yaml").exists()
        assert (d / "goldman_sachs.yaml.disabled").exists()

    def test_404_for_unknown_slug(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)
        r = client.delete("/api/kb/employers/nonexistent")
        assert r.status_code == 404

    def test_422_unsafe_slug(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)
        r = client.delete("/api/kb/employers/../evil")
        assert r.status_code in (422, 404)


# ---------------------------------------------------------------------------
# POST /api/kb/commit-analysis — employer_updates write path
# ---------------------------------------------------------------------------

class TestCommitAnalysisEmployerUpdates:
    def test_valid_field_updates_yaml(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "profile_updates": {},
            "employer_updates": {
                "goldman_sachs": {
                    "ep_requirement": {"old": "EP4", "new": "EP3 (updated)"}
                }
            },
            "new_chunks": [],
        }
        r = client.post("/api/kb/commit-analysis", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert "goldman_sachs" in data["employers_updated"]

        # Verify YAML was written
        import yaml as _yaml
        with open(d / "goldman_sachs.yaml", encoding="utf-8") as f:
            written = _yaml.safe_load(f)
        assert written["ep_requirement"] == "EP3 (updated)"

    def test_unknown_field_skipped_by_allowlist(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "profile_updates": {},
            "employer_updates": {
                "goldman_sachs": {
                    "structured": {"old": None, "new": "evil value"}
                }
            },
            "new_chunks": [],
        }
        r = client.post("/api/kb/commit-analysis", json=payload)
        assert r.status_code == 200
        assert r.json()["employers_updated"] == []


# ---------------------------------------------------------------------------
# POST /api/kb/commit-analysis — profile_updates write path
# ---------------------------------------------------------------------------

class TestCommitAnalysisProfileUpdates:
    def test_valid_profile_field_updates_yaml(self, in_memory_qdrant, mock_embedder, tmp_path):
        from main import app
        import dependencies
        from services.vector_store import VectorStore
        from services.career_profiles import get_career_profile_store
        from services.employer_store import get_employer_store
        from unittest.mock import MagicMock

        pdir = make_profiles_dir(tmp_path)
        os.environ["CAREER_PROFILES_DIR"] = str(pdir)

        store = VectorStore(client=in_memory_qdrant, collection="knowledge")
        store.ensure_collection(384)
        app.dependency_overrides[dependencies.get_vector_store] = lambda: store
        app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
        app.dependency_overrides[get_career_profile_store] = lambda: MagicMock()
        app.dependency_overrides[get_employer_store] = lambda: MagicMock()

        client = TestClient(app)
        payload = {
            "profile_updates": {
                "investment_banking": {
                    "notes": {"old": "Original note", "new": "Updated note"}
                }
            },
            "employer_updates": {},
            "new_chunks": [],
        }

        r = client.post("/api/kb/commit-analysis", json=payload)
        assert r.status_code == 200
        assert "investment_banking" in r.json()["profiles_updated"]

        import yaml as _yaml
        with open(pdir / "investment_banking.yaml", encoding="utf-8") as f:
            written = _yaml.safe_load(f)
        assert written["notes"] == "Updated note"

    def test_unknown_profile_field_skipped_by_allowlist(self, in_memory_qdrant, mock_embedder, tmp_path):
        from main import app
        import dependencies
        from services.vector_store import VectorStore
        from services.career_profiles import get_career_profile_store
        from services.employer_store import get_employer_store
        from unittest.mock import MagicMock

        pdir = make_profiles_dir(tmp_path)
        os.environ["CAREER_PROFILES_DIR"] = str(pdir)

        store = VectorStore(client=in_memory_qdrant, collection="knowledge")
        store.ensure_collection(384)
        app.dependency_overrides[dependencies.get_vector_store] = lambda: store
        app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
        app.dependency_overrides[get_career_profile_store] = lambda: MagicMock()
        app.dependency_overrides[get_employer_store] = lambda: MagicMock()

        client = TestClient(app)
        payload = {
            "profile_updates": {
                "investment_banking": {
                    "structured": {"old": None, "new": "evil value"}
                }
            },
            "employer_updates": {},
            "new_chunks": [],
        }

        r = client.post("/api/kb/commit-analysis", json=payload)
        assert r.status_code == 200
        assert r.json()["profiles_updated"] == []

        import yaml as _yaml
        with open(pdir / "investment_banking.yaml", encoding="utf-8") as f:
            written = _yaml.safe_load(f)
        assert written["structured"]["sponsorship_tier"] == "High"

    def test_unsafe_employer_slug_skipped(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "profile_updates": {},
            "employer_updates": {
                "../evil": {
                    "ep_requirement": {"old": None, "new": "EP3"}
                }
            },
            "new_chunks": [],
        }
        r = client.post("/api/kb/commit-analysis", json=payload)
        assert r.status_code == 200
        assert "../evil" not in r.json().get("employers_updated", [])

    def test_unknown_employer_slug_skipped_with_warning(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "profile_updates": {},
            "employer_updates": {
                "nonexistent_corp": {
                    "ep_requirement": {"old": None, "new": "EP3"}
                }
            },
            "new_chunks": [],
        }
        r = client.post("/api/kb/commit-analysis", json=payload)
        assert r.status_code == 200
        assert "nonexistent_corp" not in r.json().get("employers_updated", [])

    def test_empty_employer_updates_returns_ok(self, in_memory_qdrant, mock_embedder, tmp_path):
        d = make_employers_dir(tmp_path)
        client, _, _ = make_employer_client(in_memory_qdrant, mock_embedder, d)

        payload = {
            "profile_updates": {},
            "employer_updates": {},
            "new_chunks": [],
        }
        r = client.post("/api/kb/commit-analysis", json=payload)
        assert r.status_code == 200
        assert r.json()["employers_updated"] == []
