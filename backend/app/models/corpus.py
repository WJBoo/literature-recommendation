from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="started", index=True)
    target_works: Mapped[int | None] = mapped_column(Integer)
    selection_mode: Mapped[str | None] = mapped_column(String(64))
    embedding_provider: Mapped[str | None] = mapped_column(String(64))
    stats: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CorpusArtifact(Base):
    __tablename__ = "corpus_artifacts"
    __table_args__ = (UniqueConstraint("artifact_key", name="uq_corpus_artifact_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    artifact_key: Mapped[str] = mapped_column(String(512), index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), index=True)
    storage_backend: Mapped[str] = mapped_column(String(64), index=True)
    storage_url: Mapped[str | None] = mapped_column(String(2048))
    local_path: Mapped[str | None] = mapped_column(String(2048))
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(128), index=True)
    artifact_metadata: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
