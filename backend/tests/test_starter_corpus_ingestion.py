from pathlib import Path
import sys
# ruff: noqa: E402


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ingest_starter_gutenberg import trim_to_start_patterns
from app.ingestion.chunking import TextChunk, count_words
from app.ingestion.quality_gate import recommendable_chunks


def test_trim_to_start_patterns_removes_frontmatter():
    text = "TITLE PAGE\n\nCONTENTS\n\nChapter list\n\nIt was the best of times, it was the worst."

    trimmed = trim_to_start_patterns(text, [r"It was the best of times"])

    assert trimmed.startswith("It was the best of times")
    assert "CONTENTS" not in trimmed


def test_ingestion_quality_gate_filters_before_excerpt_cap():
    noisy = text_chunk(
        "Not since the famous Moon Pool have we read such a remarkable story by "
        "this well-known author. This outstanding story will be discussed time "
        "and again. Transcriber's Note: this etext was produced from a magazine."
    )
    first_literary = text_chunk(
        "The road curved below the orchard, and every branch trembled with the "
        "after-rain. Julia walked beside the stranger without speaking, aware "
        "that adventure had entered quietly, not with a trumpet, but with a "
        "question she could not yet answer."
    )
    second_literary = text_chunk(
        "At dusk the lamps were lit along the quay, and the captain folded the "
        "letter into his coat. He had promised to leave before morning, but the "
        "voice behind him made the harbor seem suddenly full of doors."
    )

    result = recommendable_chunks(
        [noisy, first_literary, second_literary],
        form="prose",
        work_title="A Test Romance",
        author="Example Author",
        subjects=["Love stories", "Adventure stories"],
        max_excerpts=2,
    )

    assert result.chunks == [first_literary, second_literary]
    assert result.rejected_count >= 1


def text_chunk(text: str) -> TextChunk:
    return TextChunk(
        text=text,
        chunk_type="prose_excerpt",
        word_count=count_words(text),
    )
