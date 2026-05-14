#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.db.bootstrap import init_database
from app.db.session import async_session, engine
from app.embeddings.provider import EmbeddingProvider, HashingEmbeddingProvider, OpenAIEmbeddingProvider
from app.models import Excerpt, ExcerptEmbedding
from app.services.processed_embeddings import clear_processed_embedding_cache


HASHING_MODEL = "local-hashing-v1"
DEFAULT_BATCH_SIZE = 32


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing embedding input file: {path}")

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")


def text_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def chunks(records: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for index in range(0, len(records), size):
        yield records[index : index + size]


def choose_provider(provider_name: str, dimensions: int, model: str | None) -> EmbeddingProvider:
    if provider_name == "auto":
        provider_name = "openai" if os.getenv("OPENAI_API_KEY") else "hashing"

    if provider_name == "hashing":
        return HashingEmbeddingProvider(model=model or HASHING_MODEL, dimensions=dimensions)

    if provider_name == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for --provider openai.")
        return OpenAIEmbeddingProvider(
            model=model or settings.embedding_model,
            dimensions=dimensions,
        )

    raise ValueError(f"Unsupported embedding provider: {provider_name}")


def load_existing_embeddings(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {record["excerpt_id"]: record for record in read_jsonl(path)}


def should_reuse_existing(
    existing: dict[str, Any] | None,
    *,
    provider: EmbeddingProvider,
    provider_name: str,
    source_text_hash: str,
) -> bool:
    if existing is None:
        return False
    return (
        existing.get("provider") == provider_name
        and existing.get("model") == provider.model
        and existing.get("dimensions") == provider.dimensions
        and existing.get("source_text_hash") == source_text_hash
        and isinstance(existing.get("vector"), list)
    )


def build_embedding_records(
    input_records: list[dict[str, Any]],
    *,
    provider: EmbeddingProvider,
    provider_name: str,
    batch_size: int,
    existing_records: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    existing_records = existing_records or {}
    created_at = datetime.now(UTC).isoformat()
    output_records: list[dict[str, Any] | None] = [None] * len(input_records)
    pending: list[tuple[int, dict[str, Any], str]] = []
    reused = 0

    for index, record in enumerate(input_records):
        source_text_hash = text_hash(record["embedding_text"])
        existing = existing_records.get(record["excerpt_id"])
        if should_reuse_existing(
            existing,
            provider=provider,
            provider_name=provider_name,
            source_text_hash=source_text_hash,
        ):
            output_records[index] = existing
            reused += 1
            continue
        pending.append((index, record, source_text_hash))

    for batch in chunks([{"index": index, "record": record, "hash": hash_value} for index, record, hash_value in pending], batch_size):
        vectors = provider.embed_texts([item["record"]["embedding_text"] for item in batch])
        for item, vector in zip(batch, vectors, strict=True):
            record = item["record"]
            output_records[item["index"]] = {
                "schema_version": 1,
                "created_at": created_at,
                "excerpt_id": record["excerpt_id"],
                "work_id": record["work_id"],
                "provider": provider_name,
                "model": provider.model,
                "dimensions": provider.dimensions,
                "source_text_hash": item["hash"],
                "embedding_text": record["embedding_text"],
                "vector": vector,
            }

    return [record for record in output_records if record is not None], reused


async def write_embeddings_to_database(records: list[dict[str, Any]]) -> dict[str, int]:
    await init_database()
    written = 0
    missing_excerpts = 0
    batch_size = 100

    async with async_session() as session:
        excerpt_external_ids = [record["excerpt_id"] for record in records]
        excerpt_result = await session.execute(
            select(Excerpt.external_id, Excerpt.id).where(
                Excerpt.external_id.in_(excerpt_external_ids)
            )
        )
        excerpt_ids_by_external_id = {
            str(external_id): int(excerpt_id) for external_id, excerpt_id in excerpt_result.all()
        }

        for batch_start, batch in enumerate(chunks(records, batch_size)):
            values: list[dict[str, Any]] = []
            for record in batch:
                excerpt_id = excerpt_ids_by_external_id.get(record["excerpt_id"])
                if excerpt_id is None:
                    missing_excerpts += 1
                    continue
                values.append(
                    {
                        "excerpt_id": excerpt_id,
                        "model": record["model"],
                        "provider": record["provider"],
                        "dimensions": record["dimensions"],
                        "source_text_hash": record["source_text_hash"],
                        "embedding_text": record["embedding_text"],
                        "embedding": record["vector"],
                    }
                )

            if not values:
                continue

            statement = pg_insert(ExcerptEmbedding).values(values)
            update_columns = {
                "provider": statement.excluded.provider,
                "source_text_hash": statement.excluded.source_text_hash,
                "embedding_text": statement.excluded.embedding_text,
                "embedding": statement.excluded.embedding,
            }
            result = await session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_excerpt_embedding_model",
                    set_=update_columns,
                ).returning(ExcerptEmbedding.id)
            )
            written += len(result.all())
            await session.commit()
            print(
                f"Synced embeddings {min((batch_start + 1) * batch_size, len(records))}/{len(records)}.",
                flush=True,
            )

        if settings.database_url.startswith("postgresql"):
            try:
                await session.execute(text("ANALYZE excerpt_embeddings"))
                await session.commit()
            except Exception as exc:  # noqa: BLE001 - not fatal for deployment seeding.
                await session.rollback()
                print(
                    f"Skipped ANALYZE excerpt_embeddings after sync: {type(exc).__name__}: {exc}",
                    flush=True,
                )

    await engine.dispose()
    return {"written": written, "missing_excerpts": missing_excerpts}


async def load_database_excerpt_external_ids() -> set[str]:
    await init_database()
    try:
        async with async_session() as session:
            result = await session.execute(select(Excerpt.external_id))
            return {str(external_id) for external_id in result.scalars().all()}
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate one vector per processed excerpt.")
    parser.add_argument(
        "--input-path",
        type=Path,
        default=settings.processed_data_dir / "gutenberg_embedding_inputs.jsonl",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=settings.processed_data_dir / "gutenberg_excerpt_embeddings.jsonl",
    )
    parser.add_argument("--provider", choices=["auto", "hashing", "openai"], default="auto")
    parser.add_argument("--model", default=None)
    parser.add_argument("--dimensions", type=int, default=settings.embedding_dimensions)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--write-db", action="store_true")
    parser.add_argument(
        "--only-db-excerpts",
        action="store_true",
        help="Only generate/sync embeddings for excerpts already present in the database.",
    )
    args = parser.parse_args()

    provider = choose_provider(args.provider, args.dimensions, args.model)
    provider_name = args.provider
    if provider_name == "auto":
        provider_name = "openai" if os.getenv("OPENAI_API_KEY") else "hashing"

    input_records = read_jsonl(args.input_path)
    if args.only_db_excerpts:
        database_excerpt_ids = asyncio.run(load_database_excerpt_external_ids())
        input_records = [
            record for record in input_records if record["excerpt_id"] in database_excerpt_ids
        ]
        print(
            f"Filtered embedding input to {len(input_records)} excerpts present in the database.",
            flush=True,
        )
    existing_records = {} if args.force else load_existing_embeddings(args.output_path)
    output_records, reused = build_embedding_records(
        input_records,
        provider=provider,
        provider_name=provider_name,
        batch_size=args.batch_size,
        existing_records=existing_records,
    )
    write_jsonl(args.output_path, output_records)
    clear_processed_embedding_cache()

    generated = len(output_records) - reused
    print(
        f"Wrote {len(output_records)} excerpt embeddings to {args.output_path} "
        f"({generated} generated, {reused} reused, provider={provider_name}, "
        f"model={provider.model}, dimensions={provider.dimensions})."
    )

    if args.write_db:
        counts = asyncio.run(write_embeddings_to_database(output_records))
        print(
            f"Database embedding sync complete: {counts['written']} written, "
            f"{counts['missing_excerpts']} missing excerpts."
        )


if __name__ == "__main__":
    main()
