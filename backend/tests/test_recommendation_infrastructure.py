import json

from app.embeddings.provider import HashingEmbeddingProvider
from app.ingestion.canonicalization import (
    canonical_author,
    canonical_title,
    canonical_work_key,
    display_author,
)
from app.recommender.latent_factors import (
    build_latent_factor_artifact,
    build_vocabulary,
    project_text_to_latent_vector,
    recommend_from_latent_factors,
)
from app.recommender.content_based import ContentBasedRecommender, recommendation_reason
from app.recommender.profile import build_preference_profile_text
from app.recommender.quality import assess_excerpt_quality, is_recommendable_excerpt
from app.recommender.vector_math import cosine_similarity
from app.schemas.recommendations import RecommendationRequest
from app.schemas.recommendations import RecommendationFeedbackContext
from app.services.recommendations import RecommendationService
from app.services.classification import classify_excerpt
from app.services.embedding_jobs import ExcerptEmbeddingInput, build_excerpt_embedding_text
from app.services.processed_corpus import ProcessedCorpusService, ProcessedExcerpt, clean_display_text
from app.services.vector_search import FileVectorSearchService


def test_preference_profile_text_includes_user_tastes():
    profile = build_preference_profile_text(
        RecommendationRequest(
            genres=["romance"],
            themes=["exile"],
            forms=["poetry"],
            authors=["Jane Austen"],
            books=["Persuasion"],
        )
    )

    assert "romance" in profile
    assert "exile" in profile
    assert "poetry" in profile
    assert "Jane Austen" in profile
    assert "Persuasion" in profile


def test_cosine_similarity_scores_identical_vectors_highest():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_rule_based_classification_extracts_genre_and_mood():
    labels = classify_excerpt(
        "The hero crossed the sea in silence, thinking of fate and war.",
        form="poetry",
    )

    pairs = {(label.label_type, label.label) for label in labels}
    assert ("form", "poetry") in pairs
    assert ("genre", "epic") in pairs
    assert ("mood", "contemplative") in pairs


def test_hashing_embedding_provider_is_deterministic():
    provider = HashingEmbeddingProvider(dimensions=16)

    first = provider.embed_texts(["love and time"])[0]
    second = provider.embed_texts(["love and time"])[0]

    assert first == second
    assert len(first) == 16


def test_excerpt_embedding_text_preserves_metadata_context():
    embedding_text = build_excerpt_embedding_text(
        ExcerptEmbeddingInput(
            excerpt_id=1,
            title="The Sonnets",
            author="William Shakespeare",
            form="poetry",
            subjects=["love poetry"],
            text="Shall I compare thee...",
        )
    )

    assert "Title: The Sonnets" in embedding_text
    assert "Form: poetry" in embedding_text
    assert "Shall I compare thee" in embedding_text


def test_recommendation_service_returns_vector_ranked_demo_items(tmp_path):
    service = RecommendationService()
    service.recommender.processed_corpus = ProcessedCorpusService(
        excerpts_path=tmp_path / "missing.jsonl"
    )

    response = service.recommend(
        RecommendationRequest(genres=["romance"], themes=["love"], limit=2)
    )

    assert len(response.items) == 2
    assert response.items[0].title
    assert response.items[0].reason


