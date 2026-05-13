from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.ingestion.chunking import TextChunk
from app.recommender.quality import ExcerptQuality, assess_excerpt_quality
from app.services.processed_corpus import ProcessedExcerpt


@dataclass(frozen=True)
class QualityGateResult:
    chunks: list[TextChunk]
    rejected_reasons: Counter[str]

    @property
    def rejected_count(self) -> int:
        return sum(self.rejected_reasons.values())


def recommendable_chunks(
    chunks: list[TextChunk],
    *,
    form: str,
    work_title: str,
    author: str,
    subjects: list[str],
    max_excerpts: int | None = None,
) -> QualityGateResult:
    kept: list[TextChunk] = []
    rejected_reasons: Counter[str] = Counter()
    keep_complete_work = max_excerpts is None or max_excerpts <= 0

    for chunk in chunks:
        quality = assess_chunk_quality(
            chunk,
            form=form,
            work_title=work_title,
            author=author,
            subjects=subjects,
        )
        if quality.recommendable or keep_complete_work:
            kept.append(chunk)
            if not quality.recommendable:
                rejected_reasons.update(quality.reasons or ["low_quality"])
            if max_excerpts and len(kept) >= max_excerpts:
                break
            continue

        if quality.reasons:
            rejected_reasons.update(quality.reasons)
        else:
            rejected_reasons.update(["low_quality"])

    return QualityGateResult(chunks=kept, rejected_reasons=rejected_reasons)


def assess_chunk_quality(
    chunk: TextChunk,
    *,
    form: str,
    work_title: str,
    author: str,
    subjects: list[str],
) -> ExcerptQuality:
    return assess_excerpt_quality(
        ProcessedExcerpt(
            id="ingestion-candidate",
            work_id="ingestion-candidate-work",
            gutenberg_id="",
            title=chunk.section_title or work_title,
            author=author,
            form=form,
            subjects=subjects,
            labels=[],
            text=chunk.text,
            chunk_type=chunk.chunk_type,
            word_count=chunk.word_count,
            work_title=work_title,
            section_title=chunk.section_title,
            section_index=chunk.section_index,
            section_excerpt_index=chunk.excerpt_index_in_section,
        )
    )
