"""Tests for the standalone legacy-YAML ontology rebuild tool.

All Claude calls are represented by QueueClaude; this suite makes no network calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from models_ontology import Claim
from services.claim_store import _compute_claim_id
from tools.ontology_rebuild import (
    AnthropicClaudeClient,
    ClaudeOutputError,
    LegacyTypeError,
    RebuildError,
    _default_output,
    detect_legacy_type,
    load_legacy_document,
    rebuild_legacy_yaml,
    write_bundle,
)


class QueueClaude:
    model = "test-claude"

    def __init__(self, responses: list[dict]) -> None:
        self.responses = [json.dumps(response) for response in responses]
        self.calls: list[dict] = []

    def complete(self, *, system: str, user: str, max_tokens: int) -> str:
        self.calls.append(
            {"system": system, "user": user, "max_tokens": max_tokens}
        )
        if not self.responses:
            raise AssertionError("Unexpected extra Claude call")
        return self.responses.pop(0)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {"career_type": "Banking", "match_description": "IB", "entry_paths": []},
            "career_profile",
        ),
        (
            {"employer_name": "Bank", "tracks": ["banking"], "ep_requirement": "yes"},
            "employer",
        ),
        (
            {"full_name": "A Person", "graduation_year": 2024},
            "alumni",
        ),
        (
            {"slug": "banking", "track_name": "Banking", "status": "draft"},
            "draft_track",
        ),
        (
            {"doc_id": "guide.txt", "filename": "guide.txt", "lifecycle": "active"},
            "source_ledger",
        ),
        (
            {"tracks": [{"slug": "banking", "label": "Banking"}]},
            "track_registry",
        ),
    ],
)
def test_detect_legacy_type(payload, expected):
    assert detect_legacy_type(payload) == expected


def test_detect_legacy_type_rejects_unknown_mapping():
    with pytest.raises(LegacyTypeError, match="Could not detect"):
        detect_legacy_type({"notes": "not enough identity"})


def _career_profile(path: Path) -> None:
    path.write_text(
        """career_type: Investment Banking
