# api/tests/test_employer_store.py
"""Unit tests for EmployerEntityStore.

Test run command:
    docker compose run --rm -T api uv run --with pytest --with pytest-asyncio \
        python -m pytest tests/test_employer_store.py -v
"""
import os
import textwrap
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    """Force EmployerEntityStore to reload on each test."""
    from services.employer_store import EmployerEntityStore
    EmployerEntityStore._instance = None
    yield
    EmployerEntityStore._instance = None


@pytest.fixture
def employers_dir(tmp_path):
    """Yield a temp directory pre-populated with two valid employer YAMLs."""
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
        notes: "Superday required"
        last_updated: "2026-04-05"
    """), encoding="utf-8")

    (d / "mckinsey.yaml").write_text(textwrap.dedent("""\
        employer_name: McKinsey
        slug: mckinsey
        tracks:
          - consulting
        ep_requirement: "EP3+"
        intake_seasons:
          - Apr
        last_updated: "2026-04-05"
    """), encoding="utf-8")

    return d


# ---------------------------------------------------------------------------
# EmployerEntityStore.list_employers()
# ---------------------------------------------------------------------------

class TestListEmployers:
    def test_loads_valid_yaml(self, employers_dir, monkeypatch):
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        results = store.list_employers()
        slugs = {e["slug"] for e in results}
        assert "goldman_sachs" in slugs
        assert "mckinsey" in slugs

    def test_skips_invalid_yaml(self, employers_dir, monkeypatch):
        (employers_dir / "bad.yaml").write_text("!!invalid: [yaml", encoding="utf-8")
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        results = store.list_employers()
        # 2 valid, bad.yaml skipped
        assert len(results) == 2

    def test_skips_missing_employer_name(self, employers_dir, monkeypatch):
        (employers_dir / "noname.yaml").write_text("tracks:\n  - consulting\n", encoding="utf-8")
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        results = store.list_employers()
        slugs = {e["slug"] for e in results}
        assert "noname" not in slugs

    def test_empty_dir_returns_empty_list(self, tmp_path, monkeypatch):
        empty = tmp_path / "empty_employers"
        empty.mkdir()
        monkeypatch.setenv("EMPLOYERS_DIR", str(empty))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        assert store.list_employers() == []

    def test_missing_dir_returns_empty_list(self, tmp_path, monkeypatch):
        monkeypatch.setenv("EMPLOYERS_DIR", str(tmp_path / "nonexistent"))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        assert store.list_employers() == []

    def test_completeness_green_when_all_required_fields_present(self, employers_dir, monkeypatch):
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        goldman = next(e for e in store.list_employers() if e["slug"] == "goldman_sachs")
        assert goldman["completeness"] == "green"

    def test_completeness_amber_when_required_field_missing(self, employers_dir, monkeypatch):
        # mckinsey.yaml has no intake_seasons... wait, it does. Rewrite without ep_requirement.
        (employers_dir / "partial.yaml").write_text(textwrap.dedent("""\
            employer_name: Partial Corp
            slug: partial
            tracks:
              - tech_product
        """), encoding="utf-8")
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        partial = store.get_employer("partial")
        assert partial is not None
        assert partial["completeness"] == "amber"


# ---------------------------------------------------------------------------
# EmployerEntityStore.invalidate()
# ---------------------------------------------------------------------------

class TestInvalidate:
    def test_reload_after_invalidate(self, employers_dir, monkeypatch):
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        assert len(store.list_employers()) == 2

        # Add a new YAML after initial load
        (employers_dir / "new_corp.yaml").write_text(textwrap.dedent("""\
            employer_name: New Corp
            slug: new_corp
            tracks:
              - tech_product
            ep_requirement: "EP3"
            intake_seasons:
              - Jul
        """), encoding="utf-8")

        # Before invalidate: not visible
        assert store.get_employer("new_corp") is None

        store.invalidate()

        # After invalidate: visible
        assert store.get_employer("new_corp") is not None


# ---------------------------------------------------------------------------
# EmployerEntityStore.to_context_block()
# ---------------------------------------------------------------------------

class TestToContextBlock:
    def test_returns_empty_when_no_employers(self, tmp_path, monkeypatch):
        empty = tmp_path / "empty_employers"
        empty.mkdir()
        monkeypatch.setenv("EMPLOYERS_DIR", str(empty))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        assert store.to_context_block() == ""

    def test_filters_by_active_career_type(self, employers_dir, monkeypatch):
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        block = store.to_context_block("investment_banking")
        assert "Goldman Sachs" in block
        assert "McKinsey" not in block

    def test_career_type_none_includes_all(self, employers_dir, monkeypatch):
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        block = store.to_context_block(None)
        assert "Goldman Sachs" in block
        assert "McKinsey" in block

    def test_no_matching_employers_returns_empty(self, employers_dir, monkeypatch):
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        block = store.to_context_block("public_sector")
        assert block == ""

    def test_notes_truncated_at_150_chars(self, employers_dir, monkeypatch):
        long_notes = "x" * 200
        (employers_dir / "verbose.yaml").write_text(
            f"employer_name: Verbose Corp\nslug: verbose\ntracks:\n  - investment_banking\n"
            f"ep_requirement: EP4\nintake_seasons:\n  - Jan\nnotes: '{long_notes}'\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        block = store.to_context_block("investment_banking")
        # Notes in the block should be truncated (150 chars + "...")
        assert "x" * 200 not in block
        assert "x" * 150 in block or "..." in block

    def test_employer_missing_employer_name_handled_gracefully(self, employers_dir, monkeypatch):
        # Already tested via skip in list_employers, but verify to_context_block doesn't crash
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        # Manually insert a broken employer into _employers to test context block path
        store._ensure_loaded()
        store._employers["broken"] = {"slug": "broken", "tracks": ["investment_banking"]}
        block = store.to_context_block("investment_banking")
        # Should not raise; "Unknown" fallback used
        assert "Unknown" in block or "broken" in block

    def test_context_block_has_header_and_footer(self, employers_dir, monkeypatch):
        monkeypatch.setenv("EMPLOYERS_DIR", str(employers_dir))
        from services.employer_store import EmployerEntityStore
        store = EmployerEntityStore()
        block = store.to_context_block()
        assert "=== EMPLOYER FACTS" in block
        assert "=== END EMPLOYER FACTS ===" in block
