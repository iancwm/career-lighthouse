# api/cfg.py
"""Load YAML config files from api/cfg/ at import time.

Usage:
    from cfg import model_cfg, career_profiles_cfg, kb_cfg, track_guidance_cfg, prompts_cfg
"""
from pathlib import Path
import yaml

_CFG_DIR = Path(__file__).parent / "cfg"


def _load(name: str) -> dict:
    with open(_CFG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


model_cfg = _load("model.yaml")
career_profiles_cfg = _load("career_profiles.yaml")
kb_cfg = _load("kb.yaml")
track_guidance_cfg = _load("track_guidance.yaml")
prompts_cfg = _load("prompts.yaml")
