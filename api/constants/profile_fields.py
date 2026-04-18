# api/constants/profile_fields.py
"""Shared allowlists for career profile and employer field updates.

These frozensets guard against arbitrary YAML key injection from card-commit
and KB-commit payloads. Fields not in the allowlist are skipped with a
warning in both kb_router and session_router.

ALLOWED_PROFILE_FIELDS is the union of the former kb_router.ALLOWED_PROFILE_FIELDS
(7 fields) and session_router.ALLOWED_CARD_PROFILE_FIELDS (12 fields), plus three
Sprint 4 additions: salary_levels, visa_pathway_notes, track_name.
"""

ALLOWED_PROFILE_FIELDS: frozenset = frozenset([
    # Original kb_router fields
    "ep_sponsorship",
    "compass_score_typical",
    "recruiting_timeline",
    "salary_range_2024",
    "typical_background",
    "counselor_contact",
    "notes",
    # Additional fields from session_router ALLOWED_CARD_PROFILE_FIELDS
    "top_employers_smu",
    "international_realistic",
    "entry_paths",
    "match_description",
    "match_keywords",
    # Sprint 4 additions
    "salary_levels",
    "visa_pathway_notes",
    "track_name",
])

ALLOWED_EMPLOYER_FIELDS: frozenset = frozenset([
    "employer_name",
    "tracks",
    "ep_requirement",
    "intake_seasons",
    "application_process",
    "headcount_estimate",
    "counselor_contact",
    "notes",
])
