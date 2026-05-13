#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import delete, select, text


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.db.bootstrap import init_database
from app.db.session import async_session, engine
from app.ingestion.canonicalization import canonical_author, display_author
from app.models import Excerpt, ExcerptClassification, Work, WorkEmbedding


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing processed corpus file: {path}")

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                records.append(json.loads(line))
    return records


async def upsert_work(record: dict[str, Any]) -> Work:
    async with async_session() as session:
        work = await session.scalar(select(Work).where(Work.external_id == record["id"]))
        if work is None:
            work = Work(external_id=record["id"])
            session.add(work)

        work.source = "gutenberg"
        work.source_id = str(record["gutenberg_id"])
        work.gutenberg_id = str(record["gutenberg_id"])
        work.title = record["title"]
        work.author = display_author(record.get("author"))
        work.language = record.get("language", "en")
        work.form = record.get("form", "unknown")
        work.subjects = record.get("subjects", [])
        work.bookshelves = record.get("bookshelves", [])
        work.source_url = record.get("source_url")
        work.raw_path = record.get("raw_path")
        work.clean_path = record.get("clean_path")
        work.source_metadata = {
            "clean_word_count": record.get("clean_word_count"),
            "excerpt_count": record.get("excerpt_count"),
            "total_chunk_count": record.get("total_chunk_count"),
            "quality_filtered_chunk_count": record.get("quality_filtered_chunk_count"),
            "canonical_title": record.get("canonical_title"),
            "canonical_author": canonical_author(record.get("author")),
            "raw_author": record.get("author"),
            "processed_at": record.get("processed_at"),
        }

        await session.commit()
        await session.refresh(work)
        return work


async def upsert_excerpt(record: dict[str, Any], work: Work) -> None:
    async with async_session() as session:
        excerpt = await session.scalar(select(Excerpt).where(Excerpt.external_id == record["id"]))
        if excerpt is None:
            excerpt = Excerpt(external_id=record["id"])
            session.add(excerpt)

        excerpt.work_id = work.id
        excerpt.excerpt_index = int(record["excerpt_index"])
        excerpt.title = record.get("title")
        excerpt.text = record["text"]
        excerpt.chunk_type = record["chunk_type"]
        excerpt.word_count = int(record["word_count"])
        excerpt.start_offset = record.get("start_offset")
        excerpt.end_offset = record.get("end_offset")
        excerpt.embedding_model = settings.embedding_model
        excerpt.source_metadata = {
            "gutenberg_id": record.get("gutenberg_id"),
            "form": record.get("form"),
            "subjects": record.get("subjects", []),
            "work_title": record.get("work_title"),
            "display_title": record.get("display_title"),
            "section_title": record.get("section_title"),
            "section_index": record.get("section_index"),
            "section_excerpt_index": record.get("section_excerpt_index"),
            "excerpt_label": record.get("excerpt_label"),
            "canonical_work_title": record.get("canonical_work_title"),
            "canonical_author": canonical_author(record.get("author")),
            "raw_author": record.get("author"),
        }

        await session.flush()
        await session.execute(
            delete(ExcerptClassification).where(ExcerptClassification.excerpt_id == excerpt.id)
        )

        for label in record.get("labels", []):
            session.add(
                ExcerptClassification(
                    excerpt_id=excerpt.id,
                    label_type=label["label_type"],
                    label=label["label"],
                    source="rule",
                    confidence=None,
                    evidence=label.get("evidence"),
                )
            )

        await session.commit()


async def sync_processed_corpus(
    works_path: Path,
    excerpts_path: Path,
    *,
    prune: bool = False,
) -> dict[str, int]:
    await init_database()

    work_records = read_jsonl(works_path)
    excerpt_records = read_jsonl(excerpts_path)

    works_by_external_id: dict[str, Work] = {}
    for record in work_records:
        works_by_external_id[record["id"]] = await upsert_work(record)

    synced_excerpts = 0
    for record in excerpt_records:
        work = works_by_external_id.get(record["work_id"])
        if work is None:
            raise ValueError(f"Excerpt references unknown work_id: {record['work_id']}")
        await upsert_excerpt(record, work)
        synced_excerpts += 1

    pruned_excerpts = 0
    pruned_works = 0
    if prune:
        pruned_excerpts, pruned_works = await prune_missing_records(
            valid_work_external_ids={record["id"] for record in work_records},
            valid_excerpt_external_ids={record["id"] for record in excerpt_records},
        )

    await engine.dispose()
    return {
        "works": len(work_records),
        "excerpts": synced_excerpts,
        "pruned_excerpts": pruned_excerpts,
        "pruned_works": pruned_works,
    }


