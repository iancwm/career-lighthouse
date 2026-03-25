# api/services/career_profiles.py
"""Career profile service — YAML loading, LLM context formatting, and career type resolution.

This module is the canonical source for:
  - profile_to_context_block(): formats a profile dict into LLM-injectable text
  - CareerProfileStore: singleton that loads profiles + pre-embeds career type names
  - resolve_career_type_from_intake(): intake interest string → career type slug
  - get_career_profile_store(): FastAPI dependency

Career type switching uses cosine similarity between the user's message embedding
and pre-computed career type name embeddings. See _CAREER_TYPE_MATCH_THRESHOLD.

Note on the 'structured:' sub-object in YAML files:
  'structured:' contains machine-readable metadata (sponsorship_tier, salary ranges,
  compass_points_typical, ep_realistic). It is consumed by GET /api/kb/career-profiles
  for the admin panel and is reserved for future tool-call / structured LLM access
  (Sprint 3+). It is intentionally NOT injected into the LLM context block — the
  prose fields below are richer and better suited for natural language consumption.
"""
import logging
import os
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

logger = logging.getLogger(__name__)

# Cosine similarity threshold for query-time career type switching.
# Pre-validate before changing: cd api && uv run python ../scripts/validate_profiles.py --threshold-check
#
# Current status: EFFECTIVELY DISABLED (threshold > max possible cosine of 1.0).
#
# Threshold validation (2026-03-23) showed all-MiniLM-L6-v2 produces max cosine scores
# of 0.50–0.52 between keyword-list match_descriptions and full conversational questions.
# Worse: some questions scored higher against the WRONG track than the correct one,
# meaning any usable threshold would cause false positives (switching to wrong profile).
#
# For the demo: intake → active_career_type echo handles profile persistence reliably.
# Profile switching mid-conversation can be revisited post-demo with a better approach:
#   - Keyword matching (check for firm/role names in message text)
#   - LLM-based classification (one extra API call per message)
#   - A model trained for query classification rather than semantic similarity
_CAREER_TYPE_MATCH_THRESHOLD = 1.01

# Required top-level fields for a profile to be considered valid.
_REQUIRED_FIELDS = frozenset({
    "career_type",
    "ep_sponsorship",
    "top_employers_smu",
    "recruiting_timeline",
    "international_realistic",
    "entry_paths",
    "salary_range_2024",
    "typical_background",
})

# Intake interest value → career type slug mapping.
# Keys are normalised (lowercased, spaces → underscores).
_INTAKE_INTEREST_MAP: dict[str, str] = {
    "finance": "investment_banking",
    "banking": "investment_banking",
    "investment_banking": "investment_banking",
    "consulting": "consulting",
    "tech": "tech_product",
    "technology": "tech_product",
    "product": "tech_product",
    "tech_product": "tech_product",
    "public_sector": "public_sector",
    "government": "public_sector",
    "glc": "public_sector",
    "public_sector_glcs": "public_sector",
}
_DEFAULT_CAREER_TYPE = "general_singapore"


def resolve_career_type_from_intake(interest: Optional[str]) -> str:
    """Map an intake interest value to a career type slug.

    Returns the default career type ('general_singapore') for unknown or missing values.
    """
    if not interest:
        return _DEFAULT_CAREER_TYPE
    key = interest.lower().strip().replace(" ", "_").replace("-", "_")
    return _INTAKE_INTEREST_MAP.get(key, _DEFAULT_CAREER_TYPE)


def profile_to_context_block(profile: dict) -> str:
    """Format a career profile dict as a structured context block for LLM injection.

    This is the canonical implementation. scripts/validate_profiles.py imports from
    here to ensure the pre-validation script and production code use identical formatting.

    The 'structured:' sub-object is not included — see module docstring.
    """
    lines = [
        "=== CAREER CONTEXT (structured institutional data) ===",
        f"Career Track: {profile.get('career_type', 'Unknown')}",
        "",
        f"EP Sponsorship:\n{str(profile.get('ep_sponsorship', 'N/A')).strip()}",
        "",
        f"COMPASS Score (typical):\n{str(profile.get('compass_score_typical', 'N/A')).strip()}",
        "",
        "Top Employers (SMU pipeline):",
    ]
    for emp in profile.get("top_employers_smu", []):
        lines.append(f"  - {emp}")
    lines += [
        "",
        f"Recruiting Timeline:\n{str(profile.get('recruiting_timeline', 'N/A')).strip()}",
        "",
        f"International Candidates Realistic: {profile.get('international_realistic', 'Unknown')}",
        "",
        "Entry Paths:",
    ]
    for entry_path in profile.get("entry_paths", []):
        lines.append(f"  - {entry_path}")
    lines += [
        "",
        f"Salary Range (2024):\n{str(profile.get('salary_range_2024', 'N/A')).strip()}",
        "",
        f"Typical Background:\n{str(profile.get('typical_background', 'N/A')).strip()}",
        "",
        f"Notes:\n{str(profile.get('notes', 'N/A')).strip()}",
        "=== END CAREER CONTEXT ===",
    ]
    return "\n".join(lines)


