# api/tests/test_kb_analyse.py
"""Tests for POST /api/kb/analyse and POST /api/kb/commit-analysis endpoints."""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient


def make_client(in_memory_qdrant, mock_embedder):
    from main import app
    from services.vector_store import VectorStore
    import dependencies

    store = VectorStore(client=in_memory_qdrant, collection="knowledge")
    store.ensure_collection(384)
    app.dependency_overrides[dependencies.get_vector_store] = lambda: store
    app.dependency_overrides[dependencies.get_embedder] = lambda: mock_embedder
    return TestClient(app), store


# ---------------------------------------------------------------------------
# POST /api/kb/analyse
# ---------------------------------------------------------------------------

VALID_ANALYSIS_RESPONSE = {
    "interpretation_bullets": ["Goldman raised EP threshold to COMPASS 50+"],
    "profile_updates": {
        "investment_banking": {
            "ep_sponsorship": {"old": "High at bulge brackets", "new": "50+ COMPASS required at Goldman from 2026"}
        }
    },
    "new_chunks": [
        {
            "text": "Goldman now requires COMPASS 50+",
            "source_type": "note",
            "source_label": "counsellor_note",
            "career_type": "investment_banking",
            "chunk_id": "",
        }
    ],
    "already_covered": [],
}


class TestAnalyse:
    def test_text_note_returns_analysis(self, in_memory_qdrant, mock_embedder):
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        with patch("services.llm.analyse_kb_input", return_value=VALID_ANALYSIS_RESPONSE):
            with patch("services.career_profiles.CareerProfileStore.list_profiles", return_value=[]):
                r = client.post(
                    "/api/kb/analyse",
                    data={"text": "Goldman changed their EP policy", "source_type": "note"},
                )

        assert r.status_code == 200
        data = r.json()
        assert "interpretation_bullets" in data
        assert len(data["interpretation_bullets"]) >= 1
        assert "profile_updates" in data
        assert "new_chunks" in data
        # Server fills chunk_id
        for chunk in data["new_chunks"]:
            assert chunk["chunk_id"] != ""

    def test_empty_text_returns_422(self, in_memory_qdrant, mock_embedder):
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        r = client.post("/api/kb/analyse", data={"text": "   ", "source_type": "note"})

        assert r.status_code == 422

    def test_malformed_claude_json_returns_422(self, in_memory_qdrant, mock_embedder):
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        with patch("services.llm.analyse_kb_input", side_effect=ValueError("bad JSON")):
            with patch("services.career_profiles.CareerProfileStore.list_profiles", return_value=[]):
                r = client.post(
                    "/api/kb/analyse",
                    data={"text": "some input", "source_type": "note"},
                )

        assert r.status_code == 422
        assert "Analysis failed" in r.json()["detail"]

    def test_kb_unavailable_returns_503(self, in_memory_qdrant, mock_embedder):
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        mock_embedder.encode.side_effect = RuntimeError("embedding service down")

        with patch("services.career_profiles.CareerProfileStore.list_profiles", return_value=[]):
            r = client.post(
                "/api/kb/analyse",
                data={"text": "Goldman changed their EP policy", "source_type": "note"},
            )

        assert r.status_code == 503

    def test_chunk_ids_are_filled_by_server(self, in_memory_qdrant, mock_embedder):
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        with patch("services.llm.analyse_kb_input", return_value=VALID_ANALYSIS_RESPONSE):
            with patch("services.career_profiles.CareerProfileStore.list_profiles", return_value=[]):
                r = client.post(
                    "/api/kb/analyse",
                    data={"text": "Goldman changed their EP policy", "source_type": "note"},
                )

        assert r.status_code == 200
        chunks = r.json()["new_chunks"]
        assert all(c["chunk_id"] != "" for c in chunks)

    def test_already_covered_empty_for_novel_input(self, in_memory_qdrant, mock_embedder):
        client, _ = make_client(in_memory_qdrant, mock_embedder)
        response = {**VALID_ANALYSIS_RESPONSE, "already_covered": []}

        with patch("services.llm.analyse_kb_input", return_value=response):
            with patch("services.career_profiles.CareerProfileStore.list_profiles", return_value=[]):
                r = client.post(
                    "/api/kb/analyse",
                    data={"text": "Completely new information", "source_type": "note"},
                )

        assert r.status_code == 200
        assert r.json()["already_covered"] == []


# ---------------------------------------------------------------------------
# POST /api/kb/commit-analysis
# ---------------------------------------------------------------------------

class TestCommitAnalysis:
    def test_commits_new_chunks_to_qdrant(self, in_memory_qdrant, mock_embedder):
        client, store = make_client(in_memory_qdrant, mock_embedder)

        payload = {
            "profile_updates": {},
            "new_chunks": [
                {
                    "text": "Goldman requires COMPASS 50+ from 2026",
                    "source_type": "note",
                    "source_label": "counsellor_note",
                    "career_type": "investment_banking",
                    "chunk_id": "test-chunk-id-001",
                }
            ],
        }

        r = client.post("/api/kb/commit-analysis", json=payload)

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["chunks_added"] == 1
        assert data["profiles_updated"] == []

    def test_empty_commit_returns_zero_counts(self, in_memory_qdrant, mock_embedder):
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        r = client.post(
            "/api/kb/commit-analysis",
            json={"profile_updates": {}, "new_chunks": []},
        )

        assert r.status_code == 200
        data = r.json()
        assert data["chunks_added"] == 0
        assert data["profiles_updated"] == []

    def test_missing_profile_on_disk_skips_gracefully(self, in_memory_qdrant, mock_embedder):
        """Commit with a profile slug that doesn't exist on disk — should skip and not crash."""
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        payload = {
            "profile_updates": {
                "nonexistent_career_type": {
                    "ep_sponsorship": {"old": "old value", "new": "new value"}
                }
            },
            "new_chunks": [],
        }

        r = client.post("/api/kb/commit-analysis", json=payload)

        assert r.status_code == 200
        assert r.json()["profiles_updated"] == []

    def test_commit_writes_yaml_and_returns_slug(self, in_memory_qdrant, mock_embedder, tmp_path):
        """Commit with profile_updates writes to a YAML file and returns the slug."""
        client, _ = make_client(in_memory_qdrant, mock_embedder)

        # Create a temporary YAML profile
        profile_dir = tmp_path / "career_profiles"
        profile_dir.mkdir()
        test_profile = {
            "career_type": "Test Track",
            "ep_sponsorship": "Original value",
            "match_description": "test track",
        }
        (profile_dir / "test_track.yaml").write_text(yaml.dump(test_profile))

        payload = {
            "profile_updates": {
                "test_track": {
                    "ep_sponsorship": {"old": "Original value", "new": "Updated value"}
                }
            },
            "new_chunks": [],
        }

        with patch.dict(os.environ, {"CAREER_PROFILES_DIR": str(profile_dir)}):
            r = client.post("/api/kb/commit-analysis", json=payload)

        assert r.status_code == 200
        data = r.json()
        assert "test_track" in data["profiles_updated"]
        # Verify file was updated
        updated = yaml.safe_load((profile_dir / "test_track.yaml").read_text())
        assert updated["ep_sponsorship"] == "Updated value"