def test_excerpt_quality_rejects_boilerplate_and_heading_fragments():
    boilerplate = processed_excerpt(
        "boilerplate",
        "Excerpt 1",
        "Author",
        "prose",
        (
            "Produced by a Project Gutenberg volunteer. CONTENTS Chapter 1 Chapter 2 "
            "Chapter 3 Chapter 4 Chapter 5. This title page has no real passage yet."
        ),
    )
    heading = processed_excerpt("heading", "Chapter I", "Author", "prose", "CHAPTER I.")
    literary = processed_excerpt(
        "literary",
        "Chapter I",
        "Author",
        "prose",
        (
            "The rain had stopped before the lamps were lit, and Clara stood beside the "
            "window wondering whether the letter had changed everything. She read the "
            "last sentence again, slowly, as if the words might rearrange themselves "
            "into mercy. Outside, the street shone with a quiet silver light."
        ),
    )
    promotional_note = processed_excerpt(
        "promo",
        "Excerpt 1",
        "Magazine Editor",
        "prose",
        (
            "Not since the famous Moon Pool have we read such a remarkable story "
            "by this well-known author. This outstanding story will be discussed "
            "time and again, and readers should not fail to read it. Transcriber's "
            "Note: this etext was produced from a magazine issue."
        ),
    )
    critical_note = processed_excerpt(
        "criticism",
        "Poem 1, Section 4",
        "Literary Critic",
        "poetry",
        (
            "The extent to which this pastoral can be regarded as dramatic will now "
            "be clear. Critics have often discussed the species and its development "
            "in literary history. Readers of Theocritus will recall similar examples, "
            "and the poem has been edited by several scholars."
        ),
    )
    front_matter = processed_excerpt(
        "front-matter",
        "Chapter I",
        "Jane Austen",
        "prose",
        (
            "PREFACE.\n\nWalt Whitman has somewhere a fine and just distinction between "
            "loving by allowance and loving with personal love. This is editorial "
            "front matter.\n\nPAGE\n\nFrontispiece iv\n\nTitle-page v\n\n"
            "Heading to Chapter I. 1\n\n\"He came down to see the place\" 2"
        ),
    )
    publisher_title_page = processed_excerpt(
        "publisher-title-page",
        "The Poetical Works of Robert Bridges",
        "Robert Bridges",
        "poetry",
        (
            "VOLUME VI: The Feast of Bacchus--Second Part of the History of Nero--Notes.\n\n"
            "VOLUME VII in preparation\n\n"
            "*** This Volume completes the Uniform Edition of Mr. Robert Bridges' Works.\n\n"
            "LONDON: SMITH, ELDER & CO., 15 WATERLOO PLACE, S.W.\n\n"
            "POETICAL WORKS\n\nOF\n\nROBERT BRIDGES"
        ),
    )

    assert not is_recommendable_excerpt(boilerplate)
    assert not is_recommendable_excerpt(heading)
    assert not is_recommendable_excerpt(promotional_note)
    assert not is_recommendable_excerpt(critical_note)
    assert not is_recommendable_excerpt(front_matter)
    assert not is_recommendable_excerpt(publisher_title_page)
    assert assess_excerpt_quality(literary).score > 0.75
    assert is_recommendable_excerpt(literary)


def test_processed_recommender_filters_low_quality_excerpts(tmp_path):
    excerpts_path = tmp_path / "excerpts.jsonl"
    records = [
        excerpt_record(
            "boilerplate",
            "Title Page",
            "Noisy Author",
            "prose",
            (
                "Produced by a volunteer. CONTENTS Chapter 1 Chapter 2 Chapter 3 "
                "Chapter 4 Chapter 5. Romance adventure love time."
            ),
            work_id="noise-work",
        ),
        excerpt_record(
            "fragment",
            "Chapter V, Excerpt 4",
            "Fragment Author",
            "prose",
            'Horace Austen."',
            work_id="fragment-work",
        ),
        excerpt_record(
            "good-prose",
            "Chapter I, Excerpt 1",
            "Careful Author",
            "prose",
            (
                "The road curved below the orchard, and every branch trembled with the "
                "after-rain. Julia walked beside the stranger without speaking, aware "
                "that adventure had entered quietly, not with a trumpet, but with a "
                "question she could not yet answer. The valley opened ahead of them."
            ),
            work_id="good-work",
            labels=[{"label_type": "genre", "label": "romance", "evidence": "romance"}],
        ),
        excerpt_record(
            "matching-poetry",
            "Poem 1",
            "Poet Author",
            "poetry",
            (
                "Love called adventure from the valley and the morning answered. "
                "The heart went gladly over river, road, and hill, singing of "
                "romance, courage, and the bright uncertainty of the day."
            ),
            work_id="poem-work",
            labels=[{"label_type": "genre", "label": "romance", "evidence": "romance"}],
        ),
    ]
    excerpts_path.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )

    recommender = ContentBasedRecommender()
    recommender.processed_corpus = ProcessedCorpusService(excerpts_path=excerpts_path)

    recommendations = recommender.recommend(
        RecommendationRequest(genres=["romance"], themes=["adventure"], forms=["prose"], limit=3)
    )

    assert [recommendation.id for recommendation in recommendations] == ["good-prose"]


