from collections import Counter
from collections.abc import Iterable
import hashlib
import re

from app.embeddings.provider import HashingEmbeddingProvider
from app.core.config import settings
from app.ingestion.canonicalization import canonical_author, canonical_work_key
from app.recommender.latent_factors import latent_match_reason
from app.recommender.profile import build_preference_profile_text
from app.recommender.quality import (
    assess_excerpt_quality,
    quality_score_adjustment_from_assessment,
)
from app.recommender.vector_math import cosine_similarity
from app.schemas.recommendations import (
    RecommendationFeedbackContext,
    RecommendationRequest,
    RecommendedWork,
)
from app.services.embedding_jobs import ExcerptEmbeddingInput, build_excerpt_embedding_text
from app.services.processed_corpus import ProcessedCorpusService, ProcessedExcerpt
from app.services.processed_embeddings import ProcessedEmbeddingService
from app.services.processed_latent_factors import ProcessedLatentFactorService
from app.services.vector_search import DatabaseVectorSearchService, FileVectorSearchService


DEMO_LIBRARY = [
    {
        "id": "gutenberg-1342",
        "title": "Pride and Prejudice",
        "author": "Jane Austen",
        "form": "novel",
        "tags": {"romance", "satire", "manners", "classic"},
        "excerpt": "A sharp, social passage about first impressions, pride, and private judgment.",
    },
    {
        "id": "gutenberg-2701",
        "title": "Moby-Dick",
        "author": "Herman Melville",
        "form": "novel",
        "tags": {"adventure", "philosophy", "sea", "epic"},
        "excerpt": "A dense, oceanic meditation on obsession, fate, and the vastness of pursuit.",
    },
    {
        "id": "gutenberg-100",
        "title": "The Sonnets",
        "author": "William Shakespeare",
        "form": "poetry",
        "tags": {"poetry", "love", "time", "beauty"},
        "excerpt": "A lyric argument with time, beauty, memory, and devotion.",
    },
]

GENERIC_REASON_TAGS = {
    "all",
    "classic",
    "drama",
    "fiction",
    "literature",
    "novel",
    "poetry",
    "prose",
    "text",
}


