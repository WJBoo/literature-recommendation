#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.services.accounts import AccountService, normalize_account_store


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a file-backed accounts.json document into the Postgres account store."
    )
    parser.add_argument(
        "--input-path",
        type=Path,
        default=settings.account_store_path or settings.processed_data_dir / "accounts.json",
        help="Path to the accounts.json file to import.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and validate the input without writing to Postgres.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Allow importing an empty account store.",
    )
    args = parser.parse_args()

    if not args.input_path.exists():
        raise SystemExit(f"Account store file not found: {args.input_path}")

    store = normalize_account_store(json.loads(args.input_path.read_text(encoding="utf-8")))
    user_count = len(store["users"])
    post_count = len(store["posts"])
    thread_count = len(store["message_threads"])
    if user_count == 0 and not args.allow_empty:
        raise SystemExit("Refusing to import an empty account store. Use --allow-empty to override.")

    print(
        f"Read {user_count} users, {post_count} posts, "
        f"and {thread_count} message threads from {args.input_path}."
    )
    if args.dry_run:
        print("Dry run complete; no database write performed.")
        return

    AccountService()._write_database_store(store)
    print("Imported account store into Postgres table account_store_documents.")


if __name__ == "__main__":
    main()
