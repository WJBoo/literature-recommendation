from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.db.session import async_session
from app.ingestion.canonicalization import display_author
from app.models import Excerpt, ExcerptClassification, ExcerptEmbedding, Work
from app.services.processed_corpus import ProcessedExcerpt
from app.services.processed_corpus import ProcessedCorpusService, clean_display_text
from app.services.processed_embeddings import ProcessedEmbeddingService


@dataclass(frozen=True)
class VectorSearchCandidate:
    excerpt: ProcessedExcerpt
    vector: list[float] | None
    distance: float

    @property
    def similarity(self) -> float:
        return 1.0 - self.distance


@dataclass(frozen=True)
class FileVectorIndex:
    excerpts_by_id: dict[str, ProcessedExcerpt]
    excerpt_ids: list[str]
    matrix: Any
    row_by_excerpt_id: dict[str, int]
    vectors_by_excerpt_id: dict[str, list[float]]


class FileVectorSearchService:
    """Fast local nearest-neighbor lookup over processed JSONL embeddings.

    This keeps local development responsive when PostgreSQL/pgvector is not
    available. It still scans the local matrix, but the expensive dot products
    run in numpy and only the best candidates go through richer scoring.
    """

    def __init__(
        self,
        candidate_limit: int | None = None,
        *,
        excerpts_path: Path | None = None,
        embeddings_path: Path | None = None,
    ) -> None:
        self.candidate_limit = candidate_limit or settings.recommendation_vector_candidate_limit
        self.excerpts_path = excerpts_path or settings.processed_data_dir / "gutenberg_excerpts.jsonl"
        self.embeddings_path = (
            embeddings_path or settings.processed_data_dir / "gutenberg_excerpt_embeddings.jsonl"
        )

    def nearest_excerpts(
        self,
        query_vector: list[float],
        *,
        limit: int | None = None,
        exclude_excerpt_ids: set[str] | None = None,
        forms: set[str] | None = None,
        genres: set[str] | None = None,
    ) -> list[VectorSearchCandidate] | None:
        if settings.recommendation_vector_backend == "postgres":
            return None
        index = self._index()
        if index is None or not query_vector:
            return None

        try:
            import numpy as np
        except ImportError:
            return None

        query = np.asarray(query_vector, dtype=np.float32)
        if query.shape[0] != index.matrix.shape[1]:
            return None
        query_norm = float(np.linalg.norm(query))
        if query_norm == 0.0:
            return []

        similarities = index.matrix @ (query / query_norm)
        for excerpt_id in exclude_excerpt_ids or set():
            row = index.row_by_excerpt_id.get(excerpt_id)
            if row is not None:
                similarities[row] = -np.inf
        if forms:
            for excerpt_id, row in index.row_by_excerpt_id.items():
                if index.excerpts_by_id[excerpt_id].form.lower() not in forms:
                    similarities[row] = -np.inf
        if genres:
            for excerpt_id, row in index.row_by_excerpt_id.items():
                if not genres.intersection(index.excerpts_by_id[excerpt_id].tags):
                    similarities[row] = -np.inf

        finite_count = int(np.isfinite(similarities).sum())
        if finite_count == 0:
            return []

        candidate_count = min(limit or self.candidate_limit, finite_count)
        if candidate_count < len(similarities):
            top_indices = np.argpartition(-similarities, candidate_count - 1)[:candidate_count]
            top_indices = top_indices[np.argsort(-similarities[top_indices])]
        else:
            top_indices = np.argsort(-similarities)

        candidates: list[VectorSearchCandidate] = []
        for raw_index in top_indices:
            row = int(raw_index)
            score = float(similarities[row])
            if not np.isfinite(score):
                continue
            excerpt_id = index.excerpt_ids[row]
            candidates.append(
                VectorSearchCandidate(
                    excerpt=index.excerpts_by_id[excerpt_id],
                    vector=index.vectors_by_excerpt_id[excerpt_id],
                    distance=1.0 - score,
                )
            )
        return candidates

    def vectors_for_external_ids(
        self,
        excerpt_ids: set[str],
        *,
        dimensions: int,
    ) -> list[list[float]]:
        if not excerpt_ids:
            return []
        index = self._index()
        if index is None:
            return []
        return [
            vector
            for excerpt_id, vector in index.vectors_by_excerpt_id.items()
            if excerpt_id in excerpt_ids and len(vector) == dimensions
        ]

    def _index(self) -> FileVectorIndex | None:
        return _load_file_vector_index(str(self.excerpts_path), str(self.embeddings_path))


