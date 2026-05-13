from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path

from app.core.config import settings


@dataclass(frozen=True)
class ProcessedExcerptEmbedding:
    excerpt_id: str
    work_id: str
    provider: str
    model: str
    dimensions: int
    source_text_hash: str
    vector: list[float]


class ProcessedEmbeddingService:
    def __init__(self, embeddings_path: Path | None = None) -> None:
        self.embeddings_path = (
            embeddings_path or settings.processed_data_dir / "gutenberg_excerpt_embeddings.jsonl"
        )

    def list_excerpt_embeddings(self) -> list[ProcessedExcerptEmbedding]:
        return _load_excerpt_embeddings(str(self.embeddings_path))

    def by_excerpt_id(self) -> dict[str, ProcessedExcerptEmbedding]:
        return {embedding.excerpt_id: embedding for embedding in self.list_excerpt_embeddings()}


@lru_cache(maxsize=8)
def _load_excerpt_embeddings(path: str) -> list[ProcessedExcerptEmbedding]:
    embeddings_path = Path(path)
    if not embeddings_path.exists():
        return []

    embeddings: list[ProcessedExcerptEmbedding] = []
    try:
        with embeddings_path.open("r", encoding="utf-8") as records:
            for line in records:
                if not line.strip():
                    continue
                record = json.loads(line)
                embeddings.append(
                    ProcessedExcerptEmbedding(
                        excerpt_id=record["excerpt_id"],
                        work_id=record["work_id"],
                        provider=record["provider"],
                        model=record["model"],
                        dimensions=record["dimensions"],
                        source_text_hash=record["source_text_hash"],
                        vector=record["vector"],
                    )
                )
    except OSError:
        return []
    return embeddings


def clear_processed_embedding_cache() -> None:
    _load_excerpt_embeddings.cache_clear()