def test_file_vector_search_ranks_and_excludes_jsonl_embeddings(tmp_path):
    excerpts_path = tmp_path / "excerpts.jsonl"
    embeddings_path = tmp_path / "embeddings.jsonl"
    excerpts = [
        processed_excerpt("sea-1", "Sea Voyage", "Author", "prose", "whale sea ocean mast"),
        processed_excerpt("love-1", "Love Poem", "Poet", "poetry", "rose beloved beauty time"),
    ]
    excerpts_path.write_text(
        "\n".join(
            json.dumps(
                {
                    "id": excerpt.id,
                    "work_id": excerpt.work_id,
                    "gutenberg_id": excerpt.gutenberg_id,
                    "title": excerpt.title,
                    "author": excerpt.author,
                    "form": excerpt.form,
                    "subjects": excerpt.subjects,
                    "labels": excerpt.labels,
                    "text": excerpt.text,
                    "chunk_type": excerpt.chunk_type,
                    "word_count": excerpt.word_count,
                    "work_title": excerpt.title,
                }
            )
            for excerpt in excerpts
        ),
        encoding="utf-8",
    )

    provider = HashingEmbeddingProvider(dimensions=16)
    embedding_records = []
    for excerpt in excerpts:
        vector = provider.embed_texts([excerpt.text])[0]
        embedding_records.append(
            {
                "excerpt_id": excerpt.id,
                "work_id": excerpt.work_id,
                "provider": "local",
                "model": "local-hashing-v1",
                "dimensions": 16,
                "source_text_hash": excerpt.id,
                "vector": vector,
            }
        )
    embeddings_path.write_text(
        "\n".join(json.dumps(record) for record in embedding_records),
        encoding="utf-8",
    )

    search = FileVectorSearchService(
        candidate_limit=2,
        excerpts_path=excerpts_path,
        embeddings_path=embeddings_path,
    )
    query_vector = provider.embed_texts(["whale sea ocean"])[0]

    candidates = search.nearest_excerpts(query_vector, limit=2)
    assert candidates is not None
    assert candidates[0].excerpt.id == "sea-1"

    filtered = search.nearest_excerpts(
        query_vector,
        limit=2,
        exclude_excerpt_ids={"sea-1"},
    )
    assert filtered is not None
    assert all(candidate.excerpt.id != "sea-1" for candidate in filtered)