class ContentBasedRecommender:
    """Content-based recommender facade.

    The current local path uses deterministic vectors so the API works without
    an OpenAI key. Once generated excerpt vectors exist, it reuses them instead
    of recomputing every candidate vector per request.
    """

    def __init__(self) -> None:
        self.demo_embedding_provider = HashingEmbeddingProvider(dimensions=settings.embedding_dimensions)
        self.processed_corpus = ProcessedCorpusService()
        self.processed_embeddings = ProcessedEmbeddingService()
        self.processed_latent_factors = ProcessedLatentFactorService()
        self.database_vector_search = DatabaseVectorSearchService()
        self.file_vector_search = FileVectorSearchService()

    def recommend(
        self,
        request: RecommendationRequest,
        feedback_context: RecommendationFeedbackContext | None = None,
    ) -> list[RecommendedWork]:
        processed_excerpts = self.processed_corpus.list_excerpts()
        if processed_excerpts:
            return self._recommend_processed_excerpts(request, processed_excerpts, feedback_context)

        return self._recommend_demo_items(request)

    async def recommend_async(
        self,
        request: RecommendationRequest,
        feedback_context: RecommendationFeedbackContext | None = None,
    ) -> list[RecommendedWork]:
        indexed_recommendations = await self._recommend_indexed_excerpts(
            request,
            feedback_context or RecommendationFeedbackContext(),
        )
        if indexed_recommendations is not None:
            return indexed_recommendations
        return self.recommend(request, feedback_context)

    async def _recommend_indexed_excerpts(
        self,
        request: RecommendationRequest,
        feedback_context: RecommendationFeedbackContext,
    ) -> list[RecommendedWork] | None:
        profile_text = build_preference_profile_text(request)
        embedding_provider = HashingEmbeddingProvider(dimensions=settings.embedding_dimensions)
        profile_vector = embedding_provider.embed_texts([profile_text])[0]
        candidate_limit = max(settings.recommendation_vector_candidate_limit, request.limit * 80)
        needs_feedback_vectors = bool(
            feedback_context.positive_excerpt_ids or feedback_context.negative_excerpt_ids
        )
        requested_forms = {form.lower() for form in request.forms}
        requested_genres = expanded_request_tags(request.genres)
        candidates = await self.database_vector_search.nearest_excerpts(
            profile_vector,
            limit=candidate_limit,
            exclude_excerpt_ids=set(feedback_context.negative_excerpt_ids),
            include_vectors=needs_feedback_vectors,
            forms=requested_forms,
            genres=requested_genres,
        )
        if candidates is None:
            candidates = self.file_vector_search.nearest_excerpts(
                profile_vector,
                limit=candidate_limit,
                exclude_excerpt_ids=set(feedback_context.negative_excerpt_ids),
                forms=requested_forms,
                genres=requested_genres,
            )
            if candidates is None:
                return None

            positive_vectors = self.file_vector_search.vectors_for_external_ids(
                set(feedback_context.positive_excerpt_ids),
                dimensions=len(profile_vector),
            )
            negative_vectors = self.file_vector_search.vectors_for_external_ids(
                set(feedback_context.negative_excerpt_ids),
                dimensions=len(profile_vector),
            )
        else:
            positive_vectors = (
                await self.database_vector_search.vectors_for_external_ids(
                    set(feedback_context.positive_excerpt_ids),
                    dimensions=len(profile_vector),
                )
                or []
            )
            negative_vectors = (
                await self.database_vector_search.vectors_for_external_ids(
                    set(feedback_context.negative_excerpt_ids),
                    dimensions=len(profile_vector),
                )
                or []
            )
        user_post_excerpts = self.processed_corpus.list_user_post_excerpts()
        if not candidates and not user_post_excerpts:
            return []

        candidate_excerpts = [candidate.excerpt for candidate in candidates]
        candidate_ids = {excerpt.id for excerpt in candidate_excerpts}
        candidate_excerpts.extend(
            excerpt for excerpt in user_post_excerpts if excerpt.id not in candidate_ids
        )
        scored = self._score_processed_excerpts(
            request,
            feedback_context,
            candidate_excerpts,
            profile_text=profile_text,
            profile_vector=profile_vector,
            embedding_provider=embedding_provider,
            vector_scores={
                candidate.excerpt.id: candidate.similarity for candidate in candidates
            },
            candidate_vectors={
                candidate.excerpt.id: candidate.vector
                for candidate in candidates
                if candidate.vector is not None
            },
            positive_vectors=positive_vectors,
            negative_vectors=negative_vectors,
        )
        return self._diversified_recommendations(scored, request, feedback_context)

    def _recommend_processed_excerpts(
        self,
        request: RecommendationRequest,
        excerpts: list[ProcessedExcerpt],
        feedback_context: RecommendationFeedbackContext | None,
    ) -> list[RecommendedWork]:
        feedback_context = feedback_context or RecommendationFeedbackContext()
        profile_text = build_preference_profile_text(request)
        stored_vectors = self.processed_embeddings.by_excerpt_id()
        vector_dimensions = self._stored_vector_dimensions(stored_vectors) or settings.embedding_dimensions
        embedding_provider = HashingEmbeddingProvider(dimensions=vector_dimensions)
        profile_vector = embedding_provider.embed_texts([profile_text])[0]
        excerpts_by_id = {excerpt.id: excerpt for excerpt in excerpts}
        positive_vectors = self._vectors_for_ids(
            set(feedback_context.positive_excerpt_ids),
            excerpts_by_id,
            stored_vectors,
            embedding_provider,
        )
        negative_vectors = self._vectors_for_ids(
            set(feedback_context.negative_excerpt_ids),
            excerpts_by_id,
            stored_vectors,
            embedding_provider,
        )
        scored = self._score_processed_excerpts(
            request,
            feedback_context,
            excerpts,
            profile_text=profile_text,
            profile_vector=profile_vector,
            stored_vectors=stored_vectors,
            embedding_provider=embedding_provider,
            positive_vectors=positive_vectors,
            negative_vectors=negative_vectors,
        )
        return self._diversified_recommendations(scored, request, feedback_context)

    def _score_processed_excerpts(
        self,
        request: RecommendationRequest,
        feedback_context: RecommendationFeedbackContext,
        excerpts: list[ProcessedExcerpt],
        *,
        profile_text: str,
        profile_vector: list[float],
        stored_vectors: dict[str, object] | None = None,
        embedding_provider: HashingEmbeddingProvider | None = None,
        vector_scores: dict[str, float] | None = None,
        candidate_vectors: dict[str, list[float]] | None = None,
        positive_vectors: list[list[float]] | None = None,
        negative_vectors: list[list[float]] | None = None,
    ) -> list[tuple[float, ProcessedExcerpt, str | None]]:
        requested_tags = {
            *expanded_request_tags(request.genres + request.themes + request.moods),
            *{form.lower() for form in request.forms},
        }
        requested_genres = expanded_request_tags(request.genres)
        requested_authors = {canonical_author(author) for author in request.authors}
        requested_books = {book.lower() for book in request.books}
        requested_forms = {form.lower() for form in request.forms}
        positive_ids = set(feedback_context.positive_excerpt_ids)
        negative_ids = set(feedback_context.negative_excerpt_ids)
        saved_ids = set(feedback_context.saved_excerpt_ids)
        latent_vectors = self.processed_latent_factors.by_excerpt_id()
        latent_factor_labels = self.processed_latent_factors.factor_labels()
        latent_query_vector = (
            self.processed_latent_factors.project_text(profile_text) if latent_vectors else []
        )
        positive_latent_vectors = [
            vector for excerpt_id, vector in latent_vectors.items() if excerpt_id in positive_ids
        ]
        negative_latent_vectors = [
            vector for excerpt_id, vector in latent_vectors.items() if excerpt_id in negative_ids
        ]
        positive_vectors = positive_vectors or []
        negative_vectors = negative_vectors or []
        stored_vectors = stored_vectors or {}
        vector_scores = vector_scores or {}
        candidate_vectors = candidate_vectors or {}
        needs_candidate_vector = bool(positive_vectors or negative_vectors)

        scored = []
        for excerpt in excerpts:
            if excerpt.id in negative_ids:
                continue
            quality = assess_excerpt_quality(excerpt)
            if not quality.recommendable:
                continue
            if request.max_word_count and excerpt.word_count > request.max_word_count:
                continue
            if requested_forms and excerpt.form.lower() not in requested_forms:
                continue
            if requested_genres and not requested_genres.intersection(excerpt.tags):
                continue
            candidate_vector = candidate_vectors.get(excerpt.id)
            vector_score = vector_scores.get(excerpt.id)
            if candidate_vector is None and (vector_score is None or needs_candidate_vector):
                if embedding_provider is None:
                    continue
                candidate_vector = self._excerpt_vector(excerpt, stored_vectors, embedding_provider)
            if vector_score is None:
                if candidate_vector is None:
                    continue
                vector_score = cosine_similarity(profile_vector, candidate_vector)
            metadata_score = len(requested_tags.intersection(excerpt.tags)) * 0.15
            if excerpt.form.lower() in requested_forms:
                metadata_score += 0.25
            if canonical_author(excerpt.author) in requested_authors:
                metadata_score += 0.35
            if any(
                book in excerpt.title.lower() or book in excerpt.work_title.lower()
                for book in requested_books
            ):
                metadata_score += 0.35

            latent_vector = latent_vectors.get(excerpt.id)
            latent_profile_score = (
                cosine_similarity(latent_query_vector, latent_vector) * 0.65
                if latent_query_vector and latent_vector
                else 0.0
            )
            latent_positive_score = (
                average_similarity(latent_vector, positive_latent_vectors) * 0.25
                if latent_vector
                else 0.0
            )
            latent_negative_score = (
                max_similarity(latent_vector, negative_latent_vectors) * 0.35
                if latent_vector
                else 0.0
            )
            latent_reason = (
                latent_match_reason(latent_query_vector, latent_vector, latent_factor_labels)
                if latent_vector
                else None
            )
            positive_score = (
                average_similarity(candidate_vector, positive_vectors) * 0.35
                if candidate_vector is not None
                else 0.0
            )
            negative_score = (
                max_similarity(candidate_vector, negative_vectors) * 0.45
                if candidate_vector is not None
                else 0.0
            )
            already_saved_penalty = 0.4 if excerpt.id in saved_ids else 0.0
            quality_adjustment = quality_score_adjustment_from_assessment(quality)
            scored.append(
                (
                    vector_score
                    + metadata_score
                    + latent_profile_score
                    + positive_score
                    + latent_positive_score
                    + quality_adjustment
                    - negative_score
                    - latent_negative_score
                    - already_saved_penalty,
                    excerpt,
                    latent_reason,
                )
            )

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return scored

    def _recommend_demo_items(self, request: RecommendationRequest) -> list[RecommendedWork]:
        requested_tags = set(request.genres + request.themes + request.moods + request.forms)
        profile_text = build_preference_profile_text(request)
        profile_vector = self.demo_embedding_provider.embed_texts([profile_text])[0]

        scored = []
        for item in DEMO_LIBRARY:
            candidate_text = self._candidate_text(item)
            candidate_vector = self.demo_embedding_provider.embed_texts([candidate_text])[0]
            vector_score = cosine_similarity(profile_vector, candidate_vector)
            metadata_score = len(requested_tags.intersection(item["tags"])) * 0.15
            if item["form"] in request.forms:
                metadata_score += 0.25
            scored.append((vector_score + metadata_score, item))

        scored.sort(key=lambda pair: pair[0], reverse=True)

        return [
            RecommendedWork(
                id=item["id"],
                title=item["title"],
                author=item["author"],
                form=item["form"],
                reason="Matches **your selected genres, forms, or themes**"
                if score > 0
                else "Based on **your literary preferences**",
                excerpt=item["excerpt"],
                tags=sorted(str(tag).title() for tag in item["tags"]),
            )
            for score, item in scored[: request.limit]
        ]

    def _candidate_text(self, item: dict[str, object]) -> str:
        tags = ", ".join(sorted(item["tags"]))  # type: ignore[arg-type]
        return (
            f"Title: {item['title']}. Author: {item['author']}. "
            f"Form: {item['form']}. Tags: {tags}. Excerpt: {item['excerpt']}"
        )

    def _processed_candidate_text(self, excerpt: ProcessedExcerpt) -> str:
        return build_excerpt_embedding_text(
            ExcerptEmbeddingInput(
                excerpt_id=0,
                title=excerpt.title,
                author=excerpt.author,
                form=excerpt.form,
                subjects=excerpt.subjects,
                text=excerpt.text,
            )
        )

    def _stored_vector_dimensions(self, stored_vectors: dict[str, object]) -> int | None:
        for stored_vector in stored_vectors.values():
            return getattr(stored_vector, "dimensions", None)
        return None

    def _excerpt_vector(
        self,
        excerpt: ProcessedExcerpt,
        stored_vectors: dict[str, object],
        embedding_provider: HashingEmbeddingProvider,
    ) -> list[float]:
        stored_embedding = stored_vectors.get(excerpt.id)
        if stored_embedding is not None:
            return stored_embedding.vector
        candidate_text = self._processed_candidate_text(excerpt)
        return embedding_provider.embed_texts([candidate_text])[0]

    def _vectors_for_ids(
        self,
        excerpt_ids: set[str],
        excerpts_by_id: dict[str, ProcessedExcerpt],
        stored_vectors: dict[str, object],
        embedding_provider: HashingEmbeddingProvider,
    ) -> list[list[float]]:
        vectors: list[list[float]] = []
        for excerpt_id in excerpt_ids:
            excerpt = excerpts_by_id.get(excerpt_id)
            if excerpt is None:
                continue
            vectors.append(self._excerpt_vector(excerpt, stored_vectors, embedding_provider))
        return vectors

    def _diversified_recommendations(
        self,
        scored: list[tuple[float, ProcessedExcerpt, str | None]],
        request: RecommendationRequest,
        feedback_context: RecommendationFeedbackContext,
    ) -> list[RecommendedWork]:
        recommendations: list[RecommendedWork] = []
        selected_ids: set[str] = set()
        author_counts: Counter[str] = Counter()
        form_counts: Counter[str] = Counter()
        length_counts: Counter[str] = Counter()
        work_counts: Counter[str] = Counter()
        unit_counts: Counter[str] = Counter()
        positive_ids = set(feedback_context.positive_excerpt_ids)
        requested_forms = {form.lower() for form in request.forms}
        requested_tags = {
            *expanded_request_tags(request.genres + request.themes + request.moods),
            *{form.lower() for form in request.forms},
        }
        requested_genres = expanded_request_tags(request.genres)
        feedback_examples = self._feedback_examples(feedback_context)

        for strict in (True, False):
            for score, excerpt, latent_reason in scored:
                if len(recommendations) >= request.limit:
                    return recommendations
                if excerpt.id in selected_ids:
                    continue
                unit_key = recommendation_unit_key(excerpt)
                if unit_counts[unit_key] >= 1:
                    continue
                if strict and excerpt.id in positive_ids:
                    continue
                if strict and requested_forms and excerpt.form.lower() not in requested_forms:
                    continue
                if strict and requested_tags and not requested_tags.intersection(excerpt.tags):
                    continue
                if requested_genres and not requested_genres.intersection(excerpt.tags):
                    continue
                if strict and not passes_diversity(
                    excerpt,
                    author_counts,
                    form_counts,
                    length_counts,
                    work_counts,
                    request.limit,
                    requested_forms,
                ):
                    continue

                selected_ids.add(excerpt.id)
                author_counts[canonical_author(excerpt.author)] += 1
                form_counts[excerpt.form] += 1
                length_counts[length_bucket(excerpt.word_count)] += 1
                work_counts[canonical_work_key(excerpt.author, excerpt.work_title or excerpt.title)] += 1
                unit_counts[unit_key] += 1
                recommendations.append(
                    RecommendedWork(
                        id=excerpt.id,
                        title=display_recommendation_title(excerpt),
                        author=excerpt.author,
                        form=excerpt.form,
                        reason=recommendation_reason(
                            score,
                            excerpt,
                            request,
                            feedback_context,
                            latent_reason,
                            feedback_examples,
                        ),
                        excerpt=excerpt.preview,
                        tags=recommendation_tags(excerpt),
                        work_title=excerpt.work_title,
                        section_title=excerpt.section_title,
                        excerpt_label=excerpt.excerpt_label,
                    )
                )

        return recommendations

    def _feedback_examples(
        self, feedback_context: RecommendationFeedbackContext
    ) -> dict[str, ProcessedExcerpt]:
        positive_ids = set(feedback_context.positive_excerpt_ids)
        if not positive_ids:
            return {}
        return {
            excerpt.id: excerpt
            for excerpt in self.processed_corpus.list_excerpts()
            if excerpt.id in positive_ids
        }


