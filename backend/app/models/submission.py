from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserSubmission(Base):
    __tablename__ = "user_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    body: Mapped[str] = mapped_column(Text)
    form: Mapped[str] = mapped_column(String(64), default="unknown", index=True)
    visibility: Mapped[str] = mapped_column(String(32), default="private", index=True)
    word_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