def test_reader_item_includes_same_work_neighbors(tmp_path):
    excerpts_path = tmp_path / "excerpts.jsonl"
    records = [
        {
            "id": "excerpt-1",
            "work_id": "work-1",
            "gutenberg_id": "1",
            "title": "Chapter I, Excerpt 1",
            "author": "Author",
            "form": "prose",
            "subjects": [],
            "labels": [],
            "text": "First excerpt.",
            "chunk_type": "prose_excerpt",
            "word_count": 2,
            "work_title": "A Work",
            "section_title": "Chapter I",
            "section_index": 1,
            "section_excerpt_index": 1,
        },
        {
            "id": "excerpt-2",
            "work_id": "work-1",
            "gutenberg_id": "1",
            "title": "Chapter I, Excerpt 2",
            "author": "Author",
            "form": "prose",
            "subjects": [],
            "labels": [],
            "text": "Second excerpt.",
            "chunk_type": "prose_excerpt",
            "word_count": 2,
            "work_title": "A Work",
            "section_title": "Chapter I",
            "section_index": 1,
            "section_excerpt_index": 2,
        },
        {
            "id": "excerpt-3",
            "work_id": "work-2",
            "gutenberg_id": "2",
            "title": "Other Work",
            "author": "Author",
            "form": "prose",
            "subjects": [],
            "labels": [],
            "text": "Other excerpt.",
            "chunk_type": "prose_excerpt",
            "word_count": 2,
            "work_title": "Other Work",
        },
    ]
    excerpts_path.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )
    service = RecommendationService()
    service.processed_corpus = ProcessedCorpusService(excerpts_path=excerpts_path)

    item = service.reader_item("excerpt-1")

    assert item is not None
    assert item.first_item is None
    assert item.previous_item is None
    assert item.next_item is not None
    assert item.next_item.id == "excerpt-2"
    assert item.section_excerpt_index == 1
    assert item.section_excerpt_count == 2

    second_item = service.reader_item("excerpt-2")

    assert second_item is not None
    assert second_item.first_item is not None
    assert second_item.first_item.id == "excerpt-1"
    assert second_item.previous_item is not None
    assert second_item.previous_item.id == "excerpt-1"
    assert second_item.next_item is None
    assert second_item.section_excerpt_index == 2
    assert second_item.section_excerpt_count == 2


def test_search_author_result_uses_full_author_profile(tmp_path):
    excerpts_path = tmp_path / "excerpts.jsonl"
    records = [
        {
            "id": f"author-work-{index}",
            "work_id": f"work-{index}",
            "gutenberg_id": str(index),
            "title": f"Work {index}",
            "author": "Many Works Author",
            "form": "prose" if index % 2 else "poetry",
            "subjects": ["searchable"],
            "labels": [],
            "text": "A compact excerpt.",
            "chunk_type": "excerpt",
            "word_count": 3,
            "work_title": f"Work {index}",
        }
        for index in range(5)
    ]
    excerpts_path.write_text(
        "\n".join(json.dumps(record) for record in records),
        encoding="utf-8",
    )
    service = RecommendationService()
    service.processed_corpus = ProcessedCorpusService(excerpts_path=excerpts_path)

    response = service.search("Many Works Author", limit=1)

    assert response.authors[0].name == "Many Works Author"
    assert response.authors[0].work_count == 5
    assert response.authors[0].excerpt_count == 5
    assert response.authors[0].forms == ["poetry", "prose"]


def test_latent_factor_artifact_projects_preferences_and_ranks_excerpts():
    excerpts = [
        processed_excerpt(
            "sea-1",
            "Moby-Dick",
            "Herman Melville",
            "prose",
            "whale sea voyage ocean mast harpoon whale sea",
        ),
        processed_excerpt(
            "love-1",
            "The Sonnets",
            "William Shakespeare",
            "poetry",
            "love beauty time rose beloved love beauty",
        ),
        processed_excerpt(
            "court-1",
            "Pride and Prejudice",
            "Jane Austen",
            "prose",
            "marriage courtship manners family estate marriage",
        ),
    ]
    artifact = build_latent_factor_artifact(
        excerpts,
        factors=3,
        max_terms=100,
        min_document_frequency=1,
    )

    assert artifact["factors"] == 3
    assert len(artifact["excerpts"]) == 3
    assert artifact["excerpts"][0]["primary_factors"]

    query_vector = project_text_to_latent_vector("sea whale ocean voyage", artifact)
    assert len(query_vector) == 3

    recommendations = recommend_from_latent_factors(
        RecommendationRequest(themes=["sea", "voyage"], books=["Moby-Dick"]),
        excerpts,
        artifact,
    )
    assert recommendations[0][1].id == "sea-1"


