import importlib
import json


def test_session_store_canonicalizes_legacy_track_slugs(monkeypatch, tmp_path):
    monkeypatch.setenv("SESSIONS_DIR", str(tmp_path))

    import services.session_store as session_store_module

    importlib.reload(session_store_module)
    session_store_module.SessionStore._instance = None

    legacy_payload = {
        "id": "legacy-session",
        "status": "analyzed",
        "raw_input": "Legacy track payload",
        "intent_cards": [
            {
                "card_id": "card-track-1",
                "domain": "track",
                "summary": "Legacy DSAI update",
                "diff": {
                    "slug": "data_science_and_artificial_intelligence",
                    "match_keywords": ["data science", "python"],
                },
                "raw_input_ref": "Legacy note",
                "status": "committed",
            }
        ],
        "track_guidance": {
            "status": "clustered_uncertainty",
            "recommendation": "Check the definitions.",
            "nearest_tracks": [
                {"slug": "data_science", "label": "Data Science", "score": 0.82},
                {"slug": "consulting", "label": "Consulting", "score": 0.31},
            ],
            "recurrence_count": 1,
            "cluster_key": "data_science|consulting",
        },
        "created_by": "test",
        "created_at": "2026-04-12T00:00:00+00:00",
        "updated_at": "2026-04-12T00:00:00+00:00",
    }

    session_path = tmp_path / "legacy-session.json"
    session_path.write_text(json.dumps(legacy_payload, indent=2), encoding="utf-8")

    store = session_store_module.SessionStore()
    session = store.get_session("legacy-session")

    assert session is not None
    assert session.intent_cards[0]["diff"]["slug"] == "dsai"
    assert session.track_guidance is not None
    assert session.track_guidance.nearest_tracks[0].slug == "dsai"

    rewritten = json.loads(session_path.read_text(encoding="utf-8"))
    assert rewritten["intent_cards"][0]["diff"]["slug"] == "dsai"
    assert rewritten["track_guidance"]["nearest_tracks"][0]["slug"] == "dsai"
