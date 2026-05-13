from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - optional until pgvector is installed.
    Vector = None  # type: ignore[assignment]


def embedding_column() -> object:
    if Vector is not None:
        return mapped_column(Vector(settings.embedding_dimensions), nullable=False)
    return mapped_column(JSON, nullable=False)


def utcnow() -> datetime:
    return datetime.now(UTC)


class ExcerptEmbedding(Base):
    __tablename__ = "excerpt_embeddings"
    __table_args__ = (
        UniqueConstraint("excerpt_id", "model", "dimensions", name="uq_excerpt_embedding_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    excerpt_id: Mapped[int] = mapped_column(ForeignKey("excerpts.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(128), index=True)
    provider: Mapped[str] = mapped_column(String(64), default="openai", index=True)
    dimensions: Mapped[int] = mapped_column(Integer, default=settings.embedding_dimensions)
    source_text_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    embedding_text: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float]] = embedding_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    excerpt: Mapped["Excerpt"] = relationship(back_populates="embeddings")


class WorkEmbedding(Base):
    __tablename__ = "work_embeddings"
    __table_args__ = (UniqueConstraint("work_id", "model", "dimensions", name="uq_work_embedding_model"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"), index=True)
    model: Mapped[str] = mapped_column(String(128), index=True)
    provider: Mapped[str] = mapped_column(String(64), default="openai", index=True)
    dimensions: Mapped[int] = mapped_column(Integer, default=settings.embedding_dimensions)
    source_text_hash: Mapped[str | None] = mapped_column(String(128), index=True)
    embedding_text: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float]] = embedding_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserProfileEmbedding(Base):
    __tablename__ = "user_profile_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    anonymous_user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    profile_text: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(128), index=True)
    provider: Mapped[str] = mapped_column(String(64), default="openai", index=True)
    dimensions: Mapped[int] = mapped_column(Integer, default=settings.embedding_dimensions)
    embedding: Mapped[list[float]] = embedding_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
