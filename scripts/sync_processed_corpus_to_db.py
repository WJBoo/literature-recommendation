#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert


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
    batch_size: int = 1_000,
) -> dict[str, int]:
    await init_database()

    work_records = read_jsonl(works_path)
    excerpt_records = read_jsonl(excerpts_path)

    if settings.database_url.startswith("postgresql"):
        works_by_external_id = await upsert_work_records(work_records, batch_size=batch_size)
        synced_excerpts = await upsert_excerpt_records(
            excerpt_records,
            works_by_external_id=works_by_external_id,
            batch_size=batch_size,
        )
    else:
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


async def upsert_work_records(
    records: list[dict[str, Any]],
    *,
    batch_size: int,
) -> dict[str, int]:
    works_by_external_id: dict[str, int] = {}
    total = len(records)
    async with async_session() as session:
        for batch_start, batch in batched(records, batch_size):
            values = [work_values(record) for record in batch]
            statement = pg_insert(Work).values(values)
            update_columns = {
                "source": statement.excluded.source,
                "source_id": statement.excluded.source_id,
                "gutenberg_id": statement.excluded.gutenberg_id,
                "title": statement.excluded.title,
                "author": statement.excluded.author,
                "language": statement.excluded.language,
                "form": statement.excluded.form,
                "subjects": statement.excluded.subjects,
                "bookshelves": statement.excluded.bookshelves,
                "source_url": statement.excluded.source_url,
                "raw_path": statement.excluded.raw_path,
                "clean_path": statement.excluded.clean_path,
                "source_metadata": statement.excluded.source_metadata,
                "updated_at": func.now(),
            }
            result = await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[Work.external_id],
                    set_=update_columns,
                ).returning(Work.external_id, Work.id)
            )
            works_by_external_id.update(
                {str(external_id): int(work_id) for external_id, work_id in result.all()}
            )
            await session.commit()
            print(
                f"Synced works {min(batch_start + len(batch), total)}/{total}.",
                flush=True,
            )
    return works_by_external_id


async def upsert_excerpt_records(
    records: list[dict[str, Any]],
    *,
    works_by_external_id: dict[str, int],
    batch_size: int,
) -> int:
    synced_excerpts = 0
    total = len(records)
    async with async_session() as session:
        for batch_start, batch in batched(records, batch_size):
            values = []
            for record in batch:
                work_id = works_by_external_id.get(record["work_id"])
                if work_id is None:
                    raise ValueError(f"Excerpt references unknown work_id: {record['work_id']}")
                values.append(excerpt_values(record, work_id=work_id))

            statement = pg_insert(Excerpt).values(values)
            update_columns = {
                "work_id": statement.excluded.work_id,
                "excerpt_index": statement.excluded.excerpt_index,
                "title": statement.excluded.title,
                "text": statement.excluded.text,
                "chunk_type": statement.excluded.chunk_type,
                "word_count": statement.excluded.word_count,
                "start_offset": statement.excluded.start_offset,
                "end_offset": statement.excluded.end_offset,
                "embedding_model": statement.excluded.embedding_model,
                "source_metadata": statement.excluded.source_metadata,
                "updated_at": func.now(),
            }
            result = await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[Excerpt.external_id],
                    set_=update_columns,
                ).returning(Excerpt.external_id, Excerpt.id)
            )
            excerpt_ids_by_external_id = {
                str(external_id): int(excerpt_id) for external_id, excerpt_id in result.all()
            }

            excerpt_ids = list(excerpt_ids_by_external_id.values())
            if excerpt_ids:
                await session.execute(
                    delete(ExcerptClassification).where(
                        ExcerptClassification.excerpt_id.in_(excerpt_ids)
                    )
                )

            classification_values = classification_records(batch, excerpt_ids_by_external_id)
            for classification_batch in chunked(classification_values, 5_000):
                classification_statement = pg_insert(ExcerptClassification).values(
                    classification_batch
                )
                await session.execute(
                    classification_statement.on_conflict_do_nothing(
                        index_elements=[
                            ExcerptClassification.excerpt_id,
                            ExcerptClassification.label_type,
                            ExcerptClassification.label,
                        ]
                    )
                )

            await session.commit()
            synced_excerpts += len(batch)
            print(
                f"Synced excerpts {min(batch_start + len(batch), total)}/{total}.",
                flush=True,
            )
    return synced_excerpts


def work_values(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "external_id": record["id"],
        "source": "gutenberg",
        "source_id": str(record["gutenberg_id"]),
        "gutenberg_id": str(record["gutenberg_id"]),
        "title": record["title"],
        "author": display_author(record.get("author")),
        "language": record.get("language", "en"),
        "form": record.get("form", "unknown"),
        "subjects": record.get("subjects", []),
        "bookshelves": record.get("bookshelves", []),
        "source_url": record.get("source_url"),
        "raw_path": record.get("raw_path"),
        "clean_path": record.get("clean_path"),
        "source_metadata": {
            "clean_word_count": record.get("clean_word_count"),
            "excerpt_count": record.get("excerpt_count"),
            "total_chunk_count": record.get("total_chunk_count"),
            "quality_filtered_chunk_count": record.get("quality_filtered_chunk_count"),
            "canonical_title": record.get("canonical_title"),
            "canonical_author": canonical_author(record.get("author")),
            "raw_author": record.get("author"),
            "processed_at": record.get("processed_at"),
        },
    }


def excerpt_values(record: dict[str, Any], *, work_id: int) -> dict[str, Any]:
    return {
        "external_id": record["id"],
        "work_id": work_id,
        "excerpt_index": int(record["excerpt_index"]),
        "title": record.get("title"),
        "text": record["text"],
        "chunk_type": record["chunk_type"],
        "word_count": int(record["word_count"]),
        "start_offset": record.get("start_offset"),
        "end_offset": record.get("end_offset"),
        "embedding_model": settings.embedding_model,
        "source_metadata": {
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
        },
    }


def classification_records(
    excerpt_records: list[dict[str, Any]],
    excerpt_ids_by_external_id: dict[str, int],
) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for record in excerpt_records:
        excerpt_id = excerpt_ids_by_external_id.get(record["id"])
        if excerpt_id is None:
            continue
        for label in record.get("labels", []):
            values.append(
                {
                    "excerpt_id": excerpt_id,
                    "label_type": label["label_type"],
                    "label": label["label"],
                    "source": "rule",
                    "confidence": None,
                    "evidence": label.get("evidence"),
                }
            )
    return values


def batched(records: list[dict[str, Any]], batch_size: int) -> list[tuple[int, list[dict[str, Any]]]]:
    safe_batch_size = max(1, batch_size)
    return [
        (index, records[index : index + safe_batch_size])
        for index in range(0, len(records), safe_batch_size)
    ]


def chunked(records: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    safe_batch_size = max(1, batch_size)
    return [records[index : index + safe_batch_size] for index in range(0, len(records), safe_batch_size)]


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
    parser.add_argument("--batch-size", type=int, default=1_000)
    args = parser.parse_args()

    counts = asyncio.run(
        sync_processed_corpus(
            args.works_path,
            args.excerpts_path,
            prune=args.prune,
            batch_size=args.batch_size,
        )
    )
    print(
        f"Synced {counts['works']} works and {counts['excerpts']} excerpts. "
        f"Pruned {counts['pruned_works']} works and {counts['pruned_excerpts']} excerpts."
    )


if __name__ == "__main__":
    main()
