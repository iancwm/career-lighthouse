from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest


@pytest.fixture
def session_router_module():
    mock_embedder = MagicMock()
    mock_embedder.encode.return_value = np.ones(384, dtype=np.float32)
    mock_vector_store = MagicMock()
    fake_dependencies = types.ModuleType("dependencies")
    fake_dependencies.get_embedder = lambda: mock_embedder
    fake_dependencies.get_vector_store = lambda: mock_vector_store
    fake_dependencies.require_admin_key = lambda: None

    original_dependencies = sys.modules.get("dependencies")
    sys.modules["dependencies"] = fake_dependencies

    base_dir = Path(__file__).resolve().parent.parent
    router_path = base_dir / "routers" / "session_router.py"
    spec = importlib.util.spec_from_file_location("session_router_alumni_detection", router_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["session_router_alumni_detection"] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    try:
        yield module
    finally:
        sys.modules.pop("session_router_alumni_detection", None)
        if original_dependencies is None:
            sys.modules.pop("dependencies", None)
        else:
            sys.modules["dependencies"] = original_dependencies


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        ("alumni_1.txt", True),
        ("alumni_2.txt", True),
        ("alumni_3.txt", True),
        ("non_alumni_1.txt", False),
        ("non_alumni_2.txt", False),
    ],
)
def test_is_alumni_heavy_fixture_corpus(session_router_module, fixture_name: str, expected: bool):
    fixture_path = Path(__file__).parent / "fixtures" / "alumni_heavy_notes" / fixture_name
    text = fixture_path.read_text(encoding="utf-8")
    assert session_router_module._is_alumni_heavy(text) is expected


def test_build_alumni_cards_downgrades_hallucinated_update(session_router_module):
    cards = session_router_module._build_alumni_cards(
        {
            "alumni": [
                {
                    "is_update": True,
                    "matched_slug": "ghost-slug",
                    "source_excerpt": "Alicia Tan joined Stripe as a product manager.",
                    "profile_proposals": {
                        "full_name": {"value": "Alicia Tan"},
                        "current_company": {"value": "Stripe"},
                    },
                }
            ]
        },
        "session-1",
        [{"slug": "existing-slug", "full_name": "Existing Person", "current_company": "Grab"}],
    )

    assert len(cards) == 1
    assert cards[0]["is_update"] is False
    assert cards[0]["matched_slug"] is None
    assert cards[0]["diff"]["slug"] == "alicia_tan"


def test_build_alumni_cards_applies_slug_collision_suffix_and_confidence_defaults(session_router_module):
    cards = session_router_module._build_alumni_cards(
        {
            "alumni": [
                {
                    "source": "counselor",
                    "source_excerpt": "Maya Lim graduated from SMU and joined Grab as an analyst.",
                    "profile_proposals": {
                        "full_name": {"value": "Maya Lim"},
                        "current_company": {"value": "Grab"},
                        "career_trajectory_summary": {"value": "SMU to Grab analyst path"},
                    },
                }
            ]
        },
        "session-2",
        [{"slug": "maya-lim", "full_name": "Maya Lim", "current_company": "Grab"}],
    )

    assert len(cards) == 1
    assert cards[0]["diff"]["slug"].startswith("maya_lim-")
    assert cards[0]["proposals"]["current_company"]["confidence"] == 85