def average_similarity(vector: list[float], vectors: list[list[float]]) -> float:
    if not vectors:
        return 0.0
    return sum(cosine_similarity(vector, candidate) for candidate in vectors) / len(vectors)


def max_similarity(vector: list[float], vectors: list[list[float]]) -> float:
    if not vectors:
        return 0.0
    return max(cosine_similarity(vector, candidate) for candidate in vectors)


def passes_diversity(
    excerpt: ProcessedExcerpt,
    author_counts: Counter[str],
    form_counts: Counter[str],
    length_counts: Counter[str],
    work_counts: Counter[str],
    limit: int,
    requested_forms: set[str] | None = None,
) -> bool:
    requested_forms = requested_forms or set()
    author_cap = 1 if limit <= 8 else 2 if limit <= 16 else 3
    form_cap = max(3, int(limit * 0.65))
    length_cap = max(3, int(limit * 0.65))
    if work_counts[canonical_work_key(excerpt.author, excerpt.work_title or excerpt.title)] >= 1:
        return False
    if author_counts[canonical_author(excerpt.author)] >= author_cap:
        return False
    if excerpt.form.lower() not in requested_forms and form_counts[excerpt.form] >= form_cap:
        return False
    if length_counts[length_bucket(excerpt.word_count)] >= length_cap:
        return False
    return True


