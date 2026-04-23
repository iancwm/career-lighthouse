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
    "singapore_headcount_estimate",
    "counselor_contact",
    "notes",
])

ALLOWED_ALUMNI_FIELDS: frozenset = frozenset([
    "full_name",
    "name",
    "degree",
    "school",
    "graduation_school",
    "graduation_program",
    "graduation_year",
    "current_title",
    "current_company",
    "available_for_mentoring",
    "notes",
    "career_goals_domains",
    "help_capacity",
    "can_refer",
    "can_refer_confidence",
    "can_refer_evidence",
    "can_refer_rationale",
    "network_strength",
    "mentoring_modes",
    "communication_style",
    "preferred_student_traits",
    "common_interests",
    "consent_for_referrals",
    "consent_scope_notes",
    "source_type",
    "source_label",
    "source_timestamp",
    "trace_id",
    "lifecycle",
    "deleted",
    "superseded_by",
    "archived_at",
    "last_confirmed_at",
    "last_updated",
])

ALLOWED_ALUMNI_LINK_FIELDS: frozenset = frozenset([
    "company_slug",
    "company_name",
    "role_title",
    "start_date",
    "end_date",
    "link_type",
    "confidence",
    "evidence",
    "rationale",
    "source_type",
    "source_label",
    "source_timestamp",
])
