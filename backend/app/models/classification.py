from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ExcerptClassification(Base):
    __tablename__ = "excerpt_classifications"
    __table_args__ = (
        UniqueConstraint("excerpt_id", "label_type", "label", name="uq_excerpt_classification"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    excerpt_id: Mapped[int] = mapped_column(ForeignKey("excerpts.id", ondelete="CASCADE"), index=True)
    label_type: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(128), index=True)
    source: Mapped[str] = mapped_column(String(64), default="rule", index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    excerpt: Mapped["Excerpt"] = relationship(back_populates="classifications")
