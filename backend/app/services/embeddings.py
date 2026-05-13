from __future__ import annotations

from collections.abc import Sequence

from app.core.config import settings
from app.embeddings.provider import (
    EmbeddingProvider,
    HashingEmbeddingProvider,
    OpenAIEmbeddingProvider,
)


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self.provider = provider or self._default_provider()

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        cleaned = [text.strip() for text in texts if text.strip()]
        if not cleaned:
            return []
        return self.provider.embed_texts(cleaned)

    def embed_text(self, text: str) -> list[float]:
        vectors = self.embed_texts([text])
        if not vectors:
            return []
        return vectors[0]

    def _default_provider(self) -> EmbeddingProvider:
        if settings.embedding_provider == "hashing":
            return HashingEmbeddingProvider(dimensions=settings.embedding_dimensions)
        return OpenAIEmbeddingProvider(
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )

