from pathlib import Path
import sys

from app.embeddings.provider import HashingEmbeddingProvider


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.generate_excerpt_embeddings import build_embedding_records, text_hash


def test_build_embedding_records_creates_one_vector_per_input():
    input_records = [
        {
            "excerpt_id": "excerpt-1",
            "work_id": "work-1",
            "embedding_text": "Title: Test\nExcerpt:\nLove and time.",
        }
    ]
    provider = HashingEmbeddingProvider(dimensions=8)

    records, reused = build_embedding_records(
        input_records,
        provider=provider,
        provider_name="hashing",
        batch_size=2,
    )

    assert reused == 0
    assert len(records) == 1
    assert records[0]["excerpt_id"] == "excerpt-1"
    assert records[0]["source_text_hash"] == text_hash(input_records[0]["embedding_text"])
    assert len(records[0]["vector"]) == 8


def test_build_embedding_records_reuses_unchanged_existing_vector():
    input_records = [
        {
            "excerpt_id": "excerpt-1",
            "work_id": "work-1",
            "embedding_text": "Title: Test\nExcerpt:\nLove and time.",
        }
    ]
    provider = HashingEmbeddingProvider(dimensions=8)
    existing = {
        "excerpt-1": {
            "excerpt_id": "excerpt-1",
            "work_id": "work-1",
            "provider": "hashing",
            "model": provider.model,
            "dimensions": provider.dimensions,
            "source_text_hash": text_hash(input_records[0]["embedding_text"]),
            "vector": [0.0] * 8,
        }
    }

    records, reused = build_embedding_records(
        input_records,
        provider=provider,
        provider_name="hashing",
        batch_size=2,
        existing_records=existing,
    )

    assert reused == 1
    assert records[0]["vector"] == [0.0] * 8
