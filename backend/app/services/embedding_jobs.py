from __future__ import annotations

from dataclasses import dataclass

from app.services.embeddings import EmbeddingService


@dataclass(frozen=True)
class ExcerptEmbeddingInput:
    excerpt_id: int
    title: str | None
    author: str | None
    form: str
    subjects: list[str]
    text: str
    work_title: str | None = None
    section_title: str | None = None


@dataclass(frozen=True)
class ExcerptEmbeddingResult:
    excerpt_id: int
    embedding_text: str
    vector: list[float]


class EmbeddingJobService:
    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service or EmbeddingService()

    def embed_excerpt(self, excerpt: ExcerptEmbeddingInput) -> ExcerptEmbeddingResult:
        embedding_text = build_excerpt_embedding_text(excerpt)
        vector = self.embedding_service.embed_text(embedding_text)
        return ExcerptEmbeddingResult(
            excerpt_id=excerpt.excerpt_id,
            embedding_text=embedding_text,
            vector=vector,
        )


def build_excerpt_embedding_text(excerpt: ExcerptEmbeddingInput) -> str:
    metadata = [
        f"Title: {excerpt.title or 'Untitled'}",
        f"Author: {excerpt.author or 'Unknown'}",
        f"Form: {excerpt.form}",
    ]
    if excerpt.work_title and excerpt.work_title != excerpt.title:
        metadata.insert(1, f"Work: {excerpt.work_title}")
    if excerpt.section_title:
        metadata.append(f"Section: {excerpt.section_title}")
    if excerpt.subjects:
        metadata.append(f"Subjects: {', '.join(excerpt.subjects)}")
    metadata.append(f"Excerpt:\n{excerpt.text}")
    return "\n".join(metadata)
