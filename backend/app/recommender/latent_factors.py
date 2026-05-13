from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import math
import re
from typing import Any

import numpy as np

from app.recommender.profile import build_preference_profile_text
from app.recommender.vector_math import cosine_similarity
from app.schemas.recommendations import RecommendationRequest
from app.services.processed_corpus import ProcessedExcerpt


LATENT_FACTOR_MODEL = "local-tfidf-svd-v1"
TOKEN_PATTERN = re.compile(r"[a-z][a-z']{2,}")
STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "all",
    "also",
    "among",
    "and",
    "any",
    "are",
    "asked",
    "because",
    "been",
    "before",
    "being",
    "but",
    "can",
    "could",
    "did",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "her",
    "him",
    "his",
    "how",
    "into",
    "its",
    "just",
    "may",
    "more",
    "not",
    "now",
    "one",
    "our",
    "out",
    "shall",
    "she",
    "should",
    "such",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "thou",
    "thy",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "will",
    "with",
    "would",
    "you",
    "your",
    "author",
    "authors",
    "aoi",
    "away",
    "back",
    "bce",
    "book",
    "books",
    "chapter",
    "chapters",
    "character",
    "complete",
    "contents",
    "copyright",
    "came",
    "come",
    "damon",
    "dat",
    "day",
    "days",
    "dear",
    "delia",
    "den",
    "dey",
    "didn't",
    "distributed",
    "doesn't",
    "don't",
    "drama",
    "edition",
    "editor",
    "ebook",
    "ence",
    "english",
    "ere",
    "every",
    "fer",
    "fiction",
    "foreword",
    "get",
    "give",
    "goes",
    "going",
    "got",
    "good",
    "great",
    "gutenberg",
    "hand",
    "hands",
    "hath",
    "haue",
    "hear",
    "heard",
    "home",
    "house",
    "ich",
    "illustrated",
    "introduction",
    "i'll",
    "ile",
    "juvenile",
    "know",
    "last",
    "let",
    "letter",
    "letters",
    "long",
    "literature",
    "little",
    "like",
    "looked",
    "loue",
    "made",
    "make",
    "man",
    "marl",
    "men",
    "miss",
    "moment",
    "mrs",
    "much",
    "name",
    "new",
    "nor",
    "note",
    "notes",
    "online",
    "poem",
    "poems",
    "poetical",
    "poetry",
    "prose",
    "project",
    "proofreading",
    "prepared",
    "printed",
    "preface",
    "public",
    "publisher",
    "kwasind",
    "right",
    "robyn",
    "round",
    "ryght",
    "said",
    "say",
    "saw",
    "selfe",
    "seemed",
    "sir",
    "some",
    "somers",
    "soon",
    "stood",
    "ter",
    "text",
    "thee",
    "tell",
    "reserved",
    "translations",
    "translated",
    "translator",
    "transcriber",
    "transcribers",
    "thing",
    "things",
    "think",
    "thought",
    "three",
    "till",
    "told",
    "took",
    "unto",
    "upon",
    "very",
    "volume",
    "volumes",
    "want",
    "went",
    "well",
    "works",
    "word",
    "words",
    "world",
    "wid",
    "why",
    "wuz",
    "yes",
}


def build_latent_factor_artifact(
    excerpts: list[ProcessedExcerpt],
    *,
    factors: int = 16,
    max_terms: int = 3500,
    min_document_frequency: int = 2,
) -> dict[str, Any]:
    documents = [excerpt_latent_text(excerpt) for excerpt in excerpts]
    work_ids = [excerpt.work_id for excerpt in excerpts]
    vocabulary = build_vocabulary(
        documents,
        work_ids=work_ids,
        max_terms=max_terms,
        min_document_frequency=min_document_frequency,
    )
    if not vocabulary:
        raise ValueError("Cannot build latent factors without vocabulary terms.")

    matrix, idf = build_tfidf_matrix(documents, vocabulary)
    factor_count = min(factors, matrix.shape[0], matrix.shape[1])
    if factor_count < 1:
        raise ValueError("Cannot build latent factors from an empty document-term matrix.")

    left, singular_values, components = np.linalg.svd(matrix, full_matrices=False)
    left = left[:, :factor_count]
    singular_values = singular_values[:factor_count]
    components = components[:factor_count, :]
    excerpt_vectors = left * singular_values

    factor_records = [
        describe_factor(index, component, vocabulary)
        for index, component in enumerate(components)
    ]

    return {
        "schema_version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "model": LATENT_FACTOR_MODEL,
        "factors": factor_count,
        "max_terms": max_terms,
        "min_document_frequency": min_document_frequency,
        "vocabulary": vocabulary,
        "idf": idf.tolist(),
        "singular_values": singular_values.tolist(),
        "components": components.tolist(),
        "factor_labels": factor_records,
        "excerpts": [
            {
                "excerpt_id": excerpt.id,
                "work_id": excerpt.work_id,
                "title": excerpt.title,
                "author": excerpt.author,
                "form": excerpt.form,
                "vector": excerpt_vectors[index].tolist(),
                "primary_factors": primary_factors_for_vector(
                    excerpt_vectors[index].tolist(),
                    factor_records,
                ),
            }
            for index, excerpt in enumerate(excerpts)
        ],
    }


