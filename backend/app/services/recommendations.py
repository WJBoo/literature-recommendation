from collections.abc import Iterable

from app.recommender.content_based import ContentBasedRecommender, DEMO_LIBRARY
from app.schemas.recommendations import (
    AuthorExcerptResponse,
    AuthorProfileResponse,
    AuthorSearchResult,
    AuthorWorkResponse,
    ReaderItemResponse,
    ReaderNavigationItem,
    RecommendationFeedbackContext,
    RecommendationRequest,
    RecommendationResponse,
    RecommendedWork,
    SearchResultResponse,
)
from app.services.processed_corpus import ProcessedCorpusService, ProcessedExcerpt


class RecommendationService:
    def __init__(self) -> None:
        self.recommender = ContentBasedRecommender()
        self.processed_corpus = ProcessedCorpusService()

    def recommend(
        self,
        request: RecommendationRequest,
        feedback_context: RecommendationFeedbackContext | None = None,
    ) -> RecommendationResponse:
        items = self.recommender.recommend(request, feedback_context)
        return RecommendationResponse(items=items)

    async def recommend_async(
        self,
        request: RecommendationRequest,
        feedback_context: RecommendationFeedbackContext | None = None,
    ) -> RecommendationResponse:
        items = await self.recommender.recommend_async(request, feedback_context)
        return RecommendationResponse(items=items)

    def reader_item(self, item_id: str) -> ReaderItemResponse | None:
        processed = self.processed_corpus.find_reader_item(item_id)
        if processed:
            (
                first_item,
                previous_item,
                next_item,
                section_excerpt_count,
            ) = self._reader_context_for_processed_item(processed)
            return ReaderItemResponse(
                id=processed.id,
                work_id=processed.work_id,
                title=display_item_title(processed),
                author=processed.author,
                form=processed.form,
                text=processed.text,
                chunk_type=processed.chunk_type,
                word_count=processed.word_count,
                subjects=processed.subjects,
                work_title=processed.work_title,
                section_title=processed.section_title,
                section_excerpt_index=processed.section_excerpt_index,
                section_excerpt_count=section_excerpt_count,
                excerpt_label=processed.excerpt_label,
                media=processed.media,
                first_item=first_item,
                previous_item=previous_item,
                next_item=next_item,
            )

        for item in DEMO_LIBRARY:
            if item["id"] == item_id:
                return ReaderItemResponse(
                    id=item["id"],
                    work_id=item["id"],
                    title=item["title"],
                    author=item["author"],
                    form=item["form"],
                    text=item["excerpt"],
                    chunk_type="demo",
                    word_count=len(item["excerpt"].split()),
                    subjects=sorted(item["tags"]),
                    work_title=item["title"],
                )

        return None

    def author_profile(
        self, author_id: str, followed_author_ids: set[str] | None = None
    ) -> AuthorProfileResponse | None:
        excerpts = self.processed_corpus.excerpts_by_author(author_id)
        if not excerpts:
            return None
        followed_author_ids = followed_author_ids or set()
        author_name = excerpts[0].author
        works = author_works(excerpts)
        subjects = top_values(subject for excerpt in excerpts for subject in excerpt.subjects)
        forms = sorted({excerpt.form for excerpt in excerpts})
        samples = sorted(excerpts, key=lambda excerpt: excerpt.word_count, reverse=True)[:9]
        return AuthorProfileResponse(
            id=author_id,
            name=author_name,
            forms=forms,
            subjects=subjects[:12],
            work_count=len(works),
            excerpt_count=len(excerpts),
            works=works,
            sample_excerpts=[author_excerpt_response(excerpt) for excerpt in samples],
            followed=author_id in followed_author_ids,
        )

    def search(self, query: str, limit: int = 12) -> SearchResultResponse:
        excerpts = self.processed_corpus.search_excerpts(query, limit=limit * 4)
        author_map: dict[str, list[ProcessedExcerpt]] = {}
        works_by_id: dict[str, ProcessedExcerpt] = {}
        for excerpt in excerpts:
            author_map.setdefault(self.processed_corpus.author_id(excerpt.author), []).append(excerpt)
            works_by_id.setdefault(excerpt.work_id, excerpt)
        authors = [
            author_search_result(
                author_id,
                self.processed_corpus.excerpts_by_author(author_id) or author_excerpts,
            )
            for author_id, author_excerpts in author_map.items()
        ][:limit]
        works = [
            RecommendedWork(
                id=excerpt.id,
                title=display_item_title(excerpt),
                author=excerpt.author,
                form=excerpt.form,
                reason="Matched **your search**",
                excerpt=excerpt.preview,
                tags=[excerpt.form.title()],
                work_title=excerpt.work_title,
                section_title=excerpt.section_title,
                excerpt_label=excerpt.excerpt_label,
            )
            for excerpt in list(works_by_id.values())[:limit]
        ]
        return SearchResultResponse(authors=authors, works=works)

    def _reader_context_for_processed_item(
        self, item: ProcessedExcerpt
    ) -> tuple[
        ReaderNavigationItem | None,
        ReaderNavigationItem | None,
        ReaderNavigationItem | None,
        int | None,
    ]:
        work_excerpts = [
            excerpt
            for excerpt in self.processed_corpus.list_excerpts()
            if excerpt.work_id == item.work_id
        ]
        item_index = next(
            (index for index, excerpt in enumerate(work_excerpts) if excerpt.id == item.id),
            None,
        )
        if item_index is None:
            return None, None, None, None

        first_excerpt = work_excerpts[0] if item_index > 0 else None
        previous_excerpt = work_excerpts[item_index - 1] if item_index > 0 else None
        next_excerpt = (
            work_excerpts[item_index + 1]
            if item_index + 1 < len(work_excerpts)
            else None
        )
        return (
            navigation_item(first_excerpt),
            navigation_item(previous_excerpt),
            navigation_item(next_excerpt),
            section_excerpt_count(item, work_excerpts),
        )


