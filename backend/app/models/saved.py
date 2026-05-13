from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class SavedFolder(Base):
    __tablename__ = "saved_folders"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_saved_folder_user_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), default="Saved", index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="saved_folders")
    saved_excerpts: Mapped[list["SavedExcerpt"]] = relationship(
        back_populates="folder", cascade="all, delete-orphan"
    )


class SavedExcerpt(Base):
    __tablename__ = "saved_excerpts"
    __table_args__ = (
        UniqueConstraint("folder_id", "saved_item_key", name="uq_saved_excerpt_folder_item"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    folder_id: Mapped[int] = mapped_column(
        ForeignKey("saved_folders.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    excerpt_id: Mapped[int] = mapped_column(ForeignKey("excerpts.id", ondelete="CASCADE"), index=True)
    work_id: Mapped[int | None] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), index=True)
    saved_item_key: Mapped[str] = mapped_column(String(180), index=True)
    saved_kind: Mapped[str] = mapped_column(String(24), default="excerpt", index=True)
    selected_text: Mapped[str | None] = mapped_column(Text)
    selection_start: Mapped[int | None] = mapped_column(Integer)
    selection_end: Mapped[int | None] = mapped_column(Integer)
    highlight_color: Mapped[str | None] = mapped_column(String(24))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    folder: Mapped[SavedFolder] = relationship(back_populates="saved_excerpts")