def recommend_from_latent_factors(
    request: RecommendationRequest,
    excerpts: list[ProcessedExcerpt],
    artifact: dict[str, Any],
) -> list[tuple[float, ProcessedExcerpt, str]]:
    query_vector = project_text_to_latent_vector(build_preference_profile_text(request), artifact)
    excerpt_vectors = {
        record["excerpt_id"]: record["vector"] for record in artifact.get("excerpts", [])
    }
    factor_labels = artifact.get("factor_labels", [])

    scored: list[tuple[float, ProcessedExcerpt, str]] = []
    for excerpt in excerpts:
        vector = excerpt_vectors.get(excerpt.id)
        if vector is None:
            continue
        score = cosine_similarity(query_vector, vector)
        scored.append((score, excerpt, latent_factor_reason(vector, factor_labels)))

    scored.sort(key=lambda item: item[0], reverse=True)
    return scored


def project_text_to_latent_vector(text: str, artifact: dict[str, Any]) -> list[float]:
    vocabulary = artifact.get("vocabulary", [])
    idf = np.array(artifact.get("idf", []), dtype=float)
    components = np.array(artifact.get("components", []), dtype=float)
    if len(vocabulary) == 0 or idf.size == 0 or components.size == 0:
        return []

    term_to_index = {term: index for index, term in enumerate(vocabulary)}
    counts = Counter(token for token in tokenize(text) if token in term_to_index)
    vector = np.zeros(len(vocabulary), dtype=float)
    for term, count in counts.items():
        vector[term_to_index[term]] = 1.0 + math.log(count)
    vector *= idf
    return (vector @ components.T).tolist()


def excerpt_latent_text(excerpt: ProcessedExcerpt) -> str:
    labels = " ".join(label.get("label", "") for label in excerpt.labels)
    subjects = " ".join(excerpt.subjects)
    return (
        f"{excerpt.form} {subjects} {labels} {excerpt.text}"
    )


def build_vocabulary(
    documents: list[str],
    *,
    work_ids: list[str] | None = None,
    max_terms: int,
    min_document_frequency: int,
    max_single_work_share: float = 0.65,
    max_large_corpus_document_share: float = 0.28,
) -> list[str]:
    term_frequency: Counter[str] = Counter()
    document_frequency: Counter[str] = Counter()
    term_work_frequency: dict[str, Counter[str]] = {}

    work_ids = work_ids or [str(index) for index, _ in enumerate(documents)]
    for document, work_id in zip(documents, work_ids, strict=True):
        tokens = tokenize(document)
        term_frequency.update(tokens)
        document_frequency.update(set(tokens))
        token_counts = Counter(tokens)
        for token, count in token_counts.items():
            term_work_frequency.setdefault(token, Counter())[work_id] += count

    candidates = [
        term
        for term, frequency in term_frequency.items()
        if document_frequency[term] >= min_document_frequency and frequency > 1
        and not is_large_corpus_filler(
            document_frequency[term],
            document_count=len(documents),
            max_document_share=max_large_corpus_document_share,
        )
        and not is_single_work_concentrated(
            term_work_frequency[term],
            max_single_work_share=max_single_work_share,
        )
    ]
    candidates.sort(key=lambda term: (term_frequency[term], document_frequency[term], term), reverse=True)
    return sorted(candidates[:max_terms])


