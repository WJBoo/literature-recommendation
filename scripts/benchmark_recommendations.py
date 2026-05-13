#!/usr/bin/env python
from __future__ import annotations
# ruff: noqa: E402

import argparse
import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings
from app.schemas.recommendations import RecommendationRequest
from app.services.processed_corpus import ProcessedCorpusService
from app.services.processed_embeddings import ProcessedEmbeddingService
from app.services.processed_latent_factors import ProcessedLatentFactorService
from app.services.recommendations import RecommendationService


DEFAULT_QUERIES = [
    RecommendationRequest(genres=["romance"], themes=["love", "society"], forms=["prose"], limit=12),
    RecommendationRequest(genres=["gothic"], themes=["fear", "ambition"], forms=["prose"], limit=12),
    RecommendationRequest(genres=["epic poetry"], themes=["war", "journey"], forms=["poetry"], limit=12),
    RecommendationRequest(genres=["mystery"], themes=["crime", "logic"], forms=["prose"], limit=12),
    RecommendationRequest(themes=["time", "beauty", "memory"], forms=["poetry"], limit=12),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark local recommendation performance.")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument(
        "--mode",
        choices=["async", "sync"],
        default="async",
        help="Use async to include the pgvector path when available; sync measures the file fallback.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=settings.processed_data_dir / "recommendation_benchmark.json",
    )
    args = parser.parse_args()

    corpus_service = ProcessedCorpusService()
    excerpts = corpus_service.list_excerpts()
    work_count = len({excerpt.work_id for excerpt in excerpts})
    embedding_count = len(ProcessedEmbeddingService().list_excerpt_embeddings())
    latent_artifact = ProcessedLatentFactorService().load_artifact() or {}

    service = RecommendationService()
    if args.mode == "async":
        samples, durations_ms = asyncio.run(run_async_benchmark(service, args.runs))
    else:
        samples, durations_ms = run_sync_benchmark(service, args.runs)

    benchmark = {
        "created_at": datetime.now(UTC).isoformat(),
        "runs": args.runs,
        "mode": args.mode,
        "query_count": len(DEFAULT_QUERIES),
        "work_count": work_count,
        "excerpt_count": len(excerpts),
        "embedding_count": embedding_count,
        "latent_factor_count": latent_artifact.get("factors", 0),
        "latency_ms": {
            "min": round(min(durations_ms), 3) if durations_ms else 0,
            "median": round(statistics.median(durations_ms), 3) if durations_ms else 0,
            "mean": round(statistics.fmean(durations_ms), 3) if durations_ms else 0,
            "max": round(max(durations_ms), 3) if durations_ms else 0,
        },
        "samples": samples,
    }

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(json.dumps(benchmark, ensure_ascii=True, indent=2), encoding="utf-8")
    print(
        f"Benchmarked {benchmark['query_count']} queries x {args.runs} runs over "
        f"{work_count} works / {len(excerpts)} excerpts."
    )
    print(
        "Latency ms: "
        f"median={benchmark['latency_ms']['median']} "
        f"mean={benchmark['latency_ms']['mean']} "
        f"max={benchmark['latency_ms']['max']}"
    )
    print(f"Wrote {args.output_path}")


async def run_async_benchmark(
    service: RecommendationService,
    runs: int,
) -> tuple[list[dict[str, Any]], list[float]]:
    samples: list[dict[str, Any]] = []
    durations_ms: list[float] = []

    for run_index in range(1, runs + 1):
        for query_index, request in enumerate(DEFAULT_QUERIES, start=1):
            started = time.perf_counter()
            response = await service.recommend_async(request)
            duration_ms = (time.perf_counter() - started) * 1000
            durations_ms.append(duration_ms)
            samples.append(
                {
                    "run": run_index,
                    "query": query_index,
                    "duration_ms": round(duration_ms, 3),
                    "result_count": len(response.items),
                    "top_result": response.items[0].title if response.items else None,
                }
            )
    return samples, durations_ms


def run_sync_benchmark(
    service: RecommendationService,
    runs: int,
) -> tuple[list[dict[str, Any]], list[float]]:
    samples: list[dict[str, Any]] = []
    durations_ms: list[float] = []

    for run_index in range(1, runs + 1):
        for query_index, request in enumerate(DEFAULT_QUERIES, start=1):
            started = time.perf_counter()
            response = service.recommend(request)
            duration_ms = (time.perf_counter() - started) * 1000
            durations_ms.append(duration_ms)
            samples.append(
                {
                    "run": run_index,
                    "query": query_index,
                    "duration_ms": round(duration_ms, 3),
                    "result_count": len(response.items),
                    "top_result": response.items[0].title if response.items else None,
                }
            )
    return samples, durations_ms


if __name__ == "__main__":
    main()
