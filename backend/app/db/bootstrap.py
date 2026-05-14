from __future__ import annotations

from sqlalchemy import text

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine


async def init_database(*, drop_existing: bool = False) -> None:
    """Create database extension support and all SQLAlchemy-owned tables."""
    import app.models  # noqa: F401

    async with engine.begin() as connection:
        if settings.database_url.startswith("postgresql"):
            await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        if drop_existing:
            await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
        if settings.database_url.startswith("postgresql"):
            await connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS account_store_documents ("
                    "key VARCHAR(120) PRIMARY KEY, "
                    "payload JSONB NOT NULL, "
                    "updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()"
                    ")"
                )
            )
            await connection.execute(text("ALTER TABLE works ALTER COLUMN gutenberg_id TYPE VARCHAR(128)"))
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_excerpt_embeddings_embedding_cosine "
                    "ON excerpt_embeddings USING ivfflat (embedding vector_cosine_ops) "
                    "WITH (lists = 100)"
                )
            )
            await connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_excerpt_embeddings_model_dimensions "
                    "ON excerpt_embeddings (model, dimensions)"
                )
            )
