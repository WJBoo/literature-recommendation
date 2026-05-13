#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
import asyncio
from datetime import UTC, datetime
import json
import mimetypes
from pathlib import Path
import sys
from typing import Any, Iterable

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.db.bootstrap import init_database
from app.db.session import async_session, engine
from app.models import CorpusArtifact
from app.services.storage import ObjectStorageService, StorageConfigurationError


PROCESSED_ARTIFACTS = (
    "gutenberg_works.jsonl",
    "gutenberg_excerpts.jsonl",
    "gutenberg_embedding_inputs.jsonl",
    "gutenberg_excerpt_embeddings.jsonl",
    "gutenberg_excerpt_latent_factors.json",
    "gutenberg_bulk_failures.jsonl",
    "recommendation_benchmark.json",
)


def iter_artifacts(include: set[str]) -> Iterable[tuple[str, Path, Path]]:
    if "processed" in include:
        for name in PROCESSED_ARTIFACTS:
            path = settings.processed_data_dir / name
            if path.exists():
                yield "processed", path, Path(name)
        curated_dir = settings.processed_data_dir / "curated_ekphrasis"
        if curated_dir.exists():
            for path in sorted(curated_dir.rglob("*")):
                if path.is_file():
                    yield "processed", path, Path("curated_ekphrasis") / path.relative_to(curated_dir)
    if "clean" in include:
        clean_dir = settings.processed_data_dir / "gutenberg_clean"
        if clean_dir.exists():
            for path in sorted(clean_dir.rglob("*.txt")):
                yield "clean_text", path, path.relative_to(clean_dir)
    if "raw" in include:
        raw_dir = settings.gutenberg_raw_dir
        if raw_dir.exists():
            for path in sorted(raw_dir.rglob("*")):
                if path.is_file():
                    yield "raw_text", path, path.relative_to(raw_dir)


def artifact_key(artifact_type: str, relative_path: Path) -> str:
    return "/".join(
        part.strip("/")
        for part in (settings.object_storage_corpus_prefix, artifact_type, str(relative_path))
        if part
    ).replace("\\", "/")


def sync_artifacts(include: set[str], *, dry_run: bool = False) -> list[dict[str, Any]]:
    storage = ObjectStorageService()
    if storage.backend == "inline" and not dry_run:
        raise StorageConfigurationError(
            "Set MEDIA_STORAGE_BACKEND=local or MEDIA_STORAGE_BACKEND=s3 before syncing corpus artifacts."
        )

    manifest: list[dict[str, Any]] = []
    for artifact_type, path, relative_path in iter_artifacts(include):
        key = artifact_key(artifact_type, relative_path)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if dry_run:
            record = {
                "artifact_key": key,
                "artifact_type": artifact_type,
                "storage_backend": storage.backend,
                "storage_url": None,
                "local_path": str(path),
                "byte_size": path.stat().st_size,
                "sha256": None,
                "artifact_metadata": {"dry_run": True},
            }
        else:
            stored = storage.upload_bytes(path.read_bytes(), key=key, content_type=content_type)
            record = {
                "artifact_key": key,
                "artifact_type": artifact_type,
                "storage_backend": stored.backend,
                "storage_url": stored.url,
                "local_path": str(path),
                "byte_size": stored.byte_size,
                "sha256": stored.sha256,
                "artifact_metadata": {"content_type": stored.content_type},
            }
        manifest.append(record)
    return manifest


def write_manifest(records: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as target:
        for record in records:
            target.write(json.dumps(record, ensure_ascii=False) + "\n")


async def write_manifest_to_database(records: list[dict[str, Any]]) -> int:
    await init_database()
    count = 0
    async with async_session() as session:
        for record in records:
            artifact = await session.scalar(
                select(CorpusArtifact).where(CorpusArtifact.artifact_key == record["artifact_key"])
            )
            if artifact is None:
                artifact = CorpusArtifact(artifact_key=record["artifact_key"])
                session.add(artifact)
            artifact.artifact_type = record["artifact_type"]
            artifact.storage_backend = record["storage_backend"]
            artifact.storage_url = record["storage_url"]
            artifact.local_path = record["local_path"]
            artifact.byte_size = record["byte_size"]
            artifact.sha256 = record["sha256"]
            artifact.artifact_metadata = record.get("artifact_metadata", {})
            artifact.updated_at = datetime.now(UTC)
            count += 1
        await session.commit()
    await engine.dispose()
    return count


def parse_include(values: list[str]) -> set[str]:
    include = set(values or ["processed", "clean"])
    allowed = {"processed", "clean", "raw"}
    unknown = include - allowed
    if unknown:
        raise ValueError(f"Unknown artifact group(s): {', '.join(sorted(unknown))}")
    return include


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync processed/raw corpus artifacts to local or S3-compatible object storage."
    )
    parser.add_argument(
        "--include",
        action="append",
        choices=["processed", "clean", "raw"],
        help="Artifact group to sync. Repeatable. Defaults to processed + clean.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=settings.processed_data_dir / "corpus_artifacts_manifest.jsonl",
    )
    parser.add_argument("--write-db", action="store_true", help="Upsert artifact metadata into Postgres.")
    parser.add_argument("--dry-run", action="store_true", help="Print/write manifest without uploading files.")
    args = parser.parse_args()

    records = sync_artifacts(parse_include(args.include or []), dry_run=args.dry_run)
    write_manifest(records, args.manifest_path)
    db_count = 0
    if args.write_db and not args.dry_run:
        db_count = asyncio.run(write_manifest_to_database(records))
    print(
        f"Prepared {len(records)} corpus artifacts in {args.manifest_path}. "
        f"Database rows written: {db_count}."
    )


if __name__ == "__main__":
    main()
