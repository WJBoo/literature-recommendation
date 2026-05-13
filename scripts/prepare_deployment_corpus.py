#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_command(command: list[str], *, dry_run: bool) -> None:
    printable = " ".join(shlex.quote(part) for part in command)
    print(f"$ {printable}")
    if dry_run:
        return
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the repeatable corpus preparation path for deployment/staging."
    )
    parser.add_argument("--target-works", type=int, default=1500)
    parser.add_argument("--selection-mode", choices=["balanced", "score"], default="balanced")
    parser.add_argument("--embedding-provider", choices=["hashing", "openai"], default="hashing")
    parser.add_argument("--latent-factors", type=int, default=32)
    parser.add_argument("--max-latent-terms", type=int, default=8000)
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--skip-quality-filter", action="store_true")
    parser.add_argument("--skip-latent", action="store_true")
    parser.add_argument("--skip-db", action="store_true")
    parser.add_argument("--sync-artifacts", action="store_true")
    parser.add_argument("--include-raw-artifacts", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.skip_ingest:
        run_command(
            [
                PYTHON,
                "scripts/ingest_bulk_gutenberg.py",
                "--target-works",
                str(args.target_works),
                "--selection-mode",
                args.selection_mode,
            ],
            dry_run=args.dry_run,
        )

    run_command([PYTHON, "scripts/canonicalize_processed_corpus.py", "--write"], dry_run=args.dry_run)

    if not args.skip_quality_filter:
        run_command([PYTHON, "scripts/filter_processed_corpus_quality.py", "--write"], dry_run=args.dry_run)

    run_command(
        [PYTHON, "scripts/generate_excerpt_embeddings.py", "--provider", args.embedding_provider],
        dry_run=args.dry_run,
    )

    if not args.skip_latent:
        run_command(
            [
                PYTHON,
                "scripts/generate_latent_factors.py",
                "--factors",
                str(args.latent_factors),
                "--max-terms",
                str(args.max_latent_terms),
            ],
            dry_run=args.dry_run,
        )

    if not args.skip_db:
        run_command([PYTHON, "scripts/init_database.py"], dry_run=args.dry_run)
        run_command([PYTHON, "scripts/sync_processed_corpus_to_db.py", "--prune"], dry_run=args.dry_run)
        run_command(
            [
                PYTHON,
                "scripts/generate_excerpt_embeddings.py",
                "--provider",
                args.embedding_provider,
                "--write-db",
            ],
            dry_run=args.dry_run,
        )

    if args.sync_artifacts:
        command = [PYTHON, "scripts/sync_corpus_artifacts_to_storage.py", "--include", "processed", "--include", "clean"]
        if args.include_raw_artifacts:
            command.extend(["--include", "raw"])
        if not args.skip_db:
            command.append("--write-db")
        run_command(command, dry_run=args.dry_run)

    run_command([PYTHON, "scripts/benchmark_recommendations.py", "--runs", "1", "--mode", "async"], dry_run=args.dry_run)


if __name__ == "__main__":
    main()
