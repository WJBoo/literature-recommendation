from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Work(Base):
    __tablename__ = "works"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_work_source_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64), default="gutenberg", index=True)
    source_id: Mapped[str | None] = mapped_column(String(128), index=True)
    gutenberg_id: Mapped[str | None] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    author: Mapped[str | None] = mapped_column(String(512), index=True)
    language: Mapped[str] = mapped_column(String(16), default="en", index=True)
    form: Mapped[str] = mapped_column(String(64), default="unknown", index=True)
    subjects: Mapped[list[str]] = mapped_column(JSON, default=list)
    bookshelves: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    raw_path: Mapped[str | None] = mapped_column(String(1024))
    clean_path: Mapped[str | None] = mapped_column(String(1024))
    source_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    excerpts: Mapped[list["Excerpt"]] = relationship(
        back_populates="work", cascade="all, delete-orphan"
    )


class Excerpt(Base):
    __tablename__ = "excerpts"
    __table_args__ = (UniqueConstraint("work_id", "excerpt_index", name="uq_work_excerpt_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), index=True)
    excerpt_index: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str | None] = mapped_column(String(512))
    text: Mapped[str] = mapped_column(Text)
    chunk_type: Mapped[str] = mapped_column(String(64), index=True)
    word_count: Mapped[int] = mapped_column(Integer)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    source_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    work: Mapped[Work] = relationship(back_populates="excerpts")
    classifications: Mapped[list["ExcerptClassification"]] = relationship(
        back_populates="excerpt", cascade="all, delete-orphan"
    )
    embeddings: Mapped[list["ExcerptEmbedding"]] = relationship(
        back_populates="excerpt", cascade="all, delete-orphan"
    )
