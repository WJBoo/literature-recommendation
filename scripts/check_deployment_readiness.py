#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
import asyncio
import json
from pathlib import Path
import sys

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.db.session import engine
from app.services.storage import ObjectStorageService


def line(status: str, message: str) -> dict[str, str]:
    print(f"[{status}] {message}")
    return {"status": status, "message": message}


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as source:
        return sum(1 for row in source if row.strip())


async def database_checks() -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    if not settings.database_url.startswith("postgresql"):
        checks.append(line("warn", "DATABASE_URL is not PostgreSQL; pgvector will not be used."))
        return checks
    try:
        async with engine.connect() as connection:
            vector_enabled = await connection.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            )
            checks.append(line("ok" if vector_enabled else "fail", "pgvector extension is installed."))
            counts = (await connection.execute(text(
                "SELECT "
                "(SELECT count(*) FROM works) AS works, "
                "(SELECT count(*) FROM excerpts) AS excerpts, "
                "(SELECT count(*) FROM excerpt_embeddings) AS embeddings"
            ))).mappings().one()
            checks.append(line("ok", f"database rows: {counts['works']} works, {counts['excerpts']} excerpts, {counts['embeddings']} embeddings."))
            vector_index = await connection.scalar(
                text("SELECT to_regclass('public.ix_excerpt_embeddings_embedding_cosine') IS NOT NULL")
            )
            checks.append(line("ok" if vector_index else "warn", "excerpt embedding cosine index exists."))
    except Exception as exc:  # noqa: BLE001 - readiness should report, not crash.
        checks.append(line("fail", f"database check failed: {exc}"))
    finally:
        await engine.dispose()
    return checks


def file_checks() -> list[dict[str, str]]:
    processed = settings.processed_data_dir
    works = count_jsonl(processed / "gutenberg_works.jsonl")
    excerpts = count_jsonl(processed / "gutenberg_excerpts.jsonl")
    embeddings = count_jsonl(processed / "gutenberg_excerpt_embeddings.jsonl")
    checks = [line("ok" if works else "fail", f"processed works file has {works} records.")]
    checks.append(line("ok" if excerpts else "fail", f"processed excerpts file has {excerpts} records."))
    checks.append(line("ok" if embeddings else "warn", f"processed embedding file has {embeddings} records."))
    return checks


def storage_checks() -> list[dict[str, str]]:
    storage = ObjectStorageService()
    checks = [line("ok", f"media storage backend: {storage.backend}.")]
    if storage.backend == "inline":
        checks.append(line("warn", "media is still stored inline; use local or s3 before public beta uploads."))
    elif storage.backend == "local":
        checks.append(line("ok", f"local media dir: {settings.media_upload_dir}."))
    elif storage.backend == "s3":
        missing = [
            name
            for name, value in {
                "OBJECT_STORAGE_BUCKET": settings.object_storage_bucket,
                "OBJECT_STORAGE_PUBLIC_BASE_URL": settings.object_storage_public_base_url,
            }.items()
            if not value
        ]
        checks.append(line("fail" if missing else "ok", f"object storage required settings: {', '.join(missing) if missing else 'present'}."))
    return checks


def account_store_checks() -> list[dict[str, str]]:
    backend = settings.account_store_backend.strip().lower()
    database_backed = backend in {"database", "postgres", "postgresql", "db"} or (
        backend == "auto"
        and settings.app_env.strip().lower() == "production"
        and settings.database_url.startswith("postgresql")
    )
    if database_backed:
        return [line("ok", "account store is database-backed for redeploy durability.")]
    if settings.app_env.strip().lower() == "production":
        return [
            line(
                "warn",
                "account store is file-backed in production; attach persistent storage or set ACCOUNT_STORE_BACKEND=database.",
            )
        ]
    return [line("ok", "account store is file-backed for local development.")]


async def main_async(json_output: bool) -> None:
    checks: list[dict[str, str]] = []
    checks.extend(file_checks())
    checks.extend(account_store_checks())
    checks.extend(storage_checks())
    checks.extend(await database_checks())
    if json_output:
        print(json.dumps({"checks": checks}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether the current corpus/storage/vector setup is deployment-ready.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    asyncio.run(main_async(args.json))


if __name__ == "__main__":
    main()
