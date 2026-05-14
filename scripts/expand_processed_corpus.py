#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.services.processed_corpus import clear_processed_corpus_cache
from scripts.ingest_bulk_gutenberg import (
    DEFAULT_DOWNLOAD_DELAY_SECONDS,
    DEFAULT_MAX_EXCERPTS_PER_WORK,
    DEFAULT_MAX_POETRY_EXCERPTS_PER_WORK,
    DEFAULT_MIN_WORK_WORDS,
    CATALOG_URL,
    author_key,
    ensure_catalog,
    process_candidate,
    read_catalog_rows,
    select_catalog_candidates,
    title_key,
)
from scripts.ingest_starter_gutenberg import USER_AGENT, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append new Gutenberg works to the existing processed corpus without reprocessing it."
    )
    parser.add_argument("--target-new-works", type=int, default=500)
    parser.add_argument("--candidate-limit", type=int, default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--catalog-url", default=CATALOG_URL)
    parser.add_argument(
        "--catalog-path",
        type=Path,
        default=settings.gutenberg_raw_dir / "pg_catalog.csv.gz",
    )
    parser.add_argument("--refresh-catalog", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--download-delay", type=float, default=DEFAULT_DOWNLOAD_DELAY_SECONDS)
    parser.add_argument("--max-failures", type=int, default=100)
    parser.add_argument("--min-work-words", type=int, default=DEFAULT_MIN_WORK_WORDS)
    parser.add_argument("--max-excerpts-per-work", type=int, default=DEFAULT_MAX_EXCERPTS_PER_WORK)
    parser.add_argument(
        "--max-poetry-excerpts-per-work",
        type=int,
        default=DEFAULT_MAX_POETRY_EXCERPTS_PER_WORK,
    )
    parser.add_argument("--include-nonliterary", action="store_true")
    parser.add_argument("--allow-unknown-authors", action="store_true")
    parser.add_argument("--allow-part-records", action="store_true")
    parser.add_argument("--allow-duplicate-titles", action="store_true")
    parser.add_argument("--selection-mode", choices=["balanced", "score"], default="balanced")
    args = parser.parse_args()

    processed_dir = settings.processed_data_dir
    raw_dir = settings.gutenberg_raw_dir
    clean_dir = processed_dir / "gutenberg_clean"
    raw_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)

    works_path = processed_dir / "gutenberg_works.jsonl"
    excerpts_path = processed_dir / "gutenberg_excerpts.jsonl"
    embedding_inputs_path = processed_dir / "gutenberg_embedding_inputs.jsonl"
    failures_path = processed_dir / "gutenberg_bulk_failures.jsonl"

    existing_works = read_jsonl(works_path)
    existing_excerpts = read_jsonl(excerpts_path)
    existing_embedding_inputs = read_jsonl(embedding_inputs_path)
    existing_failures = read_jsonl(failures_path)
    existing_gutenberg_ids = {
        str(work.get("gutenberg_id") or "").strip()
        for work in existing_works
        if str(work.get("gutenberg_id") or "").strip()
    }
    existing_author_title_keys = {
        (
            str(work.get("canonical_author") or "").strip(),
            str(work.get("canonical_title") or "").strip(),
        )
        for work in existing_works
        if str(work.get("canonical_author") or "").strip()
        and str(work.get("canonical_title") or "").strip()
    }

    ensure_catalog(args.catalog_path, args.catalog_url, refresh=args.refresh_catalog)
    rows = list(read_catalog_rows(args.catalog_path))
    candidate_limit = args.candidate_limit or max(
        len(existing_works) + args.target_new_works * 4,
        args.target_new_works * 8,
    )
    candidates = select_catalog_candidates(
        rows,
        target_count=candidate_limit,
        offset=args.offset,
        include_nonliterary=args.include_nonliterary,
        allow_unknown_authors=args.allow_unknown_authors,
        allow_part_records=args.allow_part_records,
        allow_duplicate_titles=args.allow_duplicate_titles,
        selection_mode=args.selection_mode,
    )
    candidates = [
        candidate
        for candidate in candidates
        if candidate.gutenberg_id not in existing_gutenberg_ids
        and (author_key(candidate.authors), title_key(candidate.title)) not in existing_author_title_keys
    ]

    print(
        f"Existing corpus has {len(existing_works)} works and {len(existing_excerpts)} excerpts. "
        f"Found {len(candidates)} new candidate works from {len(rows)} catalog rows."
    )
    for preview in candidates[:10]:
        print(
            f"  {preview.gutenberg_id}: {preview.title} / "
            f"{', '.join(preview.authors) or 'Unknown'} score={preview.score}"
        )
    if args.dry_run:
        return

    new_works: list[dict[str, object]] = []
    new_excerpts: list[dict[str, object]] = []
    new_embedding_inputs: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60) as client:
        for candidate in candidates:
            if len(new_works) >= args.target_new_works:
                break
            if len(failures) >= args.max_failures:
                print(f"Stopping after {len(failures)} failures.")
                break
            try:
                result = process_candidate(
                    candidate,
                    client=client,
                    raw_dir=raw_dir,
                    clean_dir=clean_dir,
                    force_download=args.force_download,
                    min_work_words=args.min_work_words,
                    max_excerpts_per_work=args.max_excerpts_per_work,
                    max_poetry_excerpts_per_work=args.max_poetry_excerpts_per_work,
                    existing_excerpt_count=len(existing_excerpts) + len(new_excerpts),
                )
            except Exception as exc:  # noqa: BLE001 - operational script should keep moving.
                failures.append(
                    {
                        "gutenberg_id": candidate.gutenberg_id,
                        "title": candidate.title,
                        "error": str(exc),
                        "failed_at": datetime.now(UTC).isoformat(),
                    }
                )
                print(f"Failed {candidate.gutenberg_id}: {candidate.title} - {exc}", flush=True)
                continue

            if result is None:
                failures.append(
                    {
                        "gutenberg_id": candidate.gutenberg_id,
                        "title": candidate.title,
                        "error": "Skipped by work-length or excerpt-quality filters",
                        "failed_at": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            work_record, excerpts, embedding_inputs = result
            new_works.append(work_record)
            new_excerpts.extend(excerpts)
            new_embedding_inputs.extend(embedding_inputs)
            print(
                f"Added {candidate.gutenberg_id}: {candidate.title} "
                f"({work_record['excerpt_count']} excerpts, "
                f"{len(new_works)}/{args.target_new_works} new works)",
                flush=True,
            )
            if args.download_delay > 0 and work_record.get("source_url") != "local-cache":
                time.sleep(args.download_delay)

    write_jsonl(works_path, [*existing_works, *new_works])
    write_jsonl(excerpts_path, [*existing_excerpts, *new_excerpts])
    write_jsonl(embedding_inputs_path, [*existing_embedding_inputs, *new_embedding_inputs])
    write_jsonl(failures_path, [*existing_failures, *failures])
    clear_processed_corpus_cache()

    print(
        f"Corpus now has {len(existing_works) + len(new_works)} works and "
        f"{len(existing_excerpts) + len(new_excerpts)} excerpts."
    )
    print(f"Added {len(failures)} new failures/skips to {failures_path}.")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                records.append(json.loads(line))
    return records


if __name__ == "__main__":
    main()
