from pathlib import Path

import yaml

from cfg import career_profiles_cfg


PROFILES_DIR = Path(__file__).resolve().parents[2] / "knowledge" / "career_profiles"


def test_checked_in_career_profiles_satisfy_the_runtime_schema():
    required_fields = set(career_profiles_cfg["required_fields"])
    failures = {}

    for path in sorted(PROFILES_DIR.glob("*.yaml")):
        profile = yaml.safe_load(path.read_text(encoding="utf-8"))
        missing_fields = sorted(required_fields - set(profile or {}))
        if missing_fields:
            failures[path.name] = missing_fields

    assert failures == {}
