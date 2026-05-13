from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.schemas.interactions import (
    InteractionLogRequest,
    InteractionLogResponse,
    InteractionSummaryResponse,
)


class InteractionLoggingService:
    """Append-only event logger used before the full database event pipeline exists."""

    def __init__(self, event_log_path: Path | None = None) -> None:
        self.event_log_path = event_log_path or settings.interaction_log_path

    def log_event(self, request: InteractionLogRequest) -> InteractionLogResponse:
        created_at = datetime.now(UTC)
        event_id = str(uuid4())
        record = {
            "schema_version": 1,
            "event_id": event_id,
            "created_at": created_at.isoformat(),
            **request.model_dump(mode="json"),
        }

        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.event_log_path.open("a", encoding="utf-8") as event_log:
            event_log.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")

        return InteractionLogResponse(event_id=event_id, accepted=True, created_at=created_at)

    def summarize(self) -> InteractionSummaryResponse:
        if not self.event_log_path.exists():
            return InteractionSummaryResponse(total_events=0, by_event_type={})

        counts: Counter[str] = Counter()
        total = 0
        with self.event_log_path.open("r", encoding="utf-8") as event_log:
            for line in event_log:
                if not line.strip():
                    continue
                total += 1
                record = json.loads(line)
                counts[record.get("event_type", "unknown")] += 1

        return InteractionSummaryResponse(total_events=total, by_event_type=dict(counts))