def test_recommendation_reason_hides_raw_latent_factor_labels():
    excerpt = ProcessedExcerpt(
        id="sonnet-1",
        work_id="sonnets",
        gutenberg_id="1041",
        title="Sonnet 18",
        author="William Shakespeare",
        form="poetry",
        subjects=["poetry", "love", "time"],
        labels=[],
        text="Shall I compare thee to a summer's day?",
        chunk_type="full_poem",
        word_count=8,
        work_title="Shakespeare's Sonnets",
        section_title="Sonnet 18",
    )

    reason = recommendation_reason(
        1.0,
        excerpt,
        RecommendationRequest(forms=["poetry"], themes=["love"]),
        RecommendationFeedbackContext(),
        "Matches latent factor: poetry, all, love, time",
    )

    assert "latent factor" not in reason.lower()
    assert "all, love, time" not in reason
    assert "poetry" in reason or "love" in reason


def test_recommendation_titles_are_book_first_for_prose_and_poem_first_for_poetry():
    prose_one = ProcessedExcerpt(
        id="austen-1",
        work_id="austen-work",
        gutenberg_id="1342",
        title="Chapter 1, Excerpt 1",
        author="Jane Austen",
        form="prose",
        subjects=[],
        labels=[{"label_type": "genre", "label": "romance"}],
        text="Elizabeth walked through the room with lively thought and feeling.",
        chunk_type="prose_excerpt",
        word_count=90,
        work_title="Pride and Prejudice",
    )
    prose_two = ProcessedExcerpt(
        id="austen-2",
        work_id="austen-work",
        gutenberg_id="1342",
        title="Chapter 2, Excerpt 1",
        author="Jane Austen",
        form="prose",
        subjects=[],
        labels=[{"label_type": "genre", "label": "romance"}],
        text="Darcy considered the room and the conversation in silence.",
        chunk_type="prose_excerpt",
        word_count=90,
        work_title="Pride and Prejudice",
    )
    poem = ProcessedExcerpt(
        id="sonnet-18",
        work_id="sonnets",
        gutenberg_id="1041",
        title="Sonnet 18",
        author="William Shakespeare",
        form="poetry",
        subjects=[],
        labels=[{"label_type": "genre", "label": "romance"}],
        text="Shall I compare thee to a summer's day?",
        chunk_type="full_poem",
        word_count=80,
        work_title="Shakespeare's Sonnets",
    )

    recommendations = ContentBasedRecommender()._diversified_recommendations(
        [(1.0, prose_one, None), (0.9, prose_two, None), (0.8, poem, None)],
        RecommendationRequest(genres=["romance"], limit=5),
        RecommendationFeedbackContext(),
    )

    assert [item.id for item in recommendations] == ["austen-1", "sonnet-18"]
    assert recommendations[0].title == "Pride and Prejudice"
    assert recommendations[1].title == "Sonnet 18"


def test_latent_vocabulary_filters_metadata_noise():
    excerpts = [
        processed_excerpt(
            "one",
            "A Chapter",
            "Editor, 1820-1900 [Editor]",
            "prose",
            (
                "chapter translated editor edition poetry prose contents transcriber "
                "prepared moon silver longing"
            ),
        ),
        processed_excerpt(
            "two",
            "Another Chapter",
            "Translator, 1820-1900 [Translator]",
            "prose",
            (
                "chapter translated editor edition poetry prose contents transcriber "
                "prepared moon silver dream"
            ),
        ),
    ]

    artifact = build_latent_factor_artifact(
        excerpts,
        factors=2,
        max_terms=20,
        min_document_frequency=1,
    )

    assert "chapter" not in artifact["vocabulary"]
    assert "translated" not in artifact["vocabulary"]
    assert "editor" not in artifact["vocabulary"]
    assert "contents" not in artifact["vocabulary"]
    assert "transcriber" not in artifact["vocabulary"]
    assert "moon" in artifact["vocabulary"]


