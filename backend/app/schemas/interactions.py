from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


InteractionEventType = Literal[
    "open",
    "read_start",
    "read_progress",
    "read_complete",
    "like",
    "dislike",
    "save",
    "annotate",
    "skip",
    "search",
]


class InteractionLogRequest(BaseModel):
    event_type: InteractionEventType
    user_id: int | None = None
    anonymous_user_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    work_id: str | None = Field(default=None, max_length=128)
    excerpt_id: str | None = Field(default=None, max_length=128)
    value: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InteractionLogResponse(BaseModel):
    event_id: str
    accepted: bool
    created_at: datetime


class InteractionSummaryResponse(BaseModel):
    total_events: int
    by_event_type: dict[str, int]
