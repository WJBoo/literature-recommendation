from __future__ import annotations

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    user_id: int | None = None
    genres: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    forms: list[str] = Field(default_factory=list)
    authors: list[str] = Field(default_factory=list)
    books: list[str] = Field(default_factory=list)
    max_word_count: int | None = Field(default=None, ge=1, le=5000)
    limit: int = Field(default=12, ge=1, le=50)


class RecommendedWork(BaseModel):
    id: str
    title: str
    author: str
    form: str
    reason: str
    excerpt: str
    tags: list[str] = Field(default_factory=list)
    work_title: str | None = None
    section_title: str | None = None
    excerpt_label: str | None = None


class RecommendationResponse(BaseModel):
    items: list[RecommendedWork]


class PoemOfTheDayResponse(BaseModel):
    date: str
    work: RecommendedWork


class MusicTrackResponse(BaseModel):
    id: str
    title: str
    composer: str
    performer: str
    duration: str
    tone_tags: list[str] = Field(default_factory=list)
    audio_url: str
    source_url: str
    license: str
    reason: str


class MusicCatalogResponse(BaseModel):
    tones: dict[str, str] = Field(default_factory=dict)
    composers: list[str] = Field(default_factory=list)
    tracks: list[MusicTrackResponse] = Field(default_factory=list)


class ListeningRecommendationResponse(BaseModel):
    item_id: str
    title: str
    author: str
    tone: str
    tone_label: str
    summary: str
    tracks: list[MusicTrackResponse] = Field(default_factory=list)


class ReaderNavigationItem(BaseModel):
    id: str
    title: str
    author: str
    form: str
    work_title: str | None = None


class ReaderMediaItem(BaseModel):
    id: str
    media_type: str
    data_url: str
    alt_text: str | None = None
    caption: str | None = None


class ReaderItemResponse(BaseModel):
    id: str
    work_id: str
    title: str
    author: str
    form: str
    text: str
    chunk_type: str
    word_count: int
    subjects: list[str] = Field(default_factory=list)
    work_title: str | None = None
    section_title: str | None = None
    section_excerpt_index: int | None = None
    section_excerpt_count: int | None = None
    excerpt_label: str | None = None
    media: list[ReaderMediaItem] = Field(default_factory=list)
    first_item: ReaderNavigationItem | None = None
    previous_item: ReaderNavigationItem | None = None
    next_item: ReaderNavigationItem | None = None


class AuthorWorkResponse(BaseModel):
    work_id: str
    title: str
    form: str
    excerpt_count: int
    first_excerpt_id: str
    subjects: list[str] = Field(default_factory=list)


class AuthorExcerptResponse(BaseModel):
    id: str
    title: str
    work_title: str | None = None
    form: str
    preview: str
    word_count: int
    subjects: list[str] = Field(default_factory=list)


class AuthorProfileResponse(BaseModel):
    id: str
    name: str
    forms: list[str] = Field(default_factory=list)
    subjects: list[str] = Field(default_factory=list)
    work_count: int
    excerpt_count: int
    works: list[AuthorWorkResponse] = Field(default_factory=list)
    sample_excerpts: list[AuthorExcerptResponse] = Field(default_factory=list)
    followed: bool = False


class AuthorSearchResult(BaseModel):
    id: str
    name: str
    forms: list[str] = Field(default_factory=list)
    work_count: int
    excerpt_count: int


class SearchResultResponse(BaseModel):
    authors: list[AuthorSearchResult] = Field(default_factory=list)
    works: list[RecommendedWork] = Field(default_factory=list)


class RecommendationFeedbackContext(BaseModel):
    positive_excerpt_ids: list[str] = Field(default_factory=list)
    liked_excerpt_ids: list[str] = Field(default_factory=list)
    negative_excerpt_ids: list[str] = Field(default_factory=list)
    saved_excerpt_ids: list[str] = Field(default_factory=list)
