from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.recommender.latent_factors import project_text_to_latent_vector


class ProcessedLatentFactorService:
    def __init__(self, artifact_path: Path | None = None) -> None:
        self.artifact_path = (
            artifact_path or settings.processed_data_dir / "gutenberg_excerpt_latent_factors.json"
        )

    def load_artifact(self) -> dict[str, Any] | None:
        return _load_latent_factor_artifact(str(self.artifact_path))

    def by_excerpt_id(self) -> dict[str, list[float]]:
        return _latent_vectors_by_excerpt_id(str(self.artifact_path))

    def factor_labels(self) -> list[dict[str, Any]]:
        return _latent_factor_labels(str(self.artifact_path))

    def project_text(self, text: str) -> list[float]:
        artifact = self.load_artifact()
        if not artifact:
            return []
        return project_text_to_latent_vector(text, artifact)

    def factor_reason(self, excerpt_id: str) -> str | None:
        artifact = self.load_artifact()
        if not artifact:
            return None
        factors = artifact.get("factor_labels", [])
        for record in artifact.get("excerpts", []):
            if record.get("excerpt_id") != excerpt_id:
                continue
            primary_factors = record.get("primary_factors", [])
            if not primary_factors:
                return None
            factor_id = primary_factors[0]["factor_id"]
            if 0 <= factor_id < len(factors):
                return f"Matches latent factor: {factors[factor_id]['label']}"
        return None


@lru_cache(maxsize=4)
def _load_latent_factor_artifact(path: str) -> dict[str, Any] | None:
    artifact_path = Path(path)
    if not artifact_path.exists():
        return None
    try:
        with artifact_path.open("r", encoding="utf-8") as source:
            return json.load(source)
    except (OSError, json.JSONDecodeError):
        return None


@lru_cache(maxsize=4)
def _latent_vectors_by_excerpt_id(path: str) -> dict[str, list[float]]:
    artifact = _load_latent_factor_artifact(path)
    if not artifact:
        return {}
    return {
        record["excerpt_id"]: record["vector"]
        for record in artifact.get("excerpts", [])
        if isinstance(record.get("vector"), list)
    }


@lru_cache(maxsize=4)
def _latent_factor_labels(path: str) -> list[dict[str, Any]]:
    artifact = _load_latent_factor_artifact(path)
    if not artifact:
        return []
    return artifact.get("factor_labels", [])


def clear_processed_latent_factor_cache() -> None:
    _load_latent_factor_artifact.cache_clear()
    _latent_vectors_by_excerpt_id.cache_clear()
    _latent_factor_labels.cache_clear()
