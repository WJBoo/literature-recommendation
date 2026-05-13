from app.schemas.interactions import InteractionLogRequest
from app.services.interaction_logging import InteractionLoggingService


def test_log_event_writes_jsonl_record(tmp_path):
    event_log_path = tmp_path / "interactions.jsonl"
    service = InteractionLoggingService(event_log_path=event_log_path)

    response = service.log_event(
        InteractionLogRequest(
            event_type="like",
            anonymous_user_id="reader-1",
            session_id="session-1",
            work_id="gutenberg-1342",
            metadata={"surface": "reader"},
        )
    )

    assert response.accepted is True
    lines = event_log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert '"event_type": "like"' in lines[0]
    assert response.event_id in lines[0]


def test_summarize_counts_event_types(tmp_path):
    event_log_path = tmp_path / "interactions.jsonl"
    service = InteractionLoggingService(event_log_path=event_log_path)
    service.log_event(InteractionLogRequest(event_type="like", work_id="gutenberg-1342"))
    service.log_event(InteractionLogRequest(event_type="save", work_id="gutenberg-1342"))
    service.log_event(InteractionLogRequest(event_type="like", work_id="gutenberg-84"))

    summary = service.summarize()

    assert summary.total_events == 3
    assert summary.by_event_type == {"like": 2, "save": 1}