match_description: investment banking internships
recruiting_timeline: Applications close on 2026-09-30.
salary_range_2024: SGD 85000-95000.
""",
        encoding="utf-8",
    )


def _valid_extraction(quote: str) -> dict:
    return {
        "summary": "One runtime claim and one schema-blocked compensation claim.",
        "entities": [
            {
                "ref": "investment_banking",
                "entity_type": "career_track",
                "canonical_name": "Investment Banking",
                "aliases": [],
                "parent_ref": None,
                "geography": None,
                "external_ids": {"career_profile_slug": "investment_banking"},
                "legacy_field_paths": ["career_type"],
            }
        ],
        "supported_claims": [
            {
                "ref": "application_deadline",
                "claim_type": "application_window",
                "subject_ref": "investment_banking",
                "object_ref": None,
                "payload": {
                    "claim_type": "application_window",
                    "programme_id": None,
                    "opens_on": None,
                    "closes_on": "2026-09-30",
                    "date_precision": "exact_date",
                    "intake_year": 2026,
                },
                "scope": {
                    "geography": None,
                    "organization_unit_id": None,
                    "programme_id": None,
                    "role_id": None,
                    "seniority": None,
                    "candidate_segment": None,
                    "academic_year": None,
                },
                "valid_time": {"valid_from": None, "valid_until": "2026-09-30"},
                "observed_at": None,
                "confidence": {
                    "extraction": 0.9,
                    "evidence_strength": 0.9,
                    "source_reliability": 0.9,
                },
                "evidence": [
                    {
                        "quote": quote,
                        "support_type": "directly_supports",
                        "legacy_field_path": "recruiting_timeline",
                        "extraction_confidence": 0.9,
                    }
                ],
            }
        ],
        "blocked_claims": [
            {
                "ref": "analyst_salary",
                "target_claim_type": "compensation_observation",
                "summary": "Reported analyst salary range.",
                "legacy_field_paths": ["salary_range_2024"],
                "blockers": ["unsupported_claim_type", "missing_source"],
                "questions": ["Which survey supports this range?"],
            }
        ],
        "unmapped_fields": [
            {
                "legacy_field_path": "match_description",
                "reason": "Retrieval metadata is not a factual claim.",
                "disposition": "preserve_as_metadata",
            }
        ],
    }


def _gap_audit() -> dict:
    return {
        "needs_user_input": [
            {
                "need_id": "deadline_scope",
                "priority": "high",
                "category": "scope",
                "question": "Which employer and programme use this deadline?",
                "reason": "A track-wide deadline would overgeneralize the claim.",
                "affected_refs": ["application_deadline"],
                "affected_legacy_fields": ["recruiting_timeline"],
                "suggested_answer_format": "Employer, programme, geography, intake year.",
            }
        ],
        "warnings": ["The deadline is currently scoped only to a career track."],
    }


def test_rebuild_materializes_review_bundle_and_caps_legacy_confidence(tmp_path):
    source = tmp_path / "investment_banking.yaml"
    _career_profile(source)
    quote = "Applications close on 2026-09-30."
    claude = QueueClaude([_valid_extraction(quote), _gap_audit()])
    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)

    bundle = rebuild_legacy_yaml(source, claude, now=now)

    assert len(claude.calls) == 2
    assert bundle.legacy_source.detected_type == "career_profile"
    assert bundle.status == "needs_user_input"
    assert {entity.entity_type for entity in bundle.entities} == {
        "career_track",
        "source_document",
    }
    assert len(bundle.evidence) == 1
    assert bundle.evidence[0].excerpt == quote
    assert source.read_text().find(quote) == bundle.evidence[0].locator.character_start
    assert len(bundle.claims) == 1
    claim = Claim.model_validate(bundle.claims[0].model_dump(mode="json"))
    assert claim.assertion_status == "reported"
    assert claim.review_status == "proposed"
    assert claim.confidence.evidence_strength == 0.5
    assert claim.confidence.source_reliability == 0.35
    assert claim.claim_id == _compute_claim_id(
        claim.claim_type,
        claim.subject_entity_id,
        claim.object_entity_id,
        claim.payload,
        claim.scope,
    )
    assert bundle.source_metadata.source_id == bundle.source_metadata.filename
    assert {need.need_kind for need in bundle.needs_user_input} == {
        "missing_scope",
        "missing_original_source",
        "schema_priority",
    }
    assert all(need.need_id.startswith("need-") for need in bundle.needs_user_input)
    assert len(bundle.blocked_claims) == 1


def test_local_scope_and_payload_refs_become_stable_entity_ids(tmp_path):
    source = tmp_path / "investment_banking.yaml"
    _career_profile(source)
    extraction = _valid_extraction("Applications close on 2026-09-30.")
    extraction["entities"].append(
        {
            "ref": "summer_analyst_programme",
            "entity_type": "programme",
            "canonical_name": "Summer Analyst Programme",
            "aliases": [],
            "parent_ref": None,
            "geography": None,
            "external_ids": {},
            "legacy_field_paths": ["recruiting_timeline"],
        }
    )
    claim = extraction["supported_claims"][0]
    claim["payload"]["programme_id"] = "summer_analyst_programme"
    claim["scope"]["programme_id"] = "summer_analyst_programme"

    bundle = rebuild_legacy_yaml(
        source,
        QueueClaude([extraction, _gap_audit()]),
    )

    runtime_claim = bundle.claims[0]
    assert runtime_claim.payload.programme_id == "programme-summer_analyst_programme"
    assert runtime_claim.scope.programme_id == "programme-summer_analyst_programme"


def test_non_exact_evidence_triggers_one_claude_correction(tmp_path):
    source = tmp_path / "investment_banking.yaml"
    _career_profile(source)
    bad = _valid_extraction("This sentence was invented.")
    corrected = _valid_extraction("Applications close on 2026-09-30.")
    claude = QueueClaude([bad, corrected, _gap_audit()])

    bundle = rebuild_legacy_yaml(source, claude)

    assert len(claude.calls) == 3
    assert "VALIDATION ERRORS" in claude.calls[1]["user"]
    assert bundle.evidence[0].excerpt == "Applications close on 2026-09-30."


def test_unaccounted_top_level_field_triggers_correction(tmp_path):
    source = tmp_path / "investment_banking.yaml"
    _career_profile(source)
    incomplete = _valid_extraction("Applications close on 2026-09-30.")
    incomplete["unmapped_fields"] = []
    corrected = _valid_extraction("Applications close on 2026-09-30.")
    claude = QueueClaude([incomplete, corrected, _gap_audit()])

    rebuild_legacy_yaml(source, claude)

    assert len(claude.calls) == 3
    assert "match_description" in claude.calls[1]["user"]


def test_invalid_output_after_correction_fails_without_writing(tmp_path):
    source = tmp_path / "investment_banking.yaml"
    _career_profile(source)
    bad = _valid_extraction("Not in source.")
    claude = QueueClaude([bad, bad])

    with pytest.raises(ClaudeOutputError, match="failed validation"):
        rebuild_legacy_yaml(source, claude)


def test_load_document_rejects_non_mapping_yaml(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(RebuildError, match="top-level mapping"):
        load_legacy_document(path)


def test_load_document_enforces_api_input_size_limit(tmp_path):
    path = tmp_path / "large.yaml"
    path.write_text("career_type: " + ("x" * 50), encoding="utf-8")

    with pytest.raises(RebuildError, match="limit is 20"):
        load_legacy_document(path, max_input_chars=20)


def test_duplicate_yaml_keys_are_exposed_as_required_human_input(tmp_path):
    source = tmp_path / "investment_banking.yaml"
    source.write_text(
        """career_type: Investment Banking