class DatabaseVectorSearchService:
    """Nearest-neighbor lookup over pgvector-backed excerpt embeddings.

    This service is intentionally optional. If PostgreSQL is unavailable, not
    synced, or not using pgvector, callers should fall back to the JSONL scorer.
    """

    def __init__(self, candidate_limit: int | None = None) -> None:
        self.candidate_limit = candidate_limit or settings.recommendation_vector_candidate_limit

    async def available(self) -> bool:
        if settings.recommendation_vector_backend == "file":
            return False
        if not settings.database_url.startswith("postgresql"):
            return False
        return True

    async def nearest_excerpts(
        self,
        query_vector: list[float],
        *,
        limit: int | None = None,
        exclude_excerpt_ids: set[str] | None = None,
        include_vectors: bool = False,
        forms: set[str] | None = None,
        genres: set[str] | None = None,
    ) -> list[VectorSearchCandidate] | None:
        if not await self.available():
            return None
        if not query_vector:
            return None

        exclude_excerpt_ids = exclude_excerpt_ids or set()
        limit = limit or self.candidate_limit
        distance = ExcerptEmbedding.embedding.cosine_distance(query_vector).label("distance")
        selected_columns = [Excerpt, Work, distance]
        if include_vectors:
            selected_columns.insert(2, ExcerptEmbedding.embedding)
        statement = (
            select(*selected_columns)
            .join(Work, Excerpt.work_id == Work.id)
            .join(ExcerptEmbedding, ExcerptEmbedding.excerpt_id == Excerpt.id)
            .where(
                ExcerptEmbedding.dimensions == len(query_vector),
                ExcerptEmbedding.model.in_([settings.embedding_model, "local-hashing-v1"]),
            )
            .order_by(distance)
            .limit(limit)
        )
        if exclude_excerpt_ids:
            statement = statement.where(Excerpt.external_id.not_in(exclude_excerpt_ids))
        if forms:
            statement = statement.where(func.lower(Work.form).in_(forms))
        if genres:
            genre_match = (
                select(ExcerptClassification.id)
                .where(
                    ExcerptClassification.excerpt_id == Excerpt.id,
                    ExcerptClassification.label_type == "genre",
                    func.lower(ExcerptClassification.label).in_(genres),
                )
                .exists()
            )
            statement = statement.where(genre_match)

        try:
            async with async_session() as session:
                rows = (await session.execute(statement)).all()
                if not rows:
                    return []

                excerpt_ids = [row[0].id for row in rows]
                labels = await self._labels_by_excerpt_id(session, excerpt_ids)
                candidates: list[VectorSearchCandidate] = []
                for row in rows:
                    excerpt = row[0]
                    work = row[1]
                    vector = list(row[2]) if include_vectors else None
                    row_distance = row[3] if include_vectors else row[2]
                    candidates.append(
                        VectorSearchCandidate(
                            excerpt=self._processed_excerpt_from_row(
                                excerpt,
                                work,
                                labels.get(excerpt.id, []),
                            ),
                            vector=vector,
                            distance=float(row_distance),
                        )
                    )
                return candidates
        except (SQLAlchemyError, OSError, PermissionError, ValueError):
            return None

    async def vectors_for_external_ids(
        self,
        excerpt_ids: set[str],
        *,
        dimensions: int,
    ) -> list[list[float]] | None:
        if not await self.available():
            return None
        if not excerpt_ids:
            return []

        statement = (
            select(ExcerptEmbedding.embedding)
            .join(Excerpt, ExcerptEmbedding.excerpt_id == Excerpt.id)
            .where(
                Excerpt.external_id.in_(excerpt_ids),
                ExcerptEmbedding.dimensions == dimensions,
                ExcerptEmbedding.model.in_([settings.embedding_model, "local-hashing-v1"]),
            )
        )
        try:
            async with async_session() as session:
                rows = (await session.execute(statement)).scalars().all()
                return [list(vector) for vector in rows]
        except (SQLAlchemyError, OSError, PermissionError, ValueError):
            return None

    async def _labels_by_excerpt_id(self, session: Any, excerpt_ids: list[int]) -> dict[int, list[dict[str, str]]]:
        if not excerpt_ids:
            return {}
        rows = (
            await session.execute(
                select(ExcerptClassification).where(
                    ExcerptClassification.excerpt_id.in_(excerpt_ids)
                )
            )
        ).scalars()
        labels_by_id: dict[int, list[dict[str, str]]] = {}
        for label in rows:
            labels_by_id.setdefault(label.excerpt_id, []).append(
                {
                    "label_type": label.label_type,
                    "label": label.label,
                    "evidence": label.evidence or "",
                }
            )
        return labels_by_id

    def _processed_excerpt_from_row(
        self,
        excerpt: Excerpt,
        work: Work,
        labels: list[dict[str, str]],
    ) -> ProcessedExcerpt:
        source_metadata = excerpt.source_metadata or {}
        subjects = source_metadata.get("subjects") or work.subjects or []
        return ProcessedExcerpt(
            id=excerpt.external_id,
            work_id=work.external_id,
            gutenberg_id=str(work.gutenberg_id or source_metadata.get("gutenberg_id") or ""),
            title=source_metadata.get("display_title") or excerpt.title or "Excerpt",
            author=display_author(work.author),
            form=str(source_metadata.get("form") or work.form or "unknown"),
            subjects=list(subjects),
            labels=labels,
            text=clean_display_text(excerpt.text),
            chunk_type=excerpt.chunk_type,
            word_count=excerpt.word_count,
            work_title=str(source_metadata.get("work_title") or work.title or excerpt.title or ""),
            display_title=str(source_metadata.get("display_title") or excerpt.title or ""),
            section_title=source_metadata.get("section_title"),
            section_index=source_metadata.get("section_index"),
            section_excerpt_index=source_metadata.get("section_excerpt_index"),
            excerpt_label=source_metadata.get("excerpt_label"),
        )


