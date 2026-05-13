#!/usr/bin/env python
from __future__ import annotations

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

    async with async_session() as session:
        for record in records:
            excerpt = await session.scalar(
                select(Excerpt).where(Excerpt.external_id == record["excerpt_id"])
            )
            if excerpt is None:
                missing_excerpts += 1
                continue

            embedding = await session.scalar(
                select(ExcerptEmbedding).where(
                    ExcerptEmbedding.excerpt_id == excerpt.id,
                    ExcerptEmbedding.model == record["model"],
                    ExcerptEmbedding.dimensions == record["dimensions"],
                )
            )
            if embedding is None:
                embedding = ExcerptEmbedding(
                    excerpt_id=excerpt.id,
                    model=record["model"],
                    dimensions=record["dimensions"],
                )
                session.add(embedding)

            embedding.provider = record["provider"]
            embedding.source_text_hash = record["source_text_hash"]
            embedding.embedding_text = record["embedding_text"]
            embedding.embedding = record["vector"]
            written += 1

        if settings.database_url.startswith("postgresql"):
            await session.execute(text("ANALYZE excerpt_embeddings"))
        await session.commit()

    await engine.dispose()
    return {"written": written, "missing_excerpts": missing_excerpts}


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
    args = parser.parse_args()

    provider = choose_provider(args.provider, args.dimensions, args.model)
    provider_name = args.provider
    if provider_name == "auto":
        provider_name = "openai" if os.getenv("OPENAI_API_KEY") else "hashing"

    input_records = read_jsonl(args.input_path)
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