def navigation_item(excerpt: ProcessedExcerpt | None) -> ReaderNavigationItem | None:
    if excerpt is None:
        return None
    return ReaderNavigationItem(
        id=excerpt.id,
        title=display_item_title(excerpt),
        author=excerpt.author,
        form=excerpt.form,
        work_title=excerpt.work_title,
    )


def section_excerpt_count(item: ProcessedExcerpt, work_excerpts: list[ProcessedExcerpt]) -> int | None:
    if item.section_excerpt_index is None:
        return None

    if item.section_index is not None:
        count = sum(
            1
            for excerpt in work_excerpts
            if excerpt.section_index == item.section_index
        )
    elif item.section_title:
        normalized_title = item.section_title.strip().lower()
        count = sum(
            1
            for excerpt in work_excerpts
            if (excerpt.section_title or "").strip().lower() == normalized_title
        )
    else:
        return None

    return count or None


def author_works(excerpts: list[ProcessedExcerpt]) -> list[AuthorWorkResponse]:
    grouped: dict[str, list[ProcessedExcerpt]] = {}
    for excerpt in excerpts:
        grouped.setdefault(excerpt.work_id, []).append(excerpt)

    works = []
    for work_excerpts in grouped.values():
        first = work_excerpts[0]
        subjects = top_values(subject for excerpt in work_excerpts for subject in excerpt.subjects)
        works.append(
            AuthorWorkResponse(
                work_id=first.work_id,
                title=first.work_title or first.title,
                form=first.form,
                excerpt_count=len(work_excerpts),
                first_excerpt_id=first.id,
                subjects=subjects[:8],
            )
        )
    return sorted(works, key=lambda work: work.title.lower())


def author_excerpt_response(excerpt: ProcessedExcerpt) -> AuthorExcerptResponse:
    return AuthorExcerptResponse(
        id=excerpt.id,
        title=display_item_title(excerpt),
        work_title=excerpt.work_title,
        form=excerpt.form,
        preview=excerpt.preview,
        word_count=excerpt.word_count,
        subjects=excerpt.subjects[:8],
    )


def display_item_title(excerpt: ProcessedExcerpt) -> str:
    if excerpt.form.lower() == "poetry":
        return excerpt.title
    return excerpt.work_title or excerpt.title


def author_search_result(
    author_id: str, excerpts: list[ProcessedExcerpt]
) -> AuthorSearchResult:
    return AuthorSearchResult(
        id=author_id,
        name=excerpts[0].author,
        forms=sorted({excerpt.form for excerpt in excerpts}),
        work_count=len({excerpt.work_id for excerpt in excerpts}),
        excerpt_count=len(excerpts),
    )


def top_values(values: Iterable[object]) -> list[str]:
    counts: dict[str, int] = {}
    for value in values:
        cleaned = str(value).strip()
        if cleaned:
            counts[cleaned] = counts.get(cleaned, 0) + 1
    return [
        value
        for value, _ in sorted(
            counts.items(), key=lambda item: (item[1], item[0].lower()), reverse=True
        )
    ]