@lru_cache(maxsize=4)
def _load_file_vector_index(excerpts_path: str, embeddings_path: str) -> FileVectorIndex | None:
    try:
        import numpy as np
    except ImportError:
        return None

    excerpts = ProcessedCorpusService(excerpts_path=Path(excerpts_path)).list_excerpts()
    embeddings = ProcessedEmbeddingService(embeddings_path=Path(embeddings_path)).list_excerpt_embeddings()
    if not excerpts or not embeddings:
        return None

    excerpts_by_id = {excerpt.id: excerpt for excerpt in excerpts}
    dimensions: int | None = None
    rows: list[list[float]] = []
    excerpt_ids: list[str] = []
    vectors_by_excerpt_id: dict[str, list[float]] = {}
    for embedding in embeddings:
        if embedding.excerpt_id not in excerpts_by_id:
            continue
        vector = embedding.vector
        if not vector:
            continue
        if dimensions is None:
            dimensions = embedding.dimensions or len(vector)
        if len(vector) != dimensions:
            continue
        rows.append(vector)
        excerpt_ids.append(embedding.excerpt_id)
        vectors_by_excerpt_id[embedding.excerpt_id] = vector

    if not rows:
        return None

    matrix = np.asarray(rows, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1)
    valid_rows = norms > 0
    if not bool(valid_rows.all()):
        matrix = matrix[valid_rows]
        norms = norms[valid_rows]
        excerpt_ids = [
            excerpt_id for excerpt_id, valid in zip(excerpt_ids, valid_rows.tolist(), strict=True) if valid
        ]
        vectors_by_excerpt_id = {
            excerpt_id: vectors_by_excerpt_id[excerpt_id] for excerpt_id in excerpt_ids
        }

    if matrix.size == 0:
        return None

    normalized_matrix = matrix / norms[:, None]
    return FileVectorIndex(
        excerpts_by_id={excerpt_id: excerpts_by_id[excerpt_id] for excerpt_id in excerpt_ids},
        excerpt_ids=excerpt_ids,
        matrix=normalized_matrix,
        row_by_excerpt_id={excerpt_id: index for index, excerpt_id in enumerate(excerpt_ids)},
        vectors_by_excerpt_id=vectors_by_excerpt_id,
    )


def clear_file_vector_index_cache() -> None:
    _load_file_vector_index.cache_clear()