match_description: first description
match_description: replacement description
structured:
  salary_min_sgd: 80000
  salary_min_sgd: 90000
""",
        encoding="utf-8",
    )
    extraction = {
        "summary": "No runtime-supported claims.",
        "entities": [],
        "supported_claims": [],
        "blocked_claims": [],
        "unmapped_fields": [
            {
                "legacy_field_path": field,
                "reason": "Duplicate-key test fixture metadata.",
                "disposition": "requires_user_input",
            }
            for field in ("career_type", "match_description", "structured")
        ],
    }
    empty_audit = {"needs_user_input": [], "warnings": []}

    bundle = rebuild_legacy_yaml(
        source,
        QueueClaude([extraction, empty_audit]),
    )

    assert bundle.legacy_source.duplicate_key_paths == [
        "match_description",
        "structured.salary_min_sgd",
    ]
    duplicate_need = next(
        need for need in bundle.needs_user_input if need.need_kind == "duplicate_value"
    )
    assert duplicate_need.priority == "high"
    assert "structured.salary_min_sgd" in duplicate_need.affected_legacy_fields
    assert any("Duplicate YAML keys" in warning for warning in bundle.warnings)


def test_alumni_rebuild_requires_explicit_personal_data_permission(tmp_path):
    source = tmp_path / "alumni.yaml"
    source.write_text(
        "full_name: Example Person\ngraduation_year: 2024\n",
        encoding="utf-8",
    )
    claude = QueueClaude([])

    with pytest.raises(RebuildError, match="personal data"):
        rebuild_legacy_yaml(source, claude)

    assert claude.calls == []


def test_write_bundle_is_atomic_and_refuses_overwrite(tmp_path):
    source = tmp_path / "investment_banking.yaml"
    _career_profile(source)
    bundle = rebuild_legacy_yaml(
        source,
        QueueClaude(
            [
                _valid_extraction("Applications close on 2026-09-30."),
                _gap_audit(),
            ]
        ),
    )
    output = tmp_path / "bundle.yaml"

    write_bundle(output, bundle)
    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert payload["bundle_version"] == "1.1"
    assert payload["claims"][0]["review_status"] == "proposed"
    assert output.stat().st_mode & 0o777 == 0o600
    assert not output.with_suffix(".yaml.tmp").exists()

    with pytest.raises(RebuildError, match="already exists"):
        write_bundle(output, bundle)


def test_v11_metadata_privacy_and_semantic_need_ids_are_materialized(tmp_path):
    source = tmp_path / "investment_banking.yaml"
    _career_profile(source)
    extraction = _valid_extraction("Applications close on 2026-09-30.")
    first_audit = _gap_audit()
    first_audit["needs_user_input"][0]["need_id"] = "model-wording-a"
    second_audit = _gap_audit()
    second_audit["needs_user_input"][0]["need_id"] = "model-wording-b"

    first = rebuild_legacy_yaml(source, QueueClaude([extraction, first_audit]))
    second = rebuild_legacy_yaml(source, QueueClaude([extraction, second_audit]))

    assert first.bundle_version == "1.1"
    assert first.tool_metadata.name == "career-lighthouse-ontology-rebuild"
    assert first.generation_metadata.api_calls == 2
    assert first.generation_metadata.input_tokens == 0
    assert first.privacy_assessment.status == "unreviewed"
    assert first.privacy_assessment.contains_personal_data is None
    first_ids = {need.need_kind: need.need_id for need in first.needs_user_input}
    second_ids = {need.need_kind: need.need_id for need in second.needs_user_input}
    assert first_ids == second_ids
    assert all(need_id.startswith("need-") for need_id in first_ids.values())


def test_anthropic_client_requires_explicit_egress_confirmation():
    with pytest.raises(RebuildError, match="egress confirmation"):
        AnthropicClaudeClient(api_key="test-key")


def test_source_mutation_aborts_write_and_leaves_no_bundle_or_tmp(tmp_path):
    source = tmp_path / "investment_banking.yaml"
    _career_profile(source)
    bundle = rebuild_legacy_yaml(
        source,
        QueueClaude(
            [
                _valid_extraction("Applications close on 2026-09-30."),
                _gap_audit(),
            ]
        ),
    )
    source.write_text(source.read_text(encoding="utf-8") + "notes: changed\n", encoding="utf-8")
    output = tmp_path / "bundle.yaml"

    with pytest.raises(RebuildError, match="source changed"):
        write_bundle(output, bundle)

    assert not output.exists()
    assert not output.with_suffix(".yaml.tmp").exists()


def test_protected_output_paths_and_symlinked_paths_are_rejected(tmp_path, monkeypatch):
    source = tmp_path / "investment_banking.yaml"
    _career_profile(source)
    bundle = rebuild_legacy_yaml(
        source,
        QueueClaude(
            [
                _valid_extraction("Applications close on 2026-09-30."),
                _gap_audit(),
            ]
        ),
    )
    protected = tmp_path / "knowledge" / "employers"
    protected.mkdir(parents=True)
    monkeypatch.setenv("EMPLOYERS_DIR", str(protected))

    with pytest.raises(RebuildError, match="protected"):
        write_bundle(protected / "bundle.yaml", bundle)

    symlink_parent = tmp_path / "knowledge-link"
    symlink_parent.symlink_to(protected, target_is_directory=True)
    with pytest.raises(RebuildError, match="protected"):
        write_bundle(symlink_parent / "bundle.yaml", bundle)


def test_default_output_is_repo_root_relative():
    output = _default_output(Path("some/source.yaml"))
    assert output == Path(__file__).resolve().parents[2] / "build" / "ontology-rebuild" / "source.ontology.yaml"
