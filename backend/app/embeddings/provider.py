from __future__ import annotations

from collections.abc import Sequence
from hashlib import blake2b
import math
import re
from typing import Protocol


class EmbeddingProvider(Protocol):
    model: str
    dimensions: int

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed one or more strings into fixed-width vectors."""


class OpenAIEmbeddingProvider:
    """OpenAI embedding provider for production-quality semantic recommendations."""

    def __init__(self, model: str, dimensions: int) -> None:
        self.model = model
        self.dimensions = dimensions

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        from openai import OpenAI

        client = OpenAI()
        response = client.embeddings.create(
            model=self.model,
            input=list(texts),
            dimensions=self.dimensions,
            encoding_format="float",
        )
        return [item.embedding for item in response.data]


class HashingEmbeddingProvider:
    """Deterministic local fallback for tests and offline development.

    This is not the production recommendation model. It only lets the rest of the
    vector pipeline be exercised without an API key.
    """

    def __init__(self, model: str = "local-hashing-v1", dimensions: int = 384) -> None:
        self.model = model
        self.dimensions = dimensions

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"\b[\w'-]+\b", text.lower())
        for token in tokens:
            digest = blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