def recommendation_unit_key(excerpt: ProcessedExcerpt) -> str:
    work_key = canonical_work_key(excerpt.author, excerpt.work_title or excerpt.title)
    if excerpt.form.lower() == "poetry":
        return f"poem::{work_key}::{excerpt.title.lower()}"
    return f"book::{work_key}"


def display_recommendation_title(excerpt: ProcessedExcerpt) -> str:
    if excerpt.form.lower() == "poetry":
        return excerpt.title
    return excerpt.work_title or excerpt.title


def length_bucket(word_count: int) -> str:
    if word_count < 250:
        return "short"
    if word_count < 800:
        return "medium"
    return "long"


def recommendation_reason(
    score: float,
    excerpt: ProcessedExcerpt,
    request: RecommendationRequest,
    feedback_context: RecommendationFeedbackContext,
    latent_reason: str | None = None,
    feedback_examples: dict[str, ProcessedExcerpt] | None = None,
) -> str:
    feedback_reason = recommendation_reason_from_feedback(
        excerpt,
        feedback_context,
        feedback_examples or {},
    )
    if feedback_reason:
        return feedback_reason

    requested_authors = {canonical_author(author) for author in request.authors}
    author_match = canonical_author(excerpt.author) in requested_authors
    book_match = any(
        book.lower() in excerpt.title.lower() or book.lower() in excerpt.work_title.lower()
        for book in request.books
    )
    requested_tags = {
        tag.lower()
        for tag in request.genres + request.themes + request.moods + request.forms
    }
    matched_tags = sorted(requested_tags.intersection(excerpt.tags))
    displayed_tags = [
        tag for tag in matched_tags if tag.lower().strip() not in GENERIC_REASON_TAGS
    ] or matched_tags
    matched_tag_text = format_bold_list(displayed_tags[:3])
    if author_match and matched_tags:
        author_label = bold_reason_label(excerpt.author)
        return reason_variant(
            excerpt,
            "author-tags",
            [
                f"Pairs {author_label} with your interest in {matched_tag_text}",
                f"Because {author_label} and {matched_tag_text} both fit your profile",
                f"Draws on {author_label} plus the {matched_tag_text} thread in your tastes",
            ],
        )
    if book_match and matched_tags:
        work_title = excerpt.work_title or excerpt.title
        work_label = bold_reason_label(work_title)
        return reason_variant(
            excerpt,
            "book-tags",
            [
                f"From {work_label}, tuned to {matched_tag_text}",
                f"Connects {work_label} with your {matched_tag_text} preferences",
                f"Pulled from {work_label} because {matched_tag_text} is active in your profile",
            ],
        )
    if author_match:
        author_label = bold_reason_label(excerpt.author)
        return reason_variant(
            excerpt,
            "author",
            [
                f"Because you already named {author_label}",
                f"More from {author_label}, one of your preferred writers",
                f"Selected through your author preference for {author_label}",
            ],
        )
    if book_match:
        work_title = excerpt.work_title or excerpt.title
        work_label = bold_reason_label(work_title)
        return reason_variant(
            excerpt,
            "book",
            [
                f"From {work_label}, a work in your preferences",
                f"Returns to {work_label} from your reading profile",
                f"Because {work_label} is already on your preference map",
            ],
        )
    if matched_tags:
        return reason_variant(
            excerpt,
            "tags",
            [
                f"Recommended for your interest in {matched_tag_text}",
                f"Fits the {matched_tag_text} pattern in your preferences",
                f"Picked up from your {matched_tag_text} signals",
                f"Leans into the {matched_tag_text} side of your reading profile",
            ],
        )
    if latent_reason:
        latent_label = latent_reason_label(latent_reason)
        latent_label = bold_reason_label(latent_label)
        return reason_variant(
            excerpt,
            "latent",
            [
                f"Semantically close to your {latent_label} reading pattern",
                f"Nearby in the latent space around {latent_label}",
                f"Recommended through a latent {latent_label} similarity",
            ],
        )
    if author_match:
        return "Matches **an author in your preferences**"
    if book_match:
        return "Matches **a work in your preferences**"
    if score > 0:
        return reason_variant(
            excerpt,
            "profile",
            [
                "Based on **your literary preferences**",
                "A close content match for **your current taste profile**",
                "Recommended from **your preference vector**",
            ],
        )
    return "Adds **variety** to your recommendations"


def recommendation_reason_from_feedback(
    excerpt: ProcessedExcerpt,
    feedback_context: RecommendationFeedbackContext,
    feedback_examples: dict[str, ProcessedExcerpt],
) -> str | None:
    positive_ids = set(feedback_context.positive_excerpt_ids)
    if not positive_ids or excerpt.id in positive_ids:
        return None

    best_example = best_feedback_example(excerpt, feedback_examples.values())
    if best_example is None:
        tags = display_reason_tags(excerpt)
        if tags:
            tag_text = format_bold_list(tags[:2])
            return reason_variant(
                excerpt,
                "feedback-tags",
                [
                    f"Shares {tag_text} signals with pieces you liked or saved",
                    f"Extends your liked/saved pattern toward {tag_text}",
                    f"Recommended from the {tag_text} side of your feedback",
                ],
            )
        form_label = bold_reason_label(excerpt.form)
        return f"Another {form_label} selection shaped by your likes and saves"

    signal = feedback_signal_label(best_example.id, feedback_context)
    source_title = short_title(best_example.work_title or best_example.title)
    source_label = bold_reason_label(source_title)
    shared_tags = display_shared_tags(excerpt, best_example)
    if canonical_author(excerpt.author) == canonical_author(best_example.author):
        author_label = bold_reason_label(excerpt.author)
        form_label = bold_reason_label(excerpt.form)
        return reason_variant(
            excerpt,
            "feedback-author",
            [
                f"More {form_label} by {author_label}, after {source_label}",
                f"Because you {signal} {source_label}, here is more {author_label}",
                f"Follows your {signal} signal from {source_label} back to {author_label}",
            ],
        )
    if shared_tags:
        shared_tag_text = format_bold_list(shared_tags[:2])
        return reason_variant(
            excerpt,
            "feedback-shared-tags",
            [
                f"Shares {shared_tag_text} with {source_label}, which you {signal}",
                f"Because {source_label} carried {shared_tag_text}",
                f"Extends the {shared_tag_text} pattern from {source_label}",
                f"Similar signals to {source_label}: {shared_tag_text}",
            ],
        )
    if excerpt.form.lower() == best_example.form.lower():
        form_label = bold_reason_label(excerpt.form)
        return reason_variant(
            excerpt,
            "feedback-form",
            [
                f"Another {form_label} selection after {source_label}",
                f"Because you {signal} {source_label}, this keeps the {form_label} mode",
                f"Follows the form of {source_label} with more {form_label}",
            ],
        )
    return reason_variant(
        excerpt,
        "feedback-language",
        [
            f"Close in language to {source_label}, which you {signal}",
            f"Recommended from the stylistic neighborhood of {source_label}",
            f"Carries a similar language profile to {source_label}",
        ],
    )


def best_feedback_example(
    excerpt: ProcessedExcerpt, examples: Iterable[ProcessedExcerpt]
) -> ProcessedExcerpt | None:
    best: tuple[int, ProcessedExcerpt] | None = None
    for example in examples:
        score = feedback_example_score(excerpt, example)
        if best is None or score > best[0]:
            best = (score, example)
    return best[1] if best else None


def feedback_example_score(excerpt: ProcessedExcerpt, example: ProcessedExcerpt) -> int:
    shared_tags = topical_tags(excerpt).intersection(topical_tags(example))
    score = len(shared_tags)
    if canonical_author(excerpt.author) == canonical_author(example.author):
        score += 5
    if excerpt.form.lower() == example.form.lower():
        score += 3
    if canonical_work_key(excerpt.author, excerpt.work_title or excerpt.title) == canonical_work_key(
        example.author,
        example.work_title or example.title,
    ):
        score += 2
    return score


def feedback_signal_label(
    excerpt_id: str, feedback_context: RecommendationFeedbackContext
) -> str:
    if excerpt_id in set(feedback_context.saved_excerpt_ids):
        return "saved"
    if excerpt_id in set(feedback_context.liked_excerpt_ids):
        return "liked"
    return "liked or saved"


def topical_tags(excerpt: ProcessedExcerpt) -> set[str]:
    return {
        tag
        for tag in excerpt.tags
        if tag and tag.lower().strip() not in GENERIC_REASON_TAGS and len(tag.strip()) > 2
    }