def test_latent_vocabulary_filters_names_and_common_filler():
    single_work_vocabulary = build_vocabulary(
        [
            "jourdain moon",
            "jourdain silver",
            "jourdain bright",
            "jourdain evening",
        ],
        work_ids=["moliere"] * 4,
        max_terms=20,
        min_document_frequency=1,
    )
    assert "jourdain" not in single_work_vocabulary

    large_corpus_documents = [
        "commonword raretheme raretheme" if index < 2 else "commonword"
        for index in range(40)
    ] + ["quietpassage" for _ in range(80)]
    large_corpus_vocabulary = build_vocabulary(
        large_corpus_documents,
        work_ids=[f"work-{index}" for index, _ in enumerate(large_corpus_documents)],
        max_terms=20,
        min_document_frequency=1,
    )
    assert "commonword" not in large_corpus_vocabulary
    assert "raretheme" in large_corpus_vocabulary


def test_quality_rejects_index_pages_and_display_cleaner_strips_markup():
    index_like = processed_excerpt(
        "index",
        "Index",
        "Editor",
        "prose",
        (
            "Nay, 730\nPride and Prejudice, 42\nLondon, 99\nElizabeth Bennet, 120\n"
            "Darcy, 121\nPublisher, 5"
        ),
    )

    assert not is_recommendable_excerpt(index_like)
    assert clean_display_text("_Nay_, she answered with courage.") == "Nay, she answered with courage."


def test_display_cleaner_trims_mixed_table_of_contents_prefix():
    text = (
        "PAGE\n\nFrontispiece iv\n\nTitle-page v\n\nHeading to Chapter I. 1\n\n"
        "\"He came down to see the place\" 2\n\nThe End 476\n\n"
        "It is a truth universally acknowledged, that a single man in possession "
        "of a good fortune must be in want of a wife."
    )

    assert clean_display_text(text).startswith("It is a truth universally acknowledged")


def test_canonical_work_keys_group_edition_variants():
    plain = canonical_work_key(
        "Twain, Mark, 1835-1910",
        "Adventures of Huckleberry Finn",
    )
    edition = canonical_work_key(
        "Twain, Mark, 1835-1910 [Author]",
        "The Adventures of Huckleberry Finn (Tom Sawyer's Comrade)",
    )

    assert plain == edition
    assert display_author(
        "Homer, 751?BCE-651?BCE, Pope, Alexander, 1688-1744 [Translator]"
    ) == "Homer"
    assert display_author("Shakespeare, William, 1564-1616 [Editor]") == "William Shakespeare"
    assert canonical_author("Shakespeare, William, 1564-1616 [Editor]") == "william shakespeare"
    assert (
        canonical_author(
            "Williamson, Jack, 1908-2006, Paul, Frank R. (Frank Rudolph), "
            "1884-1963 [Illustrator]"
        )
        == "jack williamson"
    )
    assert canonical_title("The Complete Works of William Shakespeare") == (
        "complete works of william shakespeare"
    )
    assert canonical_title("Alice's Adventures in Wonderland Illustrated by Arthur Rackham") == (
        "alice s adventures in wonderland"
    )


def processed_excerpt(
    excerpt_id: str,
    title: str,
    author: str,
    form: str,
    text: str,
) -> ProcessedExcerpt:
    return ProcessedExcerpt(
        id=excerpt_id,
        work_id=f"{excerpt_id}-work",
        gutenberg_id="0",
        title=title,
        author=author,
        form=form,
        subjects=[],
        labels=[],
        text=text,
        chunk_type="excerpt",
        word_count=len(text.split()),
    )


def excerpt_record(
    excerpt_id: str,
    title: str,
    author: str,
    form: str,
    text: str,
    *,
    work_id: str,
    labels: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "id": excerpt_id,
        "work_id": work_id,
        "gutenberg_id": "0",
        "title": title,
        "author": author,
        "form": form,
        "subjects": [],
        "labels": labels or [],
        "text": text,
        "chunk_type": "excerpt",
        "word_count": len(text.split()),
        "work_title": title,
    }
