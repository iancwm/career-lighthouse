#!/usr/bin/env python3
"""cleanup_sessions.py — delete completed/cancelled sessions older than N days.

Usage:
    python3 scripts/cleanup_sessions.py [--days N] [--dry-run] [--sessions-dir PATH]

Resolution order for sessions directory:
    1. --sessions-dir CLI argument
    2. SESSIONS_DIR environment variable
    3. <repo-root>/data/sessions/ (default)

Only sessions whose status is a terminal state (completed, cancelled) AND whose
file mtime is older than --days are deleted.  All other files are skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Terminal session statuses — derived from session_router.py and session_store.py.
# "completed" is set by _check_session_completion when all cards are committed/discarded.
# "cancelled" is set by the /cancel endpoint.
TERMINAL_STATUSES = {"completed", "cancelled"}


def resolve_sessions_dir(cli_arg: str | None) -> Path:
    """Return the sessions directory path using the documented priority order."""
    if cli_arg:
        return Path(cli_arg)
    env_val = os.environ.get("SESSIONS_DIR")
    if env_val:
        return Path(env_val)
    # Default: <script's parent dir (repo root)>/data/sessions
    return Path(__file__).resolve().parents[1] / "data" / "sessions"


def iter_session_files(sessions_dir: Path):
    """Yield all .json files under sessions_dir (scoped sub-dirs + legacy flat files)."""
    # Scoped layout: <sessions_dir>/<counsellor_id>/<session_id>.json
    for entry in sessions_dir.iterdir():
        if entry.is_dir():
            yield from entry.glob("*.json")
    # Legacy flat layout: <sessions_dir>/<session_id>.json
    yield from sessions_dir.glob("*.json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete completed/cancelled sessions older than N days.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        metavar="N",
        help="Age threshold in days (default: 30). Files older than this are eligible for deletion.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview which files would be deleted without actually deleting them.",
    )
    parser.add_argument(
        "--sessions-dir",
        metavar="PATH",
        default=None,
        help="Override the sessions directory (also reads SESSIONS_DIR env var).",
    )
    args = parser.parse_args()

    sessions_dir = resolve_sessions_dir(args.sessions_dir)

    if not sessions_dir.exists():
        print(f"ERROR: Sessions directory does not exist: {sessions_dir}", file=sys.stderr)
        return 1

    if not sessions_dir.is_dir():
        print(f"ERROR: Sessions path is not a directory: {sessions_dir}", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).timestamp()
    cutoff_seconds = args.days * 86400

    scanned = 0
    deleted = 0
    skipped_active = 0
    skipped_recent = 0
    skipped_error = 0

    prefix = "[DRY RUN] " if args.dry_run else ""

    try:
        session_files = list(iter_session_files(sessions_dir))
    except OSError as exc:
        print(f"ERROR: Could not list sessions directory {sessions_dir}: {exc}", file=sys.stderr)
        return 1

    for path in session_files:
        scanned += 1

        # Load and validate JSON
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: Skipping malformed or unreadable file {path}: {exc}", file=sys.stderr)
            skipped_error += 1
            continue

        status = data.get("status", "")

        # Check terminal status
        if status not in TERMINAL_STATUSES:
            skipped_active += 1
            continue

        # Check file age using mtime
        try:
            mtime = path.stat().st_mtime
        except OSError as exc:
            print(f"WARNING: Could not stat {path}: {exc}", file=sys.stderr)
            skipped_error += 1
            continue

        age_seconds = now - mtime
        if age_seconds < cutoff_seconds:
            skipped_recent += 1
            continue

        # Both conditions met — delete (or preview)
        age_days = age_seconds / 86400
        session_id = data.get("id", path.stem)
        if args.dry_run:
            print(f"{prefix}Would delete: {path}  (status={status}, age={age_days:.1f}d)")
        else:
            try:
                path.unlink()
                print(f"Deleted: {path}  (status={status}, age={age_days:.1f}d, id={session_id})")
            except OSError as exc:
                print(f"WARNING: Could not delete {path}: {exc}", file=sys.stderr)
                skipped_error += 1
                continue
        deleted += 1

    # Summary
    action = "would be deleted" if args.dry_run else "deleted"
    print(
        f"\nSummary: {scanned} scanned, {deleted} {action}, "
        f"{skipped_active} skipped (active status), "
        f"{skipped_recent} skipped (too recent), "
        f"{skipped_error} skipped (errors)"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