class CareerProfileStore:
    """Singleton that loads career profile YAMLs and pre-computes career type name embeddings.

    Profiles are loaded lazily on first access. Invalid profiles are skipped with a
    WARNING — the store always initialises successfully even if all profiles fail.

    Dependency graph at load time:
      CareerProfileStore._load_profiles()
        └── Embedder (singleton) — model already loaded by chat requests; no extra cost

    Usage:
        store = CareerProfileStore()
        profile = store.get_profile("investment_banking")  # None if not found/unknown
        slug    = store.match_career_type(query_vec)       # None if score < threshold
        items   = store.list_profiles()                    # for admin endpoint
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._profiles: dict[str, dict] = {}            # slug → profile dict
        self._type_embeddings: dict[str, np.ndarray] = {}  # slug → 384-dim vector (cosine-eligible only)
        self._load_profiles()
        self._loaded = True

    def _load_profiles(self) -> None:
        profiles_dir = Path(os.environ.get(
            "CAREER_PROFILES_DIR",
            str(Path(__file__).parent.parent.parent / "knowledge" / "career_profiles"),
        ))
        if not profiles_dir.exists():
            logger.warning(
                "Career profiles directory not found: %s — profile injection disabled", profiles_dir
            )
            return

        # Embedder is a singleton; importing here avoids circular imports at module level.
        from services.embedder import Embedder
        embedder = Embedder()

        yaml_files = sorted(profiles_dir.glob("*.yaml"))
        loaded = 0
        for yaml_path in yaml_files:
            slug = yaml_path.stem
            try:
                with open(yaml_path, encoding="utf-8") as f:
                    profile = yaml.safe_load(f)
                if not isinstance(profile, dict):
                    logger.warning(
                        "Career profile %s: not a valid YAML mapping — skipping", yaml_path.name
                    )
                    continue
                missing = _REQUIRED_FIELDS - set(profile.keys())
                if missing:
                    logger.warning(
                        "Career profile %s: missing required fields %s — skipping",
                        yaml_path.name, sorted(missing),
                    )
                    continue
                # Use match_description if present — richer keyword text produces
                # more reliable cosine scores against full student messages.
                # Falls back to career_type name if match_description is absent.
                match_text = str(profile.get("match_description") or profile["career_type"]).strip()
                self._profiles[slug] = profile
                # match_cosine: false → only activatable via intake, never by cosine switching
                if profile.get("match_cosine", True):
                    self._type_embeddings[slug] = embedder.encode(match_text)
                else:
                    logger.info(
                        "Career profile %s: match_cosine=false — excluded from cosine switching", slug
                    )
                loaded += 1
                logger.info("Loaded career profile: %s (%s)", slug, profile.get("career_type", slug))
            except yaml.YAMLError as exc:
                logger.warning(
                    "Career profile %s: YAML parse error — skipping: %s", yaml_path.name, exc
                )
            except Exception as exc:
                logger.warning(
                    "Career profile %s: failed to load — skipping: %s", yaml_path.name, exc
                )

        logger.info(
            "CareerProfileStore: loaded %d/%d profiles from %s",
            loaded, len(yaml_files), profiles_dir,
        )

    def get_profile(self, slug: Optional[str]) -> Optional[dict]:
        """Return the profile dict for a career type slug, or None if not found.

        Never raises. Logs a WARNING for non-None slugs that don't match any profile
        (e.g., stale slug sent by client after a profile was renamed or removed).
        """
        if not slug:
            return None
        self._ensure_loaded()
        profile = self._profiles.get(slug)
        if profile is None:
            logger.warning(
                "CareerProfileStore: unknown career type slug %r — treating as no profile", slug
            )
        return profile

    def match_career_type(self, query_embedding: np.ndarray) -> Optional[str]:
        """Return the best-matching career type slug if cosine score >= threshold, else None.

        Uses dot product of normalised embeddings (equivalent to cosine similarity
        since Embedder uses normalize_embeddings=True).
        """
        self._ensure_loaded()
        if not self._type_embeddings:
            return None
        best_slug = None
        best_score = 0.0
        for slug, type_vec in self._type_embeddings.items():
            score = float(np.dot(query_embedding, type_vec))
            if score > best_score:
                best_score = score
                best_slug = slug
        if best_score >= _CAREER_TYPE_MATCH_THRESHOLD:
            return best_slug
        return None

    def list_profiles(self) -> list[dict]:
        """Return metadata for all loaded profiles (for the admin /career-profiles endpoint).

        Includes structured: fields for machine-readable filtering. Profile completeness
        is indicated by has_counselor_contact (False while counselor_contact is a TODO).
        """
        self._ensure_loaded()
        result = []
        for slug, profile in self._profiles.items():
            structured = profile.get("structured") or {}
            counselor = str(profile.get("counselor_contact", ""))
            result.append({
                "slug": slug,
                "career_type": profile.get("career_type", slug),
                "ep_tier": structured.get("sponsorship_tier"),
                "ep_realistic": structured.get("ep_realistic"),
                "salary_min_sgd": structured.get("salary_min_sgd"),
                "salary_max_sgd": structured.get("salary_max_sgd"),
                "compass_points_typical": structured.get("compass_points_typical"),
                "has_counselor_contact": bool(counselor and "TODO" not in counselor),
            })
        return result


def get_career_profile_store() -> CareerProfileStore:
    """FastAPI dependency — returns the CareerProfileStore singleton."""
    return CareerProfileStore()
