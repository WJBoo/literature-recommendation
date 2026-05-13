from unittest import TestCase

from app.ingestion.chunking import POEM_MAX_INTACT_WORDS, chunk_text


class ChunkingTests(TestCase):
    def test_poem_at_limit_stays_intact(self) -> None:
        poem = "word " * POEM_MAX_INTACT_WORDS

        chunks = chunk_text(poem, "poetry")

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_type, "full_poem")
        self.assertEqual(chunks[0].word_count, POEM_MAX_INTACT_WORDS)

    def test_poem_over_limit_splits(self) -> None:
        poem = "word " * (POEM_MAX_INTACT_WORDS + 1)

        chunks = chunk_text(poem, "poetry")

        self.assertEqual(len(chunks), 2)
        self.assertEqual([chunk.word_count for chunk in chunks], [POEM_MAX_INTACT_WORDS, 1])
        self.assertTrue(all(chunk.chunk_type == "poem_section" for chunk in chunks))

    def test_poetry_collection_splits_whole_poems_by_heading(self) -> None:
        poems = (
            "I\n\n"
            "First poem line one.\n"
            "First poem line two.\n\n"
            "II\n\n"
            "Second poem line one.\n"
            "Second poem line two.\n\n"
            "III\n\n"
            "Third poem line one."
        )

        chunks = chunk_text(poems, "poetry")

        self.assertEqual(len(chunks), 3)
        self.assertEqual([chunk.chunk_type for chunk in chunks], ["full_poem"] * 3)
        self.assertTrue(chunks[0].text.startswith("I"))
        self.assertEqual(chunks[0].section_title, "Poem 1")
        self.assertNotIn("II", chunks[0].text)
        self.assertTrue(chunks[1].text.startswith("II"))
        self.assertEqual(chunks[1].section_title, "Poem 2")
        self.assertNotIn("III", chunks[1].text)

    def test_poetry_collection_can_split_when_first_heading_was_trimmed(self) -> None:
        poems = (
            "First poem line one.\n"
            "First poem line two.\n\n"
            "II\n\n"
            "Second poem line one.\n"
            "Second poem line two.\n\n"
            "III\n\n"
            "Third poem line one."
        )

        chunks = chunk_text(poems, "poetry")

        self.assertEqual(len(chunks), 3)
        self.assertTrue(chunks[0].text.startswith("First poem"))
        self.assertTrue(chunks[1].text.startswith("II"))

    def test_prose_chunks_track_chapter_metadata(self) -> None:
        prose = (
            "Opening chapter paragraph.\n\n"
            "CHAPTER II.\n\n"
            "Second chapter paragraph.\n\n"
            "CHAPTER III.\n\n"
            "Third chapter paragraph."
        )

        chunks = chunk_text(prose, "prose")

        self.assertEqual([chunk.section_title for chunk in chunks], ["Chapter I", "Chapter II", "Chapter III"])
        self.assertEqual([chunk.excerpt_index_in_section for chunk in chunks], [1, 1, 1])

    def test_prose_preserves_order_around_long_paragraph(self) -> None:
        prose = "intro " * 20 + "\n\n" + "long. " * 950

        chunks = chunk_text(prose, "prose")

        self.assertEqual(chunks[0].word_count, 20)
        self.assertTrue(chunks[0].text.startswith("intro"))
