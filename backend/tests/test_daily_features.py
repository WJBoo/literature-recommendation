from app.services.daily_features import is_poem_of_day_candidate
from app.services.processed_corpus import ProcessedExcerpt


def test_poem_of_day_prefers_short_non_epic_poems():
    sonnet = processed_poem(
        "sonnet-1",
        "Sonnet 18",
        "Shall I compare thee to a summer's day? Thou art more lovely and more temperate.",
    )

    assert is_poem_of_day_candidate(sonnet)


def test_poem_of_day_rejects_long_or_epic_poems():
    long_poem = processed_poem("long", "A Long Poem", "word " * 230)
    iliad_excerpt = processed_poem(
        "iliad",
        "Book I",
        "Sing, goddess, the anger of Achilles, son of Peleus.",
        work_title="The Iliad",
        subjects=["Epic poetry"],
    )

    assert not is_poem_of_day_candidate(long_poem)
    assert not is_poem_of_day_candidate(iliad_excerpt)


def processed_poem(
    excerpt_id: str,
    title: str,
    text: str,
    *,
    work_title: str = "Collected Poems",
    subjects: list[str] | None = None,
) -> ProcessedExcerpt:
    return ProcessedExcerpt(
        id=excerpt_id,
        work_id=f"{excerpt_id}-work",
        gutenberg_id="0",
        title=title,
        author="Example Poet",
        form="poetry",
        subjects=subjects or [],
        labels=[],
        text=text,
        chunk_type="poem",
        word_count=len(text.split()),
        work_title=work_title,
    )