async def prune_missing_records(
    *,
    valid_work_external_ids: set[str],
    valid_excerpt_external_ids: set[str],
) -> tuple[int, int]:
    async with async_session() as session:
        if settings.database_url.startswith("postgresql"):
            return await prune_missing_records_with_temp_tables(
                session,
                valid_work_external_ids=valid_work_external_ids,
                valid_excerpt_external_ids=valid_excerpt_external_ids,
            )

        gutenberg_work_ids = select(Work.id).where(Work.source == "gutenberg")
        obsolete_work_ids = select(Work.id).where(
            Work.source == "gutenberg",
            Work.external_id.not_in(valid_work_external_ids),
        )
        await session.execute(delete(WorkEmbedding).where(WorkEmbedding.work_id.in_(obsolete_work_ids)))
        excerpt_result = await session.execute(
            delete(Excerpt).where(
                Excerpt.work_id.in_(gutenberg_work_ids),
                Excerpt.external_id.not_in(valid_excerpt_external_ids),
            )
        )
        work_result = await session.execute(
            delete(Work).where(
                Work.source == "gutenberg",
                Work.external_id.not_in(valid_work_external_ids),
            )
        )
        await session.commit()
        return int(excerpt_result.rowcount or 0), int(work_result.rowcount or 0)


async def prune_missing_records_with_temp_tables(
    session: Any,
    *,
    valid_work_external_ids: set[str],
    valid_excerpt_external_ids: set[str],
) -> tuple[int, int]:
    await session.execute(
        text("CREATE TEMP TABLE valid_work_external_ids (external_id text PRIMARY KEY) ON COMMIT DROP")
    )
    await session.execute(
        text("CREATE TEMP TABLE valid_excerpt_external_ids (external_id text PRIMARY KEY) ON COMMIT DROP")
    )
    await insert_temp_ids(session, "valid_work_external_ids", valid_work_external_ids)
    await insert_temp_ids(session, "valid_excerpt_external_ids", valid_excerpt_external_ids)

    await session.execute(
        text(
            "DELETE FROM work_embeddings "
            "USING works "
            "WHERE work_embeddings.work_id = works.id "
            "AND works.source = 'gutenberg' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM valid_work_external_ids valid "
            "  WHERE valid.external_id = works.external_id"
            ")"
        )
    )
    excerpt_result = await session.execute(
        text(
            "DELETE FROM excerpts "
            "USING works "
            "WHERE excerpts.work_id = works.id "
            "AND works.source = 'gutenberg' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM valid_excerpt_external_ids valid "
            "  WHERE valid.external_id = excerpts.external_id"
            ")"
        )
    )
    work_result = await session.execute(
        text(
            "DELETE FROM works "
            "WHERE works.source = 'gutenberg' "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM valid_work_external_ids valid "
            "  WHERE valid.external_id = works.external_id"
            ")"
        )
    )
    await session.commit()
    return int(excerpt_result.rowcount or 0), int(work_result.rowcount or 0)


async def insert_temp_ids(session: Any, table_name: str, ids: set[str]) -> None:
    statement = text(f"INSERT INTO {table_name} (external_id) VALUES (:external_id)")
    sorted_ids = sorted(ids)
    batch_size = 5_000
    for index in range(0, len(sorted_ids), batch_size):
        batch = sorted_ids[index : index + batch_size]
        if batch:
            await session.execute(statement, [{"external_id": value} for value in batch])


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync processed Gutenberg JSONL records into the DB.")
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
    parser.add_argument("--prune", action="store_true")
    args = parser.parse_args()

    counts = asyncio.run(
        sync_processed_corpus(args.works_path, args.excerpts_path, prune=args.prune)
    )
    print(
        f"Synced {counts['works']} works and {counts['excerpts']} excerpts. "
        f"Pruned {counts['pruned_works']} works and {counts['pruned_excerpts']} excerpts."
    )


if __name__ == "__main__":
    main()