def display_shared_tags(
    excerpt: ProcessedExcerpt, example: ProcessedExcerpt
) -> list[str]:
    shared = sorted(topical_tags(excerpt).intersection(topical_tags(example)))
    return [tag.replace("_", " ") for tag in shared[:3]]


def display_reason_tags(excerpt: ProcessedExcerpt) -> list[str]:
    return [tag.lower() for tag in recommendation_tags(excerpt) if tag.lower() not in GENERIC_REASON_TAGS]


def short_title(value: str, max_length: int = 42) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= max_length:
        return cleaned
    clipped = cleaned[:max_length]
    last_space = clipped.rfind(" ")
    return f"{clipped[:last_space if last_space > 20 else max_length].strip()}..."


def reason_variant(excerpt: ProcessedExcerpt, salt: str, templates: list[str]) -> str:
    if not templates:
        return ""
    digest = hashlib.sha1(f"{salt}:{excerpt.id}".encode("utf-8")).hexdigest()
    return templates[int(digest[:8], 16) % len(templates)]


def clean_reason_label(value: str) -> str:
    return " ".join(value.replace("*", "").split())


def bold_reason_label(value: str) -> str:
    return f"**{clean_reason_label(value)}**"


def format_bold_list(values: list[str]) -> str:
    return format_list([bold_reason_label(value) for value in values])


def latent_reason_label(reason: str) -> str:
    _, separator, label = reason.partition(":")
    return label.strip() if separator and label.strip() else reason


def format_list(values: list[str]) -> str:
    labels = [value.replace("_", " ") for value in values if value]
    if not labels:
        return "your preferences"
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"


def expanded_request_tags(values: list[str]) -> set[str]:
    tags: set[str] = set()
    for value in values:
        lowered = value.lower().strip()
        if not lowered:
            continue
        tags.add(lowered)
        tags.update(token for token in re.findall(r"[a-z0-9]+", lowered) if len(token) > 1)
    return tags


def recommendation_tags(excerpt: ProcessedExcerpt) -> list[str]:
    tags = [excerpt.form]
    tags.extend(
        label.get("label", "")
        for label in excerpt.labels
        if label.get("label_type") in {"genre", "mood", "form"} and label.get("label")
    )
    deduped: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = tag.lower().strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(tag.replace("_", " ").title())
    return deduped[:6]