def is_single_work_concentrated(
    work_counts: Counter[str],
    *,
    max_single_work_share: float,
) -> bool:
    total = sum(work_counts.values())
    if total < 4 or len(work_counts) > 3:
        return False
    return max(work_counts.values()) / total > max_single_work_share


def is_large_corpus_filler(
    document_frequency: int,
    *,
    document_count: int,
    max_document_share: float,
) -> bool:
    if document_count < 100:
        return False
    return document_frequency / document_count > max_document_share


def build_tfidf_matrix(
    documents: list[str],
    vocabulary: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    term_to_index = {term: index for index, term in enumerate(vocabulary)}
    matrix = np.zeros((len(documents), len(vocabulary)), dtype=float)
    document_frequency = np.zeros(len(vocabulary), dtype=float)

    for row, document in enumerate(documents):
        counts = Counter(token for token in tokenize(document) if token in term_to_index)
        for term, count in counts.items():
            column = term_to_index[term]
            matrix[row, column] = 1.0 + math.log(count)
        document_frequency[matrix[row] > 0] += 1.0

    idf = np.log((1.0 + len(documents)) / (1.0 + document_frequency)) + 1.0
    matrix *= idf
    row_norms = np.linalg.norm(matrix, axis=1)
    row_norms[row_norms == 0] = 1.0
    matrix = matrix / row_norms[:, np.newaxis]
    return matrix, idf


def tokenize(text: str) -> list[str]:
    return [
        token.strip("'")
        for token in TOKEN_PATTERN.findall(text.lower())
        if is_latent_token(token.strip("'"))
    ]


def is_latent_token(token: str) -> bool:
    if token in STOPWORDS:
        return False
    if token.endswith("'s"):
        return False
    if len(token) < 3:
        return False
    if len(set(token.replace("'", ""))) <= 2:
        return False
    return True


def describe_factor(index: int, component: np.ndarray, vocabulary: list[str]) -> dict[str, Any]:
    ranked_positive = np.argsort(component)[::-1][:8]
    ranked_negative = np.argsort(component)[:8]
    positive_terms = [vocabulary[position] for position in ranked_positive]
    negative_terms = [vocabulary[position] for position in ranked_negative]
    positive_label = ", ".join(positive_terms[:4])
    negative_label = ", ".join(negative_terms[:4])
    return {
        "factor_id": index,
        "label": positive_label,
        "positive_label": positive_label,
        "negative_label": negative_label,
        "positive_terms": positive_terms,
        "negative_terms": negative_terms,
    }


def primary_factors_for_vector(
    vector: list[float],
    factor_records: list[dict[str, Any]],
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    ranked = sorted(range(len(vector)), key=lambda index: abs(vector[index]), reverse=True)
    primary = []
    for index in ranked[:limit]:
        record = factor_records[index]
        label = record["positive_label"] if vector[index] >= 0 else record["negative_label"]
        primary.append(
            {
                "factor_id": index,
                "label": label,
                "score": vector[index],
            }
        )
    return primary


def latent_factor_reason(vector: list[float], factor_labels: list[dict[str, Any]]) -> str:
    if not vector or not factor_labels:
        return "Matches the latent literary factor profile"
    factor_index = max(range(len(vector)), key=lambda index: abs(vector[index]))
    factor = factor_labels[factor_index]
    label = factor["positive_label"] if vector[factor_index] >= 0 else factor["negative_label"]
    return f"Matches latent factor: {label}"


def latent_match_reason(
    query_vector: list[float],
    excerpt_vector: list[float],
    factor_labels: list[dict[str, Any]],
) -> str | None:
    if not query_vector or not excerpt_vector or not factor_labels:
        return None
    factor_count = min(len(query_vector), len(excerpt_vector), len(factor_labels))
    if factor_count == 0:
        return None

    contributions = [
        query_vector[index] * excerpt_vector[index] for index in range(factor_count)
    ]
    factor_index = max(range(factor_count), key=lambda index: contributions[index])
    if contributions[factor_index] <= 0:
        factor_index = max(range(factor_count), key=lambda index: abs(excerpt_vector[index]))

    factor = factor_labels[factor_index]
    label = (
        factor["positive_label"]
        if query_vector[factor_index] >= 0
        else factor["negative_label"]
    )
    return f"Matches latent factor: {label}"
