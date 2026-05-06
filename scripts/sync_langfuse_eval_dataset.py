#!/usr/bin/env python3
"""Sync canonical eval fixtures from repo into a Langfuse dataset.

Usage:
    # Dry run (no writes) — safe with or without LANGFUSE_* configured:
    python scripts/sync_langfuse_eval_dataset.py --dry-run

    # Live upsert:
    LANGFUSE_PUBLIC_KEY=pk-... LANGFUSE_SECRET_KEY=sk-... LANGFUSE_HOST=https://cloud.langfuse.com \
        python scripts/sync_langfuse_eval_dataset.py

The script reads api/tests/fixtures/eval_queries.jsonl (the canonical repo
truth set) and upserts each item into a Langfuse dataset named
LANGFUSE_EVAL_DATASET (default: "career-lighthouse-evals").

Exit codes:
    0 — success (or dry-run with 0 errors)
    1 — one or more items failed to upsert
    2 — Langfuse is not configured and --dry-run was not passed
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FIXTURES_PATH = (
    Path(__file__).resolve().parent.parent
    / "api"
    / "tests"
    / "fixtures"
    / "eval_queries.jsonl"
)
DEFAULT_DATASET_NAME = "career-lighthouse-evals"


def load_fixtures(path: Path) -> list[dict]:
    items = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        items.append(json.loads(line))
    return items


def _langfuse_is_configured() -> bool:
    return bool(
        os.environ.get("LANGFUSE_PUBLIC_KEY")
        and os.environ.get("LANGFUSE_SECRET_KEY")
    )


def _build_langfuse_client():
    try:
        from langfuse import Langfuse
    except ImportError:
        logger.error(
            "langfuse package is not installed. "
            "Run: uv add langfuse  (or: pip install langfuse)"
        )
        sys.exit(1)

    public_key = os.environ["LANGFUSE_PUBLIC_KEY"]
    secret_key = os.environ["LANGFUSE_SECRET_KEY"]
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    return Langfuse(public_key=public_key, secret_key=secret_key, host=host)


def _ensure_dataset(client, name: str):
    try:
        return client.get_dataset(name)
    except Exception:
        logger.info("Dataset %r not found; creating it.", name)
        return client.create_dataset(name=name, description="Career Lighthouse canonical eval queries")


def _item_input(fixture: dict) -> dict:
    return {"query": fixture["query"]}


def _item_expected_output(fixture: dict) -> dict:
    out = {}
    if "expected_employer" in fixture:
        out["expected_employer"] = fixture["expected_employer"]
    if "expected_track" in fixture:
        out["expected_track"] = fixture["expected_track"]
    if "should_not_say_no_info" in fixture:
        out["should_not_say_no_info"] = fixture["should_not_say_no_info"]
    return out


def sync(
    fixtures: list[dict],
    *,
    dataset_name: str,
    dry_run: bool,
) -> int:
    if dry_run:
        logger.info(
            "[dry-run] Would upsert %d items into dataset %r", len(fixtures), dataset_name
        )
        for i, fix in enumerate(fixtures, 1):
            logger.info("  %d. %s", i, fix["query"][:80])
        return 0

    client = _build_langfuse_client()
    _ensure_dataset(client, dataset_name)

    errors = 0
    for i, fixture in enumerate(fixtures, 1):
        try:
            client.create_dataset_item(
                dataset_name=dataset_name,
                input=_item_input(fixture),
                expected_output=_item_expected_output(fixture),
                metadata={"source": "eval_queries.jsonl", "index": i},
            )
            logger.info("  upserted: %s", fixture["query"][:80])
        except Exception as exc:
            logger.error("  FAILED item %d: %s — %s", i, fixture["query"][:60], exc)
            errors += 1

    client.flush()
    logger.info("Sync complete: %d items, %d errors.", len(fixtures), errors)
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be upserted without writing to Langfuse.",
    )
    parser.add_argument(
        "--dataset-name",
        default=os.environ.get("LANGFUSE_EVAL_DATASET", DEFAULT_DATASET_NAME),
        help=f"Langfuse dataset name (default: {DEFAULT_DATASET_NAME}).",
    )
    parser.add_argument(
        "--fixtures",
        default=str(FIXTURES_PATH),
        help="Path to eval_queries.jsonl fixture file.",
    )
    args = parser.parse_args()

    fixtures_path = Path(args.fixtures)
    if not fixtures_path.exists():
        logger.error("Fixtures file not found: %s", fixtures_path)
        sys.exit(1)

    fixtures = load_fixtures(fixtures_path)
    logger.info("Loaded %d fixtures from %s", len(fixtures), fixtures_path)

    if not args.dry_run and not _langfuse_is_configured():
        logger.error(
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are not set. "
            "Use --dry-run to preview without writing, or set the env vars."
        )
        sys.exit(2)

    errors = sync(fixtures, dataset_name=args.dataset_name, dry_run=args.dry_run)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
