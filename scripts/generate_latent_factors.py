#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.recommender.latent_factors import (
    build_latent_factor_artifact,
    recommend_from_latent_factors,
)
from app.schemas.recommendations import RecommendationRequest
from app.services.processed_corpus import ProcessedCorpusService
from app.services.processed_latent_factors import clear_processed_latent_factor_cache


def write_json(path: Path, artifact: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        json.dump(artifact, output, ensure_ascii=True, indent=2, sort_keys=True)


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate latent factors for excerpts and print preference recommendations."
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=settings.processed_data_dir / "gutenberg_excerpt_latent_factors.json",
    )
    parser.add_argument("--factors", type=int, default=16)
    parser.add_argument("--max-terms", type=int, default=3500)
    parser.add_argument("--min-document-frequency", type=int, default=2)
    parser.add_argument("--genres", default="romance,poetry")
    parser.add_argument("--forms", default="poetry")
    parser.add_argument("--themes", default="love,time,beauty")
    parser.add_argument("--moods", default="")
    parser.add_argument("--authors", default="")
    parser.add_argument("--books", default="")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    corpus_service = ProcessedCorpusService()
    excerpts = corpus_service.list_excerpts()
    if not excerpts:
        raise RuntimeError("No processed excerpts found. Run Gutenberg ingestion first.")

    artifact = build_latent_factor_artifact(
        excerpts,
        factors=args.factors,
        max_terms=args.max_terms,
        min_document_frequency=args.min_document_frequency,
    )
    write_json(args.output_path, artifact)
    clear_processed_latent_factor_cache()

    print(
        f"Wrote {len(artifact['excerpts'])} excerpt latent-factor vectors to {args.output_path} "
        f"(model={artifact['model']}, factors={artifact['factors']}, "
        f"terms={len(artifact['vocabulary'])})."
    )
    print("\nLatent factors:")
    for factor in artifact["factor_labels"]:
        print(
            f"  {factor['factor_id']:02d}: {factor['label']} "
            f"(opposite: {', '.join(factor['negative_terms'][:4])})"
        )

    request = RecommendationRequest(
        genres=split_list(args.genres),
        forms=split_list(args.forms),
        themes=split_list(args.themes),
        moods=split_list(args.moods),
        authors=split_list(args.authors),
        books=split_list(args.books),
        limit=args.limit,
    )
    print("\nLatent-factor recommendations for the provided preferences:")
    for rank, (score, excerpt, reason) in enumerate(
        recommend_from_latent_factors(request, excerpts, artifact)[: args.limit],
        start=1,
    ):
        print(
            f"  {rank}. {excerpt.title} / {excerpt.author} "
            f"[{excerpt.id}] score={score:.3f} - {reason}"
        )


if __name__ == "__main__":
    main()
