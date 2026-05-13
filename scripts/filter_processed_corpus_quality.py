#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.recommender.quality import assess_excerpt_quality
from app.services.processed_corpus import ProcessedExcerpt, clear_processed_corpus_cache
from app.services.processed_embeddings import clear_processed_embedding_cache
from app.services.processed_latent_factors import clear_processed_latent_factor_cache


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
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


def processed_excerpt_from_record(record: dict[str, Any]) -> ProcessedExcerpt:
    return ProcessedExcerpt(
        id=record["id"],
        work_id=record["work_id"],
        gutenberg_id=record.get("gutenberg_id", ""),
        title=record.get("display_title") or record.get("title") or "Excerpt",
        author=record.get("author") or "Unknown",
        form=record.get("form") or "unknown",
        subjects=record.get("subjects", []),
        labels=record.get("labels", []),
        text=record["text"],
        chunk_type=record["chunk_type"],
        word_count=int(record["word_count"]),
        work_title=record.get("work_title", record.get("title", "")),
        display_title=record.get("display_title", record.get("title", "")),
        section_title=record.get("section_title"),
        section_index=record.get("section_index"),
        section_excerpt_index=record.get("section_excerpt_index"),
        excerpt_label=record.get("excerpt_label"),
    )


def filter_corpus(
    *,
    works_path: Path,
    excerpts_path: Path,
    embedding_inputs_path: Path,
    embeddings_path: Path,
    write: bool,
) -> dict[str, Any]:
    works = read_jsonl(works_path)
    excerpts = read_jsonl(excerpts_path)
    embedding_inputs = read_jsonl(embedding_inputs_path)
    embeddings = read_jsonl(embeddings_path)

    removed_by_work: Counter[str] = Counter()
    removed_reasons: Counter[str] = Counter()
    kept_excerpts: list[dict[str, Any]] = []

    for record in excerpts:
        quality = assess_excerpt_quality(processed_excerpt_from_record(record))
        if quality.recommendable:
            kept_excerpts.append(record)
            continue
        removed_by_work.update([record["work_id"]])
        removed_reasons.update(quality.reasons or ("low_quality",))

    kept_excerpt_ids = {record["id"] for record in kept_excerpts}
    kept_work_ids = {record["work_id"] for record in kept_excerpts}
    kept_embedding_inputs = [
        record for record in embedding_inputs if record.get("excerpt_id") in kept_excerpt_ids
    ]
    kept_embeddings = [
        record for record in embeddings if record.get("excerpt_id") in kept_excerpt_ids
    ]

    kept_works: list[dict[str, Any]] = []
    excerpt_count_by_work = Counter(record["work_id"] for record in kept_excerpts)
    for record in works:
        work_id = record["id"]
        if work_id not in kept_work_ids:
            continue
        updated_record = dict(record)
        updated_record["excerpt_count"] = excerpt_count_by_work[work_id]
        updated_record["quality_filtered_chunk_count"] = int(
            updated_record.get("quality_filtered_chunk_count") or 0
        ) + removed_by_work[work_id]
        kept_works.append(updated_record)

    if write:
        write_jsonl(works_path, kept_works)
        write_jsonl(excerpts_path, kept_excerpts)
        write_jsonl(embedding_inputs_path, kept_embedding_inputs)
        write_jsonl(embeddings_path, kept_embeddings)
        clear_processed_corpus_cache()
        clear_processed_embedding_cache()
        clear_processed_latent_factor_cache()

    return {
        "input_works": len(works),
        "output_works": len(kept_works),
        "input_excerpts": len(excerpts),
        "output_excerpts": len(kept_excerpts),
        "input_embedding_inputs": len(embedding_inputs),
        "output_embedding_inputs": len(kept_embedding_inputs),
        "input_embeddings": len(embeddings),
        "output_embeddings": len(kept_embeddings),
        "removed_reasons": dict(removed_reasons.most_common()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Filter processed Gutenberg JSONL files using ingestion/recommendation quality rules."
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
    parser.add_argument(
        "--embeddings-path",
        type=Path,
        default=settings.processed_data_dir / "gutenberg_excerpt_embeddings.jsonl",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    counts = filter_corpus(
        works_path=args.works_path,
        excerpts_path=args.excerpts_path,
        embedding_inputs_path=args.embedding_inputs_path,
        embeddings_path=args.embeddings_path,
        write=args.write,
    )
    mode = "Wrote" if args.write else "Dry run"
    print(
        f"{mode}: {counts['input_works']} -> {counts['output_works']} works, "
        f"{counts['input_excerpts']} -> {counts['output_excerpts']} excerpts, "
        f"{counts['input_embedding_inputs']} -> {counts['output_embedding_inputs']} embedding inputs, "
        f"{counts['input_embeddings']} -> {counts['output_embeddings']} embeddings."
    )
    if counts["removed_reasons"]:
        print("Removed reasons:")
        for reason, count in counts["removed_reasons"].items():
            print(f"  {reason}: {count}")


if __name__ == "__main__":
    main()
