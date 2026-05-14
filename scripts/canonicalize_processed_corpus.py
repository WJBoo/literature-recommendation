#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.ingestion.canonicalization import (
    canonical_author,
    canonical_title,
    canonical_work_key,
    edition_noise_score,
)
from app.services.processed_corpus import clear_processed_corpus_cache
from app.services.processed_embeddings import clear_processed_embedding_cache
from app.services.processed_latent_factors import clear_processed_latent_factor_cache


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def annotate_work(record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record["canonical_title"] = canonical_title(record.get("title"))
    record["canonical_author"] = canonical_author(record.get("author"))
    record["canonical_work_key"] = canonical_work_key(record.get("author"), record.get("title"))
    return record


def annotate_excerpt(record: dict[str, Any], work: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record["canonical_work_title"] = work["canonical_title"]
    record["canonical_author"] = work["canonical_author"]
    record["canonical_work_key"] = work["canonical_work_key"]
    return record


def select_canonical_works(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    annotated = [annotate_work(record) for record in records]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in annotated:
        grouped.setdefault(record["canonical_work_key"], []).append(record)

    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for duplicates in grouped.values():
        duplicates.sort(key=work_quality_key)
        kept.append(duplicates[0])
        dropped.extend(duplicates[1:])
    kept.sort(key=work_sort_key)
    dropped.sort(key=work_sort_key)
    return kept, dropped


def work_quality_key(record: dict[str, Any]) -> tuple[int, int, int]:
    noise = edition_noise_score(record.get("title"))
    word_count = int(record.get("clean_word_count") or 0)
    gutenberg_id = numeric_gutenberg_id(record)
    return (noise, -word_count, gutenberg_id)


def work_sort_key(record: dict[str, Any]) -> tuple[int, str]:
    return (numeric_gutenberg_id(record), str(record.get("id") or ""))


def numeric_gutenberg_id(record: dict[str, Any]) -> int:
    value = str(record.get("gutenberg_id") or "").strip()
    return int(value) if value.isdigit() else 10**12


def canonicalize_corpus(
    *,
    works_path: Path,
    excerpts_path: Path,
    embedding_inputs_path: Path,
    write: bool,
) -> dict[str, int]:
    works = read_jsonl(works_path)
    excerpts = read_jsonl(excerpts_path)
    embedding_inputs = read_jsonl(embedding_inputs_path)

    kept_works, dropped_works = select_canonical_works(works)
    kept_work_ids = {record["id"] for record in kept_works}
    works_by_id = {record["id"]: record for record in kept_works}
    kept_excerpts = [
        annotate_excerpt(record, works_by_id[record["work_id"]])
        for record in excerpts
        if record.get("work_id") in kept_work_ids
    ]
    kept_excerpt_ids = {record["id"] for record in kept_excerpts}
    kept_embedding_inputs = [
        record for record in embedding_inputs if record.get("excerpt_id") in kept_excerpt_ids
    ]

    if write:
        write_jsonl(works_path, kept_works)
        write_jsonl(excerpts_path, kept_excerpts)
        write_jsonl(embedding_inputs_path, kept_embedding_inputs)
        clear_processed_corpus_cache()
        clear_processed_embedding_cache()
        clear_processed_latent_factor_cache()

    return {
        "input_works": len(works),
        "output_works": len(kept_works),
        "dropped_works": len(dropped_works),
        "input_excerpts": len(excerpts),
        "output_excerpts": len(kept_excerpts),
        "dropped_excerpts": len(excerpts) - len(kept_excerpts),
        "input_embedding_inputs": len(embedding_inputs),
        "output_embedding_inputs": len(kept_embedding_inputs),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Canonicalize processed Gutenberg titles/authors and drop duplicate editions."
    )
    parser.add_argument(
        "--works-path",
        type=Path,
        default=settings.processed_data_dir / "gutenberg_works.jsonl",
    )
    parser.add_argument(
        "--excerpts-path",
        type=Path,
        default=settings.processed_data_dir / "gutenberg_excerpts.jsonl",
    )
    parser.add_argument(
        "--embedding-inputs-path",
        type=Path,
        default=settings.processed_data_dir / "gutenberg_embedding_inputs.jsonl",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    counts = canonicalize_corpus(
        works_path=args.works_path,
        excerpts_path=args.excerpts_path,
        embedding_inputs_path=args.embedding_inputs_path,
        write=args.write,
    )
    mode = "Wrote" if args.write else "Dry run"
    print(
        f"{mode}: {counts['input_works']} -> {counts['output_works']} works, "
        f"{counts['input_excerpts']} -> {counts['output_excerpts']} excerpts, "
        f"{counts['input_embedding_inputs']} -> {counts['output_embedding_inputs']} embedding inputs. "
        f"Dropped {counts['dropped_works']} duplicate/edition works."
    )


if __name__ == "__main__":
    main()
